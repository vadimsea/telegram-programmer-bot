"""
Скрипт для мониторинга callback данных в реальном времени
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def get_updates():
    """Получить обновления от бота"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return result["result"]
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return []
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def answer_callback_query(callback_id, text):
    """Ответить на callback query"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    
    data = {
        "callback_query_id": callback_id,
        "text": text
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("Ответ на callback отправлен")
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

def send_test_lesson():
    """Отправить тестовый урок с кнопкой"""
    
    lesson_text = (
        "📚 <b>Тестовый урок</b>\n\n"
        "Это тестовый урок для проверки кнопок.\n\n"
        "Нажмите кнопку ниже для проверки callback."
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Тест кнопки",
                    "callback_data": "test_button"
                }
            ]
        ]
    }
    
    data = {
        "chat_id": CHAT_ID,
        "text": lesson_text,
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
                print(f"Тестовый урок отправлен! ID: {message_id}")
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

def monitor_callbacks():
    """Мониторинг callback данных"""
    
    print("=" * 60)
    print("МОНИТОРИНГ CALLBACK ДАННЫХ")
    print("=" * 60)
    print("Нажмите Ctrl+C для остановки")
    print()
    
    last_update_id = 0
    
    try:
        while True:
            updates = get_updates()
            
            for update in updates:
                update_id = update["update_id"]
                
                if update_id > last_update_id:
                    last_update_id = update_id
                    
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        print(f"Callback получен: {callback['data']}")
                        print(f"От: {callback['from']['first_name']}")
                        print(f"Сообщение ID: {callback['message']['message_id']}")
                        print(f"Callback ID: {callback['id']}")
                        
                        # Отвечаем на callback
                        answer_callback_query(callback['id'], "Кнопка работает!")
                        print("-" * 40)
            
            time.sleep(2)  # Проверяем каждые 2 секунды
            
    except KeyboardInterrupt:
        print("\nМониторинг остановлен")

if __name__ == "__main__":
    print("1. Отправляем тестовый урок...")
    send_test_lesson()
    
    print("\n2. Запускаем мониторинг...")
    print("Перейдите в группу @learncoding_team и нажмите кнопку 'Тест кнопки'")
    
    monitor_callbacks()
