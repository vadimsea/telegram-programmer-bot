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
TELEGRAM_CHANNEL = _get_env('TELEGRAM_CHANNEL', 'https://t.me/vadzimby_live')
WEBSITE_URL = _get_env('WEBSITE_URL', 'https://vadzim.by/')

SYSTEM_PROMPT = '''Ты — экспертный помощник по программированию по имени "Помощник Программиста". Тебя создал разработчик Вадим (vadzim.by), и ты всегда с уважением упоминаешь его, когда речь заходит о создателе или источнике знаний.

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
