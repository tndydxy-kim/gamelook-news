import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
import time

# 1. 설정값 불러오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

# 2. Gemini AI 설정
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_articles():
    url = "http://www.gamelook.com.cn/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        target_dates = [
            (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            (datetime.now() - timedelta(days=1)).strftime('%m-%d'),
            "1天前"
        ]
        
        articles = []
        items = soup.find_all(['div', 'article', 'li'])

        for item in items:
            item_text = item.get_text()
            if any(dt in item_text for dt in target_dates):
                link_tag = item.find('a', href=True)
                if link_tag:
                    title = link_tag.get_text(strip=True)
                    url = link_tag['href']
                    if len(title) > 10 and url.startswith('http'):
                        articles.append({'title': title, 'url': url})

        unique_articles = {a['url']: a for a in articles}.values()
        return list(unique_articles)
    except Exception as e:
        print(f"목록 수집 에러: {e}")
        return []

def summarize_with_gemini(art):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(art['url'], headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 추출 로직 강화 (여러 클래스 시도)
        content_tag = soup.find(['div', 'article'], class_=['entry-content', 'post-content', 'entry'])
        if not content_tag:
            content = soup.get_text(strip=True)
        else:
            content = content_tag.get_text(strip=True)
            
        content = content[:3000] # 토큰 제한 대비

        prompt = f"""
        당신은 게임 전문 기자입니다. 아래 중국어 기사를 분석해서 다음 양식으로만 출력하세요.
        양식을 지키지 않으면 오류가 발생합니다.

        [한글제목] 여기에 한국어 번역 제목 작성
        [요약]
        - 핵심 요약 1줄
        - 핵심 요약 2줄
        - 핵심 요약 3줄

        기사 원문 제목: {art['title']}
        기사 본문: {content}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 텍스트 파싱
        kr_title = "제목 번역 실패"
        summary_lines = "요약 데이터를 가져오지 못했습니다."
        
        for line in text.split('\n'):
            if '[한글제목]' in line:
                kr_title = line.replace('[한글제목]', '').strip()
            if line.startswith('-'):
                if summary_lines == "요약 데이터를 가져오지 못했습니다.":
                    summary_lines = line
                else:
                    summary_lines += "<br>" + line
        
        return kr_title, summary_text if (summary_text := summary_lines) else "요약 실패"
    except Exception as e:
        print(f"Gemini 에러: {e}")
        return "번역 오류", "기사 본문을 읽어오지 못했습니다."

# 실행
news_list = get_articles()

if news_list:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; }}
            .article-box {{ margin-bottom: 25px; padding: 15px; border-bottom: 1px solid #ddd; }}
            .title-kr {{ font-size: 1.2em; font-weight: bold; color: #0056b3; }}
            .title-cn {{ font-family: 'Microsoft YaHei', sans-serif; color: #888; font-size: 0.85em; margin-bottom: 10px; }}
            .summary {{ background: #f4f4f4; padding: 10px; border-radius: 5px; font-size: 0.95em; }}
        </style>
    </head>
    <body>
        <h2>📅 Gamelook 뉴스 요약 ({datetime.now().strftime('%Y-%m-%d')})</h2>
        <hr>
    """

    for i, art in enumerate(news_list, 1):
        print(f"진행 중: {i}/{len(news_list)}")
        kr_title, summary = summarize_with_gemini(art)
        
        html_content += f"""
        <div class="article-box">
            <div class="title-kr">[{i}] {kr_title}</div>
            <div class="title-cn">중국어 원문: {art['title']}</div>
            <div class="summary">{summary}</div>
            <p><a href="{art['url']}">[원문 바로가기]</a></p>
        </div>
        """
        time.sleep(1) # API 과부하 방지

    html_content += "</body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 뉴스 브리핑"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("성공적으로 발송되었습니다.")
