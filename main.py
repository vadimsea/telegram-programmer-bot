import logging
import asyncio
import time
import os
from collections import defaultdict
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
from enhanced_ai_handler import enhanced_ai_handler
from database import user_db
from smart_features import smart_features
from config import TELEGRAM_TOKEN, CREATOR_USERNAME, TELEGRAM_CHANNEL, WEBSITE_URL

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)




def format_code_for_telegram(text):
    """Format code blocks and basic Markdown for Telegram HTML output."""
    import re

    block_placeholders = {}
    inline_placeholders = {}

    def replace_code_block(match):
        code_content = match.group(2).rstrip()
        escaped_code = escape_code_content(code_content)
        placeholder = f'__CODE_BLOCK_{len(block_placeholders)}__'
        block_placeholders[placeholder] = f'<pre>{escaped_code}</pre>'
        return placeholder

    text = re.sub(r'```(\w+)?\n?(.*?)\n?```', replace_code_block, text, flags=re.DOTALL)

    def replace_inline_code(match):
        code_content = escape_code_content(match.group(1))
        placeholder = f'__INLINE_CODE_{len(inline_placeholders)}__'
        inline_placeholders[placeholder] = f'<code>{code_content}</code>'
        return placeholder

    text = re.sub(r'`([^`\n]+)`', replace_inline_code, text)

    text = escape_html_chars(text)
    text = convert_markdown_to_html(text)

    for placeholder, value in inline_placeholders.items():
        text = text.replace(placeholder, value)

    for placeholder, value in block_placeholders.items():
        text = text.replace(placeholder, value)

    return f"✅ <b>Ответ:</b>\n{text}"


def escape_code_content(code_text):
    """Escape HTML in code content while preserving structure"""
    code_text = code_text.replace('&', '&amp;')
    code_text = code_text.replace('<', '&lt;')
    code_text = code_text.replace('>', '&gt;')
    return code_text.strip()


def escape_html_chars(text):
    """Escape HTML special characters for safe Telegram HTML parsing"""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def convert_markdown_to_html(text: str) -> str:
    import re

    # Bold (**text**)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic (*text*)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Bullet points starting with '-', '*', or '?'
    text = re.sub(r'(^|\n)[\-*?]\s+', r'\1? ', text)
    return text


class RateLimiter:
    def __init__(self):
        self.user_requests = defaultdict(list)
        self.max_requests = 10  # requests per minute

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if now - req_time < 60
        ]

        if len(self.user_requests[user_id]) >= self.max_requests:
            return False

        self.user_requests[user_id].append(now)
        return True


class ResponseCache:
    def __init__(self):
        self.cache = {}
        self.max_size = 100

    def get(self, question_hash: str):
        return self.cache.get(question_hash)

    def set(self, question_hash: str, response: str):
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[question_hash] = response



def _is_legacy_fallback_response(text: str) -> bool:
    if not text:
        return False
    markers = ("Hello, world", "Вопрос по программированию", "Быстрый ответ из кэша")
    text_lower = text.lower()
    return any(marker.lower() in text_lower for marker in markers)
# Контекст пользователя
class UserContext:
    def __init__(self):
        self.skill_level = "beginner"
        self.preferred_language = "russian"
        self.history = []
        self.preferences = {
            'code_style': 'detailed',  # detailed, concise, beginner
            'explanation_level': 'medium',  # basic, medium, advanced
            'favorite_languages': [],
            'learning_goals': []
        }
        self.last_tip_topic = None
        self.last_tip_text = None
        self.user_id = None
        self.feedback_scores = []

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content, "timestamp": time.time()})
        if len(self.history) > 10:  # Increased history size
            self.history.pop(0)

    def get_recent_context(self, n: int):
        return self.history[-n:] if len(self.history) >= n else self.history

    def update_skill_level(self, feedback_score: int):
        self.feedback_scores.append(feedback_score)
        if len(self.feedback_scores) > 5:
            self.feedback_scores.pop(0)

        avg_score = sum(self.feedback_scores) / len(self.feedback_scores)
        if avg_score >= 4:
            self.skill_level = "advanced"
        elif avg_score >= 3:
            self.skill_level = "intermediate"
        else:
            self.skill_level = "beginner"


