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

def get_target_dates():
    """오늘과 어제의 날짜 문자열 리스트 생성 (다양한 형식 대응)"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # 대응할 날짜 형식들: 2026-03-03, 03-03, 2026-03-02, 03-02 등
    formats = [
        today.strftime('%Y-%m-%d'), today.strftime('%m-%d'),
        yesterday.strftime('%Y-%m-%d'), yesterday.strftime('%m-%d'),
        "今天", "昨天", "1天前", "刚刚"
    ]
    return formats

def fetch_articles():
    target_dates = get_target_dates()
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
            print(f"{site['name']} 수집 시도...")
            res = requests.get(site['url'], headers=headers, timeout=20)
            # 사이트별 인코딩 강제 지정 (17173은 GBK 환경이 많음)
            res.encoding = res.apparent_encoding 
            soup = BeautifulSoup(res.text, 'html.parser')
            
            found_count = 0
            # 모든 링크를 돌며 제목과 날짜 텍스트 확인
            links = soup.find_all('a', href=True)
            
            for a in links:
                url = a['href']
                title = a.get_text(strip=True)
                
                # 부모 요소나 주변 텍스트에서 날짜 정보 확인
                parent_text = a.parent.get_text() if a.parent else ""
                grand_parent_text = a.parent.parent.get_text() if a.parent and a.parent.parent else ""
                combined_text = title + parent_text + grand_parent_text

                # 1. 제목 길이 체크 (메뉴 링크 제외)
                if len(title) < 12: continue
                
                # 2. 날짜 필터링: 오늘/어제 날짜 키워드가 포함된 경우만 수집
                if any(dt in combined_text for dt in target_dates):
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
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; padding: 20px; }}
            .container {{ max-width: 700px; margin: auto; }}
            .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
            .site-group {{ margin-bottom: 30px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 3px 12px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }}
            .news-list {{ list-style: none; padding: 0; margin: 0; }}
            .news-item {{ margin-bottom: 10px; border-bottom: 1px solid #f0f0f0; padding-bottom: 5px; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
            .news-link:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">🎮 중국 게임 뉴스 통합 리포트</h2>
                <p style="margin:5px 0 0; color:#666;">발송 시점: {now_str} (최근 24시간 기사)</p>
            </div>
    """

    # 사이트별 그룹화
    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_articles = [a for a in articles if a['site'] == site_name]
        if site_articles:
            html_content += f"""
            <div class="site-group">
                <span class="site-tag" style="background-color: {site_articles[0]['color']};">{site_name}</span>
                <div class="news-list">
            """
            for art in site_articles:
                html_content += f"""
                <div class="news-item">
                    • <a href="{art['url']}" class="news-link">{art['title']}</a>
                </div>
                """
            html_content += "</div></div>"

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 게임 뉴스 리포트 (통합)"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("발송 성공")
else:
    print("해당 기간 내의 새로운 기사가 없습니다.")
