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
    prompt = f'Translate the title of the following Chinese article into Korean and summarize the content in 3 bullet points in Korean.\n\nTitle: "{article_title}"\nContent: "{article_text[:3000]}"\n\nFormat your response EXACTLY as follows:\n[Korean Title]: <Your Korean translation>\n[Summary]:\n- <Point 1>\n- <Point 2>\n- <Point 3>'
    try:
        response = model.generate_content(prompt, request_options={'timeout': 100})
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
    """기사 URL에서 본문 텍스트 추출 (가장 안정적인 선택자로 수정)"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        content_area = None
        if site_name == "Gamelook":
            content_area = soup.find('div', class_='content-text')
        elif site_name == "游戏陀螺":
            content_area = soup.find('div', class_='content-text')
        
        if content_area:
            return content_area.get_text(strip=True, separator='\n')
        else:
            print(f"    - ❌ '{site_name}' 본문 영역(<div class='content-text'>)을 찾지 못함. URL: {url}")
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
        
        # 목록 페이지에서 날짜가 포함된 모든 잠재적 기사 아이템을 찾음
        items = [tag for tag in soup.find_all(['div', 'li', 'article']) if len(tag.get_text(strip=True)) > 20]
        found_count = 0
        for item in items:
            if is_recent_article(item.get_text()):
                link_tag = item.find('a', href=True)
                if link_tag and len(link_tag.get_text(strip=True)) > 15:
                    title = link_tag.get_text(strip=True)
                    url = link_tag['href']
                    if not url.startswith('http'):
                        base_url = "https://www.youxituoluo.com" if site['name'] == "游戏陀螺" else site['url']
                        url = requests.compat.urljoin(base_url, url)
                    if not any(x['url'] == url for x in initial_articles):
                        initial_articles.append({"site": site['name'], "title": title, "url": url, "color": site['color']})
                        found_count += 1
        print(f"   {found_count}개의 최신 기사 링크를 찾았습니다.")
    except Exception as e:
        print(f"'{site['name']}' 사이트 스캔 중 오류: {e}")

print(f"\n--- 2단계: 총 {len(initial_articles)}개 기사의 본문을 수집하고 요약합니다. ---")
final_articles = []
for article in initial_articles:
    print(f"-> 처리 중: {article['title'][:30]}...")
    content = fetch_article_content(article['url'], article['site'])
    summary, korean_title = get_gemini_summary(content, article['title'])
    
    # 요약/번역에 실패하더라도 원본 정보는 유지
    article['summary'] = summary
    article['korean_title'] = korean_title
    final_articles.append(article)
    print(f"   '{korean_title}' 처리 완료.")

# --- 4. 이메일 발송 ---
if final_articles:
    now_str = datetime.now().strftime('%m/%d')
    # (이하 메일 본문 구성 및 발송 코드는 수정 없음)
    html_content = f"""<html><head><style>body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; }} .container {{ max-width: 800px; margin: auto; padding: 20px; }} .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }} .site-group {{ margin-bottom: 35px; }} .site-tag {{ font-size: 14px; font-weight: bold; color: white; padding: 5px 14px; border-radius: 6px; display: inline-block; margin-bottom: 15px; }} .news-item {{ margin-bottom: 25px; padding-left: 5px; border-bottom: 1px solid #eee; padding-bottom: 15px; }} .news-link-original {{ font-size: 18px; color: #1a0dab; text-decoration: none; font-weight: bold; }} .news-link-original:hover {{ text-decoration: underline; }} .news-title-korean {{ font-size: 14px; color: #5f6368; margin-top: 5px; font-weight: 500;}} .summary {{ margin-top: 12px; font-size: 14px; color: #3c4043; background-color:#f8f9fa; border-left: 4px solid #d6e2ff; padding: 10px 15px; white-space: pre-wrap; line-height: 1.7;}}</style></head><body><div class="container"><div class="header"><h2 style="margin:0;">📅 중국 게임 뉴스 통합 리포트 ({now_str})</h2><p style="margin:5px 0 0; color:#666;">수집 기준: Gamelook / 游戏陀螺 (Gemini 요약 포함)</p></div>"""
    for site_name in ["Gamelook", "游戏陀螺"]:
        site_list = [a for a in final_articles if a['site'] == site_name]
        if site_list:
            html_content += f"""<div class="site-group"><span class="site-tag" style="background-color: {site_list[0]['color']};">{site_name}</span>"""
            for art in site_list:
                html_content += f"""<div class="news-item"><a href="{art['url']}" class="news-link-original" target="_blank">{art['title']}</a><div class="news-title-korean">{art['korean_title']}</div><div class="summary">{art['summary']}</div></div>"""
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
        print(f"\n발송 완료! (총 {len(final_articles)}개 기사)")
    except Exception as e:
        print(f"\n이메일 발송 에러: {e}")
else:
    print("\n수집된 기사가 없습니다.")
