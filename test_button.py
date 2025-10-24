"""
Тестовый скрипт для проверки работы кнопки "Начать обучение бесплатно"
"""

import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# Загружаем переменные окружения
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

async def test_welcome_message():
    """Тест отправки приветственного сообщения"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN или CHAT_ID не настроены!")
        print(f"BOT_TOKEN: {BOT_TOKEN[:20] if BOT_TOKEN else 'НЕ НАЙДЕН'}...")
        print(f"CHAT_ID: {CHAT_ID}")
        return False
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🎓 Начать обучение бесплатно",
                callback_data="start_course"
            )],
            [InlineKeyboardButton(
                "👨‍💻 Связаться с ментором",
                url="https://t.me/vadzim_belarus"
            )],
            [InlineKeyboardButton(
                "🌐 Сайт создателя",
                url="https://vadzim.by"
            )]
        ])
        
        print("Отправляем приветственное сообщение в группу...")
        message = await bot.send_message(
            chat_id=CHAT_ID,
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        print("✅ Приветственное сообщение отправлено!")
        print(f"Message ID: {message.message_id}")
        
        # Пытаемся закрепить сообщение
        try:
            await bot.pin_chat_message(chat_id=CHAT_ID, message_id=message.message_id)
            print("✅ Сообщение закреплено!")
        except Exception as e:
            print(f"⚠️ Не удалось закрепить сообщение: {e}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")
        return False

async def test_first_lesson():
    """Тест отправки первого урока"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN или CHAT_ID не настроены!")
        return False
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # Простой первый урок для теста
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
            )],
            [InlineKeyboardButton(
                "📖 Следующий урок",
                callback_data="next_lesson_1"
            )]
        ])
        
        print("Отправляем первый урок в группу...")
        message = await bot.send_message(
            chat_id=CHAT_ID,
            text=lesson_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        print("✅ Первый урок отправлен!")
        print(f"Message ID: {message.message_id}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка отправки урока: {e}")
        return False

async def main():
    print("=" * 60)
    print("ТЕСТ КНОПКИ 'НАЧАТЬ ОБУЧЕНИЕ БЕСПЛАТНО'")
    print("=" * 60)
    
    print("\n1. Тестируем приветственное сообщение...")
    welcome_ok = await test_welcome_message()
    
    if welcome_ok:
        print("\n2. Тестируем первый урок...")
        lesson_ok = await test_first_lesson()
        
        if lesson_ok:
            print("\n✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print("Проверьте группу @learncoding_team")
        else:
            print("\n❌ Ошибка в тесте урока")
    else:
        print("\n❌ Ошибка в тесте приветственного сообщения")

if __name__ == "__main__":
    asyncio.run(main())
