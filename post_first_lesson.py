"""
Немедленная публикация первой лекции в группу @learncoding_team
"""

import asyncio
import logging
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def post_first_lesson():
    """Опубликовать первую лекцию прямо сейчас"""
    
    # Настройки для группы @learncoding_team
    BOT_TOKEN = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"  # Замените на реальный токен
    CHAT_ID = "-1001234567890"  # Замените на реальный CHAT_ID группы
    
    bot = Bot(token=BOT_TOKEN)
    
    # Первая лекция
    lesson_text = (
        "📚 <b>Урок 1. Структура HTML-документа, заголовки, абзацы, ссылки, изображения</b>\n\n"
        "💡 <b>Теория:</b>\n"
        "HTML — это язык разметки для создания веб-страниц. Основные элементы: заголовки (h1-h6), абзацы (p), ссылки (a), изображения (img). Каждый HTML-документ начинается с DOCTYPE и содержит структуру html > head > body. Теги бывают парные (открывающий и закрывающий) и одиночные (самозакрывающиеся).\n\n"
        "📝 <b>Домашнее задание:</b>\n"
        "Создайте простую HTML-страницу с заголовком, несколькими абзацами текста, ссылкой на ваш профиль и изображением. Используйте семантические теги.\n\n"
        "✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
        "🎯 <b>Уровень:</b> HTML/CSS\n"
        "📅 <b>Дата:</b> " + datetime.now().strftime('%d.%m.%Y') + "\n\n"
        "👨‍💻 <b>Ментор:</b> Вадим (vadzim.by)"
    )
    
    # Красивые кнопки
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "👨‍💻 Связаться с ментором — бесплатно", 
            url="https://t.me/vadzim_belarus"
        )],
        [InlineKeyboardButton(
            "📚 Все уроки курса", 
            url="https://t.me/learncoding_team"
        )],
        [InlineKeyboardButton(
            "🌐 Сайт создателя", 
            url="https://vadzim.by"
        )]
    ])
    
    try:
        print("Отправляем первую лекцию в группу @learncoding_team...")
        
        # Отправляем сообщение
        message = await bot.send_message(
            chat_id=CHAT_ID,
            text=lesson_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        print("Лекция успешно отправлена!")
        print(f"Тема: Урок 1. Структура HTML-документа...")
        print(f"Дата: {datetime.now().strftime('%d.%m.%Y в %H:%M')}")
        print(f"Группа: @learncoding_team")
        
        # Пытаемся закрепить сообщение
        try:
            await bot.pin_chat_message(
                chat_id=CHAT_ID,
                message_id=message.message_id
            )
            print("Сообщение закреплено!")
        except Exception as e:
            print(f"Не удалось закрепить: {e}")
            print("Убедитесь, что бот является администратором группы")
        
        print("\nПервая лекция опубликована!")
        print("Студенты могут начать изучение HTML/CSS")
        print("ДЗ можно сдавать ответами на это сообщение")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки лекции: {e}")
        print("🔧 Проверьте:")
        print("   1. Токен бота правильный")
        print("   2. Бот добавлен в группу @learncoding_team")
        print("   3. Бот является администратором группы")
        print("   4. CHAT_ID группы правильный")
        return False

async def main():
    """Главная функция"""
    print("=" * 60)
    print("ПОМОЩНИК ПРОГРАММИСТА - ПЕРВАЯ ЛЕКЦИЯ")
    print("=" * 60)
    print("Группа: @learncoding_team")
    print("Создатель: Вадим (vadzim.by)")
    print("Цель: Обучить программированию с нуля")
    print("=" * 60)
    
    success = await post_first_lesson()
    
    if success:
        print("\nГОТОВО! Первая лекция опубликована!")
        print("Студенты могут начать изучение")
        print("Следующие лекции будут каждые 4 дня")
    else:
        print("\nОШИБКА! Лекция не опубликована")
        print("Проверьте настройки и попробуйте снова")

if __name__ == "__main__":
    asyncio.run(main())
