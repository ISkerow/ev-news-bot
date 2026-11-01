import config
from parser import NewsParser


def test_brand_in_title():
    assert NewsParser.has_target_brand("BYD launches new Seal EV in Thailand")


def test_brand_in_summary_only():
    """В заголовке только модель, марка — в описании. Такое тоже берём."""
    assert NewsParser.has_target_brand(
        "Denza N8 spotted in regulatory filings",
        "The new SUV from BYD premium brand Denza shows 890 kW setup",
    )


def test_brand_spelling_variants():
    assert NewsParser.has_target_brand("LiXiang i8 deliveries start")
    assert NewsParser.has_target_brand("Li Auto reports record quarter")


def test_brand_case_insensitive():
    assert NewsParser.has_target_brand("zeekr 001 gets a facelift")


def test_news_without_target_brand_is_rejected():
    """Новость про EV вообще, но не про наши марки — в канал автосалона не идёт."""
    assert not NewsParser.has_target_brand(
        "Dems introduce new $15,000 EV tax credit bill",
        "US lawmakers propose a new incentive for electric vehicle buyers",
    )
    assert not NewsParser.has_target_brand("Tesla FSD tested on Bratislava streets")


def test_word_boundaries_hold():
    """«Avatr» не должен ловиться в слове «avatar»."""
    assert not NewsParser.has_target_brand("New avatars for the car app")


def test_empty_brand_list_disables_filter(monkeypatch):
    monkeypatch.setattr(config, "KZ_BRANDS", [])
    assert NewsParser.has_target_brand("Any news at all")


# --- Марки в базе, управляемые командами ---

import pytest
from database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "b.db"))
    await database.init_db()
    return database


async def test_brands_seeded_from_config(db):
    await db.seed_brands(["BYD", "Zeekr"])
    assert await db.get_brands() == ["BYD", "Zeekr"]
    await db.seed_brands(["Tesla"])          # повторный посев игнорируется
    assert "Tesla" not in await db.get_brands()


async def test_add_and_remove_brand(db):
    await db.seed_brands(["BYD"])
    assert await db.add_brand("Leapmotor")
    assert not await db.add_brand("leapmotor")   # дубль в другом регистре
    assert await db.remove_brand("LEAPMOTOR")    # удаляется без учёта регистра
    assert not await db.remove_brand("Nio")      # такой марки не было


async def test_filter_uses_brands_from_database():
    """Фильтр работает по переданному списку, а не по тому, что в config."""
    assert NewsParser.has_target_brand("Leapmotor C10 review", brands=["Leapmotor"])
    assert not NewsParser.has_target_brand("BYD Seal review", brands=["Leapmotor"])


async def test_empty_database_list_disables_filter():
    assert NewsParser.has_target_brand("Any car news", brands=[])
