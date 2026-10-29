from datetime import datetime, timedelta, timezone

import pytest

import main
import parser as parser_module
from parser import NewsParser


class FakeDB:
    """База, которая помнит, что уже «опубликовано»."""
    def __init__(self, known=()):
        self.known = set(known)

    async def init_db(self): pass
    async def seed_keywords(self, words): pass
    async def seed_sources(self, urls): pass
    async def get_keywords(self): return ["byd"]
    async def get_sources(self): return ["https://feed"]
    async def url_exists(self, url): return url in self.known


def news(n):
    return [{
        "url": f"https://site.com/{i}",
        "title_en": f"BYD story {i}",
        "summary_en": "",
        "image": None,
        "source": "CarNewsChina",
        "published": datetime.now(timezone.utc) - timedelta(hours=i),
    } for i in range(n)]


@pytest.fixture
def demo_env(monkeypatch):
    """Подменяет всё внешнее: базу, ленты, отправку и паузы."""
    published = []
    monkeypatch.setattr(main, "DEMO_POST_DELAY", 0)
    monkeypatch.setattr(main.queue_manager, "_is_duplicate_story",
                        lambda item: _async_false())
    monkeypatch.setattr(main.queue_manager, "publish",
                        lambda item: _async_append(published, item))
    monkeypatch.setattr(main.bot, "session", _FakeSession())
    return published


async def _async_false(): return False
async def _async_append(store, item): store.append(item)


class _FakeSession:
    async def close(self): pass


async def test_demo_publishes_requested_count(monkeypatch, demo_env):
    monkeypatch.setattr(main, "db", FakeDB())
    monkeypatch.setattr(NewsParser, "fetch_rss",
                        staticmethod(lambda *a, **k: _async_value(news(10))))
    await main.run_demo(3)
    assert len(demo_env) == 3


async def test_demo_skips_already_published(monkeypatch, demo_env):
    """Новости, которые уже выходили, демо пропускает и берёт следующие."""
    monkeypatch.setattr(main, "db", FakeDB(known={"https://site.com/0", "https://site.com/1"}))
    monkeypatch.setattr(NewsParser, "fetch_rss",
                        staticmethod(lambda *a, **k: _async_value(news(10))))
    await main.run_demo(2)
    assert [i["url"] for i in demo_env] == ["https://site.com/2", "https://site.com/3"]


async def test_demo_survives_shortage_of_news(monkeypatch, demo_env):
    """Просим 5, свежих всего 2 — публикуем сколько есть, без падения."""
    monkeypatch.setattr(main, "db", FakeDB())
    monkeypatch.setattr(NewsParser, "fetch_rss",
                        staticmethod(lambda *a, **k: _async_value(news(2))))
    await main.run_demo(5)
    assert len(demo_env) == 2


async def _async_value(v): return v


def test_retriable_statuses_cover_rate_limit_and_overload():
    """429 — превышен лимит запросов, 503 — модель занята: оба временные."""
    assert parser_module.RETRIABLE_STATUSES == {429, 503}
    assert parser_module.GEMINI_ATTEMPTS >= 2
    assert parser_module.GEMINI_RETRY_DELAY > 0
