import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

# 1. 설정값 불러오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def is_recent_article(context_text):
    """3월 3일 혹은 3월 4일 기사인지 판별"""
    now = datetime.now()
    # 대상 날짜 패턴: 03-03, 03-04, 2026-03-03, 2026-03-04, 刚刚, 小时前
    patterns = [
        now.strftime('%m-%d'), 
        (now - timedelta(days=1)).strftime('%m-%d'),
        "刚刚", "小时前", "今天", "昨天"
    ]
    return any(p in context_text for p in patterns)

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 제공해주신 정확한 뉴스 피드 주소 설정
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/?spm_id=www__17173.index.mod_wwwsitenav.0", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중: {site['url']}")
            res = requests.get(site['url'], headers=headers, timeout=30)
            res.encoding = res.apparent_encoding # 특히 17173 GBK 대응
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 사이트별 기사 리스트가 담긴 부모 요소 탐색 (가장 포괄적인 태그들)
            items = soup.find_all(['div', 'li', 'article', 'tr'])
            found_count = 0

            for item in items:
                link_tag = item.find('a', href=True)
                if not link_tag: continue
                
                title = link_tag.get_text(strip=True)
                url = link_tag['href']
                
                # 유효성 검사: 제목 길이 15자 이상
                if len(title) < 15: continue
                
                # 날짜 필터링: 해당 기사 주변 텍스트에 03-03, 03-04 등이 있는지 확인
                context_text = item.get_text()
                if is_recent_article(context_text):
                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    if not any(x['url'] == url for x in all_articles):
                        all_articles.append({
                            "site": site['name'],
                            "title": title,
                            "url": url,
                            "color": site['color']
                        })
                        found_count += 1
                
                if found_count >= 25: break # 각 사이트별 최대 25개
                    
            print(f"-> {site['name']}: {found_count}개 수집 성공")
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 본문 구성
articles = fetch_articles()

if articles:
    now_str = datetime.now().strftime('%m/%d %H:%M')
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 700px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
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
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 (3/3 ~ 3/4)</h2>
                <p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 / 17173 뉴스피드</p>
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
                    • <a href="{art['url']}" class="news-link">{art['title']}</a>
                </div>
                """
            html_content += "</div>"

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 중국 게임 시장 기사 통합 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print(f"발송 완료! (총 {len(articles)}개 기사)")
else:
    print("수집된 기사가 없습니다. 날짜 조건을 확인하세요.")
