import logging
import asyncio
import time
import os
import csv
from collections import defaultdict
from aiohttp import web
from io import StringIO, BytesIO
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.error import TelegramError
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
from scheduler_course import run_forever
from course_handler import (
    setup_course_handlers,
    send_welcome_to_group,
    handle_course_code_message,
    handle_course_mentor_message,
)
from user_progress import progress_manager as course_progress_manager
from telegram.constants import ChatType
from permissions import is_admin_identity

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
        block_placeholders[placeholder] = f'<pre><code>{escaped_code}</code></pre>'
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

    # Headings -> bold paragraphs
    text = re.sub(r'^\s*#{3}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*#{2}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*#\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Replace horizontal rules with blank lines
    text = re.sub(r'^\s*([-*_]){3,}\s*$', '', text, flags=re.MULTILINE)

    # Convert simple markdown tables to bullet lists
    lines = text.split('\n')
    processed_lines = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if i + 1 < len(lines):
                separator = lines[i + 1].strip()
                if re.match(r'^\|\s*[-:]+\s*(\|\s*[-:]+\s*)+\|?$', separator):
                    headers = [c.strip() for c in stripped.strip('|').split('|')]
                    headers = [h for h in headers if h]
                    i += 2
                    while i < len(lines):
                        row = lines[i].strip()
                        if not (row.startswith('|') and row.endswith('|')):
                            break
                        cells = [c.strip() for c in row.strip('|').split('|')]
                        pairs = []
                        for idx, cell in enumerate(cells):
                            if idx < len(headers) and headers[idx]:
                                content = cell or '—'
                                content = content or '—'
                                # wrap in code if looks like tag or contains <>
                                if '<' in content or '&lt;' in content:
                                    content = f"<code>{content}</code>"
                                pairs.append(f"<b>{headers[idx]}:</b> {content}")
                            elif cell:
                                content = cell
                                if '<' in content or '&lt;' in content:
                                    content = f"<code>{content}</code>"
                                pairs.append(content)
                        if pairs:
                            processed_lines.append('&#8226; ' + '<br>'.join(pairs))
                        i += 1
                    continue
        processed_lines.append(lines[i])
        i += 1
    text = '\n'.join(processed_lines)

    # Bold (**text**)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic (*text*)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Bullet points starting with '-', '*', or '•' (bullet)
    text = re.sub(r'(^|\n)[\-*\u2022]\s+', r'\1&#8226; ', text)
    # Numbered lists keep numbers but ensure spacing
    text = re.sub(r'\n(\d+)\.\s+', r'\n\1. ', text)
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


def is_admin_user(telegram_user) -> bool:
    """Check whether the provided Telegram user has admin privileges."""
    if telegram_user is None:
        return False
    return is_admin_identity(
        getattr(telegram_user, "id", None),
        getattr(telegram_user, "username", None),
    )


def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("👨‍💻 Связаться с создателем", url=f"tg://resolve?domain={CREATOR_USERNAME[1:]}")],
        [InlineKeyboardButton("📢 Подписаться", url=TELEGRAM_CHANNEL)],
        [InlineKeyboardButton("🌐 Посетить сайт", url=WEBSITE_URL)]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "admin_export_csv":
        if not is_admin_user(query.from_user):
            await query.answer("Only the administrator can download reports.", show_alert=True)
            return True

        message = query.message
        chat = getattr(message, "chat", None)
        if chat and getattr(chat, "type", None) != "private":
            await query.answer("Open a private chat with the bot to download the CSV.", show_alert=True)
            return True

        if message is None:
            await query.answer("CSV export is not available in this context.", show_alert=True)
            return True

        await query.answer()
        await _send_admin_export_csv(query)
        return True

    await query.answer()

    user_id = query.from_user.id
    user_context = get_user_context(user_id)

    if data == "feedback_good":
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.message:
            logger.warning("Получено обновление без сообщения")
            return

        if (
            update.effective_chat
            and update.effective_chat.type == ChatType.PRIVATE
            and update.message
            and course_progress_manager.is_expecting_mentor(update.effective_user.id)
        ):
            await handle_course_mentor_message(update, context)
            return

        if (
            update.effective_chat
            and update.effective_chat.type == ChatType.PRIVATE
            and update.message.text
            and course_progress_manager.is_expecting_code(update.effective_user.id)
        ):
            await handle_course_code_message(update, context)
            return

        user_id = update.message.from_user.id
        chat_type = getattr(update.effective_chat, "type", None)
        raw_text = update.message.text or ""
        logger.info(
            "handle_message enter: chat_type=%s chat_id=%s user_id=%s text=%r expecting_code=%s expecting_mentor=%s",
            chat_type,
            getattr(update.effective_chat, "id", None),
            user_id,
            raw_text[:200],
            course_progress_manager.is_expecting_code(user_id),
            course_progress_manager.is_expecting_mentor(user_id),
        )
        user_context = get_user_context(user_id)

        if not rate_limiter.is_allowed(user_id):
            logger.info("handle_message rate_limited: user_id=%s", user_id)
            await update.message.reply_text(
                "⏱️ Слишком много запросов! Подождите минуту.\n"
                "💡 Это помогает мне лучше обслуживать всех пользователей.",
                reply_markup=get_main_keyboard()
            )
            return

        text = raw_text

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
        logger.error(f"Критическая ошибка в handle_message: {e}", exc_info=True)
        try:
            if update and update.message:
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
    )
    
    if user_context.feedback_scores:
        avg_score = sum(user_context.feedback_scores) / len(user_context.feedback_scores)
        stats_text += f"⭐ Средняя оценка: {avg_score:.1f}/5\n"
    
    stats_text += f"📅 С нами с: {stats['member_since'][:10]}\n\n"

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
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not is_admin_user(user):
        if message:
            await message.reply_text("Only the administrator can open statistics.")
        return

    if chat and getattr(chat, "type", None) != "private":
        if message:
            await message.reply_text("Open a private chat with the bot to view the admin statistics.")
        return

    total_users = user_db.get_all_users_count()
    active_users = len(user_db.get_active_users(7))

    admin_text = (
        f"👑 Админ панель\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔥 Активных за неделю: {active_users}\n\n"
        f"📈 Статистика обновляется в реальном времени"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Экспорт CSV", callback_data="admin_export_csv")]
    ])

    await (message or update.message).reply_text(admin_text, reply_markup=keyboard)


