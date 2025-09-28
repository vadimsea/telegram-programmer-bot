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

# Р›РѕРіРёСЂРѕРІР°РЅРёРµ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def format_code_for_telegram(text):
    """Format code blocks and basic Markdown for Telegram HTML output"""
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

    text = re.sub(r'`([^`]+)`', replace_inline_code, text)

    text = escape_html_chars(text)
    text = convert_markdown_to_html(text)

    for placeholder, value in inline_placeholders.items():
        text = text.replace(placeholder, value)

    for placeholder, value in block_placeholders.items():
        text = text.replace(placeholder, value)

    return f'вњ… <b>РћС‚РІРµС‚:</b>\n{text}'

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
    # Bullet points starting with '-', '*', or '•'
    text = re.sub(r'(^|\n)[\-*•]\s+', r'\1• ', text)
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
    markers = ("Hello, world", "Р’РѕРїСЂРѕСЃ РїРѕ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЋ", "Р‘С‹СЃС‚СЂС‹Р№ РѕС‚РІРµС‚ РёР· РєСЌС€Р°")
    text_lower = text.lower()
    return any(marker.lower() in text_lower for marker in markers)
# РљРѕРЅС‚РµРєСЃС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
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


# РҐСЂР°РЅРёР»РёС‰Рµ РєРѕРЅС‚РµРєСЃС‚РѕРІ
user_contexts = {}


def get_user_context(user_id: int) -> UserContext:
    if user_id not in user_contexts:
        user_contexts[user_id] = UserContext()
    context = user_contexts[user_id]
    context.user_id = user_id
    return context


