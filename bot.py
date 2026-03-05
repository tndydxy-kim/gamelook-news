import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
import re

# --- 1. 설정값 불러오기 ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD")
RECEIVER = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 2. Gemini API 설정 ---
if not GEMINI_API_KEY:
    print("오류: GEMINI_API_KEY가 설정되지 않았습니다.")
    exit()
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_gemini_summary(article_text, article_title):
    """Gemini API를 사용하여 요약 및 번역"""
    if not article_text or len(article_text) < 50:
        return "요약 실패: 기사 본문을 가져올 수 없었습니다.", "번역 실패: 원문 없음"
    prompt = f'Translate the title of the following Chinese article into Korean and summarize the content in 3 bullet points in Korean.\n\nTitle: "{article_title}"\nContent: "{article_text[:3500]}"\n\nFormat your response EXACTLY as follows:\n[Korean Title]: <Your Korean translation>\n[Summary]:\n- <Point 1>\n- <Point 2>\n- <Point 3>'
    try:
        response = model.generate_content(prompt, request_options={'timeout': 120})
        title_match = re.search(r"\[Korean Title\]: (.*)", response.text)
        summary_match = re.search(r"\[Summary\]:([\s\S]*)", response.text)
        korean_title = title_match.group(1).strip() if title_match else "번역 실패 (응답 형식 오류)"
        summary = summary_match.group(1).strip() if summary_match else "요약 실패 (응답 형식 오류)"
        return summary, korean_title
    except Exception as e:
        if "429" in str(e): return "요약 실패 (API 사용량 초과)", "번역 실패 (API 사용량 초과)"
        print(f"!!! Gemini API 오류: {e}")
        return "요약 실패 (API 호출 오류)", "번역 실패 (API 호출 오류)"

def fetch_article_content(url, site_name):
    """사이트별 정확한 선택자를 사용하여 본문 텍스트 추출"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        content_area = None

        # --- 사이트별 정확한 '주소'를 최종 반영! ---
        if site_name == "Gamelook":
            content_area = soup.find('div', class_='entry-content clearfix')
        elif site_name == "游戏陀螺":
            content_area = soup.find('div', class_='content_con')
        
        if content_area:
            print(f"    - ✅ 본문 수집 성공! (URL: {url})")
            return content_area.get_text(strip=True, separator='\n')
        else:
            # 이 메시지가 보인다면, 사이트 구조가 또 변경된 것입니다.
            print(f"    - ❌ '{site_name}' 본문 영역을 찾지 못함. URL: {url}")
            return ""
    except Exception as e:
        print(f"    - ❌ 본문 수집 중 에러 발생: {e}")
        return ""

def is_recent_article(context_text):
    """최신 기사인지 판별"""
    now = datetime.now()
    patterns = [now.strftime('%m-%d'), (now - timedelta(days=1)).strftime('%m-%d'), "刚刚", "小时前", "今天", "昨天"]
    return any(p in context_text for p in patterns)

# --- 3. "선 수집, 후 처리" 실행 ---
print("--- 1단계: 모든 사이트에서 기사 링크를 빠르게 수집합니다. ---")
initial_articles = []
sites = [
    {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
    {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"}
]
for site in sites:
    try:
        print(f"-> '{site['name']}' 사이트 목록 스캔 중...")
        res = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        items = soup.find_all(['div', 'li', 'article'], limit=100)
        found_count = 0
        for item in items:
            if is_recent_article(item.get_text()) and item.find('a', href=True) and len(item.find('a').get_text(strip=True)) > 15:
                link_tag = item.find('a', href=True)
                title = link_tag.get_text(strip=True)
                url = link_tag['href']
                
                if not url.startswith('http'):
                    base_url = "https://www.youxituoluo.com" i
