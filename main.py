from flask import Flask
from flask import request, jsonify
from playwright.sync_api import sync_playwright 
from Wappalyzer import Wappalyzer, WebPage
import base64

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
        browser = p.chromium.launch() # or "firefox" or "webkit".
        page = browser.new_page() 
        data = []
        page.on("response", lambda response: 
        data.append({"url": response.url, "status": response.status,
            "response_headers": response.all_headers(),
            "request_headers": response.request.all_headers(),
            "timing": response.request.timing})
        ) 
        page.goto(url, wait_until="networkidle", timeout=90000) 
    
        content = page.content()

        #screenshot
        screenshot_bytes = page.screenshot(full_page=True)
    
        page.context.close() 
        browser.close()
        return jsonify(status = "success", content = content, data = data, screenshot= base64.b64encode(screenshot_bytes).decode()), 200

@app.route('/wappalyzer', methods = ['POST'])
def wappalyzer():
    url = request.json.get('url')
    if(url == None):
        return jsonify(status = 'error', message= 'url required'), 500
    
    webpage = WebPage.new_from_url(url)
    wappalyzer = Wappalyzer.latest()
    data = wappalyzer.analyze_with_versions_and_categories(webpage)
    return jsonify(status = "success", data = data), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0")