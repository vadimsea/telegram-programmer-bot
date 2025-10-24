"""
Проверка настроек бота
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

print("Текущие настройки:")
print(f"BOT_TOKEN: {os.getenv('BOT_TOKEN', 'НЕ НАЙДЕН')[:20]}...")
print(f"CHAT_ID: {os.getenv('CHAT_ID', 'НЕ НАЙДЕН')}")
print(f"COURSE_SCHEDULER_ENABLED: {os.getenv('COURSE_SCHEDULER_ENABLED', 'НЕ НАЙДЕН')}")
print(f"PERIOD_DAYS: {os.getenv('PERIOD_DAYS', 'НЕ НАЙДЕН')}")
print(f"TZ: {os.getenv('TZ', 'НЕ НАЙДЕН')}")
print()

if os.getenv('CHAT_ID') == '-1001234567890':
    print("CHAT_ID еще не настроен!")
    print("Нужно получить реальный CHAT_ID группы @learncoding_team")
    print()
    print("ИНСТРУКЦИЯ:")
    print("1. Отправьте сообщение 'тест' в группу @learncoding_team")
    print("2. Перейдите по ссылке:")
    print("   https://api.telegram.org/bot8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY/getUpdates")
    print("3. Найдите в ответе: 'chat':{'id':-1001234567890}")
    print("4. Скопируйте этот ID (например: -1001234567890)")
    print("5. Замените CHAT_ID в .env файле на реальный")
    print("6. Запустите: python main.py")
else:
    print("Все настройки готовы!")
    print("Можно запускать бота: python main.py")
