"""
Тест кнопки с детальным логированием
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def send_test_with_logging():
    """Отправить тест с детальным логированием"""
    
    text = "Тест кнопки с логированием"
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Тест с логированием",
                    "callback_data": "test_with_logging"
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
                print(f"Тест с логированием отправлен! ID: {message_id}")
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

def check_updates_detailed():
    """Проверить обновления с детальной информацией"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        print(f"Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Результат API: {result.get('ok', False)}")
            
            if result.get("ok"):
                updates = result["result"]
                print(f"Количество обновлений: {len(updates)}")
                
                if updates:
                    print("Последние обновления:")
                    for i, update in enumerate(updates[-3:]):  # Последние 3
                        print(f"  Обновление {i+1}:")
                        print(f"    ID: {update.get('update_id', 'N/A')}")
                        
                        if "message" in update:
                            msg = update["message"]
                            print(f"    Тип: сообщение")
                            print(f"    От: {msg['from']['first_name']}")
                            print(f"    Текст: {msg.get('text', 'N/A')}")
                            print(f"    Chat ID: {msg['chat']['id']}")
                        
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            print(f"    Тип: callback")
                            print(f"    От: {cb['from']['first_name']}")
                            print(f"    Данные: {cb['data']}")
                            print(f"    Сообщение ID: {cb['message']['message_id']}")
                            print(f"    Chat ID: {cb['message']['chat']['id']}")
                        
                        print()
                
                return updates
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return []
        elif response.status_code == 409:
            print("Ошибка 409: Конфликт - бот работает на Render.com")
            return []
        else:
            print(f"HTTP ошибка: {response.status_code}")
            print(f"Ответ: {response.text}")
            return []
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ КНОПКИ С ДЕТАЛЬНЫМ ЛОГИРОВАНИЕМ")
    print("=" * 60)
    
    print("\n1. Отправляем тест с логированием...")
    send_test_with_logging()
    
    print("\n2. Проверяем обновления с детальной информацией...")
    updates = check_updates_detailed()
    
    print("\nИнструкция:")
    print("1. Перейдите в группу @learncoding_team")
    print("2. Нажмите кнопку 'Тест с логированием'")
    print("3. Запустите этот скрипт снова")
    
    if updates:
        print("\nОбновления найдены!")
    else:
        print("\nОбновлений не найдено")
        print("Возможные причины:")
        print("1. Бот на Render.com не обрабатывает callback данные")
        print("2. Проблема с переменными окружения")
        print("3. Ошибка в коде обработчика callback")
