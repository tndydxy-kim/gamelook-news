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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 실행 시점 기준 '어제' 날짜 계산 (예: 오늘이 3일이면 2일 기사를 찾음)
    yesterday_full = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') # 2026-03-02
    yesterday_short = (datetime.now() - timedelta(days=1)).strftime('%m-%d')    # 03-02
    
    articles = []

    # 기사 목록을 담고 있는 모든 요소를 찾습니다.
    # Gamelook의 기사 리스트 구조를 더 폭넓게 검색합니다.
    items = soup.find_all(['div', 'li', 'article'], class_=['post-item', 'item-list', 'post'])

    for item in items:
        # 날짜 정보가 들어있는 태그 찾기
        date_tag = item.find(True, class_=['post-date', 'date', 'time', 'entry-date'])
        link_tag = item.find('a', href=True)
        
        if date_tag and link_tag:
            date_text = date_tag.get_text(strip=True)
            # 어제 날짜(Full 혹은 Short 형식)가 포함되어 있는지 확인
            if (yesterday_full in date_text) or (yesterday_short in date_text) or ("1天前" in date_text):
                title = link_tag.get_text(strip=True)
                if title and len(title) > 5: # 너무 짧은 텍스트 제외
                    articles.append({
                        'title': title,
                        'url': link_tag['href']
                    })
    
    # 중복 기사 제거
    unique_articles = {a['url']: a for a in articles}.values()
    return list(unique_articles)

def summarize(art):
    try:
        res = requests.get(art['url'], timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 본문 텍스트만 추출
        content = ""
        entry = soup.select_one('.entry-content, .post-content, article')
        if entry:
            content = entry.get_text(strip=True)[:2500]
        else:
            content = soup.get_text(strip=True)[:2500]
        
        prompt = f"중국 게임 기사를 한국어로 요약해줘. 핵심 내용 3줄 요약이 포함되어야 해.\n제목: {art['title']}\n내용: {content}"
        response = model.generate_content(prompt)
        return response.text
    except:
        return "본문 요약에 실패했습니다. 링크를 확인해 주세요."

# 실행부
news_list = get_articles()

if news_list:
    print(f"총 {len(news_list)}개의 어제자 기사를 발견했습니다.")
    report = f"📅 Gamelook 뉴스 브리핑 (발송일: {datetime.now().strftime('%Y-%m-%d')})\n\n"
    
    for i, art in enumerate(news_list, 1):
        print(f"요약 중... ({i}/{len(news_list)})")
        summary = summarize(art)
        report += f"[{i}] {art['title']}\n🔗 원문: {art['url']}\n{summary}\n\n" + "-"*30 + "\n\n"
    
    msg = EmailMessage()
    msg.set_content(report)
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 주요 뉴스 (전날 전체 기사)"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료!")
else:
    # 기사가 없을 경우에도 알림을 받고 싶으시면 이 부분을 메일 발송 코드로 채울 수 있습니다.
    print("어제 날짜로 올라온 새로운 기사가 없습니다.")
