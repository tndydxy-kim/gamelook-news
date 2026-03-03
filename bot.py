import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# 1. 설정값 불러오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 수집 대상 사이트 설정 (이름, URL, 고유 색상)
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/game/", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=20)
            res.encoding = res.apparent_encoding # 인코딩 자동 수정
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 사이트별 최신 기사 링크 추출
            links = soup.find_all('a', href=True)
            found_count = 0

            for a in links:
                url = a['href']
                title = a.get_text(strip=True)
                
                # 유효성 검사: 제목 길이 및 뉴스 링크 패턴 확인
                if len(title) < 15 or any(x['url'] == url for x in all_articles):
                    continue
                
                # 뉴스성 링크만 필터링 (숫자 포함 패턴 등)
                if not any(pattern in url for pattern in ['/202', '/content/', '/v/']):
                    continue

                if not url.startswith('http'):
                    url = requests.compat.urljoin(site['url'], url)
                
                all_articles.append({
                    "site": site['name'],
                    "title": title,
                    "url": url,
                    "color": site['color']
                })
                found_count += 1
                
                # 각 사이트별 최신 기사 최대 15개로 제한
                if found_count >= 15:
                    break
                    
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 본문 생성
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 650px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
            .site-group {{ margin-bottom: 25px; }}
            .site-title {{ font-size: 14px; font-weight: bold; color: white; padding: 3px 10px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }}
            .news-item {{ margin-bottom: 8px; list-style: none; padding-left: 0; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; }}
            .news-link:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 시장 최신 뉴스 ({datetime.now().strftime('%m/%d')})</h2>
            </div>
    """

    # 사이트별로 그룹화하여 출력
    current_site = ""
    for art in articles:
        if current_site != art['site']:
            if current_site != "":
                html_content += "</div>" # 이전 그룹 닫기
            current_site = art['site']
            html_content += f"""
            <div class="site-group">
                <span class="site-title" style="background-color: {art['color']};">{current_site}</span>
            """
        
        html_content += f"""
        <div class="news-item">
            • <a href="{art['url']}" class="news-link">{art['title']}</a>
        </div>
        """

    html_content += "</div></div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 중국 게임 뉴스 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print(f"발송 완료: 총 {len(articles)}개 기사")
else:
    print("기사를 찾지 못했습니다.")
