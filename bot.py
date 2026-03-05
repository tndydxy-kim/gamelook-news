import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json

# --- 1. 설정값 불러오기 ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD")
RECEIVER = os.environ.get("RECEIVER_EMAIL")

def is_recent_article(context_text):
    """최신 기사인지 판별 (3일 전까지로 범위 확장)"""
    now = datetime.now()
    patterns = [
        now.strftime('%Y-%m-%d'), (now - timedelta(days=1)).strftime('%Y-%m-%d'), (now - timedelta(days=2)).strftime('%Y-%m-%d'),
        now.strftime('%m-%d'), (now - timedelta(days=1)).strftime('%m-%d'), (now - timedelta(days=2)).strftime('%m-%d'),
        "刚刚", "小时前", "今天", "昨天"
    ]
    return any(p in context_text for p in patterns)

# --- 2. 기사 수집 함수 (가장 안정적인 순서로 변경) ---
def fetch_articles():
    all_articles = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 처리 순서를 변경: 17173을 가장 먼저 처리
    sites = [
        {"name": "17173", "url": "https://news.17173.com/", "color": "#d35400"},
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"}
    ]

    for site in sites:
        print(f"\n-> '{site['name']}' 사이트 목록 스캔 중...")
        found_count = 0
        try:
            if site['name'] == '17173':
                # 17173 API에서 2페이지 분량 (약 40개)의 최신 기사를 가져옴
                api_url = "https://apps.game.17173.com/cms/v1/get/article/list?page_num=1&page_size=40&cate_id=10019,10152,263171"
                res = requests.get(api_url, headers=headers, timeout=20)
                data = res.json()
                # 17173에서 가져온 기사만 임시로 담을 리스트
                temp_17173_articles = []
                for item in data['data']['list']:
                    title = item['title']
                    url = item['page_url']
                    # 중복 검사를 더 효율적으로 하기 위해, 먼저 임시 리스트에 추가
                    if not any(x['url'] == url for x in temp_17173_articles):
                        temp_17173_articles.append({"site": site['name'], "title": title, "url": url, "color": site['color']})
                        found_count += 1
                # 임시 리스트를 전체 목록에 한 번에 추가
                all_articles.extend(temp_17173_articles)
            else:
                res = requests.get(site['url'], headers=headers, timeout=30)
                res.encoding = res.apparent_encoding
                soup = BeautifulSoup(res.text, 'html.parser')
                
                items = soup.find_all(['div', 'li', 'article'], limit=200)
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
                            # 전체 목록에서 중복 검사
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
    # (메일 본문 HTML은 수정 없음)
    html_content = f"""
    <html><head><style>body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }} .container {{ max-width: 700px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; background-color: #fff; }} .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }} .site-group {{ margin-bottom: 35px; }} .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }} .news-item {{ margin-bottom: 10px; padding-left: 5px; border-bottom: 1px solid #f9f9f9; padding-bottom: 5px; }} .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }} .news-link:hover {{ text-decoration: underline; color: #d93025; }}</style></head>
    <body><div class="container"><div class="header"><h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2><p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 / 17173</p></div>
    """
    # 이메일에 표시될 순서는 원래대로 Gamelook -> 游戏陀螺 -> 17173
    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_list = [a for a in articles if a['site'] == site_name]
        if site_list:
            html_content += f"""<div class="site-group"><span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>"""
            for art in site_list:
                html_content += f"""<div class="news-item">• <a href="{art['url']}" class="news-link" target="_blank">{art['title']}</a></div>"""
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

