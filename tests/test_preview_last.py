"""Проверки для /preview, /last и /del."""
from datetime import datetime, timedelta, timezone

import pytest
from aiogram.filters import CommandObject

import config
import main
from parser import NewsParser

ADMIN = 555


class FakeMessage:
    def __init__(self, uid=ADMIN, chat_id=777):
        self.from_user = type("U", (), {"id": uid})()
        self.chat = type("C", (), {"id": chat_id})()
        self.replies = []

    async def answer(self, text, **kwargs):
        self.replies.append(text)


class FakeDB:
    def __init__(self, posts=None, known=()):
        self.posts = posts or []
        self.known = set(known)
        self.deleted = []

    async def get_keywords(self): return ["byd"]
    async def get_sources(self): return ["https://feed"]
    async def get_brands(self): return ["BYD"]
    async def url_exists(self, url): return url in self.known
    async def get_recent_posts(self, limit=5): return self.posts[:limit]
    async def delete_post_from_db(self, url): self.deleted.append(url)


def story(url="https://site/1"):
    return {"url": url, "title_en": "BYD Seal 07 arrives", "summary_en": "",
            "image": None, "source": "CarNewsChina",
            "published": datetime.now(timezone.utc) - timedelta(hours=1)}


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ID", ADMIN)
    return FakeMessage()


# --- /preview ---

async def test_preview_sends_to_admin_not_channel(monkeypatch, admin):
    """Предпросмотр уходит в личку админа, в канал ничего не публикуется."""
    monkeypatch.setattr(main, "db", FakeDB())
    monkeypatch.setattr(NewsParser, "fetch_rss", staticmethod(lambda *a, **k: _value([story()])))
    monkeypatch.setattr(main.queue_manager, "render",
                        lambda item: _value(("Заголовок", "текст поста", None)))
    sent = {}

    async def fake_send(item, text, kb, chat_id=None):
        sent["chat_id"] = chat_id
        return None
    monkeypatch.setattr(main.queue_manager, "_send_post", fake_send)

    await main.cmd_preview(admin)

    assert sent["chat_id"] == admin.chat.id          # ушло в личку
    assert sent["chat_id"] != config.CHANNEL_ID      # и точно не в канал
    assert any("не отправлен" in r for r in admin.replies)


async def test_preview_skips_published_news(monkeypatch, admin):
    """Берётся первая неопубликованная новость, а не первая попавшаяся."""
    monkeypatch.setattr(main, "db", FakeDB(known={"https://site/1"}))
    monkeypatch.setattr(NewsParser, "fetch_rss",
                        staticmethod(lambda *a, **k: _value([story("https://site/1"),
                                                             story("https://site/2")])))
    picked = {}
    monkeypatch.setattr(main.queue_manager, "render",
                        lambda item: _record(picked, item))
    monkeypatch.setattr(main.queue_manager, "_send_post",
                        lambda *a, **k: _value(None))

    await main.cmd_preview(admin)
    assert picked["url"] == "https://site/2"


async def test_preview_reports_when_nothing_to_show(monkeypatch, admin):
    monkeypatch.setattr(main, "db", FakeDB())
    monkeypatch.setattr(NewsParser, "fetch_rss", staticmethod(lambda *a, **k: _value([])))
    await main.cmd_preview(admin)
    assert any("нет" in r.lower() for r in admin.replies)


# --- /last и /del ---

def posts(n=3):
    return [{"url": f"https://site/{i}", "title": f"Пост {i}",
             "message_id": 100 + i, "posted_at": "2026-11-01"} for i in range(1, n + 1)]


async def test_last_lists_posts_with_numbers(monkeypatch, admin):
    monkeypatch.setattr(main, "db", FakeDB(posts=posts()))
    await main.cmd_last(admin)
    text = admin.replies[0]
    assert "1. Пост 1" in text and "3. Пост 3" in text
    assert "/del" in text


async def test_del_removes_the_chosen_post(monkeypatch, admin):
    """Удаляется пост с указанным номером, а не последний."""
    db = FakeDB(posts=posts())
    monkeypatch.setattr(main, "db", db)
    deleted_from_channel = {}

    async def fake_delete(chat_id, message_id):
        deleted_from_channel["message_id"] = message_id
    monkeypatch.setattr(main.bot, "delete_message", fake_delete)

    await main.cmd_del(admin, CommandObject(prefix="/", command="del", args="2"))

    assert deleted_from_channel["message_id"] == 102      # второй пост
    assert db.deleted == ["https://site/2"]


async def test_del_rejects_bad_number(monkeypatch, admin):
    db = FakeDB(posts=posts())
    monkeypatch.setattr(main, "db", db)
    await main.cmd_del(admin, CommandObject(prefix="/", command="del", args="99"))
    assert db.deleted == []
    assert any("номером" in r for r in admin.replies)


async def test_del_still_cleans_db_when_channel_delete_fails(monkeypatch, admin):
    """Пост удалили вручную — запись из базы всё равно убираем."""
    db = FakeDB(posts=posts())
    monkeypatch.setattr(main, "db", db)

    async def failing_delete(chat_id, message_id):
        raise RuntimeError("message to delete not found")
    monkeypatch.setattr(main.bot, "delete_message", failing_delete)

    await main.cmd_del(admin, CommandObject(prefix="/", command="del", args="1"))
    assert db.deleted == ["https://site/1"]


async def _value(v):
    return v


async def _record(store, item):
    store["url"] = item["url"]
    return "Заголовок", "текст", None
