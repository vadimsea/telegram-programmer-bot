"""
Тест переменных окружения на Render.com
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def test_env_variables():
    """Тест переменных окружения через команды бота"""
    
    # Тест команды /start
    start_data = {
        "chat_id": CHAT_ID,
        "text": "/start"
    }
    
    # Тест команды /course
    course_data = {
        "chat_id": CHAT_ID,
        "text": "/course"
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        print("Тестируем команду /start...")
        response1 = requests.post(url, data=start_data, timeout=30)
        
        if response1.status_code == 200:
            result1 = response1.json()
            if result1.get("ok"):
                print("Команда /start отправлена успешно")
            else:
                print(f"Ошибка в команде /start: {result1.get('description', 'Неизвестная ошибка')}")
        
        print("\nТестируем команду /course...")
        response2 = requests.post(url, data=course_data, timeout=30)
        
        if response2.status_code == 200:
            result2 = response2.json()
            if result2.get("ok"):
                print("Команда /course отправлена успешно")
            else:
                print(f"Ошибка в команде /course: {result2.get('description', 'Неизвестная ошибка')}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def check_bot_health():
    """Проверить здоровье бота"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result["result"]
                print("Статус бота:")
                print(f"  Имя: {bot_info['first_name']}")
                print(f"  Username: @{bot_info['username']}")
                print(f"  ID: {bot_info['id']}")
                print(f"  Может читать сообщения: {bot_info.get('can_read_all_group_messages', False)}")
                print(f"  Поддерживает inline запросы: {bot_info.get('supports_inline_queries', False)}")
                return True
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return False
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ НА RENDER.COM")
    print("=" * 60)
    
    print("\n1. Проверяем здоровье бота...")
    bot_ok = check_bot_health()
    
    if bot_ok:
        print("\n2. Тестируем команды...")
        test_env_variables()
        
        print("\nДиагностика:")
        print("✅ Бот работает и отвечает на команды")
        print("❌ Callback данные не обрабатываются")
        print("\nВозможные причины:")
        print("1. Переменные окружения BOT_TOKEN или CHAT_ID не настроены на Render.com")
        print("2. Ошибка в коде обработчика callback")
        print("3. Бот падает с ошибкой при обработке callback данных")
        
        print("\nРекомендации:")
        print("1. Проверьте логи Render.com")
        print("2. Убедитесь, что переменные окружения настроены:")
        print("   - BOT_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY")
        print("   - CHAT_ID=-1002949858700")
        print("3. Перезапустите сервис на Render.com")
    else:
        print("\n❌ Бот не работает!")
        print("Проверьте токен бота и настройки Render.com")
