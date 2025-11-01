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

from permissions import is_admin_identity
# Загружаем переменные окружения
load_dotenv()

try:
    from config import TELEGRAM_GROUP_USERNAME  # type: ignore
except Exception:
    raw_group_username = os.getenv('TELEGRAM_GROUP_USERNAME', '@learncoding_team') or '@learncoding_team'
    raw_group_username = raw_group_username.strip() or '@learncoding_team'
    if not raw_group_username.startswith('@'):
        raw_group_username = f'@{raw_group_username}'
    TELEGRAM_GROUP_USERNAME = raw_group_username

logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
STATE_FILE = os.getenv('STATE_FILE', 'state.json')

# Данные уроков (импортируем из scheduler_course)
from scheduler_course import HTML_CSS_LESSONS, JAVASCRIPT_LESSONS
from user_progress import progress_manager

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
            'theory': lesson_data['theory'],
            'homework': lesson_data['homework'],
            'type': lesson_type
        }
    
    async def send_lesson(self, chat_id: str, lesson_index: int, user_id: int = None) -> bool:
        """Отправить урок пользователю"""
        if not self.bot:
            logger.error("Бот не инициализирован! Проверьте BOT_TOKEN")
            return False
        
        try:
            lesson = self.make_lesson(lesson_index)
            
            # Формируем сообщение
            message_text = (
                f"📚 <b>{lesson['title']}</b>\n\n"
                f"💡 <b>Теория:</b>\n{lesson['theory']}\n\n"
                f"📝 <b>Домашнее задание:</b>\n{lesson['homework']}\n\n"
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
                "🎉 <b>Добро пожаловать в курс программирования!</b>\n\n"
                "👋 <b>Привет!</b> Я ваш персональный помощник в изучении веб-разработки.\n\n"
                "<b>📚 Что вас ждет:</b>\n"
                "• HTML/CSS основы\n"
                "• JavaScript программирование\n"
                "• Практические задания\n"
                "• Индивидуальный прогресс\n\n"
                "<b>🚀 Как начать:</b>\n"
                "1. Нажмите кнопку \"Начать обучение бесплатно\"\n"
                "2. Получите свой первый урок\n"
                "3. Изучайте в своем темпе!\n\n"
                "<b>💡 Команды:</b>\n"
                "/progress - ваш прогресс\n"
                "/next - следующий урок\n"
                "/reset - начать заново\n\n"
                "<b>🎯 Особенности системы:</b>\n"
                "• Каждый получает уроки по своему прогрессу\n"
                "• Сотни людей могут учиться одновременно\n"
                "• Персональная статистика для каждого\n"
                "• Защита от спама для стабильной работы\n\n"
                "<b>👨‍💻 Нужна помощь?</b>\n"
                "Свяжитесь с ментором Вадимом - он всегда поможет!\n\n"
                "<b>Начнем обучение?</b>"
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
                f"👋 Привет! Этот бот работает только в группе {TELEGRAM_GROUP_USERNAME}"
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
                f"Этот бот работает только в группе {TELEGRAM_GROUP_USERNAME}"
            )
            return
        
        if query.data == "start_course":
            logger.info("Обрабатываем start_course")
            try:
                user_id = query.from_user.id
                
                # Проверяем лимит запросов
                if progress_manager.is_rate_limited(user_id, "lesson"):
                    await query.edit_message_text(
                        "⏰ Слишком частые запросы!\n\n"
                        "Вы можете запросить следующий урок только раз в минуту.\n"
                        "Это защищает систему от перегрузки для всех 567 пользователей."
                    )
                    return
                
                # Получаем следующий урок для пользователя
                next_lesson = progress_manager.get_next_lesson(user_id)
                
                # Отправляем урок пользователю
                success = await course_handler.send_lesson(chat_id, next_lesson, user_id)
                
                if success:
                    # Обновляем прогресс пользователя
                    progress_manager.update_user_progress(user_id, next_lesson)
                    
                    await query.edit_message_text(
                        f"✅ Отлично! Урок {next_lesson + 1} отправлен!\n\n"
                        f"📊 Ваш прогресс: урок {next_lesson + 1} из {len(HTML_CSS_LESSONS) + len(JAVASCRIPT_LESSONS)}\n\n"
                        f"💡 <b>Совет:</b> Изучите урок внимательно, прежде чем переходить к следующему!"
                    )
                else:
                    await query.edit_message_text(
                        "❌ Произошла ошибка при отправке урока. Попробуйте позже."
                    )
            except Exception as e:
                logger.error(f"Ошибка в start_course: {e}")
                await query.edit_message_text(
                    f"Ошибка: {str(e)[:100]}..."
                )
        
        elif query.data.startswith("next_lesson_"):
            logger.info(f"Обрабатываем {query.data}")
            try:
                user_id = query.from_user.id
                lesson_index = int(query.data.split("_")[2])
                
                # Отправляем следующий урок пользователю
                success = await course_handler.send_lesson(chat_id, lesson_index, user_id)
                
                if success:
                    # Обновляем прогресс пользователя
                    progress_manager.update_user_progress(user_id, lesson_index)
                    
                    await query.edit_message_text(
                        f"✅ Урок {lesson_index + 1} отправлен!\n\n"
                        f"📊 Ваш прогресс: урок {lesson_index + 1} из {len(HTML_CSS_LESSONS) + len(JAVASCRIPT_LESSONS)}"
                    )
                else:
                    await query.edit_message_text(
                        "❌ Произошла ошибка при отправке урока. Попробуйте позже."
                    )
            except Exception as e:
                logger.error(f"Ошибка в next_lesson: {e}")
                await query.edit_message_text(
                    f"Ошибка: {str(e)[:100]}..."
                )
        elif query.data.startswith("check_theory_"):
            logger.info(f"Обрабатываем {query.data}")
            # Отправляем вопросы по теории
            lesson_index = int(query.data.split("_")[2])
            lesson = course_handler.make_lesson(lesson_index)
            
            theory_questions = f"""<b>🤔 ПРОВЕРКА ТЕОРИИ</b>

<b>Вопросы по уроку {lesson_index + 1}:</b>

1. Что означает HTML?
2. Какие три основных элемента есть в каждом HTML-документе?
3. В чем разница между парными и одиночными тегами?
4. Зачем нужен атрибут alt у изображений?

<b>📝 Ответьте на вопросы:</b>
Напишите ответы в формате:
1. [ваш ответ]
2. [ваш ответ]
3. [ваш ответ]
4. [ваш ответ]

<b>✅ Проверка:</b>
Вадим и бот проверят ваши ответы и дадут обратную связь!"""
            
            await query.edit_message_text(
                theory_questions,
                parse_mode='HTML'
            )
        else:
            logger.warning(f"Неизвестный callback: {query.data}")
            await query.answer("Неизвестная команда")
                
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("Произошла ошибка. Попробуйте позже.")

