# 代码实现了请求 HTML、CSS 和 JS 文件，并将它们内联到 HTML 文件中的功能
# 虽然没有直接涉及浏览器的渲染流程，但为后续在浏览器中渲染提供了整合后的 HTML 文件
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64

# Step 1: 下载网页 HTML 内容
url = "https://www.gamer520.com/"
response = requests.get(url)
html_content = response.text

# Step 2: 使用 BeautifulSoup 解析 HTML 内容
soup = BeautifulSoup(html_content, "html.parser")

# Step 3: 下载并内联所有 CSS 文件
css_files = []
for link in soup.find_all('link', {'rel': 'stylesheet'}):
    css_url = link.get('href')
    if css_url:
        full_css_url = urljoin(url, css_url)
        css_response = requests.get(full_css_url)
        if css_response.status_code == 200:
            css_files.append(css_response.text)
            # 替换 link 标签为内联样式
            style_tag = soup.new_tag("style")
            style_tag.string = css_response.text
            link.insert_before(style_tag)
            link.decompose()  # 移除原来的 <link> 标签

# Step 4: 下载并内联所有 JS 文件
js_files = []
for script in soup.find_all('script', {'src': True}):
    js_url = script.get('src')
    if js_url:
        full_js_url = urljoin(url, js_url)
        js_response = requests.get(full_js_url)
        if js_response.status_code == 200:
            js_files.append(js_response.text)
            # 替换 script 标签为内联脚本
            script_tag = soup.new_tag("script")
            script_tag.string = js_response.text
            script.insert_before(script_tag)
            script.decompose()  # 移除原来的 <script> 标签

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
    except requests.exceptions.RequestException:
        return None, None
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
