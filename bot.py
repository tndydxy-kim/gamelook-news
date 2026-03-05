import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import time

# Selenium 라이브러리 추가
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. 설정값 불러오기 (Github Secrets) ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD") # 16자리 앱 비밀번호
RECEIVER = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 2. Gemini API 직접 호출 함수 ---
def get_gemini_summary_direct(article_text, article_title):
    if not article_text or len(article_text) < 50:
        return "요약 실패: 기사 본문을 가져올 수 없었습니다.", "번역 실패: 원문 없음"
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f'Translate the title of the following Chinese article into Korean and summarize the content in 3 bullet points in Korean.\n\nTitle: "{article_title}"\nContent: "{article_text[:3500]}"\n\nFormat your response EXACTLY as follows:\n[Korean Title]: <Your Korean translation>\n[Summary]:\n- <Point 1>\n- <Point 2>\n- <Point 3>'
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(data), timeout=120)
        response.raise_for_status()
        result_json = response.json()
        result_text = result_json['candidates'][0]['content']['parts'][0]['text']
        
        title_match = re.search(r"\[Korean Title\]: (.*)", result_text)
        summary_match = re.search(r"\[Summary\]:([\s\S]*)", result_text)
        korean_title = title_match.group(1).strip() if title_match else "번역 실패"
        summary = summary_match.group(1).strip() if summary_match else "요약 실패"
        return summary, korean_title
    except Exception as e:
        print(f"!!! Gemini API 오류: {e}")
        return "요약 실패 (API 오류)", "번역 실패 (API 오류)"

# --- 3. 사이트별 본문 수집 함수 ---
def fetch_article_content(url, site_name):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        content_area = None
        if site_name == "Gamelook":
            content_area = soup.find('div', class_='entry-content clearfix')
        elif site_name == "游戏陀螺":
            content_area = soup.find('div', class_='content_con')
        elif site_name == "17173":
            # 17173의 본문 영역 선택자 (분석 결과)
            content_area = soup.find('div', id='mod-content')

        if content_area:
            print(f"    - ✅ '{site_name}' 본문 수집 성공!")
            return content_area.get_text(strip=True, separator='\n')
        return ""
    except Exception as e:
        print(f"    - ❌ 본문 수집 에러: {e}")
        return ""

def is_recent_article(context_text):
    now = datetime.now()
    # 17173의 날짜 형식 'YYYY-MM-DD'도 포함
    patterns = [now.strftime('%m-%d'), (now - timedelta(days=1)).strftime('%m-%d'), 
                now.strftime('%Y-%m-%d'), (now - timedelta(days=1)).strftime('%Y-%m-%d'),
                "刚刚", "小时前", "今天", "昨天"]
    return any(p in context_text for p in patterns)

# --- 4. 기사 수집 실행 ---
print("--- 1단계: 모든 사이트에서 기사 링크를 수집합니다. ---")
all_articles = []
sites = [
    {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
    {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
    {"name": "17173", "url": "https://news.17173.com/", "color": "#d35400"}
]

# Selenium Chrome 옵션 설정 (Github Actions 환경용)
chrome_options = Options()
chrome_options.add_argument("--headless") # 브라우저 창을 띄우지 않음
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Selenium 드라이버 초기화
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
except Exception as e:
    print(f"Selenium 드라이버 초기화 실패: {e}. 17173 사이트 수집을 건너뜁니다.")
    driver = None


for site in sites:
    print(f"\n-> '{site['name']}' 사이트 목록 스캔 중...")
    found_count = 0
    try:
        html_source = ""
        # 17173은 Selenium으로, 나머지는 requests로 처리
        if site['name'] == '17173' and driver:
            driver.get(site['url'])
            # 페이지가 로드될 시간을 줌
            time.sleep(5)
            # 스크롤을 3번 내려서 동적 콘텐츠 로드
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
            html_source = driver.page_source
        else:
            res = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            res.encoding = res.apparent_encoding
            html_source = res.text

        soup = BeautifulSoup(html_source, 'html.parser')
        
        # 각 사이트의 목록 구조에 맞는 선택자 사용
        if site['name'] == '17173':
            items = soup.select('ul.ptlist-news li.item')
        else:
            items = soup.find_all(['div', 'li', 'article'], limit=150)
            
        for item in items:
            date_text = item.find(class_='date')
            date_text = date_text.get_text(strip=True) if date_text else item.get_text()

            if is_recent_article(date_text):
                link_tag = item.find('a', href=True)
                if link_tag and len(link_tag.get_text(strip=True)) > 10:
                    title = link_tag.get_text(strip=True)
                    url = link_tag['href']
                    
                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    if not any(x['url'] == url for x in all_articles):
                        content = fetch_article_content(url, site['name'])
                        summary, korean_title = get_gemini_summary_direct(content, title)
                        
                        all_articles.append({
                            "site": site['name'], "title": title, "url": url,
                            "color": site['color'], "summary": summary, "korean_title": korean_title
                        })
                        found_count += 1
                        print(f"   -> '{title[:20]}...' 처리 완료.")
            
            # 너무 많은 기사를 수집하지 않도록 제한
            if found_count >= 15: break
                
        print(f"-> {site['name']}: {found_count}개 수집 성공")
    except Exception as e:
        print(f"'{site['name']}' 사이트 처리 중 오류: {e}")

if driver:
    driver.quit()

# (이하 이메일 발송 코드는 수정 없음)
if all_articles:
    now_str = datetime.now().strftime('%m/%d')
    html_content = f"""<html><head><style>/* ... 이전과 동일한 스타일 ... */</style></head><body><div class="container">...</div></body></html>""" # 본문 내용은 생략
    
    # 이메일 본문 생성 (요약/번역 내용 포함)
    email_body_html = f"""<div class="header"><h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2><p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 / 17173 (Gemini 요약 포함)</p></div>"""
    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_list = [a for a in all_articles if a['site'] == site_name]
        if site_list:
            email_body_html += f"""<div class="site-group"><span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>"""
            for art in site_list:
                email_body_html += f"""<div class="news-item"><a href="{art['url']}" class="news-link-original" target="_blank">{art['title']}</a><div class="news-title-korean">{art['korean_title']}</div><div class="summary">{art['summary']}</div></div>"""
            email_body_html += "</div>"
    
    final_html = html_content.replace('...', email_body_html) # 생략된 본문 내용을 채워넣음

    msg = EmailMessage()
    msg['Subject'] = f"[News] {now_str} 중국 게임 시장 요약 리포트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(final_html, subtype='html')
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"\n발송 완료! (총 {len(all_articles)}개 기사)")
    except Exception as e:
        print(f"\n이메일 발송 에러: {e}")
else:
    print("\n수집된 기사가 없습니다.")

