"""
Проверка callback данных с обработкой ошибки 409
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"

def get_updates_with_offset(offset=0):
    """Получить обновления с offset"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    params = {}
    if offset > 0:
        params['offset'] = offset
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return result["result"]
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return []
        elif response.status_code == 409:
            print("Ошибка 409: Конфликт - возможно, бот запущен в другом месте")
            print("Попробуем получить обновления с задержкой...")
            time.sleep(2)
            return get_updates_with_offset(offset)
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def monitor_callbacks_simple():
    """Простой мониторинг callback данных"""
    
    print("=" * 60)
    print("МОНИТОРИНГ CALLBACK ДАННЫХ")
    print("=" * 60)
    print("Нажмите Ctrl+C для остановки")
    print()
    
    last_update_id = 0
    
    try:
        while True:
            updates = get_updates_with_offset(last_update_id + 1)
            
            for update in updates:
                update_id = update["update_id"]
                
                if update_id > last_update_id:
                    last_update_id = update_id
                    
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        print(f"✅ Callback получен: {callback['data']}")
                        print(f"   От: {callback['from']['first_name']}")
                        print(f"   Сообщение ID: {callback['message']['message_id']}")
                        print(f"   Callback ID: {callback['id']}")
                        print("-" * 40)
            
            time.sleep(3)  # Проверяем каждые 3 секунды
            
    except KeyboardInterrupt:
        print("\nМониторинг остановлен")

if __name__ == "__main__":
    monitor_callbacks_simple()
