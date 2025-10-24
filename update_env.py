"""
Обновление .env файла с реальным токеном бота
"""

import os

# Создаем .env файл с реальным токеном
env_content = """TELEGRAM_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
BOT_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
CHAT_ID=-1001234567890
COURSE_SCHEDULER_ENABLED=1
PERIOD_DAYS=4
TZ=Europe/Minsk
STATE_FILE=state.json
GROQ_API_KEY=gsk_test1234567890abcdefghijklmnopqrstuvwxyz
HUGGING_FACE_TOKEN=hf_1234567890abcdefghijklmnopqrstuvwxyz
"""

# Удаляем старый .env файл
if os.path.exists('.env'):
    os.remove('.env')

# Создаем новый .env файл с UTF-8 кодировкой
with open('.env', 'w', encoding='utf-8') as f:
    f.write(env_content)

print(".env файл обновлен с вашим токеном!")
print("Теперь нужно получить CHAT_ID группы @learncoding_team")
print()
print("ИНСТРУКЦИЯ:")
print("1. Отправьте сообщение 'тест' в группу @learncoding_team")
print("2. Перейдите по ссылке:")
print("   https://api.telegram.org/bot8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY/getUpdates")
print("3. Найдите в ответе: 'chat':{'id':-1001234567890}")
print("4. Скопируйте этот ID (например: -1001234567890)")
print("5. Замените CHAT_ID в .env файле на реальный")
print("6. Запустите: python main.py")
