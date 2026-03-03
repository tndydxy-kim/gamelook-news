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
# 모델명을 가장 안정적인 버전으로 변경
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def get_articles():
    url = "http://www.gamelook.com.cn/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
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
        print(f"목록 수집 에러: {e}")
        return []

def summarize_with_gemini(art):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'http://www.gamelook.com.cn/'
    }
    try:
        res = requests.get(art['url'], headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        content = ""
        content_tag = soup.find(['div', 'article', 'section'], class_=['entry-content', 'post-content', 'entry', 'content'])
        if not content_tag:
            content_tag = soup.find('article')
        
        if content_tag:
            for s in content_tag(['script', 'style', 'aside']):
                s.decompose()
            content = content_tag.get_text(separator='\n', strip=True)
        
        if len(content) < 200:
            content = soup.get_text(separator='\n', strip=True)

        if len(content) < 100:
            return "본문 추출 실패", "기사 본문 내용이 너무 적어 요약할 수 없습니다."

        prompt = f"""
        중국어 게임 기사입니다. 아래 내용을 분석해서 한국어로 출력하세요.
        1. [한글제목]: 기사 제목을 한국어로 자연스럽게 번역해서 작성
        2. [요약]: 기사의 핵심 내용을 한국어 불렛포인트 3줄로 요약

        기사 제목: {art['title']}
        기사 본문: {content[:3500]}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        kr_title = "제목 번역 실패"
        summary_lines = []
        
        for line in text.split('\n'):
            if '[한글제목]' in line:
                kr_title = line.replace('[한글제목]', '').replace(':', '').strip()
            if line.strip().startswith('-') or line.strip().startswith('•') or (len(line) > 15 and '[' not in line):
                if len(summary_lines) < 3:
                    summary_lines.append(line.strip())
        
        summary_final = "<br>".join(summary_lines) if summary_lines else "요약 생성에 실패했습니다."
        return kr_title, summary_final

    except Exception as e:
        print(f"상세 에러 ({art['url']}): {e}")
        return "번역 오류", f"에러 발생: {str(e)}"

# 실행부
news_list = get_articles()

if news_list:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .article-box {{ margin-bottom: 30px; padding: 20px; border-left: 6px solid #0056b3; background-color: #fcfcfc; border-bottom: 1px solid #eee; }}
            .title-kr {{ font-size: 1.25em; font-weight: bold; color: #0056b3; margin-bottom: 8px; }}
            .title-cn {{ font-family: 'Microsoft YaHei', sans-serif; color: #777; font-size: 0.9em; margin-bottom: 15px; }}
            .summary {{ background: #ffffff; padding: 12px; border: 1px solid #eef; border-radius: 8px; font-size: 1em; color: #444; }}
            .link-btn {{ display: inline-block; margin-top: 10px; color: #0056b3; font-weight: bold; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h2 style="color: #222;">📅 Gamelook 주요 뉴스 브리핑 ({datetime.now().strftime('%Y-%m-%d')})</h2>
        <p style="color: #666;">어제자 기사 총 {len(news_list)}건에 대한 AI 자동 요약 보고서입니다.</p>
        <hr style="border: 0; border-top: 2px solid #eee;">
    """

    for i, art in enumerate(news_list, 1):
        print(f"처리 중... ({i}/{len(news_list)})")
        kr_title, summary = summarize_with_gemini(art)
        
        html_content += f"""
        <div class="article-box">
            <div class="title-kr">[{i}] {kr_title}</div>
            <div class="title-cn">원문: {art['title']}</div>
            <div class="summary">{summary}</div>
            <a href="{art['url']}" class="link-btn">▶ 원문 바로가기</a>
        </div>
        """
        time.sleep(2)

    html_content += """</body></html>"""

    # 메일 발송 로직 - 오타 수정 완료
    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 게임 뉴스 요약 리포트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html') # add_ -> add_alternative로 수정

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료!")
else:
    print("수집된 기사가 없습니다.")
