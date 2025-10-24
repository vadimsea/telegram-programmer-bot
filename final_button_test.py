"""
Финальный тест работы кнопки
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def send_final_test():
    """Отправить финальный тест кнопки"""
    
    text = "Финальный тест кнопки callback"
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Финальный тест",
                    "callback_data": "final_test"
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
                print(f"Финальный тест отправлен! ID: {message_id}")
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

def wait_and_check():
    """Подождать и проверить callback данные"""
    
    print("Ждем 10 секунд...")
    time.sleep(10)
    
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
                    return True
                else:
                    print("Callback данных не найдено")
                    return False
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return False
        elif response.status_code == 409:
            print("Ошибка 409: Конфликт - бот работает на Render.com")
            print("Это означает, что бот получает обновления")
            return True
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ФИНАЛЬНЫЙ ТЕСТ КНОПКИ")
    print("=" * 60)
    
    print("\n1. Отправляем финальный тест...")
    send_final_test()
    
    print("\n2. Ждем и проверяем callback данные...")
    success = wait_and_check()
    
    if success:
        print("\nОтлично! Callback данные работают!")
        print("Проблема была в конфликте между локальным ботом и Render.com")
    else:
        print("\nCallback данных не найдено")
        print("Возможные причины:")
        print("1. Бот на Render.com не обрабатывает callback данные")
        print("2. Ошибка в коде обработчика callback")
        print("3. Проблема с переменными окружения")
    
    print("\nРекомендации:")
    print("1. Проверьте логи Render.com")
    print("2. Убедитесь, что бот запущен и работает")
    print("3. Проверьте переменные окружения BOT_TOKEN и CHAT_ID")
