"""Optional MongoDB summary persistence with bot_scope isolation."""

from typing import Any

from app.config import Settings, get_mongo_client
from app.services.api_keys import get_bot_scope


class SummaryRepository:
    def __init__(self, settings: Settings | None = None, collection: Any = None):
        self._collection = collection
        if self._collection is None:
            resolved_settings = settings or Settings.from_env()
            client = get_mongo_client(
                resolved_settings.mongo_uri,
                timeout_ms=resolved_settings.mongo_timeout_ms,
            )
            if client is not None:
                self._collection = client["bot_database"]["summaries"]

    def save(self, summary_data: dict[str, Any]) -> None:
        if self._collection is None:
            return
        try:
            payload = dict(summary_data)
            payload["bot_scope"] = get_bot_scope()
            self._collection.insert_one(payload)
        except Exception as error:
            print(f"Failed to save summary to MongoDB: {error}")