def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("рџ‘ЁвЂЌрџ’» РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ СЃРѕР·РґР°С‚РµР»РµРј", url=f"tg://resolve?domain={CREATOR_USERNAME[1:]}")],
        [InlineKeyboardButton("рџ“ў РџРѕРґРїРёСЃР°С‚СЊСЃСЏ", url=TELEGRAM_CHANNEL)],
        [InlineKeyboardButton("рџЊђ РџРѕСЃРµС‚РёС‚СЊ СЃР°Р№С‚", url=WEBSITE_URL)]
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
            "рџ™Џ РЎРїР°СЃРёР±Рѕ Р·Р° РѕР±СЂР°С‚РЅСѓСЋ СЃРІСЏР·СЊ! Р­С‚Рѕ РїРѕРјРѕРіР°РµС‚ РјРЅРµ СЃС‚Р°РЅРѕРІРёС‚СЊСЃСЏ Р»СѓС‡С€Рµ.\n"
            "рџ’Ў РџРѕРґСЃРєР°Р·РєР°: Р§РµРј РєРѕРЅРєСЂРµС‚РЅРµРµ РІР°С€Рё РІРѕРїСЂРѕСЃС‹, С‚РµРј С‚РѕС‡РЅРµРµ РјРѕРё РѕС‚РІРµС‚С‹!"
        )

    elif query.data == "feedback_bad":
        user_context.update_skill_level(2)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "рџ” РР·РІРёРЅРёС‚Рµ, С‡С‚Рѕ РЅРµ СЃРјРѕРі РїРѕРјРѕС‡СЊ.\n"
            "рџ’¬ РџРѕРїСЂРѕР±СѓР№С‚Рµ:\n"
            "вЂў РџРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ\n"
            "вЂў Р”РѕР±Р°РІРёС‚СЊ Р±РѕР»СЊС€Рµ РєРѕРЅС‚РµРєСЃС‚Р°\n"
            "вЂў Р Р°Р·Р±РёС‚СЊ СЃР»РѕР¶РЅСѓСЋ Р·Р°РґР°С‡Сѓ РЅР° С‡Р°СЃС‚Рё\n\n"
            "РЇ СѓС‡СѓСЃСЊ РЅР° РІР°С€РёС… РѕС‚Р·С‹РІР°С…!"
        )

    elif query.data == "get_hint":
        hints = [
            "рџ’Ў Р”Р»СЏ Р°РЅР°Р»РёР·Р° РєРѕРґР° РїСЂРёР»РѕР¶РёС‚Рµ С„Р°Р№Р» РёР»Рё РІСЃС‚Р°РІСЊС‚Рµ РєРѕРґ РІ СЃРѕРѕР±С‰РµРЅРёРµ",
            "рџ”Ќ РћРїРёС€РёС‚Рµ, С‡С‚Рѕ РёРјРµРЅРЅРѕ РЅРµ СЂР°Р±РѕС‚Р°РµС‚ - СЌС‚Рѕ РїРѕРјРѕР¶РµС‚ РЅР°Р№С‚Рё РѕС€РёР±РєСѓ Р±С‹СЃС‚СЂРµРµ",
            "рџ“ќ РЈРєР°Р¶РёС‚Рµ СЏР·С‹Рє РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЏ РґР»СЏ Р±РѕР»РµРµ С‚РѕС‡РЅС‹С… СЃРѕРІРµС‚РѕРІ",
            "рџЋЇ Р—Р°РґР°РІР°Р№С‚Рµ РєРѕРЅРєСЂРµС‚РЅС‹Рµ РІРѕРїСЂРѕСЃС‹ РІРјРµСЃС‚Рѕ РѕР±С‰РёС…",
            "вљЎ РСЃРїРѕР»СЊР·СѓР№С‚Рµ /stats С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ СЃРІРѕР№ РїСЂРѕРіСЂРµСЃСЃ"
        ]
        import random
        hint = random.choice(hints)
        await query.message.reply_text(hint)

    elif query.data == "learning_mode":
        learning_text = (
            "рџ“љ Р РµР¶РёРј РѕР±СѓС‡РµРЅРёСЏ Р°РєС‚РёРІРёСЂРѕРІР°РЅ!\n\n"
            "рџЋ“ Р§С‚Рѕ РёР·СѓС‡Р°РµРј СЃРµРіРѕРґРЅСЏ?\n"
            "вЂў РќР°РїРёС€РёС‚Рµ 'РѕСЃРЅРѕРІС‹ python' РґР»СЏ Р±Р°Р·РѕРІРѕРіРѕ РєСѓСЂСЃР°\n"
            "вЂў РќР°РїРёС€РёС‚Рµ 'javascript РґР»СЏ РЅР°С‡РёРЅР°СЋС‰РёС…'\n"
            "вЂў РќР°РїРёС€РёС‚Рµ 'Р°Р»РіРѕСЂРёС‚РјС‹ Рё СЃС‚СЂСѓРєС‚СѓСЂС‹ РґР°РЅРЅС‹С…'\n"
            "вЂў РР»Рё Р·Р°РґР°Р№С‚Рµ СЃРІРѕР№ РІРѕРїСЂРѕСЃ РґР»СЏ РёР·СѓС‡РµРЅРёСЏ\n\n"
            "рџ’Є РЇ Р°РґР°РїС‚РёСЂСѓСЋ РѕР±СЉСЏСЃРЅРµРЅРёСЏ РїРѕРґ РІР°С€ СѓСЂРѕРІРµРЅСЊ!"
        )
        await query.message.reply_text(learning_text)


