"""Optional MongoDB summary persistence."""

from datetime import datetime
from typing import Any

from pymongo import MongoClient

from app.config import Settings


class SummaryRepository:
    def __init__(self, settings: Settings):
        self._collection = None
        if settings.mongo_uri:
            client = MongoClient(
                settings.mongo_uri,
                serverSelectionTimeoutMS=settings.mongo_timeout_ms,
                connectTimeoutMS=settings.mongo_timeout_ms,
            )
            self._collection = client["bot_database"]["summaries"]

    def save(self, summary_data: dict[str, Any]) -> None:
        if self._collection is None:
            return
        try:
            self._collection.insert_one(summary_data)
        except Exception as error:
            print(f"Failed to save summary to MongoDB: {error}")
