import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai

# 1. 환경 변수에서 정보 가져오기
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

# 2. Gemini AI 설정
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_articles():
    url = "http://www.gamelook.com.cn/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 어제 날짜 확인 (중국 사이트이므로 현재 시간 기준 전날 기사 추출)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    articles = []

    # Gamelook 기사 리스트 태그 (실제 구조에 맞춤)
    for item in soup.select('.post-item'):
        date_tag = item.select_one('.post-date')
        if date_tag and yesterday in date_tag.text:
            link_tag = item.select_one('h2 a')
            articles.append({'title': link_tag.text.strip(), 'url': link_tag['href']})
    return articles

def summarize(art):
    # 기사 본문 내용 가져오기
    res = requests.get(art['url'])
    soup = BeautifulSoup(res.text, 'html.parser')
    content = soup.select_one('.entry-content').text[:2000]
    
    prompt = f"아래 중국어 게임 기사 '{art['title']}'를 한국어로 번역하고 핵심을 3줄 요약해줘.\n내용: {content}"
    response = model.generate_content(prompt)
    return response.text

# 메인 로직 실행
news_list = get_articles()

if news_list:
    report = f"📅 {datetime.now().strftime('%Y-%m-%d')} Gamelook 뉴스 브리핑\n\n"
    for art in news_list:
        summary = summarize(art)
        report += f"▶️ {art['title']}\n🔗 원문: {art['url']}\n{summary}\n\n" + "-"*30 + "\n\n"
    
    # 이메일 전송
    msg = EmailMessage()
    msg.set_content(report)
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 뉴스 요약 보고서"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
