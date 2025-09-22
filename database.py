"""
Простая база данных для хранения пользовательских данных
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UserDatabase:
    """Простая файловая база данных для пользователей"""

    def __init__(self, db_file: str = "users.json"):
        self.db_file = db_file
        self.users_data = self._load_data()

    def _load_data(self) -> Dict:
        """Загрузить данные из файла"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading database: {e}")
                return {}
        return {}

    def _save_data(self):
        """Сохранить данные в файл"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.users_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving database: {e}")

    def get_user(self, user_id: int) -> Dict:
        """Получить данные пользователя"""
        user_key = str(user_id)
        if user_key not in self.users_data:
            self.users_data[user_key] = {
                'user_id': user_id,
                'created_at': datetime.now().isoformat(),
                'preferred_language': None,
                'skill_level': 'intermediate',
                'total_questions': 0,
                'favorite_topics': [],
                'last_active': datetime.now().isoformat()
            }
            self._save_data()

        return self.users_data[user_key]

    def update_user(self, user_id: int, updates: Dict):
        """Обновить данные пользователя"""
        user_data = self.get_user(user_id)
        user_data.update(updates)
        user_data['last_active'] = datetime.now().isoformat()
        self._save_data()

    def increment_questions(self, user_id: int):
        """Увеличить счетчик вопросов"""
        user_data = self.get_user(user_id)
        user_data['total_questions'] += 1
        self._save_data()

    def add_topic_interest(self, user_id: int, topic: str):
        """Добавить интерес к теме"""
        user_data = self.get_user(user_id)
        if 'favorite_topics' not in user_data:
            user_data['favorite_topics'] = []

        if topic not in user_data['favorite_topics']:
            user_data['favorite_topics'].append(topic)
            # Ограничиваем до 10 тем
            if len(user_data['favorite_topics']) > 10:
                user_data['favorite_topics'] = user_data['favorite_topics'][-10:]

            logger.info(f"📝 Пользователь {user_id} проявил интерес к теме: {topic}")

        self._save_data()

    def get_user_stats(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        user_data = self.get_user(user_id)

        return {
            'total_questions': user_data.get('total_questions', 0),
            'favorite_topics': user_data.get('favorite_topics', []),
            'preferred_language': user_data.get('preferred_language'),
            'skill_level': user_data.get('skill_level', 'intermediate'),
            'member_since': user_data.get('created_at', 'Unknown')
        }

    def get_all_users_count(self) -> int:
        """Получить общее количество пользователей"""
        return len(self.users_data)

    def get_active_users(self, days: int = 7) -> List[Dict]:
        """Получить активных пользователей за последние дни"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        active_users = []

        for user_data in self.users_data.values():
            last_active = datetime.fromisoformat(user_data.get('last_active', '2020-01-01'))
            if last_active > cutoff_date:
                active_users.append(user_data)

        return active_users


# Глобальный экземпляр базы данных
user_db = UserDatabase()