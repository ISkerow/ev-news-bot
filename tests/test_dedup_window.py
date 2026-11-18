"""Окно поиска той же истории с другого сайта."""

from datetime import datetime, timedelta, timezone

import config
import main


class TitlesDB:
    """Запоминает, с какой даты бот спросил недавние заголовки."""
    def __init__(self):
        self.since = None

    async def get_recent_titles(self, since_utc: str) -> list:
        self.since = datetime.strptime(since_utc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return []


async def test_dedup_looks_back_dedup_window_hours(monkeypatch):
    """Случай из канала: одна история вышла на двух сайтах с разницей в 3 дня.
    Окно по умолчанию — 5 суток, и берётся из настройки, а не из кода."""
    assert config.DEDUP_WINDOW_HOURS >= 72

    db = TitlesDB()
    monkeypatch.setattr(main.queue_manager, "db", db)
    monkeypatch.setattr(config, "DEDUP_WINDOW_HOURS", 100)

    await main.queue_manager._is_duplicate_story({"title_en": "BYD FCB sales pass 600,000"})

    age = datetime.now(timezone.utc) - db.since
    assert timedelta(hours=99) < age < timedelta(hours=101)
