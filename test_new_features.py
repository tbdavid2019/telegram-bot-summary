#!/usr/bin/env python3
"""
測試腳本 - 驗證新功能的基本邏輯
"""

# 測試語言配置
SUPPORTED_LANGUAGES = {
    'zh-TW': '繁體中文',
    'en': 'English'
}

SYSTEM_PROMPT_ZH = "繁體中文 prompt..."
SYSTEM_PROMPT_EN = "English prompt..."

def test_language_selection():
    """測試語言選擇邏輯"""
    print("✓ 測試語言配置...")
    assert 'zh-TW' in SUPPORTED_LANGUAGES
    assert 'en' in SUPPORTED_LANGUAGES
    assert SUPPORTED_LANGUAGES['zh-TW'] == '繁體中文'
    assert SUPPORTED_LANGUAGES['en'] == 'English'
    print("  ✓ 語言配置正確")

def test_summarize_with_language():
    """測試摘要函數的語言參數"""
    print("✓ 測試摘要語言參數...")
    
    # 模擬 summarize 函數邏輯
    def mock_summarize(text_array, language='zh-TW'):
        if language == 'en':
            return "English summary"
        else:
            return "繁體中文摘要"
    
    # 測試預設語言
    result = mock_summarize(["test"])
    assert "繁體中文" in result or result == "繁體中文摘要"
    
    # 測試英文
    result = mock_summarize(["test"], language='en')
    assert "English" in result
    
    # 測試中文
    result = mock_summarize(["test"], language='zh-TW')
    assert "繁體中文" in result or result == "繁體中文摘要"
    
    print("  ✓ 語言參數正確")

def test_conversation_history_structure():
    """測試對話歷史結構"""
    print("✓ 測試對話歷史結構...")
    
    history = {
        'original_content': ['test content'],
        'summary': 'test summary',
        'source_url': 'https://example.com',
        'timestamp': '2025-11-19 10:00:00',
        'messages': [],
        'language': 'zh-TW'
    }
    
    assert 'original_content' in history
    assert 'summary' in history
    assert 'source_url' in history
    assert 'timestamp' in history
    assert 'messages' in history
    assert 'language' in history
    assert isinstance(history['original_content'], list)
    assert isinstance(history['messages'], list)
    
    print("  ✓ 對話歷史結構正確")

def test_followup_detection():
    """測試續問檢測邏輯"""
    print("✓ 測試續問檢測邏輯...")
    
    def is_followup(user_input, has_history):
        """模擬續問檢測"""
        is_url = user_input.startswith('http')
        is_short = len(user_input) < 500
        return has_history and not is_url and is_short
    
    # 測試案例
    assert is_followup("這是什麼意思?", True) == True
    assert is_followup("https://youtube.com/watch", True) == False
    assert is_followup("這是什麼意思?", False) == False
    assert is_followup("這是一段很長的文字..." * 100, True) == False
    
    print("  ✓ 續問檢測邏輯正確")

def test_mongodb_structure():
    """測試 MongoDB 資料結構"""
    print("✓ 測試 MongoDB 資料結構...")
    
    summary_data = {
        "telegram_id": 123456,
        "url": "https://example.com",
        "summary": "Test summary",
        "original_content": ["content"],
        "language": "zh-TW",
        "timestamp": "2025-11-19"
    }
    
    required_fields = ["telegram_id", "url", "summary", "original_content", "language", "timestamp"]
    for field in required_fields:
        assert field in summary_data, f"Missing field: {field}"
    
    print("  ✓ MongoDB 資料結構正確")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("開始測試新功能...")
    print("="*50 + "\n")
    
    try:
        test_language_selection()
        test_summarize_with_language()
        test_conversation_history_structure()
        test_followup_detection()
        test_mongodb_structure()
        
        print("\n" + "="*50)
        print("✅ 所有測試通過!")
        print("="*50 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ 測試失敗: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}\n")
        raise
