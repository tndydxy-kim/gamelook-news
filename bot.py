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
            res = requests.get(site['url'], headers=headers, timeout=20)
            res.encoding = res.apparent_encoding # 17173 GBK 대응
            soup = BeautifulSoup(res.text, 'html.parser')
            
            found_count = 0
            # 17173은 'news-list'나 'tit' 클래스 위주로 탐색
            links = soup.select('a[href*="/2026/"], a[href*="/content/"]') if site['name'] == "17173" else soup.find_all('a', href=True)

            for a in links:
                url = a['href']
                title = a.get_text(strip=True)
                
                # 유효성 검사 (제목 길이 및 중복 확인)
                if len(title) < 15 or not url.startswith('http') or any(x['url'] == url for x in all_articles):
                    continue
                
                # 17173 및 타 사이트의 최신 기사만 수집 (최대 10개로 제한하여 스팸 방지)
                if found_count >= 10: break

                preview = get_clean_preview(url, headers)
                if preview:
                    all_articles.append({
                        "site": site['name'],
                        "title": title,
                        "url": url,
                        "preview": preview,
                        "color": site['color']
                    })
                    found_count += 1
                    
        except Exception as e:
            print(f"{site['name']} 수집 에러: {e}")
            
    return all_articles

def get_clean_preview(url, headers):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')

        # 불필요한 요소(광고, 날짜, 저작권 문구 등) 사전 제거
        for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'span', 'em']):
            tag.decompose()

        # 본문 핵심 영역 지정 시도
        content_selectors = ['.entry-content', '.post-content', '.art-content', '#Art_Content', '.js-article-content', '.content']
        content_tag = None
        for selector in content_selectors:
            content_tag = soup.select_one(selector)
            if content_tag: break
        
        target = content_tag if content_tag else soup.body
        if not target: return None

        # 텍스트 추출 및 정제
        text_lines = target.get_text(separator='\n', strip=True).split('\n')
        
        clean_lines = []
        # 노이즈 문구 필터링 (정규식)
        noise_keywords = ['공유', '다운로드', '저작권', '출처', '기자', '댓글', '전재', '2026', 'http', '편집', '로그인']
        
        for line in text_lines:
            line = line.strip()
            # 20자 이상이며 노이즈 키워드가 없는 유의미한 문장만 선택
            if len(line) > 25 and not any(kw in line for kw in noise_keywords):
                clean_lines.append(line)
                if len(clean_lines) >= 3: break
        
        return "<br>".join(clean_lines) if clean_lines else "본문 미리보기를 분석할 수 없습니다."
    except:
        return None

# 실행 및 메일 발송
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; background-color: #f4f4f7; padding: 20px; }}
            .container {{ max-width: 700px; margin: auto; background: white; padding: 30px; border-radius: 12px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 15px; margin-bottom: 25px; }}
            .article-box {{ margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
            .site-tag {{ display: inline-block; color: white; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 8px; }}
            .title {{ font-size: 18px; font-weight: bold; color: #1a0dab; text-decoration: none; line-height: 1.4; }}
            .preview {{ margin-top: 12px; color: #444; font-size: 14px; line-height: 1.6; background: #f9f9f9; padding: 15px; border-radius: 6px; border-left: 4px solid #ccc; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">🎮 중국 게임 뉴스 통합 리포트</h2>
                <p style="margin:5px 0 0; color:#888;">{datetime.now().strftime('%Y-%m-%d')} 기준 최신 기사 모음</p>
            </div>
    """

    for art in articles:
        html_content += f"""
        <div class="article-box">
            <span class="site-tag" style="background-color: {art['color']};">{art['site']}</span><br>
            <a href="{art['url']}" class="title">{art['title']}</a>
            <div class="preview">{art['preview']}</div>
        </div>
        """

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 게임 시장 주요 기사"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("발송 완료")
