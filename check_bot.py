"""
Проверка токена бота и получение CHAT_ID
"""

import asyncio
from telegram import Bot

async def check_bot_token():
    """Проверить токен бота"""
    
    print("=" * 60)
    print("ПРОВЕРКА ТОКЕНА БОТА")
    print("=" * 60)
    
    # Замените на ваш реальный токен
    BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
    
    try:
        bot = Bot(token=BOT_TOKEN)
        me = await bot.get_me()
        
        print(f"Бот работает!")
        print(f"Имя: {me.first_name}")
        print(f"Username: @{me.username}")
        print(f"ID: {me.id}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Проверьте токен бота")
        return False

async def get_chat_id():
    """Получить CHAT_ID группы"""
    
    print("\n" + "=" * 60)
    print("ПОЛУЧЕНИЕ CHAT_ID ГРУППЫ")
    print("=" * 60)
    
    BOT_TOKEN = "8332694363:AAF8W5IofpsVvjWSz1yWBciBBVP_rFrQrFY"
    
    try:
        bot = Bot(token=BOT_TOKEN)
        updates = await bot.get_updates()
        
        if updates:
            print("Найдены обновления:")
            for update in updates[-3:]:  # Последние 3
                if update.message:
                    chat = update.message.chat
                    print(f"   Тип: {chat.type}")
                    print(f"   ID: {chat.id}")
                    print(f"   Название: {chat.title or chat.first_name}")
                    print(f"   Username: @{chat.username}" if chat.username else "   Username: нет")
                    print("-" * 40)
        else:
            print("Обновлений не найдено")
            print("Отправьте сообщение в группу и попробуйте снова")
            
    except Exception as e:
        print(f"Ошибка: {e}")

async def main():
    """Главная функция"""
    
    print("ПРОВЕРКА НАСТРОЙКИ БОТА")
    print("=" * 60)
    print("1. Проверяем токен бота...")
    
    token_ok = await check_bot_token()
    
    if token_ok:
        print("\n2. Получаем CHAT_ID группы...")
        await get_chat_id()
        
        print("\n" + "=" * 60)
        print("ИНСТРУКЦИЯ:")
        print("=" * 60)
        print("1. Замените токен в файле .env")
        print("2. Замените CHAT_ID в файле .env")
        print("3. Запустите: python main.py")
        print("4. Бот начнет публиковать лекции!")
    else:
        print("\nСначала получите правильный токен бота от @BotFather")

if __name__ == "__main__":
    asyncio.run(main())
