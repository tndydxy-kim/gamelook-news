import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai

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
        print(f"기사 목록 가져오기 에러: {e}")
        return []

def summarize_with_gemini(art):
    try:
        res = requests.get(art['url'], timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 텍스트 추출 최적화
        content_tag = soup.select_one('.entry-content, .post-content, article')
        content = content_tag.get_text(strip=True)[:3000] if content_tag else soup.get_text(strip=True)[:3000]
        
        # [요청사항 반영] 제목 번역 및 3줄 요약 명령
        prompt = f"""
        중국 게임 기사를 분석해서 다음 형식으로 출력해줘.
        1. 번역된 한국어 제목
        2. 핵심 내용 한국어로 3줄 요약

        기사 제목: {art['title']}
        기사 본문: {content}
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip().split('\n')
        
        # 첫 줄은 한국어 제목, 나머지는 요약으로 분리 시도
        translated_title = result[0].replace("번역된 한국어 제목:", "").strip()
        summary_text = "<br>".join(result[1:])
        
        return translated_title, summary_text
    except Exception as e:
        print(f"요약 에러 ({art['url']}): {e}")
        return "제목 번역 실패", "본문 요약에 실패했습니다. 원문을 참조해 주세요."

# 실행
news_list = get_articles()

if news_list:
    # HTML 메일 본문 작성 (폰트 설정 포함)
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ 
                font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; 
                line-height: 1.6; 
                color: #333;
            }}
            .article-box {{ 
                margin-bottom: 30px; 
                padding: 15px; 
                border-left: 5px solid #0056b3; 
                background-color: #f9f9f9;
            }}
            .title-cn {{ 
                font-family: 'Microsoft YaHei', sans-serif; 
                color: #666; 
                font-size: 0.9em;
            }}
            .title-kr {{ 
                font-size: 1.2em; 
                font-weight: bold; 
                color: #0056b3; 
                margin-bottom: 5px;
            }}
            .summary {{ margin: 10px 0; }}
            .link-btn {{ color: #0056b3; text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h2>📅 Gamelook 뉴스 요약 보고서 ({datetime.now().strftime('%Y-%m-%d')})</h2>
        <p>전날 수집된 기사 총 {len(news_list)}건에 대한 요약입니다.</p>
        <hr>
    """

    for i, art in enumerate(news_list, 1):
        print(f"처리 중... ({i}/{len(news_list)})")
        kr_title, summary = summarize_with_gemini(art)
        
        html_content += f"""
        <div class="article-box">
            <div class="title-kr">[{i}] {kr_title}</div>
            <div class="title-cn">원문 제목: {art['title']}</div>
            <div class="summary">{summary}</div>
            <a href="{art['url']}" class="link-btn">[원문 바로가기]</a>
        </div>
        """

    html_content += "</body></html>"

    # 메일 발송 설정 (HTML 형식)
    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 주요 뉴스 요약 보고서"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.set_content("이 메일은 HTML 형식을 지원합니다. HTML 뷰어로 확인해 주세요.") # 기본 텍스트
    msg.add_alternative(html_content, subtype='html') # HTML 추가

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료!")
else:
    print("수집된 기사가 없습니다.")
