"""
Модуль для обработки команд обучения в группе
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
STATE_FILE = os.getenv('STATE_FILE', 'state.json')

# Данные уроков (импортируем из scheduler_course)
from scheduler_course import HTML_CSS_LESSONS, JAVASCRIPT_LESSONS

class CourseHandler:
    """Обработчик команд курса"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
        self.current_index = self.load_index()
        
    def load_index(self) -> int:
        """Загрузить текущий индекс урока"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('lesson_index', 0)
        except Exception as e:
            logger.error(f"Ошибка загрузки индекса урока: {e}")
        return 0
    
    def save_index(self, index: int):
        """Сохранить текущий индекс урока"""
        try:
            data = {'lesson_index': index, 'last_updated': datetime.now().isoformat()}
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения индекса урока: {e}")
    
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
        
        return {
            'title': f"Урок {idx + 1}. {lesson_data['title']}",
            'text': lesson_data['theory'],
            'hw': lesson_data['homework'],
            'type': lesson_type
        }
    
    async def send_lesson(self, chat_id: str, lesson_index: int) -> bool:
        """Отправить урок в чат"""
        if not self.bot:
            logger.error("Бот не инициализирован! Проверьте BOT_TOKEN")
            return False
        
        try:
            lesson = self.make_lesson(lesson_index)
            
            # Формируем сообщение
            message_text = (
                f"📚 <b>{lesson['title']}</b>\n\n"
                f"💡 <b>Теория:</b>\n{lesson['text']}\n\n"
                f"📝 <b>Домашнее задание:</b>\n{lesson['hw']}\n\n"
                f"✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
                f"🎯 <b>Уровень:</b> {lesson['type']}\n"
                f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}"
            )
            
            # Создаем клавиатуру
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
                    callback_data=f"next_lesson_{lesson_index + 1}"
                )]
            ])
            
            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            # Пытаемся закрепить сообщение
            try:
                await self.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                logger.info(f"Сообщение закреплено в чате {chat_id}")
            except TelegramError as e:
                logger.warning(f"Не удалось закрепить сообщение: {e}")
            
            # Сохраняем индекс
            self.save_index(lesson_index + 1)
            
            logger.info(f"Урок {lesson_index + 1} отправлен в чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки урока: {e}")
            return False
    
    async def send_welcome_message(self, chat_id: str) -> bool:
        """Отправить приветственное сообщение с кнопкой"""
        if not self.bot:
            logger.error("Бот не инициализирован! Проверьте BOT_TOKEN")
            return False
        
        try:
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
            
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            # Пытаемся закрепить приветственное сообщение
            try:
                await self.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
                logger.info(f"Приветственное сообщение закреплено в чате {chat_id}")
            except TelegramError as e:
                logger.warning(f"Не удалось закрепить приветственное сообщение: {e}")
            
            logger.info(f"Приветственное сообщение отправлено в чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки приветственного сообщения: {e}")
            return False

# Глобальный экземпляр обработчика
course_handler = CourseHandler()

async def course_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /course"""
    try:
        chat_id = str(update.effective_chat.id)
        
        # Проверяем, что команда отправлена в нужной группе
        if chat_id != CHAT_ID:
            await update.message.reply_text(
                "👋 Привет! Этот бот работает только в группе @learncoding_team"
            )
            return
        
        # Отправляем приветственное сообщение
        success = await course_handler.send_welcome_message(chat_id)
        
        if success:
            await update.message.reply_text(
                "✅ Приветственное сообщение отправлено! Проверьте закрепленные сообщения."
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке приветственного сообщения."
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        if update.message:
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    try:
        query = update.callback_query
        logger.info(f"Получен callback: {query.data} от пользователя {query.from_user.first_name}")
        
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        logger.info(f"Chat ID: {chat_id}, ожидаемый: {CHAT_ID}")
        
        # Проверяем, что команда отправлена в нужной группе
        if chat_id != CHAT_ID:
            logger.warning(f"Callback из неправильной группы: {chat_id}")
            await query.edit_message_text(
                "Этот бот работает только в группе @learncoding_team"
            )
            return
        
        if query.data == "start_course":
            logger.info("Обрабатываем start_course")
            # Отправляем первый урок
            success = await course_handler.send_lesson(chat_id, course_handler.current_index)
            
            if success:
                await query.edit_message_text(
                    "Отлично! Первый урок отправлен! Проверьте новые сообщения."
                )
            else:
                await query.edit_message_text(
                    "Произошла ошибка при отправке урока. Попробуйте позже."
                )
        
        elif query.data.startswith("next_lesson_"):
            logger.info(f"Обрабатываем {query.data}")
            # Отправляем следующий урок
            lesson_index = int(query.data.split("_")[2])
            success = await course_handler.send_lesson(chat_id, lesson_index)
            
            if success:
                await query.edit_message_text(
                    f"Урок {lesson_index + 1} отправлен! Проверьте новые сообщения."
                )
            else:
                await query.edit_message_text(
                    "Произошла ошибка при отправке урока. Попробуйте позже."
                )
        else:
            logger.warning(f"Неизвестный callback: {query.data}")
            await query.answer("Неизвестная команда")
                
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("Произошла ошибка. Попробуйте позже.")

def setup_course_handlers(application: Application):
    """Настроить обработчики команд курса"""
    application.add_handler(CommandHandler("course", course_start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Обработчики команд курса настроены")

async def send_welcome_to_group():
    """Отправить приветственное сообщение в группу"""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN или CHAT_ID не настроены!")
        return False
    
    try:
        success = await course_handler.send_welcome_message(CHAT_ID)
        if success:
            logger.info("Приветственное сообщение отправлено в группу")
        return success
    except Exception as e:
        logger.error(f"Ошибка отправки приветственного сообщения: {e}")
        return False
