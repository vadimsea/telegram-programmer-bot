"""
Обновление .env файла с реальным CHAT_ID группы
"""

import os

# Создаем .env файл с реальным CHAT_ID
env_content = """TELEGRAM_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
BOT_TOKEN=8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY
CHAT_ID=-1002949858700
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

print(".env файл обновлен с реальным CHAT_ID!")
print("CHAT_ID: -1002949858700")
print("Группа: Программирование | Веб-разработка | Обучение")
print("Админ: Вадим Анатольевич (@vadzim_belarus)")
print()
print("Теперь можно запускать бота: python main.py")
print("Первая лекция будет опубликована через 5 секунд!")
