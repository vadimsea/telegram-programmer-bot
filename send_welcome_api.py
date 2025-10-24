"""
Простой скрипт для отправки приветственного сообщения через Telegram API
"""

import requests
import json

# Настройки
BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
CHAT_ID = "-1002949858700"

def send_welcome_message():
    """Отправить приветственное сообщение через API"""
    
    welcome_text = (
        "🎓 <b>Добро пожаловать в курс веб-разработки!</b>\n\n"
        "👋 Привет! Я ваш помощник в изучении HTML, CSS и JavaScript.\n\n"
        "📚 <b>Что вас ждет:</b>\n"
        "• 11 подробных уроков с теорией и практикой\n"
        "• Примеры кода и пошаговые инструкции\n"
        "• Домашние задания для закрепления\n"
        "• Поддержка ментора\n\n"
        "🚀 <b>Начните обучение прямо сейчас!</b>\n"
        "Нажмите кнопку ниже, чтобы получить первый урок."
    )
    
    # Создаем клавиатуру
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🎓 Начать обучение бесплатно",
                    "callback_data": "start_course"
                }
            ],
            [
                {
                    "text": "👨‍💻 Связаться с ментором",
                    "url": "https://t.me/vadzim_belarus"
                }
            ],
            [
                {
                    "text": "🌐 Сайт создателя",
                    "url": "https://vadzim.by"
                }
            ]
        ]
    }
    
    # Данные для отправки
    data = {
        "chat_id": CHAT_ID,
        "text": welcome_text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    
    # URL API
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        print("Отправляем приветственное сообщение...")
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                message_id = result["result"]["message_id"]
                print(f"Сообщение отправлено! ID: {message_id}")
                
                # Пытаемся закрепить сообщение
                pin_url = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"
                pin_data = {
                    "chat_id": CHAT_ID,
                    "message_id": message_id
                }
                
                pin_response = requests.post(pin_url, data=pin_data, timeout=30)
                if pin_response.status_code == 200:
                    print("Сообщение закреплено!")
                else:
                    print("Не удалось закрепить сообщение")
                
                return True
            else:
                print(f"Ошибка API: {result.get('description', 'Неизвестная ошибка')}")
                return False
        else:
            print(f"HTTP ошибка: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("Таймаут запроса")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса: {e}")
        return False

def send_first_lesson():
    """Отправить первый урок через API"""
    
    lesson_text = (
        "📚 <b>Урок 1. Основы HTML</b>\n\n"
        "💡 <b>Теория:</b>\n"
        "HTML (HyperText Markup Language) — это основа всех веб-страниц.\n\n"
        "🔹 ОСНОВНАЯ СТРУКТУРА:\n"
        "Каждый HTML-документ начинается с <!DOCTYPE html> и содержит:\n"
        "- <html> — корневой элемент\n"
        "- <head> — метаданные\n"
        "- <body> — видимый контент\n\n"
        "📝 <b>Домашнее задание:</b>\n"
        "Создайте простую HTML-страницу с заголовком и абзацем.\n\n"
        "✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
        "🎯 <b>Уровень:</b> HTML/CSS\n"
        "📅 <b>Дата:</b> 15.01.2025"
    )
    
    # Создаем клавиатуру
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "👨‍💻 Связаться с ментором — бесплатно",
                    "url": "https://t.me/vadzim_belarus"
                }
            ],
            [
                {
                    "text": "📚 Все уроки курса",
                    "url": "https://t.me/learncoding_team"
                }
            ],
            [
                {
                    "text": "🌐 Сайт создателя",
                    "url": "https://vadzim.by"
                }
            ],
            [
                {
                    "text": "📖 Следующий урок",
                    "callback_data": "next_lesson_1"
                }
            ]
        ]
    }
    
    # Данные для отправки
    data = {
        "chat_id": CHAT_ID,
        "text": lesson_text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    
    # URL API
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        print("Отправляем первый урок...")
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
    print("=" * 60)
    print("ОТПРАВКА ПРИВЕТСТВЕННОГО СООБЩЕНИЯ")
    print("=" * 60)
    
    print("\n1. Отправляем приветственное сообщение...")
    welcome_ok = send_welcome_message()
    
    if welcome_ok:
        print("\n2. Отправляем первый урок...")
        lesson_ok = send_first_lesson()
        
        if lesson_ok:
            print("\nВСЕ СООБЩЕНИЯ ОТПРАВЛЕНЫ!")
            print("Проверьте группу @learncoding_team")
        else:
            print("\nОшибка отправки урока")
    else:
        print("\nОшибка отправки приветственного сообщения")
