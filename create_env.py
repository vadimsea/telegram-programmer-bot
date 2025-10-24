"""
Создание .env файла с правильной кодировкой
"""

import os

# Создаем .env файл с правильной кодировкой
env_content = """TELEGRAM_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789
BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789
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

print(".env файл создан с правильной кодировкой!")
print("Теперь нужно заменить токены на реальные:")
print("   1. Получите токен бота @vadzim_by_programmer_bot от @BotFather")
print("   2. Получите CHAT_ID группы @learncoding_team")
print("   3. Замените в .env файле:")
print("      TELEGRAM_TOKEN=ваш_реальный_токен")
print("      BOT_TOKEN=ваш_реальный_токен")
print("      CHAT_ID=ваш_реальный_CHAT_ID")
print("   4. Запустите: python main.py")
