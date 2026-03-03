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

def is_target_time(date_str):
    """3월 3일 00:00 ~ 3월 4일 08:00 사이의 기사인지 판별"""
    try:
        # 다양한 날짜 형식 대응 (2026-03-03, 03-03 14:00, 1시간 전 등)
        now = datetime.now()
        target_start = datetime(2026, 3, 3, 0, 0)
        target_end = datetime(2026, 3, 4, 8, 0)
        
        # '1시간 전', '5분 전' 등 상대 시간 처리
        if '小时' in date_str or '分钟' in date_str or '刚刚' in date_str:
            return True
        
        # 숫자만 추출하여 날짜 판별 (03-03, 03-04 등)
        date_match = re.search(r'(\d{1,2})[-/](\d{1,2})', date_str)
        if date_match:
            month, day = map(int, date_match.groups())
            if (month == 3 and day == 3) or (month == 3 and day == 4):
                return True
    except:
        pass
    return False

def fetch_articles():
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
            res.encoding = res.apparent_encoding if site['name'] == "17173" else 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 사이트별 기사 영역 지정
            if site['name'] == "17173":
                # 17173은 news-list 내부의 li를 직접 탐색
                items = soup.select('.news-list li')
            elif site['name'] == "游戏陀螺":
                # 游戏陀螺는 메인 피드의 기사 박스 탐색
                items = soup.select('.news-item, .post-list-item')
            else:
                items = soup.find_all(['div', 'li', 'article'])

            for item in items:
                link_tag = item.find('a', href=True)
                if not link_tag: continue
                
                title = link_tag.get_text(strip=True)
                url = link_tag['href']
                
                # 날짜 텍스트 추출 (태그 내부 혹은 속성값)
                date_text = item.get_text() 
                if site['name'] == "17173":
                    # 17173은 data-time 속성에 날짜가 있는 경우가 많음
                    date_text += str(item.get('data-time', ''))

                # 필터링: 제목 길이 + 날짜 조건(3/3~3/4 08:00)
                if len(title) > 15 and is_target_time(date_text):
                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    if not any(x['url'] == url for x in all_articles):
                        all_articles.append({
                            "site": site['name'],
                            "title": title,
                            "url": url,
                            "color": site['color']
                        })
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 생성 로직
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; padding: 20px; line-height: 1.6; }}
            .container {{ max-width: 700px; margin: auto; }}
            .site-group {{ margin-bottom: 30px; }}
            .site-tag {{ color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-bottom: 10px; display: inline-block; }}
            .news-item {{ margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
            .news-link {{ color: #1a0dab; text-decoration: none; font-size: 16px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 style="border-bottom: 3px solid #333; padding-bottom: 10px;">📅 중국 게임 뉴스 (3/3 ~ 3/4 08:00)</h2>
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
    msg['Subject'] = f"[News] 03/04 중국 게임 시장 주요 기사 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("발송 완료")
else:
    print("해당 기간의 기사가 없습니다.")
