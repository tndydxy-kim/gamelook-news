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

def get_yesterday_dates():
    now = datetime.now() - timedelta(days=1)
    # 다양한 날짜 형식 대응 (2026-03-02, 03-02, 1일 전 등)
    return [now.strftime('%Y-%m-%d'), now.strftime('%m-%d'), "1天前", "昨天"]

def fetch_articles():
    target_dates = get_yesterday_dates()
    all_articles = []
    
    # 사이트 설정 및 고유 색상
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"}, # 파랑
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/", "color": "#e67e22"}, # 주황
        {"name": "17173", "url": "https://news.17173.com/game/", "color": "#27ae60"}  # 초록
    ]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for site in sites:
        try:
            res = requests.get(site['url'], headers=headers, timeout=20)
            res.encoding = 'utf-8' if site['name'] != "17173" else 'gbk' # 17173은 인코딩 주의
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 17173은 구조가 특이하여 별도 탐색 범위를 넓힘
            items = soup.find_all(['div', 'li', 'article', 'tr'])
            
            for item in items:
                item_text = item.get_text()
                if any(dt in item_text for dt in target_dates):
                    link_tag = item.find('a', href=True)
                    if link_tag:
                        title = link_tag.get_text(strip=True)
                        url = link_tag['href']
                        if len(title) < 10: continue # 너무 짧은 메뉴 링크 등 제외
                        
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(a['url'] == url for a in all_articles):
                            preview = get_top_lines(url, headers)
                            all_articles.append({
                                "site": site['name'],
                                "title": title,
                                "url": url,
                                "preview": preview,
                                "color": site['color']
                            })
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

def get_top_lines(url, headers):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        # 사이트별 인코딩 자동 감지
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 영역 탐색
        content_tag = soup.find(['div', 'article'], class_=['entry-content', 'post-content', 'art-content', 'p-main', 'content'])
        text = content_tag.get_text(separator='\n', strip=True) if content_tag else soup.get_text(separator='\n', strip=True)
        
        # 유의미한 내용 3줄 추출
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 15]
        return "<br>".join(lines[:3])
    except:
        return "본문 미리보기를 가져올 수 없습니다."

# 실행 및 메일 구성
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background-color: #f0f2f5; padding: 20px; color: #333; }}
            .container {{ max-width: 750px; margin: auto; background: white; padding: 25px; border-radius: 12px; border: 1px solid #e1e4e8; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 15px; margin-bottom: 25px; }}
            .article-box {{ margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
            .site-tag {{ display: inline-block; color: white; padding: 3px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; }}
            .title {{ font-size: 19px; font-weight: bold; color: #1a0dab; text-decoration: none; line-height: 1.4; display: block; }}
            .title:hover {{ text-decoration: underline; }}
            .preview {{ margin-top: 12px; color: #444; font-size: 14px; line-height: 1.6; background: #f8f9fa; padding: 12px; border-radius: 6px; border-left: 4px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트</h2>
                <p style="margin:5px 0 0; color:#666; font-size:13px;">수집 대상: Gamelook, 游戏陀螺, 17173</p>
            </div>
    """

    for art in articles:
        html_content += f"""
        <div class="article-box">
            <span class="site-tag" style="background-color: {art['color']};">{art['site']}</span>
            <a href="{art['url']}" class="title">{art['title']}</a>
            <div class="preview">{art['preview']}</div>
        </div>
        """

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 중국 게임 시장 기사 모음"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 성공!")
else:
    print("새로운 기사가 없습니다.")