# РљРѕРјР°РЅРґР° /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…
    user_data = user_db.get_user(user_id)
    user_db.update_user(user_id, {
        'username': username,
        'first_name': update.message.from_user.first_name or "Unknown"
    })

    logger.info(f"рџ‘¤ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {username} ({user_id}) Р·Р°РїСѓСЃС‚РёР» Р±РѕС‚Р°")

    welcome_text = (
        "рџ‘‹ РџСЂРёРІРµС‚! РЇ РџРѕРјРѕС‰РЅРёРє РџСЂРѕРіСЂР°РјРјРёСЃС‚Р°\n"
        "рџљЂ РЎРѕР·РґР°РЅ Р’Р°РґРёРјРѕРј (vadzim.by)\n\n"
        "рџ’» РџРѕРјРѕРіСѓ СЃ:\n"
        "вЂў РђРЅР°Р»РёР·РѕРј Рё РѕС‚Р»Р°РґРєРѕР№ РєРѕРґР°\n"
        "вЂў РћР±СЉСЏСЃРЅРµРЅРёРµРј РєРѕРЅС†РµРїС†РёР№ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЏ\n"
        "вЂў РћРїС‚РёРјРёР·Р°С†РёРµР№ Рё Р°СЂС…РёС‚РµРєС‚СѓСЂРѕР№ РїСЂРёР»РѕР¶РµРЅРёР№\n"
        "вЂў Р РµС€РµРЅРёРµРј РїСЂРѕР±Р»РµРј Рё РѕС€РёР±РѕРє\n"
        "вЂў РџРµСЂСЃРѕРЅР°Р»СЊРЅС‹Рј РѕР±СѓС‡РµРЅРёРµРј РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЋ\n\n"
        "рџЋЇ РЇ Р°РґР°РїС‚РёСЂСѓСЋСЃСЊ РїРѕРґ РІР°С€ СѓСЂРѕРІРµРЅСЊ Рё СЃС‚РёР»СЊ РѕР±СѓС‡РµРЅРёСЏ!\n"
        "рџ“Љ РСЃРїРѕР»СЊР·СѓР№С‚Рµ РєРЅРѕРїРєРё РґР»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРІСЏР·Рё - СЌС‚Рѕ РїРѕРјРѕРіР°РµС‚ РјРЅРµ СЃС‚Р°РЅРѕРІРёС‚СЊСЃСЏ Р»СѓС‡С€Рµ\n\n"
        "рџ“ќ РџСЂРѕСЃС‚Рѕ РЅР°РїРёС€РёС‚Рµ СЃРІРѕР№ РІРѕРїСЂРѕСЃ РёР»Рё РєРѕРґ!\n\n"
        "вљЎ Р‘С‹СЃС‚СЂС‹Рµ РєРѕРјР°РЅРґС‹:\n"
        "/help - РџРѕР»СѓС‡РёС‚СЊ СЃРїСЂР°РІРєСѓ\n"
        "/settings - РќР°СЃС‚СЂРѕРёС‚СЊ РїСЂРµРґРїРѕС‡С‚РµРЅРёСЏ\n"
        "/about - Рћ СЃРѕР·РґР°С‚РµР»Рµ\n\n"
        "рџ‘‡ РўР°РєР¶Рµ РјРѕР¶РµС‚Рµ РІРѕСЃРїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ РєРЅРѕРїРєР°РјРё РЅРёР¶Рµ:"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_context = get_user_context(user_id)

    settings_text = (
        f"вљ™пёЏ Р’Р°С€Рё РЅР°СЃС‚СЂРѕР№РєРё:\n\n"
        f"рџЋЇ РЈСЂРѕРІРµРЅСЊ: {user_context.skill_level}\n"
        f"рџ“ќ РЎС‚РёР»СЊ РєРѕРґР°: {user_context.preferences['code_style']}\n"
        f"рџ“– РЈСЂРѕРІРµРЅСЊ РѕР±СЉСЏСЃРЅРµРЅРёР№: {user_context.preferences['explanation_level']}\n\n"
        "Р”Р»СЏ РёР·РјРµРЅРµРЅРёСЏ РЅР°РїРёС€РёС‚Рµ:\n"
        "вЂў 'СѓСЃС‚Р°РЅРѕРІРёС‚СЊ СѓСЂРѕРІРµРЅСЊ РЅР°С‡РёРЅР°СЋС‰РёР№/СЃСЂРµРґРЅРёР№/РїСЂРѕРґРІРёРЅСѓС‚С‹Р№'\n"
        "вЂў 'СЃС‚РёР»СЊ РєРѕРґР° РєСЂР°С‚РєРёР№/РїРѕРґСЂРѕР±РЅС‹Р№/РґР»СЏ РЅР°С‡РёРЅР°СЋС‰РёС…'\n"
        "вЂў 'РѕР±СЉСЏСЃРЅРµРЅРёСЏ Р±Р°Р·РѕРІС‹Рµ/СЃСЂРµРґРЅРёРµ/РїСЂРѕРґРІРёРЅСѓС‚С‹Рµ'"
    )

    await update.message.reply_text(settings_text, reply_markup=get_main_keyboard())


# РћР±СЂР°Р±РѕС‚РєР° С‚РµРєСЃС‚Р°
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_context = get_user_context(user_id)

        if not rate_limiter.is_allowed(user_id):
            await update.message.reply_text(
                "вЏ±пёЏ РЎР»РёС€РєРѕРј РјРЅРѕРіРѕ Р·Р°РїСЂРѕСЃРѕРІ! РџРѕРґРѕР¶РґРёС‚Рµ РјРёРЅСѓС‚Сѓ.\n"
                "рџ’Ў Р­С‚Рѕ РїРѕРјРѕРіР°РµС‚ РјРЅРµ Р»СѓС‡С€Рµ РѕР±СЃР»СѓР¶РёРІР°С‚СЊ РІСЃРµС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.",
                reply_markup=get_main_keyboard()
            )
            return

        text = update.message.text

        if not text or len(text.strip()) == 0:
            await update.message.reply_text(
                "рџ¤” РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РЅР°РїРёС€РёС‚Рµ РІР°С€ РІРѕРїСЂРѕСЃ РёР»Рё РєРѕРґ.",
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
                "вљ пёЏ РћР±РЅР°СЂСѓР¶РµРЅС‹ РїСЂРѕР±Р»РµРјС‹ СЃ РєРѕРґРёСЂРѕРІРєРѕР№ СЃРѕРѕР±С‰РµРЅРёСЏ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ.",
                reply_markup=get_main_keyboard()
            )
            return

        text_lower = text.lower()
        if 'СѓСЃС‚Р°РЅРѕРІРёС‚СЊ СѓСЂРѕРІРµРЅСЊ' in text_lower:
            if 'РЅР°С‡РёРЅР°СЋС‰РёР№' in text_lower:
                user_context.skill_level = 'beginner'
                await update.message.reply_text("вњ… РЈСЂРѕРІРµРЅСЊ СѓСЃС‚Р°РЅРѕРІР»РµРЅ: РЅР°С‡РёРЅР°СЋС‰РёР№")
            elif 'СЃСЂРµРґРЅРёР№' in text_lower or 'РїСЂРѕРјРµР¶СѓС‚РѕС‡РЅС‹Р№' in text_lower:
                user_context.skill_level = 'intermediate'
                await update.message.reply_text("вњ… РЈСЂРѕРІРµРЅСЊ СѓСЃС‚Р°РЅРѕРІР»РµРЅ: СЃСЂРµРґРЅРёР№")
            elif 'РїСЂРѕРґРІРёРЅСѓС‚С‹Р№' in text_lower:
                user_context.skill_level = 'advanced'
                await update.message.reply_text("вњ… РЈСЂРѕРІРµРЅСЊ СѓСЃС‚Р°РЅРѕРІР»РµРЅ: РїСЂРѕРґРІРёРЅСѓС‚С‹Р№")
            return

        if 'СЃС‚РёР»СЊ РєРѕРґР°' in text_lower:
            if 'РєСЂР°С‚РєРёР№' in text_lower:
                user_context.preferences['code_style'] = 'concise'
                await update.message.reply_text("вњ… РЎС‚РёР»СЊ РєРѕРґР°: РєСЂР°С‚РєРёР№")
            elif 'РїРѕРґСЂРѕР±РЅС‹Р№' in text_lower:
                user_context.preferences['code_style'] = 'detailed'
                await update.message.reply_text("вњ… РЎС‚РёР»СЊ РєРѕРґР°: РїРѕРґСЂРѕР±РЅС‹Р№")
            elif 'РЅР°С‡РёРЅР°СЋС‰РёС…' in text_lower:
                user_context.preferences['code_style'] = 'beginner'
                await update.message.reply_text("вњ… РЎС‚РёР»СЊ РєРѕРґР°: РґР»СЏ РЅР°С‡РёРЅР°СЋС‰РёС…")
            return

        sensitive_keywords = [
            'РїР°СЂРѕР»СЊ', 'С‚РѕРєРµРЅ', 'РєР»СЋС‡', 'password', 'token', 'key', 'api_key',
            'secret', 'СЃРµРєСЂРµС‚', 'РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ', 'config', 'env', '.env'
        ]

        if any(keyword in text_lower for keyword in sensitive_keywords):
            await update.message.reply_text(
                "рџ”’ РЇ РЅРµ РјРѕРіСѓ РїСЂРµРґРѕСЃС‚Р°РІРёС‚СЊ РґРѕСЃС‚СѓРї Рє РєРѕРЅС„РёРґРµРЅС†РёР°Р»СЊРЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРё.\n\n"
                "Р”Р»СЏ Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё РІСЃРµ РїР°СЂРѕР»Рё Рё С‚РѕРєРµРЅС‹ Р·Р°С‰РёС‰РµРЅС‹.\n"
                "Р•СЃР»Рё РЅСѓР¶РЅР° РїРѕРјРѕС‰СЊ СЃ РЅР°СЃС‚СЂРѕР№РєРѕР№ РєРѕРЅС„РёРіСѓСЂР°С†РёРё, РѕРїРёС€РёС‚Рµ Р·Р°РґР°С‡Сѓ Р±РµР· СѓРєР°Р·Р°РЅРёСЏ СЂРµР°Р»СЊРЅС‹С… РґР°РЅРЅС‹С….",
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
            logger.info(f"рџ“¦ РСЃРїРѕР»СЊР·СѓРµРј РєСЌС€РёСЂРѕРІР°РЅРЅС‹Р№ РѕС‚РІРµС‚ РґР»СЏ {user_id}")
            await update.message.reply_text(
                cached_response + "\n\nрџ’Ў Р‘С‹СЃС‚СЂС‹Р№ РѕС‚РІРµС‚ РёР· РєСЌС€Р°!",
                reply_markup=get_main_keyboard()
            )
            return

        # РЈРІРµР»РёС‡РёРІР°РµРј СЃС‡РµС‚С‡РёРє РІРѕРїСЂРѕСЃРѕРІ
        user_db.increment_questions(user_id)

        if any(word in text_lower for word in ['javascript', 'js', 'РґР¶Р°РІР°СЃРєСЂРёРїС‚']):
            user_db.add_topic_interest(user_id, 'javascript')
            if 'javascript' not in user_context.preferences['favorite_languages']:
                user_context.preferences['favorite_languages'].append('javascript')
        elif any(word in text_lower for word in ['python', 'РїРёС‚РѕРЅ', 'РїР°Р№С‚РѕРЅ']):
            user_db.add_topic_interest(user_id, 'python')
            if 'python' not in user_context.preferences['favorite_languages']:
                user_context.preferences['favorite_languages'].append('python')
        elif any(word in text_lower for word in ['РЅР°Р№РґРё РѕС€РёР±РєСѓ', 'РѕС€РёР±РєР°', 'debug']):
            user_db.add_topic_interest(user_id, 'debugging')
        elif any(word in text_lower for word in ['СЃ С‡РµРіРѕ РЅР°С‡Р°С‚СЊ', 'РЅР°С‡Р°С‚СЊ СѓС‡РёС‚СЊ', 'РѕСЃРЅРѕРІС‹']):
            user_db.add_topic_interest(user_id, 'learning')
            if 'learning_basics' not in user_context.preferences['learning_goals']:
                user_context.preferences['learning_goals'].append('learning_basics')

        user_context.add_message("user", text)

        # Р›РѕРіРёСЂСѓРµРј РІС…РѕРґСЏС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ
        logger.info(f"рџ“Ё РџРѕР»СѓС‡РµРЅРѕ СЃРѕРѕР±С‰РµРЅРёРµ РѕС‚ {user_id}: {text[:100]}...")

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
                "вЏ±пёЏ Р—Р°РїСЂРѕСЃ РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚СЃСЏ СЃР»РёС€РєРѕРј РґРѕР»РіРѕ. РџРѕРїСЂРѕР±СѓР№С‚Рµ СѓРїСЂРѕСЃС‚РёС‚СЊ РІРѕРїСЂРѕСЃ РёР»Рё РїРѕРІС‚РѕСЂРёС‚СЊ РїРѕР·Р¶Рµ.",
                reply_markup=get_main_keyboard()
            )
            return
        except Exception as ai_error:
            logger.error(f"AI handler error for user {user_id}: {ai_error}")
            await update.message.reply_text(
                "рџ¤– Р’СЂРµРјРµРЅРЅС‹Рµ РїСЂРѕР±Р»РµРјС‹ СЃ РР. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ.",
                reply_markup=get_main_keyboard()
            )
            return

        if not response or len(response.strip()) == 0:
            await update.message.reply_text(
                "рџ¤” РќРµ СѓРґР°Р»РѕСЃСЊ СЃС„РѕСЂРјРёСЂРѕРІР°С‚СЊ РѕС‚РІРµС‚. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ.",
                reply_markup=get_main_keyboard()
            )
            return

        if not is_fallback:
            response_cache.set(question_hash, response)
        else:
            logger.info("Skipping cache for fallback response")

        user_context.add_message("assistant", response)

        # Р›РѕРіРёСЂСѓРµРј РѕС‚РІРµС‚
        logger.info(f"рџ“¤ РћС‚РїСЂР°РІР»СЏРµРј РѕС‚РІРµС‚: {response[:100]}...")

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
                formatted_response = convert_markdown_to_html(safe_response)
                await update.message.reply_text(
                    f"✅ <b>Ответ:</b>\n{formatted_response}",
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )


        except Exception as send_error:
            logger.error(f"Message sending error: {send_error}")
            try:
                safe_response = escape_html_chars(response)
                formatted_response = convert_markdown_to_html(safe_response)
                await update.message.reply_text(
                    f"✅ <b>Ответ:</b>\n{formatted_response}",
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )

            except Exception:
                # Final fallback - guaranteed to work
                clean_response = ''.join(c for c in response if ord(c) < 128)  # ASCII only
                await update.message.reply_text(
                    f"вњ… РћС‚РІРµС‚: {clean_response[:1000]}",
                    reply_markup=get_main_keyboard()
                )

    except Exception as e:
        logger.error(f"РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР° РІ handle_message РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ {user_id}: {e}")
        try:
            await update.message.reply_text(
                "вќЊ РџСЂРѕРёР·РѕС€Р»Р° РЅРµРѕР¶РёРґР°РЅРЅР°СЏ РѕС€РёР±РєР°. РќР°С€Р° РєРѕРјР°РЅРґР° СѓРІРµРґРѕРјР»РµРЅР°.\n"
                "РџРѕРїСЂРѕР±СѓР№С‚Рµ:\n"
                "вЂў РџРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ\n"
                "вЂў Р Р°Р·Р±РёС‚СЊ СЃР»РѕР¶РЅС‹Р№ Р·Р°РїСЂРѕСЃ РЅР° С‡Р°СЃС‚Рё\n"
                "вЂў РџРѕРІС‚РѕСЂРёС‚СЊ С‡РµСЂРµР· РЅРµСЃРєРѕР»СЊРєРѕ РјРёРЅСѓС‚",
                reply_markup=get_main_keyboard()
            )
        except Exception as final_error:
            logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ: {final_error}")


# РљРѕРјР°РЅРґР° /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "рџ¤– РџРѕРјРѕС‰РЅРёРє РџСЂРѕРіСЂР°РјРјРёСЃС‚Р° - РЎРѕР·РґР°РЅ Р’Р°РґРёРјРѕРј (vadzim.by)\n\n"
        "рџ“‹ Р”РѕСЃС‚СѓРїРЅС‹Рµ РєРѕРјР°РЅРґС‹:\n"
        "/start - РќР°С‡Р°С‚СЊ СЂР°Р±РѕС‚Сѓ\n"
        "/help - Р­С‚Р° СЃРїСЂР°РІРєР°\n"
        "/settings - РќР°СЃС‚СЂРѕРёС‚СЊ РїСЂРµРґРїРѕС‡С‚РµРЅРёСЏ\n"
        "/about - РРЅС„РѕСЂРјР°С†РёСЏ Рѕ СЃРѕР·РґР°С‚РµР»Рµ\n\n"
        "рџ’Ў Р§С‚Рѕ СЏ СѓРјРµСЋ:\n"
        "вЂў рџ”Ќ РђРЅР°Р»РёР·РёСЂРѕРІР°С‚СЊ РєРѕРґ\n"
        "вЂў рџђ› РџРѕРјРѕРіР°С‚СЊ СЃ РѕС‚Р»Р°РґРєРѕР№\n"
        "вЂў рџ“љ РћР±СЉСЏСЃРЅСЏС‚СЊ РєРѕРЅС†РµРїС†РёРё РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЏ\n"
        "вЂў вљЎ РћРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚СЊ\n"
        "вЂў рџЏ—пёЏ Р”Р°РІР°С‚СЊ СЃРѕРІРµС‚С‹ РїРѕ Р°СЂС…РёС‚РµРєС‚СѓСЂРµ\n"
        "вЂў рџ“љ РџРµСЂСЃРѕРЅР°Р»СЊРЅРѕРµ РѕР±СѓС‡РµРЅРёРµ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЋ\n\n"
        "рџљЂ РџСЂРѕСЃС‚Рѕ РЅР°РїРёС€РёС‚Рµ РІР°С€ РІРѕРїСЂРѕСЃ РёР»Рё РєРѕРґ!\n\n"
        "рџ‘‡ РЎРІСЏР¶РёС‚РµСЃСЊ СЃ СЃРѕР·РґР°С‚РµР»РµРј С‡РµСЂРµР· РєРЅРѕРїРєРё РЅРёР¶Рµ:"
    )
    await update.message.reply_text(
        help_text,
        reply_markup=get_main_keyboard()
    )


