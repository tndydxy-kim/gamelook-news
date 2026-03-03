import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 1. 설정값 불러오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com'
    }

    # 수집 대상 사이트 설정
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/game/", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=25)
            # 17173 인코딩 강제 고정
            res.encoding = 'gbk' if site['name'] == "17173" else 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            site_articles = []
            
            # 17173 전용 로직: 메인 뉴스 리스트의 특정 패턴 추출
            if site['name'] == "17173":
                # news-list 내부의 tit 또는 a 태그 타겟팅
                items = soup.select('.news-list li a, .tit a, .list-item a')
            else:
                items = soup.find_all('a', href=True)

            for a in items:
                url = a.get('href', '')
                title = a.get_text(strip=True)
                
                # 유효성 검사
                if len(title) < 14 or not url.startswith('http'):
                    if url.startswith('//'): url = "https:" + url
                    elif url.startswith('/'): url = requests.compat.urljoin(site['url'], url)
                    else: continue

                # 중복 및 노이즈 필터링
                if any(x['url'] == url for x in all_articles) or "javascript" in url:
                    continue

                # 날짜 검증 대신 "최신 기사 패턴" 확인 (최근 연도 포함 등)
                if "/2026/" in url or "/2025/" in url or site['name'] == "游戏陀螺":
                    site_articles.append({
                        "site": site['name'],
                        "title": title,
                        "url": url,
                        "color": site['color']
                    })

            # 각 사이트별로 최신순 상위 15개만 선별 (날짜 오류 방지)
            all_articles.extend(site_articles[:15])
            print(f"-> {site['name']}: {len(site_articles[:15])}개 추출")
                    
        except Exception as e:
            print(f"{site['name']} 에러 발생: {e}")
            
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
            .container {{ max-width: 700px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ border-bottom: 2px solid #222; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 30px; }}
            .site-tag {{ font-size: 12px; font-weight: bold; color: white; padding: 4px 10px; border-radius: 5px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 10px; padding-left: 5px; border-left: 3px solid #f0f0f0; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
            .news-link:hover {{ text-decoration: underline; color: #d93025; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 시장 뉴스 브리핑</h2>
                <p style="margin:5px 0 0; color:#666;">발송 시점 기준 최신 업데이트 ({now_str})</p>
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
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 주요 게임 기사 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("성공적으로 발송되었습니다.")
else:
    print("기사를 찾을 수 없습니다.")
