"""
Проверка статуса бота и callback данных
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"

def check_bot_status():
    """Проверить статус бота"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result["result"]
                print("Бот работает!")
                print(f"   Имя: {bot_info['first_name']}")
                print(f"   Username: @{bot_info['username']}")
                print(f"   ID: {bot_info['id']}")
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

def get_updates_simple():
    """Получить обновления простым способом"""
    
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
                            "message_id": callback["message"]["message_id"],
                            "update_id": update["update_id"]
                        })
                
                if callbacks:
                    print("Callback данные:")
                    for cb in callbacks[-5:]:  # Последние 5
                        print(f"   - {cb['data']} от {cb['from']} (сообщение {cb['message_id']}, update {cb['update_id']})")
                else:
                    print("Callback данных не найдено")
                
                return callbacks
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return []
        elif response.status_code == 409:
            print("Ошибка 409: Конфликт - бот запущен в другом месте")
            print("   Это нормально, если бот работает на Render.com")
            return []
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА СТАТУСА БОТА")
    print("=" * 60)
    
    print("\n1. Проверяем статус бота...")
    bot_ok = check_bot_status()
    
    if bot_ok:
        print("\n2. Проверяем callback данные...")
        callbacks = get_updates_simple()
        
        if callbacks:
            print("\nCallback данные найдены!")
            print("Бот получает callback данные, но возможно есть ошибка в обработке")
        else:
            print("\nCallback данных не найдено")
            print("Попробуйте нажать кнопку в группе и запустить скрипт снова")
    else:
        print("\nБот не работает!")
