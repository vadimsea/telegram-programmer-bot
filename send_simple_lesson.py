"""
Простой тест кнопки через API
"""

import requests
import json
import time

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def send_simple_lesson():
    """Отправить простой урок с кнопкой"""
    
    lesson_text = (
        "📚 <b>Урок 1. Основы HTML</b>\n\n"
        "💡 <b>Теория:</b>\n"
        "HTML - это основа всех веб-страниц.\n\n"
        "📝 <b>Домашнее задание:</b>\n"
        "Создайте простую HTML-страницу.\n\n"
        "✅ <b>Сдаём ДЗ:</b> ответом на это сообщение"
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Связаться с ментором",
                    "url": "https://t.me/vadzim_belarus"
                }
            ],
            [
                {
                    "text": "Следующий урок",
                    "callback_data": "next_lesson_1"
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
                print(f"Урок отправлен! ID: {message_id}")
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
    print("Отправляем простой урок...")
    send_simple_lesson()
