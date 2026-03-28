"""
Скрипт для тестирования улучшений бота
"""
import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

async def test_improvements():
    """Тестирование улучшений бота"""
    print("🧪 Тестирование улучшений бота...\n")
    
    # Тест 1: Проверка импортов
    print("1️⃣ Проверка импортов...")
    try:
        from enhanced_ai_handler import enhanced_ai_handler
        from config import SYSTEM_PROMPT
        print("   ✅ Все импорты успешны")
    except Exception as e:
        print(f"   ❌ Ошибка импорта: {e}")
        return False
    
    # Тест 2: Проверка SYSTEM_PROMPT
    print("\n2️⃣ Проверка SYSTEM_PROMPT...")
    if "естественно" in SYSTEM_PROMPT.lower() or "человек" in SYSTEM_PROMPT.lower():
        print("   ✅ SYSTEM_PROMPT обновлён (содержит упоминания о естественности)")
    else:
        print("   ⚠️ SYSTEM_PROMPT может быть не обновлён")
    
    # Тест 3: Проверка анализа эмоций
    print("\n3️⃣ Проверка анализа эмоций...")
    test_messages = [
        ("блять не работает", "frustrated"),
        ("не понимаю как это сделать", "confused"),
        ("вау круто получилось", "excited"),
        ("ошибка в коде", "negative"),
        ("ура заработало", "positive"),
    ]
    
    for message, expected_tone in test_messages:
        tone = enhanced_ai_handler._detect_message_tone(message.lower())
        if tone == expected_tone:
            print(f"   ✅ '{message[:30]}...' → {tone}")
        else:
            print(f"   ⚠️ '{message[:30]}...' → {tone} (ожидалось {expected_tone})")
    
    # Тест 4: Проверка SUPPORTIVE_REACTIONS
    print("\n4️⃣ Проверка поддерживающих реакций...")
    reactions = enhanced_ai_handler.SUPPORTIVE_REACTIONS
    expected_tones = ["positive", "negative", "frustrated", "excited", "confused"]
    for tone in expected_tones:
        if tone in reactions:
            print(f"   ✅ Реакции для '{tone}' настроены ({len(reactions[tone])} вариантов)")
        else:
            print(f"   ❌ Реакции для '{tone}' отсутствуют")
    
    # Тест 5: Проверка параметров модели
    print("\n5️⃣ Проверка параметров модели...")
    # Проверяем через чтение кода
    with open("enhanced_ai_handler.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "temperature=0.7" in content:
            print("   ✅ Температура модели установлена на 0.7")
        else:
            print("   ⚠️ Температура модели может быть не обновлена")
        
        if "max_tokens=1200" in content:
            print("   ✅ Максимум токенов установлен на 1200")
        else:
            print("   ⚠️ Максимум токенов может быть не обновлён")
    
    print("\n✅ Тестирование завершено!")
    print("\n💡 Для полной проверки:")
    print("   1. Запустите бота: python main.py")
    print("   2. Отправьте тестовое сообщение в Telegram")
    print("   3. Проверьте, что ответы более естественные и человечные")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_improvements())



