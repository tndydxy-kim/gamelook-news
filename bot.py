import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json

# --- 1. 설정값 불러오기 (Github Secrets) ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD") # 16자리 앱 비밀번호
RECEIVER = os.environ.get("RECEIVER_EMAIL")

def is_recent_article(context_text):
    """최신 기사인지 판별"""
    now = datetime.now()
    patterns = [
        now.strftime('%m-%d'), 
        (now - timedelta(days=1)).strftime('%m-%d'),
        now.strftime('%Y-%m-%d'), 
        (now - timedelta(days=1)).strftime('%Y-%m-%d'),
        "刚刚", "小时前", "今天", "昨天"
    ]
    return any(p in context_text for p in patterns)

# --- 2. 기사 수집 함수 (17173은 API 직접 호출) ---
def fetch_articles():
    all_articles = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/", "color": "#d35400"}
    ]

    for site in sites:
        print(f"\n-> '{site['name']}' 사이트 목록 스캔 중...")
        found_count = 0
        try:
            # 17173은 API를 직접 호출하여 여러 페이지를 한 번에 가져옴
            if site['name'] == '17173':
                for page_num in range(1, 4): # 1~3 페이지 수집
                    # 17173의 기사 목록 API 주소
                    api_url = f"https://apps.game.17173.com/cms/v1/get/article/list?page_num={page_num}&cate_id=10019,10152,263171"
                    res = requests.get(api_url, headers=headers, timeout=20)
                    data = res.json()
                    for item in data['data']['list']:
                        # API 응답의 날짜 형식(YYYY-MM-DD)으로 최신 기사 판별
                        if is_recent_article(item['publish_time']):
                            title = item['title']
                            url = item['page_url']
                            if not any(x['url'] == url for x in all_articles):
                                all_articles.append({"site": site['name'], "title": title, "url": url, "color": site['color']})
                                found_count += 1
            # 다른 사이트들은 기존의 HTML 파싱 방식 사용
            else:
                res = requests.get(site['url'], headers=headers, timeout=30)
                res.encoding = res.apparent_encoding
                soup = BeautifulSoup(res.text, 'html.parser')
                
                items = soup.find_all(['div', 'li', 'article'], limit=150)
                for item in items:
                    date_tag = item.find(class_='date')
                    date_text = date_tag.get_text(strip=True) if date_tag else item.get_text()

                    if is_recent_article(date_text):
                        link_tag = item.find('a', href=True)
                        if link_tag and len(link_tag.get_text(strip=True)) > 15:
                            title = link_tag.get_text(strip=True)
                            url = link_tag['href']
                            if not url.startswith('http'):
                                url = requests.compat.urljoin(site['url'], url)
                            if not any(x['url'] == url for x in all_articles):
                                all_articles.append({"site": site['name'], "title": title, "url": url, "color": site['color']})
                                found_count += 1
            
            print(f"-> {site['name']}: {found_count}개 수집 성공")
        except Exception as e:
            print(f"'{site['name']}' 사이트 처리 중 오류: {e}")

    return all_articles

# --- 3. 메일 본문 구성 및 발송 ---
articles = fetch_articles()

if articles:
    now_str = datetime.now().strftime('%m/%d')
    # HTML 이메일 템플릿 (이미지 없이 깔끔하게)
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 700px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; background-color: #fff; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 10px; padding-left: 5px; border-bottom: 1px solid #f9f9f9; padding-bottom: 5px; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
            .news-link:hover {{ text-decoration: underline; color: #d93025; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2>
                <p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 / 17173</p>
            </div>
    """

    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_list = [a for a in articles if a['site'] == site_name]
        if site_list:
            html_content += f"""
            <div class="site-group">
                <span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>
            """
            for art in site_list:
                html_content += f"""
                <div class="news-item">
                    • <a href="{art['url']}" class="news-link" target="_blank">{art['title']}</a>
                </div>
                """
            html_content += "</div>"
            
    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {now_str} 중국 게임 시장 기사 통합 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"\n발송 완료! (총 {len(articles)}개 기사)")
    except Exception as e:
        print(f"\n이메일 발송 에러: {e}")
else:
    print("\n수집된 기사가 없습니다.")

