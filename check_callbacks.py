"""
Скрипт для проверки callback данных кнопок
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"

def get_updates():
    """Получить обновления от бота"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                updates = result["result"]
                print(f"Найдено обновлений: {len(updates)}")
                
                for update in updates[-5:]:  # Последние 5 обновлений
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        print(f"Callback: {callback['data']}")
                        print(f"От: {callback['from']['first_name']}")
                        print(f"Сообщение ID: {callback['message']['message_id']}")
                        print("-" * 40)
                
                return updates
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

if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА CALLBACK ДАННЫХ")
    print("=" * 60)
    
    updates = get_updates()
    
    if updates:
        print("\nИнструкция:")
        print("1. Перейдите в группу @learncoding_team")
        print("2. Нажмите кнопку 'Начать обучение бесплатно'")
        print("3. Запустите этот скрипт снова для проверки")
    else:
        print("Обновлений не найдено")
