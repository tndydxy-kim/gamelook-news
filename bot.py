import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
import re # 정규식 사용을 위한 re 모듈 추가

# 1. 설정값 불러오기 (Github Secrets 사용)
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD")
RECEIVER = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 2. Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_gemini_summary(article_text, article_title):
    """Gemini API를 사용하여 기사 요약 및 제목 번역"""
    if not article_text or len(article_text) < 50:
        return "본문 내용이 충분하지 않아 요약할 수 없습니다.", "번역 실패"
    
    prompt = f"""
    Please perform two tasks based on the following Chinese news article.
    Provide the output in Korean.

    Article Title: "{article_title}"
    Article Content:
    ---
    {article_text[:3000]}
    ---

    TASK 1: Translate the original article title into Korean.
    TASK 2: Summarize the key points of the article content in exactly 3 concise bullet points in Korean.

    Your response should be structured as follows, and nothing else:
    [Korean Title]: <Translated Korean title here>
    [Summary]:
    - <Summary point 1>
    - <Summary point 2>
    - <Summary point 3>
    """
    try:
        response = model.generate_content(prompt)
        
        # 응답 텍스트에서 한국어 제목과 요약 분리
        title_match = re.search(r"\[Korean Title\]: (.*)", response.text)
        summary_match = re.search(r"\[Summary\]:([\s\S]*)", response.text)

        korean_title = title_match.group(1).strip() if title_match else "제목 번역 실패"
        summary = summary_match.group(1).strip() if summary_match else "요약 생성 실패"
        
        return summary, korean_title
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return "Gemini API 호출 중 오류가 발생했습니다.", "번역 실패"

def fetch_article_content(url, site_name):
    """기사 URL에서 본문 텍스트를 추출"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')

        # 사이트별 본문 컨테이너 선택자 (필요시 수정)
        if site_name == "Gamelook":
            content_area = soup.find('div', class_='content-text')
        elif site_name == "游戏陀螺":
            # 중요: '游戏陀螺' 사이트의 실제 기사 본문 클래스명으로 변경해야 합니다.
            content_area = soup.find('div', class_='content-text') 
        else:
            content_area = soup.find('article') or soup.find('div', {'role': 'main'})

        return content_area.get_text(strip=True, separator='\n') if content_area else ""
    except Exception as e:
        print(f"본문 수집 에러 ({url}): {e}")
        return ""

def is_recent_article(context_text):
    """최신 기사(오늘, 어제)인지 판별"""
    now = datetime.now()
    patterns = [
        now.strftime('%m-%d'), 
        (now - timedelta(days=1)).strftime('%m-%d'),
        "刚刚", "小时前", "今天", "昨天"
    ]
    return any(p in context_text for p in patterns)

def fetch_articles_and_summarize():
    all_articles = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 수집 중: {site['url']}")
            res = requests.get(site['url'], headers=headers, timeout=30)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            
            items = soup.find_all(['div', 'li', 'article', 'tr'], limit=50)
            found_count = 0

            for item in items:
                link_tag = item.find('a', href=True)
                if not link_tag: continue
                
                title = link_tag.get_text(strip=True)
                url = link_tag['href']
                
                if len(title) < 15: continue
                
                context_text = item.get_text()
                if is_recent_article(context_text):
                    if not url.startswith('http'):
                        url = requests.compat.urljoin(site['url'], url)
                    
                    if not any(x['url'] == url for x in all_articles):
                        print(f"  -> 기사 발견: {title}")
                        content = fetch_article_content(url, site['name'])
                        
                        summary, korean_title = get_gemini_summary(content, title)
                        print(f"    - 요약 및 번역 완료: {korean_title}")

                        all_articles.append({
                            "site": site['name'],
                            "title": title,
                            "korean_title": korean_title,
                            "url": url,
                            "summary": summary,
                            "color": site['color']
                        })
                        found_count += 1
                
                if found_count >= 5: # 실제 운영 시 이 숫자를 25 또는 원하는 만큼 늘리세요.
                    break 
                    
            print(f"-> {site['name']}: {found_count}개 수집 성공")
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
            
    return all_articles

# --- 메일 본문 구성 및 발송 ---
articles = fetch_articles_and_summarize()
if articles:
    now_str = datetime.now().strftime('%m/%d')
    html_content = f"""
    <html><head><style>
        body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; }} .container {{ max-width: 800px; margin: auto; padding: 20px; }}
        .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
        .site-group {{ margin-bottom: 35px; }}
        .site-tag {{ font-size: 14px; font-weight: bold; color: white; padding: 5px 14px; border-radius: 6px; display: inline-block; margin-bottom: 15px; }}
        .news-item {{ margin-bottom: 25px; padding-left: 5px; border-bottom: 1px solid #eee; padding-bottom: 15px; }}
        .news-link-original {{ font-size: 18px; color: #1a0dab; text-decoration: none; font-weight: bold; }}
        .news-link-original:hover {{ text-decoration: underline; }}
        .news-title-korean {{ font-size: 14px; color: #5f6368; margin-top: 5px; font-weight: 500;}}
        .summary {{ margin-top: 12px; font-size: 14px; color: #3c4043; background-color:#f8f9fa; border-left: 4px solid #d6e2ff; padding: 10px 15px; white-space: pre-wrap; line-height: 1.7;}}
    </style></head><body><div class="container">
    <div class="header">
        <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2>
        <p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 (Gemini 요약 포함)</p>
    </div>
    """

    for site_name in ["Gamelook", "游戏陀螺"]:
        site_list = [a for a in articles if a['site'] == site_name]
        if site_list:
            html_content += f"""
            <div class="site-group">
                <span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>
            """
            for art in site_list:
                html_content += f"""
                <div class="news-item">
                    <a href="{art['url']}" class="news-link-original" target="_blank">{art['title']}</a>
                    <div class="news-title-korean">{art['korean_title']}</div>
                    <div class="summary">{art['summary']}</div>
                </div>
                """
            html_content += "</div>"
    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {now_str} 중국 게임 시장 요약 리포트"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"발송 완료! (총 {len(articles)}개 기사)")
    except Exception as e:
        print(f"이메일 발송 에러: {e}")

else:
    print("수집된 기사가 없습니다. 날짜 조건을 확인하세요.")
