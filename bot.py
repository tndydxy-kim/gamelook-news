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
# 가장 호환성이 높은 기본 모델명으로 변경
model = genai.GenerativeModel('gemini-1.5-flash')

def get_articles():
    url = "http://www.gamelook.com.cn/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=30)
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
        return []

def summarize_with_gemini(art):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(art['url'], headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 추출
        content_tag = soup.find(['div', 'article'], class_=['entry-content', 'post-content'])
        content = content_tag.get_text(strip=True) if content_tag else soup.get_text(strip=True)
        content = content[:3000]

        # 모델 호출 (프롬프트 단순화하여 성공률 제고)
        prompt = f"Translate the title to Korean and summarize the content in 3 bullet points in Korean.\nTitle: {art['title']}\nContent: {content}"
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 간단한 파싱: 첫 줄은 제목, 나머지는 요약으로 간주
        lines = [l for l in text.split('\n') if l.strip()]
        kr_title = lines[0] if lines else "번역 실패"
        summary = "<br>".join(lines[1:]) if len(lines) > 1 else "요약 실패"
        
        return kr_title, summary

    except Exception as e:
        # 에러 메시지를 메일에 직접 찍어서 확인
        return "번역 오류", f"에러 원인: {str(e)[:100]}"

# 실행부
news_list = get_articles()

if news_list:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333; }}
            .article-box {{ margin-bottom: 25px; padding: 15px; border-left: 5px solid #0056b3; background-color: #f9f9f9; }}
            .title-kr {{ font-size: 1.15em; font-weight: bold; color: #0056b3; }}
            .title-cn {{ color: #777; font-size: 0.85em; margin-bottom: 10px; }}
            .summary {{ padding: 10px; background: white; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h2>📅 Gamelook 주요 뉴스 ({datetime.now().strftime('%Y-%m-%d')})</h2>
    """

    for i, art in enumerate(news_list, 1):
        print(f"처리 중: {i}/{len(news_list)}")
        kr_title, summary = summarize_with_gemini(art)
        
        html_content += f"""
        <div class="article-box">
            <div class="title-kr">[{i}] {kr_title}</div>
            <div class="title-cn">원문: {art['title']}</div>
            <div class="summary">{summary}</div>
            <a href="{art['url']}">[원문 바로가기]</a>
        </div>
        """
        time.sleep(1)

    html_content += "</body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 뉴스 브리핑"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("성공")
else:
    print("기사 없음")