# РљРѕРјР°РЅРґР° /about
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "рџ‘ЁвЂЌрџ’» Рћ СЃРѕР·РґР°С‚РµР»Рµ:\n\n"
        "вЂў РРјСЏ: Р’Р°РґРёРј (Vadzim)\n"
        "вЂў РЎР°Р№С‚: vadzim.by\n"
        "вЂў Telegram: @vadzim_belarus\n\n"
        "рџ›  РЎРїРµС†РёР°Р»РёР·Р°С†РёСЏ:\n"
        "вЂў Full-stack СЂР°Р·СЂР°Р±РѕС‚РєР°\n"
        "вЂў Python, JavaScript, Django, React\n"
        "вЂў РЎРѕР·РґР°РЅРёРµ Telegram Р±РѕС‚РѕРІ\n"
        "вЂў Р’РµР±-РїСЂРёР»РѕР¶РµРЅРёСЏ Рё API\n"
        "вЂў Р‘Р°Р·С‹ РґР°РЅРЅС‹С… Рё РѕРїС‚РёРјРёР·Р°С†РёСЏ\n\n"
        "рџЊђ РЈСЃР»СѓРіРё:\n"
        "вЂў Р Р°Р·СЂР°Р±РѕС‚РєР° СЃР°Р№С‚РѕРІ Рё РїСЂРёР»РѕР¶РµРЅРёР№\n"
        "вЂў РЎРѕР·РґР°РЅРёРµ Telegram Р±РѕС‚РѕРІ\n"
        "вЂў РћРїС‚РёРјРёР·Р°С†РёСЏ Рё СЂРµС„Р°РєС‚РѕСЂРёРЅРі РєРѕРґР°\n"
        "вЂў РљРѕРЅСЃСѓР»СЊС‚Р°С†РёРё РїРѕ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЋ\n\n"
        "рџљЂ Р”Р»СЏ СЃРѕС‚СЂСѓРґРЅРёС‡РµСЃС‚РІР° СЃРІСЏР¶РёС‚РµСЃСЊ С‡РµСЂРµР· РєРЅРѕРїРєРё РЅРёР¶Рµ:"
    )
    await update.message.reply_text(
        about_text,
        reply_markup=get_main_keyboard()
    )


