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
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    # 오늘과 어제의 다양한 날짜 형식 대응 (2026-03-03, 03-03, 03-02 등)
    dates = [
        now.strftime('%Y-%m-%d'), now.strftime('%m-%d'),
        yesterday.strftime('%Y-%m-%d'), yesterday.strftime('%m-%d'),
        "今天", "昨天", "1天前", "刚刚"
    ]
    return dates

def fetch_articles():
    target_dates = get_target_dates()
    all_articles = []
    
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/game/", "color": "#27ae60"}
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for site in sites:
        try:
            res = requests.get(site['url'], headers=headers, timeout=20)
            # 17173은 인코딩이 다를 수 있어 자동 감지 적용
            res.encoding = res.apparent_encoding if site['name'] == "17173" else 'utf-8'
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 17173의 경우 더 넓은 범위에서 기사 추출
            search_tags = ['div', 'li', 'tr', 'p'] if site['name'] == "17173" else ['div', 'li', 'article']
            items = soup.find_all(search_tags)
            
            for item in items:
                item_text = item.get_text()
                # 날짜 키워드가 포함되어 있는지 확인
                if any(dt in item_text for dt in target_dates):
                    link_tag = item.find('a', href=True)
                    if link_tag:
                        title = link_tag.get_text(strip=True)
                        url = link_tag['href']
                        
                        # 불필요한 짧은 텍스트나 광고 제외
                        if len(title) < 12 or "광고" in title or "【" in title[:1]: continue
                        
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        # 중복 제거 및 수집
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
            print(f"{site['name']} 수집 에러: {e}")
            
    return all_articles

def get_top_lines(url, headers):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 사이트별 본문 영역 추출 시도
        content_tag = soup.find(['div', 'article'], class_=['entry-content', 'post-content', 'art-content', 'p-main', 'content', 'js-article-content'])
        if not content_tag:
            # 태그를 못 찾으면 텍스트가 많은 영역 시도
            text = soup.get_text(separator='\n', strip=True)
        else:
            text = content_tag.get_text(separator='\n', strip=True)
        
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        return "<br>".join(lines[:3])
    except:
        return "본문 미리보기를 가져올 수 없습니다."

# 실행 및 메일 전송
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background-color: #f4f4f7; padding: 20px; color: #333; }}
            .container {{ max-width: 750px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
            .article-box {{ margin-bottom: 35px; border-bottom: 1px solid #f0f0f0; padding-bottom: 25px; }}
            .site-tag {{ display: inline-block; color: white; padding: 4px 12px; border-radius: 6px; font-size: 11px; font-weight: bold; margin-bottom: 12px; }}
            .title {{ font-size: 20px; font-weight: bold; color: #1a0dab; text-decoration: none; line-height: 1.4; display: block; }}
            .preview {{ margin-top: 15px; color: #555; font-size: 14px; line-height: 1.7; background: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 5px solid #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 (오늘+어제)</h2>
                <p style="margin:8px 0 0; color:#888; font-size:13px;">Gamelook · 游戏陀螺 · 17173 실시간 업데이트</p>
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
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 주요 게임 기사 브리핑"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print(f"성공: 총 {len(articles)}개 기사 발송")
else:
    print("수집된 기사가 없습니다.")