# Хранилище контекстов
user_contexts = {}


def get_user_context(user_id: int) -> UserContext:
    if user_id not in user_contexts:
        user_contexts[user_id] = UserContext()
    context = user_contexts[user_id]
    context.user_id = user_id
    return context


def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("👨‍💻 Связаться с создателем", url=f"tg://resolve?domain={CREATOR_USERNAME[1:]}")],
        [InlineKeyboardButton("📢 Подписаться", url=TELEGRAM_CHANNEL)],
        [InlineKeyboardButton("🌐 Посетить сайт", url=WEBSITE_URL)]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_context = get_user_context(user_id)

    if query.data == "feedback_good":
        user_context.update_skill_level(5)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🙏 Спасибо за обратную связь! Это помогает мне становиться лучше.\n"
            "💡 Подсказка: Чем конкретнее ваши вопросы, тем точнее мои ответы!"
        )

    elif query.data == "feedback_bad":
        user_context.update_skill_level(2)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "😔 Извините, что не смог помочь.\n"
            "💬 Попробуйте:\n"
            "• Переформулировать вопрос\n"
            "• Добавить больше контекста\n"
            "• Разбить сложную задачу на части\n\n"
            "Я учусь на ваших отзывах!"
        )

    elif query.data == "get_hint":
        hints = [
            "💡 Для анализа кода приложите файл или вставьте код в сообщение",
            "🔍 Опишите, что именно не работает - это поможет найти ошибку быстрее",
            "📝 Укажите язык программирования для более точных советов",
            "🎯 Задавайте конкретные вопросы вместо общих",
            "⚡ Используйте /stats чтобы увидеть свой прогресс"
        ]
        import random
        hint = random.choice(hints)
        await query.message.reply_text(hint)

    elif query.data == "learning_mode":
        learning_text = (
            "📚 Режим обучения активирован!\n\n"
            "🎓 Что изучаем сегодня?\n"
            "• Напишите 'основы python' для базового курса\n"
            "• Напишите 'javascript для начинающих'\n"
            "• Напишите 'алгоритмы и структуры данных'\n"
            "• Или задайте свой вопрос для изучения\n\n"
            "💪 Я адаптирую объяснения под ваш уровень!"
        )
        await query.message.reply_text(learning_text)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    # Регистрируем пользователя в базе данных
    user_data = user_db.get_user(user_id)
    user_db.update_user(user_id, {
        'username': username,
        'first_name': update.message.from_user.first_name or "Unknown"
    })

    logger.info(f"👤 Пользователь {username} ({user_id}) запустил бота")

    welcome_text = (
        "👋 Привет! Я Помощник Программиста\n"
        "🚀 Создан Вадимом (vadzim.by)\n\n"
        "💻 Помогу с:\n"
        "• Анализом и отладкой кода\n"
        "• Объяснением концепций программирования\n"
        "• Оптимизацией и архитектурой приложений\n"
        "• Решением проблем и ошибок\n"
        "• Персональным обучением программированию\n\n"
        "🎯 Я адаптируюсь под ваш уровень и стиль обучения!\n"
        "📊 Используйте кнопки для обратной связи - это помогает мне становиться лучше\n\n"
        "📝 Просто напишите свой вопрос или код!\n\n"
        "⚡ Быстрые команды:\n"
        "/help - Получить справку\n"
        "/settings - Настроить предпочтения\n"
        "/about - О создателе\n\n"
        "👇 Также можете воспользоваться кнопками ниже:"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_context = get_user_context(user_id)

    settings_text = (
        f"⚙️ Ваши настройки:\n\n"
        f"🎯 Уровень: {user_context.skill_level}\n"
        f"📝 Стиль кода: {user_context.preferences['code_style']}\n"
        f"📖 Уровень объяснений: {user_context.preferences['explanation_level']}\n\n"
        "Для изменения напишите:\n"
        "• 'установить уровень начинающий/средний/продвинутый'\n"
        "• 'стиль кода краткий/подробный/для начинающих'\n"
        "• 'объяснения базовые/средние/продвинутые'"
    )

    await update.message.reply_text(settings_text, reply_markup=get_main_keyboard())


# Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_context = get_user_context(user_id)

        if not rate_limiter.is_allowed(user_id):
            await update.message.reply_text(
                "⏱️ Слишком много запросов! Подождите минуту.\n"
                "💡 Это помогает мне лучше обслуживать всех пользователей.",
                reply_markup=get_main_keyboard()
            )
            return

        text = update.message.text

        if not text or len(text.strip()) == 0:
            await update.message.reply_text(
                "🤔 Пожалуйста, напишите ваш вопрос или код.",
                reply_markup=get_main_keyboard()
            )
            return

        # Handle encoding issues and special characters
        try:
            # Normalize text to handle emojis and special characters
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
            if len(text) > 4000:  # Telegram message limit
                text = text[:4000] + "..."
        except Exception as encoding_error:
            logger.warning(f"Encoding issue for user {user_id}: {encoding_error}")
            await update.message.reply_text(
                "⚠️ Обнаружены проблемы с кодировкой сообщения. Попробуйте переформулировать.",
                reply_markup=get_main_keyboard()
            )
            return

        text_lower = text.lower()
        if 'установить уровень' in text_lower:
            if 'начинающий' in text_lower:
                user_context.skill_level = 'beginner'
                await update.message.reply_text("✅ Уровень установлен: начинающий")
            elif 'средний' in text_lower or 'промежуточный' in text_lower:
                user_context.skill_level = 'intermediate'
                await update.message.reply_text("✅ Уровень установлен: средний")
            elif 'продвинутый' in text_lower:
                user_context.skill_level = 'advanced'
                await update.message.reply_text("✅ Уровень установлен: продвинутый")
            return

        if 'стиль кода' in text_lower:
            if 'краткий' in text_lower:
                user_context.preferences['code_style'] = 'concise'
                await update.message.reply_text("✅ Стиль кода: краткий")
            elif 'подробный' in text_lower:
                user_context.preferences['code_style'] = 'detailed'
                await update.message.reply_text("✅ Стиль кода: подробный")
            elif 'начинающих' in text_lower:
                user_context.preferences['code_style'] = 'beginner'
                await update.message.reply_text("✅ Стиль кода: для начинающих")
            return

        sensitive_keywords = [
            'пароль', 'токен', 'ключ', 'password', 'token', 'key', 'api_key',
            'secret', 'секрет', 'конфигурация', 'config', 'env', '.env'
        ]

        if any(keyword in text_lower for keyword in sensitive_keywords):
            await update.message.reply_text(
                "🔒 Я не могу предоставить доступ к конфиденциальной информации.\n\n"
                "Для безопасности все пароли и токены защищены.\n"
                "Если нужна помощь с настройкой конфигурации, опишите задачу без указания реальных данных.",
                reply_markup=get_main_keyboard()
            )
            return

        import hashlib
        question_hash = hashlib.md5(text.encode()).hexdigest()
        cached_response = response_cache.get(question_hash)

        if cached_response and _is_legacy_fallback_response(cached_response):
            logger.info("Removing legacy fallback from cache")
            response_cache.cache.pop(question_hash, None)
            cached_response = None

        if cached_response:
            logger.info(f"📦 Используем кэшированный ответ для {user_id}")
            await update.message.reply_text(
                cached_response + "\n\n💡 Быстрый ответ из кэша!",
                reply_markup=get_main_keyboard()
            )
            return

        # Увеличиваем счетчик вопросов
        user_db.increment_questions(user_id)

        if any(word in text_lower for word in ['javascript', 'js', 'джаваскрипт']):
            user_db.add_topic_interest(user_id, 'javascript')
            if 'javascript' not in user_context.preferences['favorite_languages']:
                user_context.preferences['favorite_languages'].append('javascript')
        elif any(word in text_lower for word in ['python', 'питон', 'пайтон']):
            user_db.add_topic_interest(user_id, 'python')
            if 'python' not in user_context.preferences['favorite_languages']:
                user_context.preferences['favorite_languages'].append('python')
        elif any(word in text_lower for word in ['найди ошибку', 'ошибка', 'debug']):
            user_db.add_topic_interest(user_id, 'debugging')
        elif any(word in text_lower for word in ['с чего начать', 'начать учить', 'основы']):
            user_db.add_topic_interest(user_id, 'learning')
            if 'learning_basics' not in user_context.preferences['learning_goals']:
                user_context.preferences['learning_goals'].append('learning_basics')

        user_context.add_message("user", text)

        # Логируем входящее сообщение
        logger.info(f"📨 Получено сообщение от {user_id}: {text[:100]}...")

        is_fallback = False
        try:
            response, is_fallback = await asyncio.wait_for(
                enhanced_ai_handler.get_specialized_response(
                    text,
                    "general",
                    user_context,
                    skill_level=user_context.skill_level,
                    preferences=user_context.preferences
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout for user {user_id}")
            await update.message.reply_text(
                "⏱️ Запрос обрабатывается слишком долго. Попробуйте упростить вопрос или повторить позже.",
                reply_markup=get_main_keyboard()
            )
            return
        except Exception as ai_error:
            logger.error(f"AI handler error for user {user_id}: {ai_error}")
            await update.message.reply_text(
                "🤖 Временные проблемы с ИИ. Попробуйте переформулировать вопрос.",
                reply_markup=get_main_keyboard()
            )
            return

        if not response or len(response.strip()) == 0:
            await update.message.reply_text(
                "🤔 Не удалось сформировать ответ. Попробуйте переформулировать вопрос.",
                reply_markup=get_main_keyboard()
            )
            return

        if not is_fallback:
            response_cache.set(question_hash, response)
        else:
            logger.info("Skipping cache for fallback response")

        user_context.add_message("assistant", response)

        # Логируем ответ
        logger.info(f"📤 Отправляем ответ: {response[:100]}...")

        try:
            has_code = any([
                '\`\`\`' in response,  # Fixed: removed escaping from backticks
                '`' in response,  # Inline code
                'def ' in response,
                'function ' in response,
                'class ' in response,
                'import ' in response,
                'from ' in response,
                'console.log' in response,
                'print(' in response,
                'return ' in response,
                'html>' in response.lower(),
                'DOCTYPE' in response
            ])

            if has_code:
                formatted_response = format_code_for_telegram(response)
                await update.message.reply_text(
                    formatted_response,
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )
            else:
                safe_response = escape_html_chars(response)
                await update.message.reply_text(
                    f"✅ <b>Ответ:</b>\n{safe_response}",
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )

        except Exception as send_error:
            logger.error(f"Message sending error: {send_error}")
            try:
                safe_response = escape_html_chars(response)
                await update.message.reply_text(
                    f"✅ <b>Ответ:</b>\n{safe_response}",
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )
            except Exception:
                # Final fallback - guaranteed to work
                clean_response = ''.join(c for c in response if ord(c) < 128)  # ASCII only
                await update.message.reply_text(
                    f"✅ Ответ: {clean_response[:1000]}",
                    reply_markup=get_main_keyboard()
                )

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_message для пользователя {user_id}: {e}")
        try:
            await update.message.reply_text(
                "❌ Произошла неожиданная ошибка. Наша команда уведомлена.\n"
                "Попробуйте:\n"
                "• Переформулировать вопрос\n"
                "• Разбить сложный запрос на части\n"
                "• Повторить через несколько минут",
                reply_markup=get_main_keyboard()
            )
        except Exception as final_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {final_error}")


# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 Помощник Программиста - Создан Вадимом (vadzim.by)\n\n"
        "📋 Доступные команды:\n"
        "/start - Начать работу\n"
        "/help - Эта справка\n"
        "/settings - Настроить предпочтения\n"
        "/about - Информация о создателе\n\n"
        "💡 Что я умею:\n"
        "• 🔍 Анализировать код\n"
        "• 🐛 Помогать с отладкой\n"
        "• 📚 Объяснять концепции программирования\n"
        "• ⚡ Оптимизировать производительность\n"
        "• 🏗️ Давать советы по архитектуре\n"
        "• 📚 Персональное обучение программированию\n\n"
        "🚀 Просто напишите ваш вопрос или код!\n\n"
        "👇 Свяжитесь с создателем через кнопки ниже:"
    )
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard()
    )


# Команда /about
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "👨‍💻 О создателе:\n\n"
        "• Имя: Вадим (Vadzim)\n"
        "• Сайт: vadzim.by\n"
        "• Telegram: @vadzim_belarus\n\n"
        "🛠 Специализация:\n"
        "• Full-stack разработка\n"
        "• Python, JavaScript, Django, React\n"
        "• Создание Telegram ботов\n"
        "• Веб-приложения и API\n"
        "• Базы данных и оптимизация\n\n"
        "🌐 Услуги:\n"
        "• Разработка сайтов и приложений\n"
        "• Создание Telegram ботов\n"
        "• Оптимизация и рефакторинг кода\n"
        "• Консультации по программированию\n\n"
        "🚀 Для сотрудничества свяжитесь через кнопки ниже:"
    )
    await update.message.reply_text(
        about_text,
        reply_markup=get_main_keyboard()
    )


