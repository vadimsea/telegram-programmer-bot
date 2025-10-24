"""
Скрипт для исправления HTML-тегов в scheduler_course.py
"""

import re

def fix_html_tags():
    """Исправить HTML-теги в файле"""
    
    with open('scheduler_course.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем HTML-теги на обычный текст
    replacements = [
        (r'<([^>]+)>', r'\1'),  # Убираем угловые скобки
        (r'</([^>]+)>', r'/\1'),  # Заменяем закрывающие теги
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Сохраняем исправленный файл
    with open('scheduler_course.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("HTML-теги исправлены!")

if __name__ == "__main__":
    fix_html_tags()
