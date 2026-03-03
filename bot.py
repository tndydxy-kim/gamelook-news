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
    
    # 어제 날짜 설정 (확인하신 2026-03-02 형식)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    articles = []

    # Gamelook의 기사 아이템들을 모두 찾습니다.
    # 보통 div 태그 내의 post-item이나 li 태그 내에 기사가 위치합니다.
    items = soup.select('div.post-item, div.item-list, article')
    
    for item in items:
        # 1. 날짜 텍스트 추출
        date_tag = item.select_one('.post-date, .date, .time')
        # 2. 제목과 링크 추출
        link_tag = item.select_one('h2 a, h3 a, .post-title a')
        
        if date_tag and link_tag:
            date_text = date_tag.get_text(strip=True)
            # 날짜가 어제 날짜를 포함하는지 검사
            if yesterday in date_text:
                articles.append({
                    'title': link_tag.get_text(strip=True),
                    'url': link_tag['href']
                })
    
    # 중복 제거 (간혹 같은 기사가 두 번 잡히는 경우 대비)
    seen = set()
    unique_articles = []
    for a in articles:
        if a['url'] not in seen:
            unique_articles.append(a)
            seen.add(a['url'])
            
    return unique_articles

def summarize(art):
    try:
        # 본문 페이지 접속
        res = requests.get(art['url'], timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 기사 본문 영역만 추출 (entry-content 클래스 등)
        content_area = soup.select_one('.entry-content, .post-content, #content')
        content = content_area.get_text(strip=True)[:2000] if content_area else soup.get_text(strip=True)[:2000]
        
        prompt = f"다음은 중국 게임 기사 '{art['title']}'의 내용이야. 이 내용을 한국어로 번역하고 핵심을 3줄로 요약해줘.\n\n내용:\n{content}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"요약 중 오류 발생: {str(e)}"

# 실행
news_list = get_articles()

if news_list:
    print(f"총 {len(news_list)}개의 기사를 찾았습니다.")
    full_report = f"📅 Gamelook 뉴스 보고서 ({datetime.now().strftime('%Y-%m-%d')})\n"
    full_report += f"대상 날짜: {(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}\n\n"
    
    for idx, art in enumerate(news_list, 1):
        print(f"요약 중 ({idx}/{len(news_list)}): {art['title']}")
        summary = summarize(art)
        full_report += f"[{idx}] {art['title']}\n🔗 원문: {art['url']}\n{summary}\n\n" + "="*50 + "\n\n"
    
    # 메일 전송
    msg = EmailMessage()
    msg.set_content(full_report)
    msg['Subject'] = f"[Gamelook] {datetime.now().strftime('%m/%d')} 주요 뉴스 요약"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print("메일 발송 완료!")
else:
    print(f"대상 날짜({(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')})에 해당하는 기사가 없습니다.")