# Команда /stats - статистика пользователя
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_context = get_user_context(user_id)
    stats = user_db.get_user_stats(user_id)

    stats_text = (
        f"📊 Ваша статистика:\n\n"
        f"❓ Всего вопросов: {stats['total_questions']}\n"
        f"🎯 Уровень: {user_context.skill_level}\n"
        f"⭐ Средняя оценка: {sum(user_context.feedback_scores) / len(user_context.feedback_scores):.1f}/5\n" if user_context.feedback_scores else ""
                                                                                                                                                  f"📅 С нами с: {stats['member_since'][:10]}\n\n"
    )

    if stats['favorite_topics']:
        stats_text += "🔥 Ваши темы:\n"
        for topic in stats['favorite_topics'][-5:]:
            stats_text += f"• {topic}\n"
        stats_text += "\n"

    if user_context.preferences['favorite_languages']:
        stats_text += "💻 Изучаемые языки:\n"
        for lang in user_context.preferences['favorite_languages']:
            stats_text += f"• {lang}\n"
    else:
        stats_text += "🔍 Пока нет данных о ваших интересах\n\n"
        stats_text += "💡 Задавайте вопросы по программированию, и я буду отслеживать ваш прогресс!"

    await update.message.reply_text(
        stats_text,
        reply_markup=get_main_keyboard()
    )


