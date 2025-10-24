"""
Модуль для управления индивидуальным прогрессом пользователей
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import asyncio
from threading import Lock

logger = logging.getLogger(__name__)

class UserProgressManager:
    """Менеджер прогресса пользователей с оптимизацией для больших групп"""
    
    def __init__(self, progress_file: str = "user_progress.json"):
        self.progress_file = progress_file
        self.progress_data = self.load_progress()
        self.lock = Lock()  # Защита от одновременного доступа
        self.last_activity = {}  # Кэш последней активности
        self.rate_limit = {}  # Защита от спама
        
    def load_progress(self) -> Dict:
        """Загрузить данные о прогрессе пользователей"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки прогресса: {e}")
        return {}
    
    def save_progress(self):
        """Сохранить данные о прогрессе пользователей"""
        try:
            with self.lock:
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")
    
    def is_rate_limited(self, user_id: int, action: str = "lesson") -> bool:
        """Проверить, не превышен ли лимит запросов"""
        now = datetime.now()
        key = f"{user_id}_{action}"
        
        if key not in self.rate_limit:
            self.rate_limit[key] = now
            return False
        
        # Лимит: 1 урок в минуту, 5 уроков в час
        if action == "lesson":
            if now - self.rate_limit[key] < timedelta(minutes=1):
                return True
        elif action == "command":
            if now - self.rate_limit[key] < timedelta(seconds=5):
                return True
        
        self.rate_limit[key] = now
        return False
    
    def get_user_progress(self, user_id: int) -> Dict:
        """Получить прогресс пользователя"""
        with self.lock:
            if str(user_id) not in self.progress_data:
                self.progress_data[str(user_id)] = {
                    "current_lesson": 0,
                    "completed_lessons": [],
                    "started_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat(),
                    "total_lessons_requested": 0,
                    "last_lesson_time": None
                }
                self.save_progress()
            
            return self.progress_data[str(user_id)]
    
    def update_user_progress(self, user_id: int, lesson_index: int, completed: bool = False):
        """Обновить прогресс пользователя"""
        user_data = self.get_user_progress(user_id)
        
        if completed:
            if lesson_index not in user_data["completed_lessons"]:
                user_data["completed_lessons"].append(lesson_index)
        
        user_data["current_lesson"] = lesson_index
        user_data["last_activity"] = datetime.now().isoformat()
        user_data["total_lessons_requested"] = user_data.get("total_lessons_requested", 0) + 1
        user_data["last_lesson_time"] = datetime.now().isoformat()
        
        self.save_progress()
    
    def get_next_lesson(self, user_id: int) -> int:
        """Получить следующий урок для пользователя"""
        user_data = self.get_user_progress(user_id)
        return user_data["current_lesson"]
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        user_data = self.get_user_progress(user_id)
        return {
            "current_lesson": user_data["current_lesson"],
            "completed_count": len(user_data["completed_lessons"]),
            "started_at": user_data["started_at"],
            "last_activity": user_data["last_activity"],
            "total_lessons_requested": user_data.get("total_lessons_requested", 0),
            "last_lesson_time": user_data.get("last_lesson_time")
        }
    
    def reset_user_progress(self, user_id: int):
        """Сбросить прогресс пользователя"""
        with self.lock:
            self.progress_data[str(user_id)] = {
                "current_lesson": 0,
                "completed_lessons": [],
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "total_lessons_requested": 0,
                "last_lesson_time": None
            }
            self.save_progress()
    
    def get_all_users(self) -> List[Dict]:
        """Получить список всех пользователей"""
        users = []
        for user_id, data in self.progress_data.items():
            users.append({
                "user_id": int(user_id),
                "current_lesson": data["current_lesson"],
                "completed_count": len(data["completed_lessons"]),
                "started_at": data["started_at"],
                "last_activity": data["last_activity"],
                "total_lessons_requested": data.get("total_lessons_requested", 0)
            })
        return users
    
    def get_group_stats(self) -> Dict:
        """Получить статистику по всей группе"""
        total_users = len(self.progress_data)
        active_users = 0
        total_lessons = 0
        
        for user_id, data in self.progress_data.items():
            total_lessons += data.get("total_lessons_requested", 0)
            # Активный пользователь - тот, кто был активен в последние 7 дней
            last_activity = datetime.fromisoformat(data["last_activity"])
            if datetime.now() - last_activity < timedelta(days=7):
                active_users += 1
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_lessons_requested": total_lessons,
            "average_lessons_per_user": total_lessons / total_users if total_users > 0 else 0
        }

# Глобальный экземпляр менеджера прогресса
progress_manager = UserProgressManager()