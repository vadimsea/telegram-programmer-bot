"""
Модуль для управления индивидуальным прогрессом пользователей
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class UserProgressManager:
    """Менеджер прогресса пользователей"""
    
    def __init__(self, progress_file: str = "user_progress.json"):
        self.progress_file = progress_file
        self.progress_data = self.load_progress()
    
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
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")
    
    def get_user_progress(self, user_id: int) -> Dict:
        """Получить прогресс пользователя"""
        if str(user_id) not in self.progress_data:
            self.progress_data[str(user_id)] = {
                "current_lesson": 0,
                "completed_lessons": [],
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
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
            "last_activity": user_data["last_activity"]
        }
    
    def reset_user_progress(self, user_id: int):
        """Сбросить прогресс пользователя"""
        self.progress_data[str(user_id)] = {
            "current_lesson": 0,
            "completed_lessons": [],
            "started_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
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
                "last_activity": data["last_activity"]
            })
        return users

# Глобальный экземпляр менеджера прогресса
progress_manager = UserProgressManager()
