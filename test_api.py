#!/usr/bin/env python3
"""
Скрипт для тестирования API ключей
Запустите: python test_api.py
"""

import asyncio
import aiohttp
import json
from config import (
    GROQ_API_URL, GROQ_API_KEY,
    HUGGING_FACE_API_URL, HUGGING_FACE_TOKEN,
    SYSTEM_PROMPT
)

async def test_groq_api():
    """Тест Groq API"""
    print("🧪 Тестирую Groq API...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gemma2-9b-it",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Привет! Как дела?"}
                ],
                "max_tokens": 100,
                "temperature": 0.7
            }
            
            async with session.post(GROQ_API_URL, headers=headers, json=payload, timeout=30) as response:
                print(f"📡 Статус: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print("✅ Groq API работает!")
                    print(f"📝 Ответ: {data['choices'][0]['message']['content'][:100]}...")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка {response.status}: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

async def test_huggingface_api():
    """Тест HuggingFace API"""
    print("\n🧪 Тестирую HuggingFace API...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {HUGGING_FACE_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": "Привет! Как дела?",
                "parameters": {
                    "max_length": 100,
                    "temperature": 0.7,
                    "do_sample": True
                }
            }
            
            async with session.post(HUGGING_FACE_API_URL, headers=headers, json=payload, timeout=30) as response:
                print(f"📡 Статус: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print("✅ HuggingFace API работает!")
                    if isinstance(data, list) and len(data) > 0:
                        response_text = data[0].get("generated_text", "")
                        print(f"📝 Ответ: {response_text[:100]}...")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка {response.status}: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

async def main():
    """Главная функция"""
    print("🚀 Тестирование API ключей для Telegram бота")
    print("=" * 50)
    
    # Тест Groq
    groq_ok = await test_groq_api()
    
    # Тест HuggingFace
    hf_ok = await test_huggingface_api()
    
    # Результаты
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Groq API: {'✅ РАБОТАЕТ' if groq_ok else '❌ НЕ РАБОТАЕТ'}")
    print(f"HuggingFace API: {'✅ РАБОТАЕТ' if hf_ok else '❌ НЕ РАБОТАЕТ'}")
    
    if groq_ok and hf_ok:
        print("\n🎉 Все API работают! Бот готов к работе!")
    elif groq_ok:
        print("\n⚠️ Только Groq работает. HuggingFace нужно исправить.")
    elif hf_ok:
        print("\n⚠️ Только HuggingFace работает. Groq нужно исправить.")
    else:
        print("\n🚨 Ни один API не работает! Нужно исправить ключи.")
    
    print("\n💡 Смотрите файл API_KEYS_SETUP.md для инструкций по исправлению.")

if __name__ == "__main__":
    asyncio.run(main())
