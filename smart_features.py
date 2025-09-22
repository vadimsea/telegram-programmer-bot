"""
Умные функции для анализа кода и сообщений
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SmartFeatures:
    """Набор интеллектуальных функций для бота"""

    # Расширенный список языков
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

    def detect_language_by_code(self, code: str) -> Optional[str]:
        """Определить язык программирования по ключевым словам или синтаксису"""
        text_lower = code.lower()

        # Сначала ищем по словарю ключевых слов
        for lang, keywords in self.PROGRAMMING_LANGUAGES.items():
            if any(keyword in text_lower for keyword in keywords):
                return lang

        # Определение по синтаксису
        if re.search(r"def\s+\w+\s*\(", code) and ":" in code:
            return "python"
        elif re.search(r"function\s+\w+\s*\(", code) and "{" in code:
            return "javascript"
        elif re.search(r"public\s+class\s+\w+", code):
            return "java"
        elif "#include" in code:
            return "cpp"
        elif re.search(r"SELECT\s+.*\s+FROM", code, re.IGNORECASE):
            return "sql"

        return None

    def analyze_code_quality(self, code: str, language: str) -> Dict[str, any]:
        """Анализ качества кода"""
        lines = code.split("\n")
        non_empty_lines = [l for l in lines if l.strip()]

        metrics = {
            "total_lines": len(lines),
            "code_lines": len(non_empty_lines),
            "avg_line_length": sum(len(l) for l in non_empty_lines) / max(1, len(non_empty_lines)),
            "functions": len(re.findall(r"def\s+\w+|function\s+\w+", code)),
            "classes": len(re.findall(r"class\s+\w+", code)),
            "comments": len(re.findall(r"#.*|//.*|/\*.*?\*/", code)),
            "complexity_score": 0,
            "readability_score": 10.0,
            "issues": [],
            "suggestions": []
        }

        # Простая метрика сложности
        for kw in ["if", "for", "while", "try", "catch", "switch"]:
            metrics["complexity_score"] += len(re.findall(rf"\b{kw}\b", code))

        # Оценка читаемости
        if metrics["avg_line_length"] > 120:
            metrics["readability_score"] -= 2

        # Предупреждения
        if metrics["total_lines"] > 100:
            metrics["issues"].append({
                "type": "warning",
                "message": "Файл слишком большой — стоит разделить на модули"
            })

        if language == "python":
            if re.search(r"except\s*:", code):
                metrics["issues"].append({
                    "type": "error",
                    "message": "Используется голый except — лучше указывать конкретные исключения"
                })
            if "import *" in code:
                metrics["suggestions"].append("⚠️ Избегай import * — импортируй только нужное")
            if "def " in code and not re.search(r'""".*?"""', code, re.DOTALL):
                metrics["suggestions"].append("📝 Добавь docstring к функциям")

        if language == "javascript":
            if "var " in code:
                metrics["suggestions"].append("🔄 Используй let/const вместо var")
            if "==" in code and "===" not in code:
                metrics["suggestions"].append("✅ Используй === для строгого сравнения")

        return metrics


# Экземпляр для использования
smart_features = SmartFeatures()
