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
        # 메인 페이지의 모든 링크를 훑어 어제 날짜 기사 추출
        items = soup.find_all(['div', 'article', 'li'])
        for item in items:
            item_text = item.get_text()
            if any(dt in item_text for dt in target_dates):
                link_tag = item.find('a', href=True)
                if link_tag and len(link_tag.get_text(strip=True)) > 10:
                    articles.append({
                        'title': link_tag.get_text(strip=True),
                        'url': link_tag['href']
                    })

        unique_articles = {a['url']: a for a in articles}.values()
        return list(unique_articles)
    except:
        return []

def summarize_with_gemini(art):
    # 가장 호환성이 높은 모델 리스트 시도
    available_models = ['gemini-1.5-flash', 'gemini-pro']
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(art['url'], headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 추출 시도
        content_tag = soup.find(['div', 'article'], class_=['entry-content', 'post-content'])
        content = content_tag.get_text(strip=True) if content_tag else soup.get_text(strip=True)
        content = content[:2000] # 안정성을 위해 길이 단축

        prompt = f"당신은 뉴스 요약 비서입니다. 아래 중국어 기사 제목과 본문을 읽고 한국어로 답하세요.\n\n1. 제목 번역\n2. 핵심 내용 3줄 요약\n\n기사 제목: {art['title']}\n본문: {content}"
        
        # 모델 호출 (안전한 설정 추가)
        selected_model = genai.GenerativeModel('gemini-1.5-flash')
        response = selected_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        
        text = response.text.strip()
        lines = [l for l in text.split('\n') if l.strip()]
        
        # 제목과 요약 분리 로직
        kr_title = lines[0].replace('**', '').strip()
        summary = "<br>".join(lines[1:])
        return kr_title, summary

    except Exception as e:
        # 에러 종류를 정확히 파악하기 위한 출력
        print(f"상세 에러 내용: {str(e)}")
        return "번역/요약 중", f"내용을 처리하는 과정에서 API 응답 지연이 발생했습니다. 원문을 확인해 주세요. (에러: {str(e)[:50]})"

# 실행부
news_list = get_articles()

if news_list:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .article-box {{ margin-bottom: 25px; padding: 15px; border-left: 5px solid #0056b3; background-color: #f9f9f9; }}
            .title-kr {{ font-size: 1.15em; font-weight: bold; color: #0056b3; margin-bottom: 5px; }}
            .title-cn {{ color: #777; font-size: 0.85em; margin-bottom: 10px; }}
            .summary {{ padding: 10px; background: white; border: 1px solid #eee; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h2>📅 Gamelook 주요 뉴스 요약 ({datetime.now().strftime('%Y-%m-%d')})</h2>
    """

    for i, art in enumerate(news_list, 1):
        print(f"[{i}/{len(news_list)}] {art['title'][:20]}... 처리 중")
        kr_title, summary = summarize_with_gemini(art)
        
        html_content += f"""
        <div class="article-box">
            <div class="title-kr">[{i}] {kr_title}</div>
            <div class="title-cn">원문: {art['title']}</div>
            <div class="summary">{summary}</div>
            <p><a href="{art['url']}" style="color: #0056b3;">[원문 바로가기]</a></p>
        </div>
        """
        time.sleep(2) # 무료 티어 쿼터 제한 방지

    html_content += "</body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 뉴스 요약 보고서"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 성공!")
else:
    print("수집된 기사 없음")
