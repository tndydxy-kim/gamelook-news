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
    # 브라우저처럼 보이기 위한 헤더 강화
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
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
        # 기사 본문 가져오기 시도
        res = requests.get(art['url'], headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # [수정] 본문 추출을 위해 가장 가능성 높은 태그들을 순서대로 시도
        content = ""
        # 1순위: 특정 클래스, 2순위: article 태그, 3순위: id가 content인 것
        content_tag = soup.find(['div', 'article', 'section'], class_=['entry-content', 'post-content', 'entry', 'content'])
        if not content_tag:
            content_tag = soup.find('article')
        
        if content_tag:
            # 광고나 불필요한 태그 제거
            for s in content_tag(['script', 'style', 'aside']):
                s.decompose()
            content = content_tag.get_text(separator='\n', strip=True)
        
        # 위 시도가 모두 실패하면 페이지 전체 텍스트에서 추출
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
            if line.strip().startswith('-') or line.strip().startswith('•') or '[요약]' not in line and len(line) > 10:
                if len(summary_lines) < 3 and not line.startswith('['):
                    summary_lines.append(line.strip())
        
        summary_text = "<br>".join(summary_lines) if summary_lines else "요약 생성에 실패했습니다."
        return kr_title, summary_text

    except Exception as e:
        print(f"상세 에러 ({art['url']}): {e}")
        return "번역 오류", f"에러 발생: {str(e)}"

# 실행 및 메일 발송 로직은 이전과 동일 (안정성을 위해 재구성)
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
        time.sleep(2) # Gemini 및 서버 부하 방지용 (2초로 상향)

    html_content += """
        <p style="font-size: 0.8em; color: #999; text-align: center; margin-top: 40px;">
            본 메일은 AI에 의해 자동 생성되었습니다.
        </p>
    </body></html>
    """

    msg = EmailMessage()
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 게임 뉴스 요약 리포트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_
