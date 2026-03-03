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

    # 수집 대상 사이트 및 각 사이트별 뉴스 리스트 CSS 선택자
    sites = [
        {
            "name": "Gamelook", 
            "url": "http://www.gamelook.com.cn/", 
            "color": "#0056b3",
            "selector": ".entry-title a, .post-title a"
        },
        {
            "name": "游戏陀螺", 
            "url": "https://www.youxituoluo.com/", 
            "color": "#e67e22",
            "selector": ".news-item h2 a, .post-list-item h2 a, .tit a"
        },
        {
            "name": "17173", 
            "url": "https://news.17173.com/game/", 
            "color": "#27ae60",
            "selector": ".news-list li .tit a, .news-list li h3 a, .hot-news a"
        }
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=25)
            # 17173은 GBK 인코딩이 많으므로 자동 감지 적용
            res.encoding = res.apparent_encoding if site['name'] == "17173" else 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 지정된 셀렉터로 기사 링크 추출
            items = soup.select(site['selector'])
            found_count = 0

            for a in items:
                title = a.get_text(strip=True)
                url = a.get('href', '')
                
                # 유효성 검사 (메뉴 링크 방지를 위해 제목 15자 이상만 수집)
                if len(title) < 15 or not url or "javascript" in url:
                    continue

                if not url.startswith('http'):
                    url = requests.compat.urljoin(site['url'], url)
                
                # 중복 제거
                if not any(x['url'] == url for x in all_articles):
                    all_articles.append({
                        "site": site['name'],
                        "title": title,
                        "url": url,
                        "color": site['color']
                    })
                    found_count += 1
                
                # 각 사이트별 상위 20개까지만 수집 (최신 뉴스 위주)
                if found_count >= 20:
                    break
                    
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
            .container {{ max-width: 700px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 12px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 12px; padding-left: 5px; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
            .news-link:hover {{ text-decoration: underline; color: #d93025; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 브리핑 (3/3~3/4)</h2>
                <p style="margin:5px 0 0; color:#666;">업데이트 시점: {now_str}</p>
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
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 중국 게임 시장 기사 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("발송 완료!")
else:
    print("기사를 찾지 못했습니다.")
