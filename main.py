from flask import Flask
from flask import request, jsonify
from playwright.sync_api import sync_playwright 
from playwright_stealth import stealth_sync
from playwright.sync_api import sync_playwright
from Wappalyzer import Wappalyzer, WebPage
from bs4 import BeautifulSoup
import sys
import base64
import time

app = Flask(__name__)

@app.route('/debug', methods = ['POST'])
def debug():
    url = request.json.get('url')
    if(url == None):
        return jsonify(status = 'error', message= 'url required'), 500
    browser = request.json.get('browser')
    if(browser == None):
        return jsonify(status = 'error', message= 'browser required'), 500
    
    with sync_playwright() as p: 
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized"
                # <<< BỎ --disable-http2, --disable-quic, và các disable-features lạ
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            java_script_enabled=True,
            bypass_csp=True
        )

        page = context.new_page() 
        stealth_sync(page)
        data = []
        page.on("response", lambda response: 
        data.append({
            "url": response.url, 
            "status": response.status,
            "response_headers": response.all_headers(),
            "request_headers": response.request.all_headers(),
            "timing": response.request.timing})
        )
        console = []
        page.on("console", lambda msg: console.append({
            "type": msg.type, 
            "text": msg.text,
            "location": msg.location
        }))
        
        try:
            # 1. Goto chỉ đợi DOMContentLoaded (nhanh nhất)
            page.goto(url, timeout=90000, wait_until="domcontentloaded")

            # 2. ĐỢI SELECTOR CHÍNH CỦA TRANG (đây là "bí kíp" không bao giờ timeout)
            # Bạn chỉ cần thay selector phù hợp với từng trang
            selectors_to_wait = [
                "body",                                   # luôn có
                "title",                                  # luôn có
                "header", "nav", "main",                  # phổ biến
                "[data-testid]", "[id]", "[class]"       # fallback
            ]

            waited = False
            for selector in selectors_to_wait:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    waited = True
                    break
                except:
                    continue

            # 3. Nếu không đợi được selector → đợi cố định 5-8 giây (đủ cho JS render)
            if not waited:
                page.wait_for_timeout(8000)

            # 4. Cuối cùng mới lấy content + screenshot
            content = page.content()
            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            return jsonify({
                "status": "success",
                "url": url,
                "title": page.title(),
                "content_length": len(content),
                "screenshot": screenshot_b64,
                "content": content, 
                "data": data, 
                "console": console
            }), 200

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }), 500

        finally:
            try:
                context.close()
                browser.close()
            except:
                pass

@app.route('/wappalyzer', methods = ['POST'])
def wappalyzer():
    url = request.json.get('url')
    if(url == None):
        return jsonify(status = 'error', message= 'url required'), 500
    
    seo_info = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
                viewport={"width": 1280, "height": 800},
                bypass_csp=True
                # extra_http_headers={"Accept-Language": "vi-VN,vi;q=0.9"}  # nếu cần
            )
            page = context.new_page()

            # === Đo thời gian phản hồi ===
            start_time = time.perf_counter()

            # Navigate và chờ load hoàn chỉnh
            response = page.goto(url, wait_until="networkidle", timeout=45000)
            
            if response:
                response_start_time = time.perf_counter()
                response_time_ms = (response_start_time - start_time) * 1000  # ms
            else:
                response_time_ms = None

            time.sleep(3)  # chờ thêm JS chạy (tùy site)
            total_load_time_ms = (time.perf_counter() - start_time) * 1000

            html = page.content()

            # Lấy headers từ response chính (đây là cái bạn cần)
            response_headers = dict(response.headers)  # hoặc response.all_headers()

            seo_info["response_time_ms"] = round(response_time_ms, 2) if response_time_ms else "N/A"
            seo_info["total_load_time_ms"] = round(total_load_time_ms, 2)

            # === Phần mới: Extract title & meta bằng BeautifulSoup ===
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_tag = soup.title
            seo_info["title"] = title_tag.string.strip() if title_tag and title_tag.string else "Not found"

            # Meta description
            desc_tag = soup.find("meta", attrs={"name": "description"})
            seo_info["description"] = desc_tag["content"].strip() if desc_tag and "content" in desc_tag.attrs else "Not found"

            # Bonus: Open Graph (og:title, og:description) - rất phổ biến hiện nay
            og_title = soup.find("meta", property="og:title")
            seo_info["og:title"] = og_title["content"].strip() if og_title and "content" in og_title.attrs else None

            og_desc = soup.find("meta", property="og:description")
            seo_info["og:description"] = og_desc["content"].strip() if og_desc and "content" in og_desc.attrs else None

            # Tạo WebPage thủ công (không dùng new_from_url)
            webpage = WebPage(
                url=url,
                html=html,
                headers=response_headers,          # ← đúng chỗ này
                # cookies=page.context.cookies(),  # nếu muốn thêm (tùy chọn)
            )

            wappalyzer = Wappalyzer.latest()
            technologies = wappalyzer.analyze_with_versions_and_categories(webpage)
            browser.close()
            for tech, info in technologies.items():
                version = ", ".join(info.get("versions", []))
                categories = ", ".join(info.get("categories", []))
                print(f"• {tech:<25}  v{version:<8}  ({categories})")
            return jsonify(status = "success", data = technologies, seo = seo_info), 200
    except Exception as e:
        return jsonify(status = 'error', message = e.message), 500

if __name__ == "__main__":
<<<<<<< HEAD
    app.run(host="0.0.0.0", port=5002, debug=True)
=======
    app.run(host="0.0.0.0", port=6000, debug=True)
>>>>>>> 02711d3784eca01873ac61d304589d5f26c8ad4e
