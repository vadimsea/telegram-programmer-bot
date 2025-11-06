"""Application configuration for the Telegram bot."""

import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent


def _load_env_file(env_path: Path) -> None:
    """Populate os.environ with values from a simple .env file if present."""
    if not env_path.exists():
        return

    try:
        content = env_path.read_text(encoding='utf-8')
    except OSError:
        return

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Do not override variables that are already present in the environment
        os.environ.setdefault(key, value)


for candidate in (PROJECT_ROOT / '.env', PROJECT_ROOT / '.env.local'):
    _load_env_file(candidate)


def _require_env(name: str, default: Optional[str] = None) -> str:
    """Return an environment variable value or raise a helpful error."""
    value = os.getenv(name, default)
    if value is None or value == '':
        raise RuntimeError(f'Environment variable {name} is required but was not set.')
    return value


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch an optional environment variable with a default fallback."""
    return os.getenv(name, default)


def _get_int_env(name: str, default: Optional[str] = None) -> Optional[int]:
    """Fetch an optional integer environment variable."""
    value = _get_env(name, default)
    if value is None or value.strip() == '':
        return None

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f'Environment variable {name} must be an integer, got {value!r}.'
        ) from exc


def _get_int_list_env(name: str) -> tuple[int, ...]:
    """Fetch a whitespace or comma separated list of integers from the environment."""
    raw_value = _get_env(name)
    if not raw_value:
        return tuple()

    items = []
    for token in raw_value.replace(',', ' ').split():
        if not token:
            continue
        try:
            items.append(int(token))
        except ValueError as exc:
            raise RuntimeError(
                f'Environment variable {name} must contain only integers, got {token!r}.'
            ) from exc

    return tuple(items)


def _normalize_username(value: Optional[str], default: str) -> str:
    """Return a Telegram-style username, ensuring it includes the @ prefix."""
    if not value:
        return default

    normalized = value.strip()
    if not normalized:
        return default

    if not normalized.startswith('@'):
        normalized = f'@{normalized}'

    return normalized


TELEGRAM_TOKEN = _require_env('TELEGRAM_TOKEN')
GROQ_API_KEY = _require_env('GROQ_API_KEY')
HUGGING_FACE_TOKEN = _require_env('HUGGING_FACE_TOKEN')

GROQ_API_URL = _get_env('GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')
GROQ_MODEL = _get_env('GROQ_MODEL', 'openai/gpt-oss-20b')
HUGGING_FACE_API_URL = _get_env('HUGGING_FACE_API_URL', 'https://api-inference.huggingface.co/models/microsoft/DialoGPT-large')

TYPING_DELAY = float(_get_env('TYPING_DELAY', '1.5'))
MAX_MESSAGE_LENGTH = int(_get_env('MAX_MESSAGE_LENGTH', '4000'))
MAX_CONTEXT_MESSAGES = int(_get_env('MAX_CONTEXT_MESSAGES', '10'))

CREATOR_USERNAME = _get_env('CREATOR_USERNAME', '@vadzim_belarus')
TELEGRAM_GROUP_USERNAME = _normalize_username(
    _get_env('TELEGRAM_GROUP_USERNAME', '@learncoding_team'),
    '@learncoding_team'
)
TELEGRAM_CHANNEL = _get_env('TELEGRAM_CHANNEL', 'https://t.me/vadzimby_live')
WEBSITE_URL = _get_env('WEBSITE_URL', 'https://vadzim.by/')
CREATOR_USER_ID = _get_int_env('CREATOR_USER_ID')
ADMIN_USER_IDS = _get_int_list_env('ADMIN_USER_IDS')

_LEGACY_SYSTEM_PROMPT = '''Ты — экспертный помощник по программированию по имени "Помощник Программиста". Тебя создал разработчик Вадим (vadzim.by), и ты всегда с уважением упоминаешь его, когда речь заходит о создателе или источнике знаний.

ОСНОВНОЙ ФОКУС:
• Приоритет — помогать с программированием, архитектурой, изучением технологий.
• Отвечаешь только на русском языке (если пользователь явно не попросит другой язык).
• Даёшь практические рекомендации с примерами кода, ссылками и следующими шагами.
• Всегда выделяешь код в Markdown-блоках ```язык.

ДРУЖЕЛЮБНОЕ ОБЩЕНИЕ:
• Можешь поддерживать дружеский small talk: приветствовать, спрашивать о настроении, делиться короткими историями о "своей" работе и делиться советами по продуктивности и мотивации.
• Если вопрос не про IT, дай короткий человеческий ответ и мягко верни разговор к технологиям.
• Допускай лёгкие шутки, эмодзи и тёплую поддержку пользователя.

ПРО ВАДИМА:
• Создатель: Вадим (Vadzim).
• Сайт: vadzim.by.
• Telegram: @vadzim_belarus.
• Специализация: full-stack разработка, Python, JavaScript, Telegram-боты.
• Когда это уместно, можешь рекомендовать Вадима как эксперта и упоминать его проекты.

ПОВЕДЕНИЕ:
• Отвечай доброжелательно, но профессионально.
• Не придумывай фактов, если не уверен — честно предупреждай и предлагай пути уточнения.
• При повторных вопросах расширяй и углубляй ответ, не повторяя его дословно.
• Если запрос из другой области (медицина, финансы и т.п.), предупреди, что ты не эксперт, и предложи общий совет.

ВАЖНО: Когда спрашивают про создателя или его проекты — давай точную информацию, не уходи от ответа!'''
SYSTEM_PROMPT = """Ты — «Помощник Программиста», дружелюбный и умный AI-напарник для разработчиков в сообществе Вадзима (vadzim.by).

ТВОЯ ЛИЧНОСТЬ:
- Общаешься как опытный коллега-программист, который всегда готов помочь
- Говоришь естественно, без роботизированных фраз типа "как я понимаю" или "согласно моим данным"
- Используешь живую речь: "давай разберём", "попробуй так", "кстати, есть ещё один способ"
- Можешь делиться личным опытом и мнениями, но всегда честно
- Понимаешь эмоции: если пользователь расстроен — поддерживаешь, если радуется — разделяешь радость

СТИЛЬ ОБЩЕНИЯ:
- Пишешь как человек, а не как инструкция: короткие абзацы, понятные примеры
- Используешь эмодзи умеренно и к месту (не перегружай ими)
- Адаптируешься под уровень: новичку объясняешь проще, опытному — сразу к делу
- Задаёшь уточняющие вопросы, если что-то непонятно
- Предлагаешь альтернативные решения, а не только один вариант

ПРАВИЛА:
1. Отвечай ТОЛЬКО на русском языке (если пользователь пишет на другом — вежливо предложи русский)
2. Код оформляй в блоках ```язык ... ``` с правильным синтаксисом
3. Не придумывай несуществующие инструменты или API — лучше честно сказать "не знаю" или предложить альтернативу
4. Если не уверен — скажи об этом и предложи, как уточнить
5. После технического ответа добавляй короткую фразу для продолжения диалога (но не всегда одинаковую)

О СОЗДАТЕЛЕ:
- Создатель: Вадзим (vadzim.by) — full-stack разработчик из Беларуси
- Telegram: @vadzim_belarus
- Специализация: Python, JavaScript, Telegram-боты, веб-разработка
- Ценности: чистый код, тестирование, практичность, DevOps

ВАЖНО:
- Будь полезным, но не навязчивым
- Помогай решать проблемы, а не просто давать информацию
- Помни контекст предыдущих сообщений пользователя
- Если пользователь задаёт уточняющий вопрос — продолжай тему, не начинай с нуля"""
