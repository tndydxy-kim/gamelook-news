import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time

# Selenium 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. 설정값 불러오기 (Github Secrets) ---
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD") # 16자리 앱 비밀번호
RECEIVER = os.environ.get("RECEIVER_EMAIL")

def is_recent_article(context_text):
    """최신 기사인지 판별 (모든 사이트의 날짜 형식 지원)"""
    now = datetime.now()
    patterns = [
        now.strftime('%m-%d'), 
        (now - timedelta(days=1)).strftime('%m-%d'),
        now.strftime('%Y-%m-%d'), 
        (now - timedelta(days=1)).strftime('%Y-%m-%d'),
        "刚刚", "小时前", "今天", "昨天"
    ]
    return any(p in context_text for p in patterns)

# --- 2. 기사 수집 함수 (이미지 포함) ---
def fetch_articles_with_images():
    all_articles = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/", "color": "#d35400"}
    ]

    # Selenium Chrome 옵션 설정 (Github Actions 환경용)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Selenium 드라이버 초기화 성공")
    except Exception as e:
        print(f"❌ Selenium 드라이버 초기화 실패: {e}. 17173 사이트 수집을 건너뜁니다.")

    for site in sites:
        print(f"\n-> '{site['name']}' 사이트 목록 스캔 중...")
        found_count = 0
        try:
            html_source = ""
            # 17173은 Selenium으로, 나머지는 requests로 처리
            if site['name'] == '17173' and driver:
                driver.get(site['url'])
                time.sleep(5) # 페이지가 로드될 시간을 줌
                # 스크롤을 3번 내려서 동적 콘텐츠 로드
                print("   - 스크롤을 내려 추가 기사를 로드합니다...")
                for i in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    print(f"   - 스크롤 {i+1}/3")
                    time.sleep(3)
                html_source = driver.page_source
            else:
                res = requests.get(site['url'], headers=headers, timeout=30)
                res.encoding = res.apparent_encoding
                html_source = res.text

            soup = BeautifulSoup(html_source, 'html.parser')
            
            items = []
            if site['name'] == '17173':
                items = soup.select('ul.ptlist-news li.item')
            elif site['name'] == 'Gamelook':
                 items = soup.select('div.entry-wrap article.post')
            elif site['name'] == '游戏陀螺':
                 items = soup.select('div.article_2')

            if not items:
                 items = soup.find_all(['div', 'li', 'article'], limit=150)

            for item in items:
                # 날짜, 제목, 링크, 이미지 태그를 찾음
                date_tag = item.find(class_='date')
                date_text = date_tag.get_text(strip=True) if date_tag else item.get_text()
                link_tag = item.find('a', href=True)
                img_tag = item.find('img')

                if is_recent_article(date_text) and link_tag and len(link_tag.get_text(strip=True)) > 10:
                    title = link_tag.get_text(strip=True)
                    url = link_tag['href']
                    
                    # 이미지 URL 추출 (src 또는 data-original 속성)
                    img_url = ""
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-original') or ""

                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    # 이미지 URL이 상대 경로일 경우 절대 경로로 변환
                    if img_url and not img_url.startswith('http'):
                        img_url = requests.compat.urljoin(site['url'], img_url)

                    if not any(x['url'] == url for x in all_articles):
                        all_articles.append({
                            "site": site['name'],
                            "title": title,
                            "url": url,
                            "img_url": img_url, # 이미지 URL 추가
                            "color": site['color']
                        })
                        found_count += 1
                
                if found_count >= 15: break
                
            print(f"-> {site['name']}: {found_count}개 수집 성공")
        except Exception as e:
            print(f"'{site['name']}' 사이트 처리 중 오류: {e}")

    if driver:
        driver.quit()
    return all_articles

# --- 3. 메일 본문 구성 및 발송 ---
articles = fetch_articles_with_images()

if articles:
    now_str = datetime.now().strftime('%m/%d')
    # HTML 이메일 템플릿 (이미지 표시되도록 수정)
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; }}
            .container {{ max-width: 800px; margin: auto; padding: 20px; background-color: #ffffff; border-radius: 10px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 14px; font-weight: bold; color: white; padding: 5px 14px; border-radius: 6px; display: inline-block; margin-bottom: 15px; }}
            .news-item {{ display: flex; align-items: flex-start; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #eee; }}
            .news-item img {{ width: 160px; height: 120px; object-fit: cover; border-radius: 8px; margin-right: 20px; }}
            .news-item .text-content {{ flex: 1; }}
            .news-link {{ font-size: 18px; color: #1a0dab; text-decoration: none; font-weight: bold; }}
            .news-link:hover {{ text-decoration: underline; color: #d93025; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2>
                <p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 / 17173</p>
            </div>
    """

    for site_name in ["Gamelook", "游戏陀螺", "17173"]:
        site_list = [a for a in articles if a['site'] == site_name]
        if site_list:
            html_content += f"""
            <div class="site-group">
                <span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>
            """
            for art in site_list:
                html_content += f"""
                <div class="news-item">
                    {'<img src="' + art['img_url'] + '">' if art['img_url'] else ''}
                    <div class="text-content">
                        <a href="{art['url']}" class="news-link" target="_blank">{art['title']}</a>
                    </div>
                </div>
                """
            html_content += "</div>"
            
    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {now_str} 중국 게임 시장 기사 통합 리스트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"\n발송 완료! (총 {len(articles)}개 기사)")
    except Exception as e:
        print(f"\n이메일 발송 에러: {e}")
else:
    print("\n수집된 기사가 없습니다.")

