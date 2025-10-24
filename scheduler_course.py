"""
Фоновый модуль для автоматической публикации обучающих постов
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PERIOD_DAYS = int(os.getenv('PERIOD_DAYS', '4'))
TZ = os.getenv('TZ', 'Europe/Minsk')
COURSE_SCHEDULER_ENABLED = os.getenv('COURSE_SCHEDULER_ENABLED', '1') == '1'
STATE_FILE = os.getenv('STATE_FILE', 'state.json')

# Данные уроков
HTML_CSS_LESSONS = [
    {
        "title": "Структура HTML-документа, заголовки, абзацы, ссылки, изображения",
        "theory": "HTML — это язык разметки для создания веб-страниц. Основные элементы: заголовки (h1-h6), абзацы (p), ссылки (a), изображения (img). Каждый HTML-документ начинается с DOCTYPE и содержит структуру html > head > body. Теги бывают парные (открывающий и закрывающий) и одиночные (самозакрывающиеся).",
        "homework": "Создайте простую HTML-страницу с заголовком, несколькими абзацами текста, ссылкой на ваш профиль и изображением. Используйте семантические теги."
    },
    {
        "title": "Списки, таблицы, семантические теги",
        "theory": "HTML предоставляет различные элементы для структурирования контента: списки (ul, ol, li), таблицы (table, tr, td, th). Семантические теги (header, nav, main, section, article, aside, footer) помогают поисковикам и скрин-ридерам лучше понимать структуру страницы. Это улучшает SEO и доступность сайта.",
        "homework": "Создайте страницу с навигационным меню, основным контентом в виде статьи, боковой панелью и подвалом. Добавьте таблицу с данными и маркированный список."
    },
    {
        "title": "Подключение CSS, селекторы, наследование",
        "theory": "CSS можно подключать тремя способами: inline, в теге style или через внешний файл. Селекторы бывают по тегу, классу, ID, атрибуту. CSS работает по принципу каскада и наследования. Более специфичные правила перекрывают менее специфичные. Наследование позволяет дочерним элементам получать стили от родительских.",
        "homework": "Создайте HTML-страницу и подключите к ней CSS-файл. Используйте различные селекторы для стилизации элементов. Покажите разницу между наследованием и каскадом."
    },
    {
        "title": "Блочная модель: margin, padding, border, display",
        "theory": "Каждый HTML-элемент представляет собой прямоугольник, состоящий из content, padding, border и margin. Padding — внутренние отступы, border — граница, margin — внешние отступы. Свойство display определяет, как элемент отображается: block, inline, inline-block, flex, grid. Понимание блочной модели критично для верстки.",
        "homework": "Создайте несколько блоков с разными значениями padding, margin и border. Покажите разницу между display: block и display: inline."
    },
    {
        "title": "Flexbox и сетки",
        "theory": "Flexbox — это одномерная система раскладки для создания гибких макетов. Основные свойства: flex-direction, justify-content, align-items. CSS Grid — двумерная система для создания сложных сеток. Позволяет точно контролировать расположение элементов по строкам и столбцам. Обе технологии решают проблемы традиционной верстки.",
        "homework": "Создайте макет страницы используя Flexbox для навигации и Grid для основного контента. Сделайте адаптивную сетку с разным количеством колонок на разных экранах."
    },
    {
        "title": "Медиа-запросы, адаптивность",
        "theory": "Медиа-запросы позволяют применять CSS-стили в зависимости от характеристик устройства (ширина экрана, ориентация, плотность пикселей). Адаптивный дизайн обеспечивает корректное отображение сайта на всех устройствах. Mobile-first подход предполагает сначала создание версии для мобильных, затем расширение для больших экранов.",
        "homework": "Создайте адаптивную страницу, которая по-разному выглядит на мобильных (1 колонка), планшетах (2 колонки) и десктопах (3 колонки). Используйте медиа-запросы."
    }
]

JAVASCRIPT_LESSONS = [
    {
        "title": "Подключение JS, переменные, типы данных",
        "theory": "JavaScript можно подключить через тег script в HTML или внешний файл. Переменные объявляются через let, const или var. Основные типы данных: number, string, boolean, undefined, null, object, symbol. JavaScript — динамически типизированный язык, тип переменной определяется во время выполнения. Строгая типизация достигается через TypeScript.",
        "homework": "Создайте HTML-страницу с подключенным JavaScript. Объявите переменные разных типов, выведите их в консоль и на страницу. Покажите разницу между let, const и var."
    },
    {
        "title": "Условия и циклы",
        "theory": "Условные операторы (if, else if, else, switch) позволяют выполнять код в зависимости от условий. Циклы (for, while, do-while, for...in, for...of) повторяют выполнение кода. Тернарный оператор — краткая форма if-else. Логические операторы (&&, ||, !) используются для комбинирования условий. Понимание условий и циклов — основа программирования.",
        "homework": "Напишите программу, которая проверяет число на четность, находит максимальное из трех чисел, и выводит таблицу умножения. Используйте разные виды циклов и условий."
    },
    {
        "title": "Массивы и функции",
        "theory": "Массивы — это упорядоченные коллекции элементов. Основные методы: push, pop, shift, unshift, slice, splice, map, filter, reduce. Функции — это переиспользуемые блоки кода. Могут быть объявлены через function, function expression, arrow functions. Параметры и возвращаемые значения. Замыкания позволяют функциям запоминать внешние переменные.",
        "homework": "Создайте массив чисел и напишите функции для: поиска максимального элемента, фильтрации четных чисел, суммирования всех элементов. Используйте методы массивов и разные способы объявления функций."
    },
    {
        "title": "DOM и события",
        "theory": "DOM (Document Object Model) — это программный интерфейс для HTML/XML документов. JavaScript может изменять структуру, стиль и содержимое страницы. События — это действия пользователя (клик, наведение, ввод текста) или браузера (загрузка страницы). Event listeners позволяют реагировать на события. Event delegation — эффективный способ обработки событий.",
        "homework": "Создайте интерактивную страницу с кнопками, которые изменяют цвет фона, размер текста и добавляют новые элементы. Обработайте события клика, наведения мыши и ввода с клавиатуры."
    },
    {
        "title": "Работа с JSON и fetch()",
        "theory": "JSON (JavaScript Object Notation) — формат обмена данными между клиентом и сервером. Методы JSON.stringify() и JSON.parse() для преобразования. Fetch API — современный способ HTTP-запросов. Возвращает Promise, который можно обработать через .then() или async/await. Обработка ошибок через try/catch. CORS политика ограничивает запросы между доменами.",
        "homework": "Создайте приложение, которое получает данные с публичного API (например, JSONPlaceholder), отображает их на странице и позволяет добавлять новые записи. Обработайте ошибки загрузки данных."
    },
    {
        "title": "Мини-проект: интерактивная галерея",
        "theory": "Объединяем все изученные концепции в практическом проекте. Создаем галерею изображений с возможностью просмотра, фильтрации и добавления новых элементов. Используем модульную архитектуру, разделяем код на функции, обрабатываем пользовательский ввод и ошибки. Это финальный проект для закрепления основ JavaScript.",
        "homework": "Создайте интерактивную галерею изображений с функциями: просмотр в полном размере, фильтрация по категориям, добавление новых изображений, удаление элементов. Используйте localStorage для сохранения данных."
    }
]

class CourseScheduler:
    """Планировщик курса"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
        self.scheduler = AsyncIOScheduler(timezone=TZ)
        self.current_index = self.load_index()
        
    def load_index(self) -> int:
        """Загрузить текущий индекс урока"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('lesson_index', 0)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки индекса урока: {e}")
            logger.error(f"🔧 Создаю новый файл состояния...")
        return 0
    
    def save_index(self, index: int):
        """Сохранить текущий индекс урока"""
        try:
            data = {'lesson_index': index, 'last_updated': datetime.now().isoformat()}
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения индекса урока: {e}")
            logger.error(f"🔧 Проверьте права доступа к файлу {STATE_FILE}")
    
    def make_lesson(self, idx: int) -> Dict[str, str]:
        """Создать урок по индексу (циклически)"""
        # Определяем тип урока (HTML/CSS или JavaScript)
        lesson_type = "HTML/CSS" if (idx // len(HTML_CSS_LESSONS)) % 2 == 0 else "JavaScript"
        
        if lesson_type == "HTML/CSS":
            lesson_data = HTML_CSS_LESSONS[idx % len(HTML_CSS_LESSONS)]
            lesson_num = (idx % len(HTML_CSS_LESSONS)) + 1
        else:
            lesson_data = JAVASCRIPT_LESSONS[idx % len(JAVASCRIPT_LESSONS)]
            lesson_num = (idx % len(JAVASCRIPT_LESSONS)) + 1
        
        # Формируем домашнее задание на основе темы
        if lesson_type == "HTML/CSS":
            hw = f"Сверстайте {lesson_data['homework'].lower()}"
        else:
            hw = f"Напишите {lesson_data['homework'].lower()}"
        
        return {
            'title': f"Урок {idx + 1}. {lesson_data['title']}",
            'text': lesson_data['theory'],
            'hw': hw,
            'type': lesson_type
        }
    
    async def post_lesson(self):
        """Опубликовать урок"""
        if not self.bot or not CHAT_ID:
            logger.error("❌ Бот или CHAT_ID не настроены")
            logger.error("🔧 Проверьте настройки в .env файле")
            return
        
        try:
            lesson = self.make_lesson(self.current_index)
            
            # Формируем красивый текст сообщения на русском
            message_text = (
                f"📚 <b>{lesson['title']}</b>\n\n"
                f"💡 <b>Теория:</b>\n{lesson['text']}\n\n"
                f"📝 <b>Домашнее задание:</b>\n{lesson['hw']}\n\n"
                f"✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
                f"🎯 <b>Уровень:</b> {lesson['type']}\n"
                f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}"
            )
            
            # Создаем красивую кнопку
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "👨‍💻 Связаться с ментором — бесплатно", 
                    url="https://t.me/vadzim_belarus"
                )],
                [InlineKeyboardButton(
                    "📚 Все уроки курса", 
                    url="https://t.me/learncoding_team"
                )]
            ])
            
            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            # Пытаемся закрепить сообщение (игнорируем ошибки)
            try:
                await self.bot.pin_chat_message(
                    chat_id=CHAT_ID,
                    message_id=message.message_id
                )
            except TelegramError as e:
                logger.warning(f"⚠️ Не удалось закрепить сообщение: {e}")
                logger.warning(f"🔧 Убедитесь, что бот является администратором группы")
            
            # Красивое логирование на русском
            logger.info(f"🎓 Опубликован урок {self.current_index + 1} ({lesson['type']})")
            logger.info(f"📖 Тема: {lesson['title']}")
            logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y в %H:%M')}")
            logger.info(f"👥 Группа: @learncoding_team")
            
            # Обновляем индекс и сохраняем
            self.current_index += 1
            self.save_index(self.current_index)
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации урока: {e}")
            logger.error(f"🔧 Проверьте подключение к Telegram API")
    
    def setup_scheduler(self):
        """Настроить планировщик"""
        if not COURSE_SCHEDULER_ENABLED:
            logger.info("⏸️ Планировщик курса отключен в настройках")
            logger.info("🔧 Для включения установите COURSE_SCHEDULER_ENABLED=1 в .env")
            return
        
        if not BOT_TOKEN or not CHAT_ID:
            logger.error("❌ BOT_TOKEN или CHAT_ID не настроены в .env файле")
            logger.error("🔧 Проверьте настройки: BOT_TOKEN и CHAT_ID")
            return
        
        # Планируем первый урок через 5 секунд
        self.scheduler.add_job(
            self.post_lesson,
            'date',
            run_date=datetime.now() + timedelta(seconds=5),
            id='first_lesson'
        )
        
        # Планируем повторяющиеся уроки каждые 4 дня
        self.scheduler.add_job(
            self.post_lesson,
            IntervalTrigger(days=PERIOD_DAYS),
            id='recurring_lessons'
        )
        
        logger.info(f"🚀 Планировщик курса запущен!")
        logger.info(f"📅 Период публикации: каждые {PERIOD_DAYS} дней")
        logger.info(f"🌍 Часовой пояс: {TZ}")
        logger.info(f"👥 Целевая группа: @learncoding_team")
        logger.info(f"⏰ Первый урок через 5 секунд...")
    
    async def run_forever(self):
        """Запустить планировщик навсегда"""
        self.setup_scheduler()
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Планировщик курса успешно запущен!")
            logger.info("🎓 Готов публиковать уроки в группе @learncoding_team")
        
        # Держим процесс живым
        try:
            while True:
                await asyncio.sleep(60)  # Проверяем каждую минуту
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
            logger.info("📚 Останавливаем планировщик курса...")
            self.scheduler.shutdown()
            logger.info("✅ Планировщик успешно остановлен")


# Глобальный экземпляр планировщика
scheduler = CourseScheduler()

async def run_forever():
    """Публичная функция для запуска планировщика"""
    await scheduler.run_forever()
