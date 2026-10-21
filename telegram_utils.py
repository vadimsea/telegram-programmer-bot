"""Small, dependency-free helpers for the Telegram bot (kept separate so they are easy to test)."""

from __future__ import annotations

import re
from typing import List, Optional

TELEGRAM_SAFE_CHUNK = 3300  # Telegram allows 4096; HTML tags added later need headroom

# ---------------------------------------------------------------- long messages


def split_markdown(text: str, limit: int = TELEGRAM_SAFE_CHUNK) -> List[str]:
    """Split an answer into chunks of at most `limit` chars on line boundaries.

    Fenced code blocks that straddle a boundary are closed at the end of one chunk and reopened
    at the start of the next, so every chunk renders correctly on its own.
    """
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current: List[str] = []
    size = 0
    in_fence = False
    fence_lang = ""
    reserve = 4  # room for the closing "```" appended to a chunk that ends inside a fence

    def flush() -> None:
        nonlocal current, size
        body = "\n".join(current).strip("\n")
        if body.strip():
            chunks.append(body + ("\n```" if in_fence else ""))
        current = [f"```{fence_lang}"] if in_fence else []
        size = sum(len(line) + 1 for line in current)

    for line in text.split("\n"):
        stripped = line.strip()
        pieces = [line[i:i + limit - 20] for i in range(0, len(line), limit - 20)] or [""]
        for piece in pieces:
            if size + len(piece) + 1 > limit - reserve and current:
                flush()
            current.append(piece)
            size += len(piece) + 1
        if stripped.startswith("```"):
            if in_fence:
                in_fence = False
                fence_lang = ""
            else:
                in_fence = True
                fence_lang = stripped[3:].strip()

    body = "\n".join(current).strip("\n")
    if body.strip() and body.strip() != f"```{fence_lang}".strip():
        chunks.append(body)
    return chunks


# -------------------------------------------------------------- secret requests

_EXTRACT_VERBS = (
    r"покажи|показать|дай|дайте|скинь|пришли|назови|выведи|отправь|раскрой|сообщи|скажи|напиши|выдай|слей|"
    r"show|give|send|reveal|print|leak|tell|share|dump|expose|display"
)
_SECRET_NOUNS = (
    r"токен\w*|token\w*|парол\w+|password\w*|api[\s_-]?key\w*|ключ\w*\s+api|секрет\w*|secret\w*|"
    r"\.env|переменн\w+\s+окружения|environment\s+variables?|конфиг\w*\s+бота|credential\w*|учётн\w+\s+данн\w+"
)
_BOT_TARGET = (
    r"твой|твои|твою|твоё|у\s+тебя|бота|этого\s+бота|вашего\s+бота|ваш\s+бот|your|bot'?s|the\s+bot|this\s+bot|"
    r"render|сервер\w*\s+бота"
)
_PROMPT_EXTRACTION = (
    r"(системн\w+\s+(промпт|инструкци\w+|сообщени\w+)|system\s+prompt|твои\s+инструкции|твой\s+промпт|"
    r"your\s+(instructions|prompt)|initial\s+prompt)",
    r"(ignore|forget|disregard)\s+(all\s+|your\s+|the\s+)?(previous|prior|above)\s+(instructions|rules|prompt)",
    r"(игнорируй|забудь|отмени)\s+(все\s+|свои\s+|предыдущие\s+|прошлые\s+)+(инструкции|правила|указания)",
)


def is_secret_extraction(text_lower: str) -> bool:
    """True only when the user tries to get the BOT's secrets or system prompt.

    General programming questions ("how do I store a token in .env", "how to get a dict key")
    must pass: the old keyword filter blocked anything that contained "key", "token", "env"...
    """
    if re.search(rf"\b({_EXTRACT_VERBS})\b.{{0,40}}({_SECRET_NOUNS})", text_lower) and re.search(
        rf"({_BOT_TARGET})", text_lower
    ):
        return True
    return any(re.search(pattern, text_lower) for pattern in _PROMPT_EXTRACTION)


# --------------------------------------------------------------------- files

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json", ".yml", ".yaml", ".toml",
    ".md", ".txt", ".sql", ".sh", ".bat", ".ps1", ".java", ".kt", ".c", ".h", ".cpp", ".cs", ".go",
    ".rs", ".php", ".rb", ".swift", ".vue", ".svelte", ".xml", ".ini", ".cfg", ".env.example", ".log",
}
MAX_DOCUMENT_BYTES = 100 * 1024
MAX_DOCUMENT_CHARS = 9000

DEFAULT_FILE_QUESTION = (
    "Разбери этот файл: коротко объясни, что делает код, найди ошибки и слабые места и предложи, "
    "что улучшить в первую очередь."
)


def code_extension(filename: Optional[str]) -> Optional[str]:
    name = (filename or "").lower()
    for ext in sorted(CODE_EXTENSIONS, key=len, reverse=True):
        if name.endswith(ext):
            return ext
    return None


def build_file_prompt(filename: str, content: str, caption: Optional[str]) -> str:
    ext = (code_extension(filename) or "").lstrip(".")
    lang = {"py": "python", "js": "javascript", "ts": "typescript", "yml": "yaml", "sh": "bash"}.get(ext, ext)
    truncated = len(content) > MAX_DOCUMENT_CHARS
    body = content[:MAX_DOCUMENT_CHARS]
    question = (caption or "").strip() or DEFAULT_FILE_QUESTION
    note = "\n(файл длинный, показано начало)" if truncated else ""
    return f"{question}\n\nФайл {filename}:{note}\n```{lang}\n{body}\n```"
