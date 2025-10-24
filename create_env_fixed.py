"""
Создание файла .env с правильными настройками
"""

import os

env_content = """TELEGRAM_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
BOT_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
CHAT_ID=-1002949858700
COURSE_SCHEDULER_ENABLED=0
PERIOD_DAYS=4
TZ=Europe/Minsk
STATE_FILE=state.json
GROQ_API_KEY=gsk_test1234567890abcdefghijklmnopqrstuvwxyz
HUGGING_FACE_TOKEN=hf_1234567890abcdefghijklmnopqrstuvwxyz
"""

with open('.env', 'w', encoding='utf-8') as f:
    f.write(env_content)

print(".env файл создан с правильной кодировкой!")
print("Настройки:")
print("- BOT_TOKEN: 8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY")
print("- CHAT_ID: -1002949858700")
print("- COURSE_SCHEDULER_ENABLED: 0 (отключен автоматический планировщик)")
print("\nТеперь можно тестировать кнопку!")
