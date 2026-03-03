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

def get_date_patterns():
    """오늘과 어제에 해당하는 다양한 날짜 패턴 생성"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # 패턴 예: 2026-03-03, 03-03, 2026-03-02, 03-02 등
    patterns = [
        today.strftime('%Y-%m-%d'), today.strftime('%m-%d'),
        yesterday.strftime('%Y-%m-%d'), yesterday.strftime('%m-%d'),
        "今天", "昨天", "刚刚", "小时前"
    ]
    return patterns

def fetch_articles():
    date_patterns = get_date_patterns()
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/game/", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=25)
            # 17173은 GBK, 나머지는 자동 감지 혹은 UTF-8
            res.encoding = res.apparent_encoding if site['name'] == "17173" else 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            found_count = 0
            # 1. 모든 링크 요소를 순회
            links = soup.find_all('a', href=True)
            
            for a in links:
                url = a['href']
                title = a.get_text(strip=True)
                if len(title) < 12: continue # 메뉴 링크 등 짧은 제목 제외

                # 2. 날짜 정보 확인 (해당 링크의 부모/형제 노드 텍스트 전체 조사)
                # 사이트별로 날짜가 들어있는 위치가 다르므로 주변 텍스트를 모두 긁어옵니다.
                context_area = a.find_parent()
                context_text = context_area.get_text() if context_area else ""
                
                # 3. 날짜 패턴 매칭 (오늘/어제 기사인지 확인)
                if any(p in context_text for p in date_patterns) or any(p in title for p in date_patterns):
                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    # 중복 제거 및 수집
                    if not any(x['url'] == url for x in all_articles):
                        all_articles.append({
                            "site": site['name'],
                            "title": title,
                            "url": url,
                            "color": site['color']
                        })
                        found_count += 1
            
            print(f"-> {site['name']}: {found_count}개 수집 완료")
                    
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 본문 생성
articles = fetch_articles()

if articles:
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 700px; margin: auto; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
            .header {{ border-bottom: 2px solid #444; padding-bottom: 10px; margin-bottom: 20px; }}
            .site-group {{ margin-bottom: 25px; }}
            .site-tag {{ font-size: 12px; font-weight: bold; color: white; padding: 3px 10px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }}
            .news-item {{ margin-bottom: 8px; border-bottom: 1px solid #f9f9f9; padding-bottom: 4px; }}
            .news-link {{ font-size: 15px; color: #1a0dab; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 리포트 (통합)</h2>
                <p style="margin:5px 0 0; color:#666; font-size:13px;">업데이트: {now_str} (어제~오늘 최신 기사)</p>
            </div>
    """

    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_articles = [a for a in articles if a['site'] == site_name]
        if site_articles:
            html_content += f"""
            <div class="site-group">
                <span class="site-tag" style="background-color: {site_articles[0]['color']};">{site_name}</span>
            """
            for art in site_articles:
                html_content += f"""
                <div class="news-item">
                    • <a href="{art['url']}" class="news-link">{art['title']}</a>
                </div>
                """
            html_content += "</div>"

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 주요 게임 기사 브리핑"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료")
else:
    print("조건에 맞는 기사가 없습니다.")