# РљРѕРјР°РЅРґР° /stats - СЃС‚Р°С‚РёСЃС‚РёРєР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_context = get_user_context(user_id)
    stats = user_db.get_user_stats(user_id)

    stats_text = (
        f"рџ“Љ Р’Р°С€Р° СЃС‚Р°С‚РёСЃС‚РёРєР°:\n\n"
        f"вќ“ Р’СЃРµРіРѕ РІРѕРїСЂРѕСЃРѕРІ: {stats['total_questions']}\n"
        f"рџЋЇ РЈСЂРѕРІРµРЅСЊ: {user_context.skill_level}\n"
        f"в­ђ РЎСЂРµРґРЅСЏСЏ РѕС†РµРЅРєР°: {sum(user_context.feedback_scores) / len(user_context.feedback_scores):.1f}/5\n" if user_context.feedback_scores else ""
                                                                                                                                                  f"рџ“… РЎ РЅР°РјРё СЃ: {stats['member_since'][:10]}\n\n"
    )

    if stats['favorite_topics']:
        stats_text += "рџ”Ґ Р’Р°С€Рё С‚РµРјС‹:\n"
        for topic in stats['favorite_topics'][-5:]:
            stats_text += f"вЂў {topic}\n"
        stats_text += "\n"

    if user_context.preferences['favorite_languages']:
        stats_text += "рџ’» РР·СѓС‡Р°РµРјС‹Рµ СЏР·С‹РєРё:\n"
        for lang in user_context.preferences['favorite_languages']:
            stats_text += f"вЂў {lang}\n"
    else:
        stats_text += "рџ”Ќ РџРѕРєР° РЅРµС‚ РґР°РЅРЅС‹С… Рѕ РІР°С€РёС… РёРЅС‚РµСЂРµСЃР°С…\n\n"
        stats_text += "рџ’Ў Р—Р°РґР°РІР°Р№С‚Рµ РІРѕРїСЂРѕСЃС‹ РїРѕ РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёСЋ, Рё СЏ Р±СѓРґСѓ РѕС‚СЃР»РµР¶РёРІР°С‚СЊ РІР°С€ РїСЂРѕРіСЂРµСЃСЃ!"

    await update.message.reply_text(
        stats_text,
        reply_markup=get_main_keyboard()
    )


