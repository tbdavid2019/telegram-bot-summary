import re
import markdown

text = """
### ⓺ 【關鍵標籤 Hashtags】
#AI #機器學習 #DeepLearning #未來趨勢

Some other text. #inlineTag
#Header without space (LLM shouldn't do this but we'll see)
# This is a header
"""

# Match a '#' that is not preceded by a non-space, and is followed by a non-space and non-#.
escaped = re.sub(r'(?<!\S)#(?=[^\s#])', r'\#', text)
print("--- ESCAPED ---")
print(escaped)
print("--- HTML ---")
print(markdown.markdown(escaped))
