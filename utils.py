"""
Улучшенные утилиты для бота
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Расширенный список языков программирования
PROGRAMMING_LANGUAGES = {
    'python': ['python', 'py', 'питон', 'пайтон'],
    'javascript': ['javascript', 'js', 'джаваскрипт', 'node'],
    'typescript': ['typescript', 'ts', 'тайпскрипт'],
    'java': ['java', 'джава'],
    'cpp': ['c++', 'cpp', 'c plus plus', 'си плюс плюс'],
    'c': ['c', 'си'],
    'rust': ['rust', 'раст'],
    'go': ['go', 'golang', 'гоу'],
    'php': ['php', 'пхп'],
    'ruby': ['ruby', 'руби'],
    'swift': ['swift', 'свифт'],
    'kotlin': ['kotlin', 'котлин'],
    'sql': ['sql', 'mysql', 'postgresql', 'sqlite'],
    'html': ['html', 'хтмл'],
    'css': ['css', 'стили'],
    'bash': ['bash', 'shell', 'terminal', 'терминал']
}


def extract_programming_language(text: str) -> Optional[str]:
    """Определить язык программирования из текста"""
    text_lower = text.lower()

    for lang, keywords in PROGRAMMING_LANGUAGES.items():
        if any(keyword in text_lower for keyword in keywords):
            return lang

    # Проверяем по синтаксису кода
    if 'def ' in text and ':' in text:
        return 'python'
    elif 'function' in text and '{' in text:
        return 'javascript'
    elif 'public class' in text:
        return 'java'
    elif '#include' in text:
        return 'cpp'

    return None


def is_code_question(text: str) -> bool:
    """Определить является ли вопрос связанным с программированием"""
    programming_indicators = [
        'код', 'функция', 'переменная', 'массив', 'объект', 'класс',
        'алгоритм', 'ошибка', 'баг', 'отладка', 'программа',
        'code', 'function', 'variable', 'array', 'object', 'class',
        'algorithm', 'error', 'bug', 'debug', 'program',
        '```', 'import', 'from', 'def ', 'function', 'var ', 'let ',
        'const ', 'class ', 'interface', 'type', 'struct'
    ]

    text_lower = text.lower()
    return any(indicator in text_lower for indicator in programming_indicators)


def format_code_response(response: str) -> str:
    """Улучшенное форматирование ответа с кодом"""
    if not response:
        return response

    # Улучшаем форматирование блоков кода
    response = re.sub(r'```(\w+)?\n(.*?)\n```', r'```\1\n\2\n```', response, flags=re.DOTALL)

    # Добавляем подсветку синтаксиса для inline кода
    response = re.sub(r'`([^`]+)`', r'`\1`', response)

    # Улучшаем форматирование списков
    response = re.sub(r'\n(\d+)\. ', r'\n\1\. ', response)
    response = re.sub(r'\n- ', r'\n&#8226; ', response)

    return response


def clean_response(response: str) -> str:
    """Очистить ответ от лишних символов"""
    if not response:
        return "🤖 Получен пустой ответ от ИИ"

    # Убираем лишние переносы строк
    response = re.sub(r'\n{3,}', '\n\n', response)

    # Убираем пробелы в начале и конце
    response = response.strip()

    # Проверяем длину
    if len(response) < 10:
        return "🤖 Ответ слишком короткий, попробуйте переформулировать вопрос"

    return response


def split_long_message(text: str, max_length: int = 4000) -> List[str]:
    """Разделить длинное сообщение на части с умным разбиением"""
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # Разбиваем по абзацам
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        # Если абзац слишком длинный, разбиваем по предложениям
        if len(paragraph) > max_length:
            sentences = paragraph.split('. ')
            for sentence in sentences:
                if len(current_part + sentence) > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = sentence + '. '
                    else:
                        # Если даже одно предложение слишком длинное
                        parts.append(sentence[:max_length] + "...")
                else:
                    current_part += sentence + '. '
        else:
            if len(current_part + paragraph) > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
                else:
                    parts.append(paragraph)
            else:
                current_part += paragraph + '\n\n'

    if current_part:
        parts.append(current_part.strip())

    return parts


def analyze_code_complexity(code: str) -> Dict[str, any]:
    """Анализ сложности кода"""
    lines = code.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]

    # Подсчет различных метрик
    metrics = {
        'total_lines': len(lines),
        'code_lines': len(non_empty_lines),
        'functions': len(re.findall(r'def\s+\w+|function\s+\w+', code)),
        'classes': len(re.findall(r'class\s+\w+', code)),
        'comments': len(re.findall(r'#.*|//.*|/\*.*?\*/', code)),
        'complexity_score': 0
    }

    # Простая оценка сложности
    complexity_indicators = ['if', 'for', 'while', 'try', 'catch', 'switch']
    for indicator in complexity_indicators:
        metrics['complexity_score'] += len(re.findall(rf'\b{indicator}\b', code.lower()))

    return metrics


def generate_code_suggestions(code: str, language: str) -> List[str]:
    """Генерация предложений по улучшению кода"""
    suggestions = []

    # Общие проверки
    if len(code.split('\n')) > 50:
        suggestions.append("📏 Функция слишком длинная - рассмотри разбиение на части")

    if language == 'python':
        if 'import *' in code:
            suggestions.append("⚠️ Избегай import * - импортируй только нужные функции")
        if not re.search(r'""".*?"""', code) and 'def ' in code:
            suggestions.append("📝 Добавь docstring к функциям")

    elif language == 'javascript':
        if 'var ' in code:
            suggestions.append("🔄 Используй let/const вместо var")
        if '==' in code and '===' not in code:
            suggestions.append("✅ Используй === для строгого сравнения")

    return suggestions


def log_user_interaction(user_id: int, username: str, message: str, response_length: int):
    """Расширенное логирование взаимодействий"""
    interaction_data = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'username': username,
        'message_length': len(message),
        'response_length': response_length,
        'language': extract_programming_language(message),
        'is_code_related': is_code_question(message)
    }

    logger.info(f"User interaction: {json.dumps(interaction_data)}")


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создать прогресс-бар для длительных операций"""
    filled = int(length * current / total)
    bar = '█' * filled + '░' * (length - filled)
    percentage = int(100 * current / total)
    return f"[{bar}] {percentage}%"


def format_file_info(filename: str, size: int) -> str:
    """Форматировать информацию о файле"""
    size_kb = size / 1024
    if size_kb < 1:
        size_str = f"{size} байт"
    elif size_kb < 1024:
        size_str = f"{size_kb:.1f} КБ"
    else:
        size_str = f"{size_kb / 1024:.1f} МБ"

    return f"📄 **{filename}** ({size_str})"


def detect_code_issues(code: str, language: str) -> List[Dict[str, str]]:
    """Обнаружение потенциальных проблем в коде"""
    issues = []

    # Общие проблемы
    if len(code.split('\n')) > 100:
        issues.append({
            'type': 'warning',
            'message': 'Файл слишком большой - рассмотри разбиение на модули'
        })

    # Специфичные для языка проблемы
    if language == 'python':
        if re.search(r'except:', code):
            issues.append({
                'type': 'error',
                'message': 'Избегай голых except - указывай конкретные исключения'
            })

    elif language == 'javascript':
        if 'eval(' in code:
            issues.append({
                'type': 'security',
                'message': 'Использование eval() небезопасно'
            })

    return issues