# РљРѕРјР°РЅРґР° /admin - СЃС‚Р°С‚РёСЃС‚РёРєР° РґР»СЏ Р°РґРјРёРЅР° (С‚РѕР»СЊРєРѕ РґР»СЏ СЃРѕР·РґР°С‚РµР»СЏ)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ СЌС‚Рѕ СЃРѕР·РґР°С‚РµР»СЊ Р±РѕС‚Р°
    if username != CREATOR_USERNAME[1:]:  # РЈР±РёСЂР°РµРј @ РёР· РЅР°С‡Р°Р»Р°
        await update.message.reply_text("вќЊ Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰РµРЅ")
        return

    total_users = user_db.get_all_users_count()
    active_users = len(user_db.get_active_users(7))

    admin_text = (
        f"рџ‘‘ РђРґРјРёРЅ РїР°РЅРµР»СЊ\n\n"
        f"рџ‘Ґ Р’СЃРµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№: {total_users}\n"
        f"рџ”Ґ РђРєС‚РёРІРЅС‹С… Р·Р° РЅРµРґРµР»СЋ: {active_users}\n\n"
        f"рџ“€ РЎС‚Р°С‚РёСЃС‚РёРєР° РѕР±РЅРѕРІР»СЏРµС‚СЃСЏ РІ СЂРµР°Р»СЊРЅРѕРј РІСЂРµРјРµРЅРё"
    )

    await update.message.reply_text(admin_text)


