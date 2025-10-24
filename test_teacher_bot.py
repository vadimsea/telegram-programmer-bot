"""
Тестовый бот-учитель для демонстрации в группе @learncoding_team
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

# Демонстрационные данные
DEMO_LESSONS = [
    {
        "title": "Урок 1. Структура HTML-документа, заголовки, абзацы, ссылки, изображения",
        "theory": "HTML — это язык разметки для создания веб-страниц. Основные элементы: заголовки (h1-h6), абзацы (p), ссылки (a), изображения (img). Каждый HTML-документ начинается с DOCTYPE и содержит структуру html > head > body. Теги бывают парные (открывающий и закрывающий) и одиночные (самозакрывающиеся).",
        "homework": "Создайте простую HTML-страницу с заголовком, несколькими абзацами текста, ссылкой на ваш профиль и изображением. Используйте семантические теги.",
        "type": "HTML/CSS"
    },
    {
        "title": "Урок 2. Списки, таблицы, семантические теги",
        "theory": "HTML предоставляет различные элементы для структурирования контента: списки (ul, ol, li), таблицы (table, tr, td, th). Семантические теги (header, nav, main, section, article, aside, footer) помогают поисковикам и скрин-ридерам лучше понимать структуру страницы. Это улучшает SEO и доступность сайта.",
        "homework": "Создайте страницу с навигационным меню, основным контентом в виде статьи, боковой панелью и подвалом. Добавьте таблицу с данными и маркированный список.",
        "type": "HTML/CSS"
    },
    {
        "title": "Урок 3. Подключение CSS, селекторы, наследование",
        "theory": "CSS можно подключать тремя способами: inline, в теге style или через внешний файл. Селекторы бывают по тегу, классу, ID, атрибуту. CSS работает по принципу каскада и наследования. Более специфичные правила перекрывают менее специфичные. Наследование позволяет дочерним элементам получать стили от родительских.",
        "homework": "Создайте HTML-страницу и подключите к ней CSS-файл. Используйте различные селекторы для стилизации элементов. Покажите разницу между наследованием и каскадом.",
        "type": "HTML/CSS"
    }
]

async def send_demo_lesson(bot_token: str, chat_id: str, lesson_index: int = 0):
    """Отправить демонстрационный урок"""
    
    bot = Bot(token=bot_token)
    lesson = DEMO_LESSONS[lesson_index % len(DEMO_LESSONS)]
    
    # Формируем красивый текст сообщения
    message_text = (
        f"📚 <b>{lesson['title']}</b>\n\n"
        f"💡 <b>Теория:</b>\n{lesson['theory']}\n\n"
        f"📝 <b>Домашнее задание:</b>\n{lesson['homework']}\n\n"
        f"✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
        f"🎯 <b>Уровень:</b> {lesson['type']}\n"
        f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}\n\n"
        f"👨‍💻 <b>Ментор:</b> Вадим (vadzim.by)"
    )
    
    # Создаем красивые кнопки
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
        # Отправляем сообщение
        message = await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        # Пытаемся закрепить сообщение
        try:
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message.message_id
            )
            logger.info("📌 Сообщение закреплено")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось закрепить: {e}")
        
        logger.info(f"✅ Урок отправлен в группу @learncoding_team")
        logger.info(f"📖 Тема: {lesson['title']}")
        logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y в %H:%M')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки урока: {e}")
        return False

async def main():
    """Главная функция"""
    print("Демонстрационный бот-учитель для группы @learncoding_team")
    print("=" * 60)
    
    # Настройки (замените на реальные)
    BOT_TOKEN = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"  # Замените на реальный токен
    CHAT_ID = "-1001234567890"  # Замените на реальный CHAT_ID группы
    
    print(f"Настройки:")
    print(f"   Бот: {BOT_TOKEN[:10]}...")
    print(f"   Группа: {CHAT_ID}")
    print()
    
    print("Доступные уроки:")
    for i, lesson in enumerate(DEMO_LESSONS, 1):
        print(f"   {i}. {lesson['title']}")
    print()
    
    # Отправляем первый урок
    print("Отправляем первый урок...")
    success = await send_demo_lesson(BOT_TOKEN, CHAT_ID, 0)
    
    if success:
        print("Урок успешно отправлен!")
        print("Бот готов работать как учитель в группе!")
    else:
        print("Ошибка отправки урока")
        print("Проверьте токен бота и CHAT_ID группы")

if __name__ == "__main__":
    asyncio.run(main())