# Команда /admin - статистика для админа (только для создателя)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Проверяем, что это создатель бота
    if username != CREATOR_USERNAME[1:]:  # Убираем @ из начала
        await update.message.reply_text("❌ Доступ запрещен")
        return

    total_users = user_db.get_all_users_count()
    active_users = len(user_db.get_active_users(7))

    admin_text = (
        f"👑 Админ панель\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔥 Активных за неделю: {active_users}\n\n"
        f"📈 Статистика обновляется в реальном времени"
    )

    await update.message.reply_text(admin_text)


# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте ещё раз.",
                reply_markup=get_main_keyboard()
            )
    except:
        pass


# Запуск бота
async def bot_runner():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("settings", settings_command))  # Added settings command
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        application.add_handler(CallbackQueryHandler(button_callback))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        logger.info("🤖 Бот запущен! Создан Вадимом (vadzim.by)")
        print("🚀 Бот запущен! Создан Вадимом (vadzim.by)")

        # Простой цикл ожидания
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        if 'application' in locals():
            if getattr(application, 'running', False):
                await application.stop()
            elif getattr(application, 'initialized', False):
                await application.shutdown()


async def health_handler(request):
    return web.Response(text="OK")


async def main_entry():
    bot_task = asyncio.create_task(bot_runner())

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)

    try:
        await site.start()
        logger.info("Health check server running on port %s", port)
        await bot_task
    except asyncio.CancelledError:
        bot_task.cancel()
        raise
    except Exception:
        logger.exception("Critical error in bot loop")
        raise
    finally:
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        await runner.cleanup()

rate_limiter = RateLimiter()
response_cache = ResponseCache()

if __name__ == "__main__":
    asyncio.run(main_entry())