# РћР±СЂР°Р±РѕС‚РєР° РѕС€РёР±РѕРє
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"РћС€РёР±РєР°: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "вќЊ РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР°. РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р·.",
                reply_markup=get_main_keyboard()
            )
    except:
        pass


# Р—Р°РїСѓСЃРє Р±РѕС‚Р°
async def bot_runner():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Р”РѕР±Р°РІР»СЏРµРј РѕР±СЂР°Р±РѕС‚С‡РёРєРё
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("settings", settings_command))  # Added settings command
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        application.add_handler(CallbackQueryHandler(button_callback))

        # РћР±СЂР°Р±РѕС‚С‡РёРє РѕС€РёР±РѕРє
        application.add_error_handler(error_handler)

        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        logger.info("рџ¤– Р‘РѕС‚ Р·Р°РїСѓС‰РµРЅ! РЎРѕР·РґР°РЅ Р’Р°РґРёРјРѕРј (vadzim.by)")
        print("рџљЂ Р‘РѕС‚ Р·Р°РїСѓС‰РµРЅ! РЎРѕР·РґР°РЅ Р’Р°РґРёРјРѕРј (vadzim.by)")

        # РџСЂРѕСЃС‚РѕР№ С†РёРєР» РѕР¶РёРґР°РЅРёСЏ
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"РћС€РёР±РєР° Р·Р°РїСѓСЃРєР° Р±РѕС‚Р°: {e}")
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





