#!/usr/bin/env python3
"""
Универсальный тест моделей для API
Запустите: python test_models.py
"""

import asyncio
import aiohttp
import json
from config import (
    GROQ_API_URL, GROQ_API_KEY,
    HUGGING_FACE_API_URL, HUGGING_FACE_TOKEN,
    SYSTEM_PROMPT
)

# Список популярных моделей Groq для тестирования
GROQ_MODELS = [
    "llama3.1-8b-8192",
    "llama3.1-70b-8192", 
    "openai/gpt-oss-20b",
    "mixtral-8x7b-32768",
    "llama3.1-8b-8192"
]

# Список популярных моделей HuggingFace для тестирования
HF_MODELS = [
    "microsoft/DialoGPT-medium",
    "gpt2",
    "distilgpt2",
    "microsoft/DialoGPT-small",
    "EleutherAI/gpt-neo-125M"
]

async def test_groq_model(session, model_name):
    """Тест конкретной модели Groq"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "Ты помощник. Отвечай кратко."},
                {"role": "user", "content": "Привет"}
            ],
            "max_tokens": 50,
            "temperature": 0.7
        }
        
        async with session.post(GROQ_API_URL, headers=headers, json=payload, timeout=10) as response:
            if response.status == 200:
                return True, f"✅ {model_name} - РАБОТАЕТ"
            else:
                error_text = await response.text()
                return False, f"❌ {model_name} - Ошибка {response.status}: {error_text[:100]}"
                
    except Exception as e:
        return False, f"❌ {model_name} - Исключение: {str(e)[:100]}"

async def test_hf_model(session, model_url):
    """Тест конкретной модели HuggingFace"""
    try:
        headers = {
            "Authorization": f"Bearer {HUGGING_FACE_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": "Привет",
            "parameters": {
                "max_length": 50,
                "temperature": 0.7,
                "do_sample": True
            }
        }
        
        # Формируем полный URL для модели
        full_url = f"https://api-inference.huggingface.co/models/{model_url}"
        
        async with session.post(full_url, headers=headers, json=payload, timeout=10) as response:
            if response.status == 200:
                return True, f"✅ {model_url} - РАБОТАЕТ"
            else:
                error_text = await response.text()
                return False, f"❌ {model_url} - Ошибка {response.status}: {error_text[:100]}"
                
    except Exception as e:
        return False, f"❌ {model_url} - Исключение: {str(e)[:100]}"

async def main():
    """Главная функция"""
    print("🚀 Универсальный тест моделей API")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Тест Groq моделей
        print("\n🧪 ТЕСТИРУЮ GROQ МОДЕЛИ:")
        print("-" * 40)
        
        groq_working = []
        for model in GROQ_MODELS:
            success, message = await test_groq_model(session, model)
            print(message)
            if success:
                groq_working.append(model)
        
        # Тест HuggingFace моделей
        print("\n🧪 ТЕСТИРУЮ HUGGINGFACE МОДЕЛИ:")
        print("-" * 40)
        
        hf_working = []
        for model in HF_MODELS:
            success, message = await test_hf_model(session, model)
            print(message)
            if success:
                hf_working.append(model)
        
        # Результаты
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print(f"Groq: {len(groq_working)}/{len(GROQ_MODELS)} моделей работают")
        print(f"HuggingFace: {len(hf_working)}/{len(HF_MODELS)} моделей работают")
        
        if groq_working:
            print(f"\n✅ РАБОЧИЕ GROQ МОДЕЛИ:")
            for model in groq_working:
                print(f"   • {model}")
        
        if hf_working:
            print(f"\n✅ РАБОЧИЕ HUGGINGFACE МОДЕЛИ:")
            for model in hf_working:
                print(f"   • {model}")
        
        if not groq_working and not hf_working:
            print("\n🚨 НИ ОДНА МОДЕЛЬ НЕ РАБОТАЕТ!")
            print("💡 Проверьте API ключи и доступность сервисов")
        
        print("\n💡 После нахождения рабочих моделей обновите код!")

if __name__ == "__main__":
    asyncio.run(main())
