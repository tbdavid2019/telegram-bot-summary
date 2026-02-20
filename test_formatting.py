import markdown
from bs4 import BeautifulSoup
import re

def format_for_telegram(markdown_text):
    if not markdown_text:
        return markdown_text
        
    try:
        html = markdown.markdown(markdown_text, extensions=['nl2br'])
        soup = BeautifulSoup(html, 'html.parser')
        
        for v in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            new_text = f"<b>{v.get_text()}</b>\n\n"
            v.replace_with(new_text)
            
        for li in soup.find_all('li'):
            li.replace_with(f"• {li.get_text()}\n")
            
        for ul in soup.find_all(['ul', 'ol']):
            ul.unwrap()
            
        for p in soup.find_all('p'):
            p.replace_with(f"{p.get_text()}\n\n")
            
        for br in soup.find_all('br'):
            br.replace_with("\n")
            
        for strong in soup.find_all('strong'):
            strong.name = 'b'
            
        for em in soup.find_all('em'):
            em.name = 'i'
            
        final_text = str(soup)
        final_text = re.sub(r'\n{3,}', '\n\n', final_text)
        import html as html_lib
        final_text = html_lib.unescape(final_text)
        
        return final_text.strip()
    except Exception as e:
        print(f"Error: {e}")
        return markdown_text

test_input = """
# 這是大標題
## 這是副標題
這裡是一段普通文字，裡面有 **粗體** 和 *斜體*。
還有一行換行測試
看看他會不會連在一起。

### 重點清單
- 第一點
- 第二點
- 第三點

[這是一個連結](https://example.com/)
"""

print("=== 原始 Markdown ===")
print(test_input)
print("\n=== Telegram HTML 輸出 ===")
print(format_for_telegram(test_input))
