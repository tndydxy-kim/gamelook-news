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

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 수집 대상 사이트 설정
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/?spm_id=www__17173.index.mod_wwwsitenav.0", "color": "#27ae60"}
    ]

    # 날짜 필터 패턴 (3/3, 3/4)
    now = datetime.now()
    target_dates = [now.strftime('%m-%d'), (now - timedelta(days=1)).strftime('%m-%d'), "今天", "昨天"]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=30)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            
            found_count = 0
            
            # --- 17173 전용 수집 로직 (대량 수집용) ---
            if site['name'] == "17173":
                # 17173은 기사가 담긴 모든 가능한 패턴을 다 뒤집니다.
                # .news-list 내부 뿐만 아니라 모든 리스트 아이템과 tit 클래스 포함
                items = soup.select('.news-list li, .hot-news li, .tit-list li, .comm-list li')
                
                for item in items:
                    link_tag = item.find('a', href=True)
                    if not link_tag: continue
                    
                    title = link_tag.get_text(strip=True)
                    url = link_tag['href']
                    
                    # 날짜 확인 (텍스트 OR data-time 속성)
                    date_info = item.get_text() + str(item.get('data-time', ''))
                    
                    # 제목이 너무 짧지 않고, 날짜가 타겟(어제~오늘)에 맞는 경우
                    if len(title) >= 12 and any(d in date_info for d in target_dates):
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1
            
            # --- Gamelook & 游戏陀螺 (기존 로직 유지) ---
            else:
                links = soup.find_all('a', href=True)
                for a in links:
                    title = a.get_text(strip=True)
                    url = a['href']
                    
                    # 기사 주변 텍스트에서 날짜 확인
                    context = a.parent.get_text()
                    
                    if len(title) >= 15 and any(d in context for d in target_dates):
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1
                
            print(f"-> {site['name']}: {found_count}개 수집 성공")
            
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 본문 구성
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 750px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 8px; border-bottom: 1px dotted #ccc; padding-bottom: 5px; }}
            .news-link {{ font-size: 15px; color: #1a0dab; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 시장 통합 리포트 (3/3 ~ 3/4)</h2>
                <p style="margin:5px 0 0; color:#666;">수집 대상: Gamelook, 游戏陀螺, 17173 (대량 수집 모드)</p>
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
