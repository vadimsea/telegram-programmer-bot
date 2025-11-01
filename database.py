"""Persistent user database helper with optional external storage path."""

from __future__ import annotations

import atexit
import json
import logging
import os
from datetime import datetime, timedelta
from threading import RLock
from typing import Dict, List, Optional

DEFAULT_DB_FILE = "users.json"
ENV_DB_FILE_VAR = "USER_DB_FILE"

logger = logging.getLogger(__name__)


class UserDatabase:
    """Simple JSON-backed storage for user statistics with thread-safety."""

    def __init__(self, db_file: Optional[str] = None) -> None:
        path = (db_file or os.getenv(ENV_DB_FILE_VAR) or DEFAULT_DB_FILE).strip()
        if not path:
            path = DEFAULT_DB_FILE

        if os.path.isdir(path):
            path = os.path.join(path, DEFAULT_DB_FILE)

        directory = os.path.dirname(os.path.abspath(path))
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                logger.error("Failed to create directory for user DB at %s: %s", directory, exc)

        self.db_file = path
        self._lock = RLock()
        self.users_data: Dict[str, Dict] = self._load_data()
        atexit.register(self._save_data)

    def _load_data(self) -> Dict[str, Dict]:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Error loading database %s: %s", self.db_file, exc)
        return {}

    def _save_data(self) -> None:
        with self._lock:
            try:
                with open(self.db_file, "w", encoding="utf-8") as fh:
                    json.dump(self.users_data, fh, ensure_ascii=False, indent=2)
            except OSError as exc:
                logger.error("Error saving database %s: %s", self.db_file, exc)

    def get_user(self, user_id: int) -> Dict:
        user_key = str(user_id)
        with self._lock:
            if user_key not in self.users_data:
                now_iso = datetime.now().isoformat()
                self.users_data[user_key] = {
                    "user_id": user_id,
                    "created_at": now_iso,
                    "preferred_language": None,
                    "skill_level": "intermediate",
                    "total_questions": 0,
                    "favorite_topics": [],
                    "last_active": now_iso,
                }
                self._save_data()
            return self.users_data[user_key]

    def update_user(self, user_id: int, updates: Dict) -> None:
        user_key = str(user_id)
        with self._lock:
            record = self.users_data.get(user_key) or self.get_user(user_id)
            record.update(updates)
            record["last_active"] = datetime.now().isoformat()
            self.users_data[user_key] = record
            self._save_data()

    def increment_questions(self, user_id: int) -> None:
        user_key = str(user_id)
        with self._lock:
            record = self.users_data.get(user_key) or self.get_user(user_id)
            record["total_questions"] = record.get("total_questions", 0) + 1
            record["last_active"] = datetime.now().isoformat()
            self.users_data[user_key] = record
            self._save_data()

    def add_topic_interest(self, user_id: int, topic: str) -> None:
        user_key = str(user_id)
        with self._lock:
            record = self.users_data.get(user_key) or self.get_user(user_id)
            topics = record.setdefault("favorite_topics", [])
            if topic not in topics:
                topics.append(topic)
                record["favorite_topics"] = topics[-10:]  # keep last 10
                logger.info("User %s added topic interest %s", user_id, topic)
            record["last_active"] = datetime.now().isoformat()
            self.users_data[user_key] = record
            self._save_data()

    def get_user_stats(self, user_id: int) -> Dict:
        record = self.get_user(user_id)
        return {
            "total_questions": record.get("total_questions", 0),
            "favorite_topics": record.get("favorite_topics", []),
            "preferred_language": record.get("preferred_language"),
            "skill_level": record.get("skill_level", "intermediate"),
            "member_since": record.get("created_at", "Unknown"),
        }

    def get_all_users_count(self) -> int:
        with self._lock:
            return len(self.users_data)

    def get_active_users(self, days: int = 7) -> List[Dict]:
        cutoff = datetime.now() - timedelta(days=days)
        active: List[Dict] = []
        with self._lock:
            for record in self.users_data.values():
                last_active_str = record.get("last_active")
                try:
                    last_active = datetime.fromisoformat(last_active_str) if last_active_str else None
                except ValueError:
                    last_active = None
                if last_active and last_active > cutoff:
                    active.append(dict(record))
        return active


user_db = UserDatabase()
