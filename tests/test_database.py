import pytest
from database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init_db()
    return database


# --- Дедупликация новостей ---

async def test_url_exists_after_add(db):
    assert not await db.url_exists("https://a.com/1")
    await db.add_news("https://a.com/1", "Заголовок", 100)
    assert await db.url_exists("https://a.com/1")

async def test_add_news_duplicate_is_ignored(db):
    await db.add_news("https://a.com/1", "Первый", 100)
    await db.add_news("https://a.com/1", "Дубль", 200)
    last = await db.get_last_post()
    assert last["message_id"] == 100

async def test_get_last_post_and_delete(db):
    await db.add_news("https://a.com/1", "Первый", 100)
    await db.add_news("https://a.com/2", "Второй", 200)
    last = await db.get_last_post()
    assert last["url"] == "https://a.com/2"
    await db.delete_post_from_db("https://a.com/2")
    assert not await db.url_exists("https://a.com/2")

async def test_get_stats_counts(db):
    await db.add_news("https://a.com/1", "Один", 1)
    await db.add_news("https://a.com/2", "Два", 2)
    stats = await db.get_stats()
    assert stats["total"] == 2
    assert stats["today"] == 2

async def test_recent_titles_for_story_dedup(db):
    await db.add_news("https://a.com/1", "Заголовок RU", 1, title_en="Tesla cuts prices")
    await db.add_news("https://a.com/2", "Без английского", 2)  # старый формат, без title_en
    titles = await db.get_recent_titles("2000-01-01 00:00:00")
    assert titles == ["Tesla cuts prices"]

async def test_get_stats_respects_today_start(db):
    await db.add_news("https://a.com/1", "Один", 1)
    stats = await db.get_stats(today_start="2999-01-01 00:00:00")
    assert stats["total"] == 1
    assert stats["today"] == 0  # граница «сегодня» в будущем — за сегодня ничего


# --- Ключевые слова ---

async def test_seed_keywords_once(db):
    await db.seed_keywords(["ev", "Tesla ", "BYD"])
    assert await db.get_keywords() == ["byd", "ev", "tesla"]
    await db.seed_keywords(["мусор"])  # повторный посев игнорируется
    assert "мусор" not in await db.get_keywords()

async def test_add_and_remove_keyword(db):
    assert await db.add_keyword("Zeekr")
    assert not await db.add_keyword("zeekr")   # дубль
    assert await db.remove_keyword("zeekr")
    assert not await db.remove_keyword("nio")  # не было


# --- Источники ---

async def test_seed_sources_once(db):
    await db.seed_sources(["https://a.com/feed/"])
    assert await db.get_sources() == ["https://a.com/feed/"]
    await db.seed_sources(["https://b.com/feed/"])
    assert await db.get_sources() == ["https://a.com/feed/"]

async def test_add_and_remove_source(db):
    assert await db.add_source("https://c.com/feed/")
    assert not await db.add_source("https://c.com/feed/")
    assert await db.remove_source("https://c.com/feed/")
    assert not await db.remove_source("https://x.com/")
