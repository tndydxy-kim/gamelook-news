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
    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 찾고자 하는 어제 날짜 형식들
    target_dates = [
        (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), # 2026-03-02
        (datetime.now() - timedelta(days=1)).strftime('%m-%d'),    # 03-02
        "1天前" # 중국어로 '1일 전'
    ]
    print(f"찾고 있는 날짜 키워드: {target_dates}")

    articles = []

    # 모든 기사 아이템(div)을 대상으로 루프
    # Gamelook의 다양한 기사 박스 구조를 모두 포함
    items = soup.find_all(['div', 'article', 'li'])

    for item in items:
        item_text = item.get_text()
        # 해당 박스 안에 어제 날짜가 포함되어 있는지 확인
        if any(dt in item_text for dt in target_dates):
            link_tag = item.find('a', href=True)
            if link_tag:
                title = link_tag.get_text(strip=True)
                url = link_tag['href']
                # 제목이 너무 짧거나 중복, 이미 추가된 URL은 제외
                if len(title) > 10 and url.startswith('http'):
                    articles.append({'title': title, 'url': url})

    # 중복 제거
    unique_articles = {a['url']: a for a in articles}.values()
    return list(unique_articles)

def summarize(art):
    try:
        res = requests.get(art['url'], timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        content = soup.get_text(strip=True)[:2500]
        
        prompt = f"이 기사를 한국어로 3줄 요약해줘.\n제목: {art['title']}\n내용: {content}"
        response = model.generate_content(prompt)
        return response.text
    except:
        return "요약 실패"

# 실행
news_list = get_articles()

if news_list:
    print(f"성공! {len(news_list)}개의 기사를 찾았습니다.")
    report = f"📅 Gamelook 어제자 기사 요약 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    for i, art in enumerate(news_list, 1):
        print(f"요약 중... ({i}/{len(news_list)})")
        summary = summarize(art)
        report += f"[{i}] {art['title']}\n🔗 원문: {art['url']}\n{summary}\n\n" + "-"*30 + "\n\n"
    
    msg = EmailMessage()
    msg.set_content(report)
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 뉴스 요약 보고서"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료!")
else:
    # 기사를 못 찾았을 때, 설정 문제인지 확인하기 위해 '강제'로 아무 기사나 하나 보냄
    print("기사를 못 찾아서 테스트 모드로 전환합니다.")
    test_art = {'title': '사이트 연결 테스트 기사', 'url': 'http://www.gamelook.com.cn/'}
    summary = "기사를 자동으로 찾지 못했습니다. 사이트 구조를 확인해야 합니다."
    report = f"기사 수집 실패 알림\n\n원문: {test_art['url']}\n{summary}"
    
    msg = EmailMessage()
    msg.set_content(report)
    msg['Subject'] = "[Gamelook] 수집 실패 확인 메일"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("수집 실패 알림 메일을 보냈습니다.")
