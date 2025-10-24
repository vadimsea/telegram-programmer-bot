"""
Проверка статуса Render.com и бота
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def check_render_status():
    """Проверить статус Render.com (если доступно)"""
    
    print("Проверка статуса Render.com...")
    print("Перейдите в панель управления Render.com и проверьте:")
    print("1. Статус сервиса (должен быть 'Live')")
    print("2. Логи сервиса (должны быть без ошибок)")
    print("3. Переменные окружения (BOT_TOKEN, CHAT_ID)")
    print()

def test_simple_message():
    """Отправить простое сообщение"""
    
    text = "Тест работы бота"
    
    data = {
        "chat_id": CHAT_ID,
        "text": text
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                message_id = result["result"]["message_id"]
                print(f"Простое сообщение отправлено! ID: {message_id}")
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

def check_recent_messages():
    """Проверить последние сообщения в чате"""
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                updates = result["result"]
                
                messages = []
                for update in updates:
                    if "message" in update:
                        message = update["message"]
                        if str(message["chat"]["id"]) == CHAT_ID:
                            messages.append({
                                "text": message.get("text", ""),
                                "from": message["from"]["first_name"],
                                "date": message["date"]
                            })
                
                if messages:
                    print("Последние сообщения в группе:")
                    for msg in messages[-5:]:  # Последние 5
                        print(f"  - {msg['text']} от {msg['from']}")
                else:
                    print("Сообщений в группе не найдено")
                
                return messages
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
    print("ПРОВЕРКА СТАТУСА RENDER.COM И БОТА")
    print("=" * 60)
    
    print("\n1. Проверяем статус Render.com...")
    check_render_status()
    
    print("\n2. Отправляем простое сообщение...")
    test_simple_message()
    
    print("\n3. Проверяем последние сообщения...")
    messages = check_recent_messages()
    
    print("\nДиагностика:")
    if messages:
        print("✅ Сообщения в группе найдены")
        print("✅ Бот может отправлять сообщения")
        print("❌ Проблема с обработкой callback данных")
    else:
        print("❌ Сообщений в группе не найдено")
        print("❌ Возможно, бот не работает на Render.com")
    
    print("\nРекомендации:")
    print("1. Проверьте логи Render.com")
    print("2. Убедитесь, что переменные окружения настроены")
    print("3. Перезапустите сервис на Render.com")