async def _send_admin_export_csv(query):
    if not user_db.users_data:
        await query.message.reply_text("Пока нет данных для экспорта.")
        return


    fieldnames = [
        "user_id",
        "username",
        "first_name",
        "preferred_language",
        "skill_level",
        "total_questions",
        "favorite_topics",
        "learning_goals",
        "created_at",
        "last_active",
    ]

    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()

    for record in user_db.users_data.values():
        writer.writerow({
            "user_id": record.get("user_id"),
            "username": record.get("username") or "",
            "first_name": record.get("first_name") or "",
            "preferred_language": record.get("preferred_language") or "",
            "skill_level": record.get("skill_level") or "",
            "total_questions": record.get("total_questions", 0),
            "favorite_topics": "; ".join(record.get("favorite_topics", [])),
            "learning_goals": "; ".join(record.get("learning_goals", [])),
            "created_at": record.get("created_at") or "",
            "last_active": record.get("last_active") or "",
        })

    buffer = BytesIO(stream.getvalue().encode("utf-8"))
    buffer.seek(0)
    filename = f"users_export_{datetime.now(datetime.UTC):%Y%m%d_%H%M%S}.csv"

    await query.message.reply_document(
        document=InputFile(buffer, filename=filename),
        caption="Экспорт пользователей (UTF-8)"
    )
# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.error:
        logger.error("Ошибка в обработчике", exc_info=context.error)
    else:
        logger.error("Ошибка в обработчике (context.error пуст)")
    try:
        if update and update.message:
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте ещё раз.",
                reply_markup=get_main_keyboard(),
            )
        elif update and update.callback_query:
            q = update.callback_query
            try:
                await q.answer("Что-то пошло не так. Попробуй ещё раз.", show_alert=True)
            except TelegramError as te:
                logger.warning("error_handler callback answer: %s", te)
    except TelegramError as e:
        logger.warning("error_handler notify user: %s", e)


# Запуск бота
_tg_app: Application | None = None
_tg_consumer_task: asyncio.Task | None = None


def _webhook_base_url() -> str | None:
    # Render отдаёт внешний URL в RENDER_EXTERNAL_URL (например https://xxx.onrender.com)
    return (os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBHOOK_BASE_URL") or "").strip() or None


async def bot_runner(*, mode: str = "auto") -> None:
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        global _tg_app
        _tg_app = application

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("settings", settings_command))  # Added settings command
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(admin_|feedback_)"))
        setup_course_handlers(application)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        base = _webhook_base_url()
        use_webhook = (mode == "webhook") or (mode == "auto" and base is not None)

        # ВАЖНО: webhook и polling нельзя смешивать — иначе получим 409 Conflict.
        if not use_webhook:
            # Polling mode: сначала гарантированно гасим webhook, потом стартуем polling.
            try:
                await application.bot.delete_webhook(drop_pending_updates=True)
            except Exception as e:
                logger.warning("delete_webhook failed (continuing): %s", e)

        await application.initialize()
        await application.start()

        # В webhook-режиме Updater не стартует, поэтому делаем свой consumer очереди апдейтов.
        # Важно: при рестартах Render может создаваться новый Application — старый consumer нужно отменять.
        global _tg_consumer_task
        if _tg_consumer_task is not None and not _tg_consumer_task.done():
            try:
                _tg_consumer_task.cancel()
            except Exception:
                pass
            try:
                await _tg_consumer_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        if True:
            async def _consume_updates() -> None:
                logger.info("update_consumer started (mode=%s)", mode)
                try:
                    while True:
                        u = await application.update_queue.get()
                        try:
                            logger.info("update_consumer got update: %s", type(u).__name__)
                            logger.info("update_consumer process_update start")
                            try:
                                await asyncio.wait_for(application.process_update(u), timeout=15)
                            except asyncio.TimeoutError:
                                logger.error("update_consumer process_update TIMEOUT (15s) — skipping update")
                            logger.info("update_consumer process_update end")
                        except Exception as e:
                            logger.error("update_consumer process_update failed: %s", e, exc_info=e)
                        finally:
                            try:
                                application.update_queue.task_done()
                            except Exception:
                                pass
                except asyncio.CancelledError:
                    logger.info("update_consumer cancelled")
                    raise
                except Exception as e:
                    logger.error("update_consumer crashed: %s", e, exc_info=e)
                    raise

            # Важно привязать таск к PTB Application, чтобы он не терялся.
            _tg_consumer_task = application.create_task(_consume_updates(), name="tg-update-consumer")

        if use_webhook:
            if not base:
                raise RuntimeError("Webhook mode requested but WEBHOOK_BASE_URL/RENDER_EXTERNAL_URL is not set.")
            try:
                await application.bot.set_webhook(url=f"{base}/tg-webhook", drop_pending_updates=True)
            except Exception as e:
                logger.error("set_webhook failed: %s", e)
                raise
        else:
            await application.updater.start_polling()

        logger.info("🤖 Бот запущен! Создан Вадимом (vadzim.by)")
        print("🚀 Бот запущен! Создан Вадимом (vadzim.by)")
        
        # Отправляем приветственное сообщение в группу
        try:
            await send_welcome_to_group()
        except Exception as e:
            logger.error(f"Ошибка отправки приветственного сообщения: {e}")

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


