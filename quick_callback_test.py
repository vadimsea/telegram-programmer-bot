"""
Быстрый тест callback данных
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def send_test_message():
    """Отправить тестовое сообщение с кнопкой"""
    
    text = "Тест кнопки callback"
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Тест",
                    "callback_data": "test_button"
                }
            ]
        ]
    }
    
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": json.dumps(keyboard)
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                message_id = result["result"]["message_id"]
                print(f"Тестовое сообщение отправлено! ID: {message_id}")
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

def check_callbacks():
    """Проверить callback данные"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                updates = result["result"]
                
                callbacks = []
                for update in updates:
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        callbacks.append({
                            "data": callback["data"],
                            "from": callback["from"]["first_name"],
                            "message_id": callback["message"]["message_id"]
                        })
                
                if callbacks:
                    print("Найдены callback данные:")
                    for cb in callbacks:
                        print(f"  - {cb['data']} от {cb['from']} (сообщение {cb['message_id']})")
                else:
                    print("Callback данных не найдено")
                
                return callbacks
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return []
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("БЫСТРЫЙ ТЕСТ CALLBACK")
    print("=" * 60)
    
    print("\n1. Отправляем тестовое сообщение...")
    send_test_message()
    
    print("\n2. Проверяем callback данные...")
    callbacks = check_callbacks()
    
    if not callbacks:
        print("\nИнструкция:")
        print("1. Перейдите в группу @learncoding_team")
        print("2. Нажмите кнопку 'Тест' в последнем сообщении")
        print("3. Запустите этот скрипт снова")
    else:
        print("\nОтлично! Callback данные работают!")
