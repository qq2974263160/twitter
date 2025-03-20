from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from urllib.parse import urljoin  # 新增导入
import base64  # 新增导入
import requests

# 设置 ChromeDriver 的路径
# 请将 'path/to/chromedriver' 替换为实际的 ChromeDriver 路径
service = Service('C:/Users/29742/AppData/Local/Google/Chrome/Application/chrome.exe')
driver = webdriver.Chrome(service=service)

# 打开网页
url = "https://www.huggingface.co"  # 替换为实际的网页 URL
driver.get(url)

# 等待页面加载完成（可根据实际情况调整等待时间）
driver.implicitly_wait(10)

# 获取完整的 HTML 内容
html_content = driver.page_source

# 使用 BeautifulSoup 解析 HTML 内容
soup = BeautifulSoup(html_content, "html.parser")

# Step 3: 下载并内联所有 CSS 文件
css_files = []
for link in soup.find_all('link', {'rel': 'stylesheet'}):
    css_url = link.get('href')
    if css_url:
        full_css_url = urljoin(url, css_url)
        try:
            css_response = requests.get(full_css_url)
            if css_response.status_code == 200:
                css_files.append(css_response.text)
                # 替换 link 标签为内联样式
                style_tag = soup.new_tag("style")
                style_tag.string = css_response.text
                link.insert_before(style_tag)
                link.decompose()  # 移除原来的 <link> 标签
        except requests.exceptions.RequestException as e:
            print(f"请求 CSS 文件 {full_css_url} 时出错: {e}")

# Step 4: 下载并内联所有 JS 文件
js_files = []
for script in soup.find_all('script', {'src': True}):
    js_url = script.get('src')
    if js_url:
        full_js_url = urljoin(url, js_url)
        try:
            js_response = requests.get(full_js_url)
            if js_response.status_code == 200:
                js_files.append(js_response.text)
                # 替换 script 标签为内联脚本
                script_tag = soup.new_tag("script")
                script_tag.string = js_response.text
                script.insert_before(script_tag)
                script.decompose()  # 移除原来的 <script> 标签
        except requests.exceptions.RequestException as e:
            print(f"请求 JS 文件 {full_js_url} 时出错: {e}")

# Step 5: 下载并内联所有图片和字体资源
def convert_to_base64(resource_url):
    try:
        response = requests.get(resource_url)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type')
            if content_type:
                # 提取文件类型
                file_type = content_type.split('/')[-1]
                return base64.b64encode(response.content).decode('utf-8'), file_type
    except requests.exceptions.RequestException as e:
        print(f"请求资源 {resource_url} 时出错: {e}")
    return None, None

# 处理所有的图片资源
for img_tag in soup.find_all('img', {'src': True}):
    img_url = img_tag.get('src')
    if img_url:
        full_img_url = urljoin(url, img_url)
        img_base64, img_type = convert_to_base64(full_img_url)
        if img_base64 and img_type:
            img_tag['src'] = f"data:image/{img_type};base64,{img_base64}"

# 处理所有的字体资源
for font_tag in soup.find_all('link', {'rel': 'stylesheet', 'type': 'font/woff2'}):
    font_url = font_tag.get('href')
    if font_url:
        full_font_url = urljoin(url, font_url)
        font_base64, font_type = convert_to_base64(full_font_url)
        if font_base64 and font_type:
            font_tag['href'] = f"data:font/{font_type};base64,{font_base64}"

# Step 6: 保存合并后的 HTML 文件
output_file = "huggingface_complete_page.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(soup.prettify())

print(f"完整的 HTML 文件已保存为: {output_file}")

# 关闭浏览器
driver.quit()