import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

# 1. 설정값 불러오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def get_yesterday_dates():
    now = datetime.now() - timedelta(days=1)
    return [now.strftime('%Y-%m-%d'), now.strftime('%m-%d'), "1天前"]

def fetch_articles():
    target_dates = get_yesterday_dates()
    all_articles = []
    
    # 수집 대상 사이트 정의
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/"},
        {"name": "17173", "url": "https://news.17173.com/game/"},
        {"name": "游戏陀螺 (Youxituoluo)", "url": "https://www.youxituoluo.com/"}
    ]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for site in sites:
        try:
            print(f"{site['name']} 수집 중...")
            res = requests.get(site['url'], headers=headers, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            count = 0
            # 모든 링크를 탐색하여 날짜 조건 확인
            items = soup.find_all(['div', 'li', 'article'])
            for item in items:
                item_text = item.get_text()
                if any(dt in item_text for dt in target_dates):
                    link_tag = item.find('a', href=True)
                    if link_tag and len(link_tag.get_text(strip=True)) > 10:
                        title = link_tag.get_text(strip=True)
                        url = link_tag['href']
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        # 중복 방지 및 기사 상세 상단 3줄 가져오기
                        if not any(a['url'] == url for a in all_articles):
                            top_lines = get_top_lines(url, headers)
                            all_articles.append({
                                "site": site['name'],
                                "title": title,
                                "url": url,
                                "preview": top_lines
                            })
                            count += 1
            print(f"- {site['name']}: {count}개 발견")
        except Exception as e:
            print(f"{site['name']} 접속 실패: {e}")
            
    return all_articles

def get_top_lines(url, headers):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        # 본문 태그를 찾아 상단 텍스트 추출
        content_tag = soup.find(['div', 'article', 'section'], class_=['entry-content', 'post-content', 'art-content', 'content'])
        text = content_tag.get_text(separator='\n', strip=True) if content_tag else soup.get_text(separator='\n', strip=True)
        # 상단 3줄 추출
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        return "<br>".join(lines[:3])
    except:
        return "본문 내용을 불러올 수 없습니다."

# 메인 실행부
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background-color: #f4f7f9; padding: 20px; }}
            .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ border-bottom: 2px solid #0056b3; padding-bottom: 10px; margin-bottom: 20px; }}
            .site-tag {{ display: inline-block; background: #0056b3; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-bottom: 5px; }}
            .article-box {{ border-bottom: 1px solid #eee; padding: 15px 0; }}
            .title {{ font-size: 18px; font-weight: bold; color: #333; text-decoration: none; display: block; margin-bottom: 8px; }}
            .preview {{ color: #666; font-size: 14px; line-height: 1.5; background: #f9f9f9; padding: 10px; border-radius: 5px; }}
            .link-btn {{ color: #0056b3; font-size: 13px; font-weight: bold; text-decoration: none; display: inline-block; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🎮 중국 게임 뉴스 통합 브리핑</h2>
                <p>{(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')} 기준 업데이트</p>
            </div>
    """

    for art in articles:
        html_content += f"""
        <div class="article-box">
            <span class="site-tag">{art['site']}</span>
            <a href="{art['url']}" class="title">{art['title']}</a>
            <div class="preview">{art['preview']}</div>
            <a href="{art['url']}" class="link-btn">원문 읽기 →</a>
        </div>
        """

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] 중국 게임 시장 주요 기사 리포트 ({(datetime.now()-timedelta(days=1)).strftime('%m/%d')})"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("통합 뉴스레터 발송 완료!")
else:
    print("수집된 기사가 없습니다.")
