"""
Тест работы бота через API
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def test_bot_commands():
    """Тест команд бота"""
    
    # Тест команды /start
    start_text = "/start"
    
    data = {
        "chat_id": CHAT_ID,
        "text": start_text
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                message_id = result["result"]["message_id"]
                print(f"Команда /start отправлена! ID: {message_id}")
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

def test_course_command():
    """Тест команды /course"""
    
    course_text = "/course"
    
    data = {
        "chat_id": CHAT_ID,
        "text": course_text
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                message_id = result["result"]["message_id"]
                print(f"Команда /course отправлена! ID: {message_id}")
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

def check_bot_webhook():
    """Проверить webhook бота"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result["result"]
                print("Webhook информация:")
                print(f"  URL: {webhook_info.get('url', 'Не установлен')}")
                print(f"  Pending updates: {webhook_info.get('pending_update_count', 0)}")
                print(f"  Last error: {webhook_info.get('last_error_message', 'Нет')}")
                return webhook_info
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return None
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ РАБОТЫ БОТА")
    print("=" * 60)
    
    print("\n1. Проверяем webhook...")
    webhook_info = check_bot_webhook()
    
    print("\n2. Тестируем команду /start...")
    test_bot_commands()
    
    print("\n3. Тестируем команду /course...")
    test_course_command()
    
    print("\nИнструкция:")
    print("1. Перейдите в группу @learncoding_team")
    print("2. Проверьте, ответил ли бот на команды")
    print("3. Если бот не отвечает, проверьте логи Render.com")
