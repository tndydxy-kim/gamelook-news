import os
import smtplib
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 1. 设置
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
RECEIVER = os.environ["RECEIVER_EMAIL"]

def fetch_articles():
    all_articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 日期判定标准
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    target_dates = [now.strftime('%m-%d'), yesterday.strftime('%m-%d'), "03-03", "03-04", "今天", "昨天"]

    sites = [
        {"name": "Gamelook", "url": "http://www.gamelook.com.cn/", "color": "#0056b3"},
        {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/news", "color": "#e67e22"},
        {"name": "17173", "url": "https://news.17173.com/?spm_id=www__17173.index.mod_wwwsitenav.0", "color": "#27ae60"}
    ]

    for site in sites:
        try:
            print(f"{site['name']} 正在抓取...")
            res = requests.get(site['url'], headers=headers, timeout=30)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            
            found_count = 0

            # --- 17173 专项强化逻辑 ---
            if site['name'] == "17173":
                # 扫描所有新闻容器 li
                items = soup.find_all(['li', 'div'], class_=lambda x: x and ('item' in x or 'news' in x or 'tit' in x))
                for item in items:
                    a = item.find('a', href=True)
                    if not a: continue
                    
                    title = a.get_text(strip=True)
                    url = a['href']
                    # 17173 的日期可能在文本里，也可能在 data-time 属性里
                    full_text = item.get_text() + str(item.get('data-time', ''))
                    
                    if len(title) >= 12 and any(d in full_text for d in target_dates):
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1

            # --- Gamelook & 游戏陀螺 恢复原始稳定逻辑 ---
            else:
                links = soup.find_all('a', href=True)
                for a in links:
                    title = a.get_text(strip=True)
                    url = a['href']
                    # 检查父容器是否有日期
                    parent_text = a.parent.get_text() if a.parent else ""
                    
                    if len(title) >= 14 and any(d in (title + parent_text) for d in target_dates):
                        if not url.startswith('http'):
                            url = requests.compat.urljoin(site['url'], url)
                        
                        if not any(x['url'] == url for x in all_articles):
                            all_articles.append({
                                "site": site['name'], "title": title, "url": url, "color": site['color']
                            })
                            found_count += 1
            
            print(f"-> {site['name']}: 成功抓取 {found_count} 条")
        except Exception as e:
            print(f"{site['name']} 出错: {e}")
            
    return all_articles

# 邮件生成
articles = fetch_articles()

if articles:
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 750px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ border-bottom: 3px solid #333; padding-bottom: 10px; margin-bottom: 25px; }}
            .site-group {{ margin-bottom: 35px; }}
            .site-tag {{ font-size: 13px; font-weight: bold; color: white; padding: 4px 12px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
            .news-item {{ margin-bottom: 10px; border-bottom: 1px dotted #ddd; padding-bottom: 5px; }}
            .news-link {{ font-size: 16px; color: #1a0dab; text-decoration: none; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">📅 中国游戏市场资讯 (3/3 ~ 3/4)</h2>
                <p style="margin:5px 0 0; color:#666;">自动汇总: Gamelook / 游戏陀螺 / 17173 (增强版)</p>
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
                    • <a href="{art['url']}" class="news-link">{art['title']}</a>
                </div>
                """
            html_content += "</div>"

    html_content += "</div></body></html>"

    msg = EmailMessage()
    msg['Subject'] = f"[News] {datetime.now().strftime('%m/%d')} 中国游戏市场资讯汇总"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
    print(f"发送成功! 总计 {len(articles)} 条资讯")