async def tg_webhook_handler(request: web.Request) -> web.Response:
    """
    Webhook endpoint для Telegram (Render).
    """
    if _tg_app is None:
        return web.Response(status=503, text="Bot not ready")
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    try:
        update = Update.de_json(data, _tg_app.bot)
    except Exception as e:
        logger.error("webhook update decode failed: %s", e)
        return web.Response(status=400, text="Bad update")

    # Трассировка: чтобы увидеть ВСЕ входящие апдейты (сообщения/кнопки/команды).
    try:
        u = update
        if getattr(u, "message", None) and u.message:
            m = u.message
            logger.info(
                "WEBHOOK update: message chat_id=%s user_id=%s text=%r",
                getattr(m.chat, "id", None),
                getattr(m.from_user, "id", None),
                (m.text or "")[:200],
            )
        elif getattr(u, "callback_query", None) and u.callback_query:
            cq = u.callback_query
            logger.info(
                "WEBHOOK update: callback user_id=%s chat_id=%s data=%r",
                getattr(getattr(cq, "from_user", None), "id", None),
                getattr(getattr(getattr(cq, "message", None), "chat", None), "id", None),
                (cq.data or "")[:200],
            )
        else:
            logger.info("WEBHOOK update: type=%s keys=%s", type(u).__name__, list((data or {}).keys())[:20])
    except Exception as e:
        logger.warning("WEBHOOK trace failed: %s", e)

    # Кладём update в очередь — его обработает consumer (см. bot_runner).
    try:
        await _tg_app.update_queue.put(update)
        try:
            qsize = _tg_app.update_queue.qsize()
        except Exception:
            qsize = -1
        logger.info("webhook enqueued update (qsize=%s)", qsize)
    except Exception as e:
        logger.error("webhook enqueue failed: %s", e, exc_info=e)
        return web.Response(status=500, text="Enqueue failed")
    return web.Response(text="OK")


async def main_entry():
    """
    На Render сервис должен слушать PORT и отвечать на health-check.
    Важно: ошибка/завершение bot_runner() не должна останавливать HTTP-сервер.
    """
    scheduler_task = asyncio.create_task(run_forever())
    bot_mode = (os.getenv("BOT_MODE") or "auto").strip().lower()
    bot_task = asyncio.create_task(bot_runner(mode=bot_mode))

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    # webhook endpoint for Render
    app.router.add_post("/tg-webhook", tg_webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)

    bot_restart_delay_s = 5
    max_bot_restart_delay_s = 300
    scheduler_restart_delay_s = 30

    try:
        await site.start()
        logger.info("Health check server running on port %s", port)

        # Держим процесс живым. Если бот/планировщик неожиданно завершатся —
        # логируем и перезапускаем, но HTTP-сервер не выключаем.
        while True:
            try:
                if bot_task.done():
                    exc = bot_task.exception()
                    if exc:
                        logger.error("bot_runner crashed: %s", exc, exc_info=exc)
                    else:
                        logger.error("bot_runner stopped unexpectedly (no exception). Restarting...")

                    bot_task = asyncio.create_task(bot_runner())
                    await asyncio.sleep(bot_restart_delay_s)
                    bot_restart_delay_s = min(bot_restart_delay_s * 2, max_bot_restart_delay_s)

                if scheduler_task.done():
                    exc = scheduler_task.exception()
                    if exc:
                        logger.error("scheduler_course.run_forever crashed: %s", exc, exc_info=exc)
                    else:
                        logger.error(
                            "scheduler_course.run_forever stopped unexpectedly (no exception). Restarting..."
                        )
                    scheduler_task = asyncio.create_task(run_forever())
                    await asyncio.sleep(scheduler_restart_delay_s)

                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Нельзя позволить мелкой ошибке оборвать сервис.
                logger.exception("Main loop error (kept running)")
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        bot_task.cancel()
        scheduler_task.cancel()
        raise
    finally:
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        if not scheduler_task.done():
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        await runner.cleanup()

rate_limiter = RateLimiter()
response_cache = ResponseCache()

if __name__ == "__main__":
    asyncio.run(main_entry())




