import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
import re

# 1. 설정값 불러오기
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD")
RECEIVER = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 2. Gemini API 설정
if not GEMINI_API_KEY:
    print("에러: GEMINI_API_KEY가 설정되지 않았습니다.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_gemini_summary(article_text, article_title):
    if not article_text or len(article_text) < 50:
        return "요약 실패: 기사 본문을 가져올 수 없었습니다.", "번역 실패: 원문 없음"
    
    prompt = f"""
    Please perform two tasks based on the following Chinese news article.
    Provide the output in Korean.
    Article Title: "{article_title}"
    Article Content: --- {article_text[:3000]} ---
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
        title_match = re.search(r"\[Korean Title\]: (.*)", response.text)
        summary_match = re.search(r"\[Summary\]:([\s\S]*)", response.text)
        korean_title = title_match.group(1).strip() if title_match else "제목 번역 실패 (응답 형식 오류)"
        summary = summary_match.group(1).strip() if summary_match else "요약 생성 실패 (응답 형식 오류)"
        return summary, korean_title
    except Exception as e:
        # 429 에러를 명확히 구분하여 사용자에게 알려줌
        if "429" in str(e):
            print(f"!!! Gemini API 사용량 초과(429): {e}")
            return "요약 실패 (API 하루 사용량 초과)", "번역 실패 (API 사용량 초과)"
        else:
            print(f"!!! Gemini API 호출 오류: {e}")
            return "Gemini API 호출 중 오류 발생", "번역 실패 (API 에러)"

def fetch_article_content(url, site_name):
    """기사 URL에서 본문 텍스트를 추출 (선택자 수정)"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    print(f"    - 본문 수집 시도: {url}")
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        content_area = None
        if site_name == "Gamelook":
            content_area = soup.find('div', class_='wx_text_underline')
        elif site_name == "游戏陀螺":
            content_area = soup.find('div', class_='content-text')
        
        if content_area:
            content_text = content_area.get_text(strip=True, separator='\n')
            print(f"    - ✅ 본문 수집 성공! (길이: {len(content_text)})")
            return content_text
        else:
            print(f"    - ❌ 본문 수집 실패: '{site_name}' 사이트에서 본문 영역을 찾을 수 없습니다.")
            return ""
    except Exception as e:
        print(f"    - ❌ 본문 수집 에러 ({url}): {e}")
        return ""

def is_recent_article(context_text):
    now = datetime.now()
    patterns = [now.strftime('%m-%d'), (now - timedelta(days=1)).strftime('%m-%d'), "刚刚", "小时前", "今天", "昨天"]
    return any(p in context_text for p in patterns)

def fetch_articles_and_summarize():
    all_articles = []
    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"}
    ]
    for site in sites:
        try:
            print(f"\n{site['name']} 수집 중: {site['url']}")
            res = requests.get(site['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 游戏陀螺 사이트의 목록 구조에 더 최적화된 탐색
            if site['name'] == '游戏陀螺':
                items = soup.select('div.news-list-item, li.news-list-item')
            else:
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
                        base_url = "https://www.youxituoluo.com" if site['name'] == "游戏陀螺" else site['url']
                        url = requests.compat.urljoin(base_url, url)
                    if not any(x['url'] == url for x in all_articles):
                        print(f"  -> 기사 발견: {title}")
                        content = fetch_article_content(url, site['name'])
                        summary, korean_title = get_gemini_summary(content, title)
                        all_articles.append({
                            "site": site['name'], "title": title, "korean_title": korean_title,
                            "url": url, "summary": summary, "color": site['color']
                        })
                        found_count += 1
                if found_count >= 5: break
            print(f"-> {site['name']}: {found_count}개 수집 성공")
        except Exception as e:
            print(f"{site['name']} 에러: {e}")
    return all_articles

# (이하 메일 발송 코드는 수정 없음)
articles = fetch_articles_and_summarize()
if articles:
    now_str = datetime.now().strftime('%m/%d')
    html_content = f"""
    <html><head><style>
        body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; }} .container {{ max-width: 800px; margin: auto; padding: 20px; }}
        .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }} .site-group {{ margin-bottom: 35px; }}
        .site-tag {{ font-size: 14px; font-weight: bold; color: white; padding: 5px 14px; border-radius: 6px; display: inline-block; margin-bottom: 15px; }}
        .news-item {{ margin-bottom: 25px; padding-left: 5px; border-bottom: 1px solid #eee; padding-bottom: 15px; }}
        .news-link-original {{ font-size: 18px; color: #1a0dab; text-decoration: none; font-weight: bold; }}
        .news-link-original:hover {{ text-decoration: underline; }} .news-title-korean {{ font-size: 14px; color: #5f6368; margin-top: 5px; font-weight: 500;}}
        .summary {{ margin-top: 12px; font-size: 14px; color: #3c4043; background-color:#f8f9fa; border-left: 4px solid #d6e2ff; padding: 10px 15px; white-space: pre-wrap; line-height: 1.7;}}
    </style></head><body><div class="container"><div class="header">
        <h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2>
        <p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 (Gemini 요약 포함)</p>
    </div>
    """
    for site_name in ["Gamelook", "游戏陀螺"]:
        site_list = [a for a in articles if a['site'] == site_name]
        if site_list:
            html_content += f"""<div class="site-group"><span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>"""
            for art in site_list:
                html_content += f"""
                <div class="news-item">
                    <a href="{art['url']}" class="news-link-original" target="_blank">{art['title']}</a>
                    <div class="news-title-korean">{art['korean_title']}</div>
                    <div class="summary">{art['summary']}</div>
                </div>"""
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
        print(f"\n발송 완료! (총 {len(articles)}개 기사)")
    except Exception as e:
        print(f"\n이메일 발송 에러: {e}")
else:
    print("\n수집된 기사가 없습니다. 날짜 조건을 확인하세요.")

