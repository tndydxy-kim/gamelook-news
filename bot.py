import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 1. 설정값
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 각 사이트별 최적화된 수집 경로
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/?spm_id=www__17173.index.mod_wwwsitenav.0", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            res = requests.get(site['url'], headers=headers, timeout=30)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            found_count = 0

            # --- [Gamelook & 游戏陀螺] 초기 잘 작동하던 단순 로직 유지 ---
            if site['name'] in ["Gamelook", "游戏陀螺"]:
                links = soup.find_all('a', href=True)
                for a in links:
                    title = a.get_text(strip=True)
                    url = a['href']
                    
                    # 메뉴/광고 제외 (제목 길이 15자 이상)
                    if len(title) >= 15:
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1
                    if found_count >= 25: break # 상위 25개만

            # --- [17173] 누락 방지를 위한 공격적 수집 로직 ---
            else:
                # 17173은 뉴스 리스트의 제목(tit)과 링크를 모두 훑음
                items = soup.select('.news-list li, .tit-list li, .comm-list li, .hot-news li')
                for item in items:
                    a = item.find('a', href=True)
                    if not a: continue
                    
                    title = a.get_text(strip=True)
                    url = a['href']
                    
                    # 17173 특유의 짧은 제목이나 광고성 '抢号' 등 제외
                    if len(title) >= 12 and "抢号" not in title:
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1
            
            print(f"-> {site['name']}: {found_count}개 수집")
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# 메일 본문 구성 (디자인 유지)
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 750px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 8px; border-bottom: 1px dotted #ccc; padding-bottom: 5px; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트</h2>
                <p style="margin:5px 0 0; color:#666;">업데이트: {datetime.now().strftime('%m/%d %H:%M')}</p>
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
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 중국 게임 뉴스 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print(f"발송 완료: 총 {len(articles)}개 기사")
