"""
Тест кнопки "Следующий урок" через API
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def test_callback_button():
    """Тест кнопки через API"""
    
    # Создаем тестовое сообщение с кнопкой
    test_text = (
        "🧪 <b>Тест кнопки</b>\n\n"
        "Нажмите кнопку ниже для проверки callback обработки."
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Тест callback",
                    "callback_data": "test_callback"
                }
            ],
            [
                {
                    "text": "Начать обучение",
                    "callback_data": "start_course"
                }
            ]
        ]
    }
    
    data = {
        "chat_id": CHAT_ID,
        "text": test_text,
        "parse_mode": "HTML",
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
                print("Теперь нажмите кнопки в группе для проверки callback")
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

def check_recent_callbacks():
    """Проверить последние callback данные"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                updates = result["result"]
                print(f"Найдено обновлений: {len(updates)}")
                
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
                    print("Последние callback данные:")
                    for cb in callbacks[-3:]:  # Последние 3
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
    print("ТЕСТ CALLBACK КНОПОК")
    print("=" * 60)
    
    print("\n1. Отправляем тестовое сообщение...")
    test_callback_button()
    
    print("\n2. Проверяем последние callback данные...")
    check_recent_callbacks()
    
    print("\nИнструкция:")
    print("1. Перейдите в группу @learncoding_team")
    print("2. Нажмите кнопку 'Тест callback' или 'Начать обучение'")
    print("3. Запустите этот скрипт снова для проверки callback данных")