async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра прогресса"""
    try:
        user_id = update.effective_user.id
        stats = progress_manager.get_user_stats(user_id)
        
        progress_text = f"""📊 <b>Ваш прогресс в курсе:</b>

🎯 <b>Текущий урок:</b> {stats['current_lesson'] + 1}
✅ <b>Завершено уроков:</b> {stats['completed_count']}
📅 <b>Начали обучение:</b> {stats['started_at'][:10]}
🕐 <b>Последняя активность:</b> {stats['last_activity'][:16]}

<b>Команды:</b>
/progress - показать этот прогресс
/reset - сбросить прогресс
/next - получить следующий урок"""
        
        await update.message.reply_text(progress_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка в команде /progress: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для сброса прогресса"""
    try:
        user_id = update.effective_user.id
        progress_manager.reset_user_progress(user_id)
        
        await update.message.reply_text(
            "🔄 Ваш прогресс сброшен!\n\n"
            "Теперь вы можете начать обучение заново с первого урока."
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде /reset: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def send_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отправки кнопки 'Учиться бесплатно' (только для админов)"""
    try:
        user_id = update.effective_user.id
        
        # Проверяем, что это админ (Вадим)
        if not is_admin_identity(user_id, getattr(update.effective_user, "username", None)):
            await update.message.reply_text(
                "❌ Эта команда доступна только администраторам."
            )
            return
        
        chat_id = str(update.effective_chat.id)
        
        # Проверяем, что команда отправлена в нужной группе
        if chat_id != CHAT_ID:
            await update.message.reply_text(
                f"👋 Эта команда работает только в группе {TELEGRAM_GROUP_USERNAME}"
            )
            return
        
        # Отправляем кнопку
        success = await course_handler.send_welcome_message(chat_id)
        
        if success:
            await update.message.reply_text(
                "✅ Кнопка 'Учиться бесплатно' отправлена в группу!"
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке кнопки."
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /sendbutton: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статистики группы (только для админов)"""
    try:
        user_id = update.effective_user.id
        
        # Проверяем, что это админ (Вадим)
        if not is_admin_identity(user_id, getattr(update.effective_user, "username", None)):
            await update.message.reply_text(
                "❌ Эта команда доступна только администраторам."
            )
            return
        
        # Получаем статистику группы
        group_stats = progress_manager.get_group_stats()
        
        stats_text = f"""📊 <b>СТАТИСТИКА ГРУППЫ</b>

👥 <b>Всего пользователей:</b> {group_stats['total_users']}
🟢 <b>Активных пользователей:</b> {group_stats['active_users']}
📚 <b>Всего уроков запрошено:</b> {group_stats['total_lessons_requested']}
📈 <b>Среднее уроков на пользователя:</b> {group_stats['average_lessons_per_user']:.1f}

<b>💡 Анализ:</b>
• Активность: {group_stats['active_users']/group_stats['total_users']*100:.1f}% пользователей активны
• Прогресс: {group_stats['average_lessons_per_user']:.1f} уроков в среднем
• Система работает стабильно для {group_stats['total_users']} пользователей"""
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка в команде /stats: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения следующего урока"""
    try:
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Проверяем, что команда отправлена в нужной группе
        if chat_id != CHAT_ID:
            await update.message.reply_text(
                f"👋 Привет! Этот бот работает только в группе {TELEGRAM_GROUP_USERNAME}"
            )
            return
        
        # Проверяем лимит запросов
        if progress_manager.is_rate_limited(user_id, "lesson"):
            await update.message.reply_text(
                "⏰ Слишком частые запросы!\n\n"
                "Вы можете запросить следующий урок только раз в минуту.\n"
                "Это защищает систему от перегрузки для всех 567 пользователей."
            )
            return
        
        # Получаем следующий урок для пользователя
        next_lesson = progress_manager.get_next_lesson(user_id)
        
        # Отправляем урок пользователю
        success = await course_handler.send_lesson(chat_id, next_lesson, user_id)
        
        if success:
            # Обновляем прогресс пользователя
            progress_manager.update_user_progress(user_id, next_lesson)
            
            await update.message.reply_text(
                f"✅ Урок {next_lesson + 1} отправлен!\n\n"
                f"📊 Ваш прогресс: урок {next_lesson + 1} из {len(HTML_CSS_LESSONS) + len(JAVASCRIPT_LESSONS)}\n\n"
                f"💡 <b>Совет:</b> Изучите урок внимательно, прежде чем переходить к следующему!"
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке урока. Попробуйте позже."
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /next: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

def setup_course_handlers(application: Application):
    """Настроить обработчики команд курса"""
    application.add_handler(CommandHandler("course", course_start_command))
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("next", next_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("sendbutton", send_button_command))
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
