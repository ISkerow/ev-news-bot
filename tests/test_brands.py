import pytest

import config
from database import Database
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


def test_other_brand_in_title_wins_over_ours_in_summary():
    """Случай из канала: новость про Chery прошла, потому что в описании упомянут BYD."""
    assert not NewsParser.has_target_brand(
        "Patent images reveal off-road version of Chery JV kei car",
        "The electric microcar will compete with the BYD Racco",
    )


def test_our_brand_in_title_passes_even_next_to_other():
    """Сравнение «наша против чужой» в заголовке — это новость и про нашу марку."""
    assert NewsParser.has_target_brand("BYD Seal outsells Tesla Model 3 in China")


def test_brand_added_by_command_is_not_treated_as_other():
    """Чужая марка, добавленная в наш список (/add_brand), становится нашей."""
    assert NewsParser.has_target_brand(
        "Leapmotor C16 gets a facelift", brands=["BYD", "Leapmotor"]
    )


def test_word_boundaries_hold():
    """«Avatr» не должен ловиться в слове «avatar»."""
    assert not NewsParser.has_target_brand("New avatars for the car app")


def test_empty_brand_list_disables_filter(monkeypatch):
    monkeypatch.setattr(config, "KZ_BRANDS", [])
    assert NewsParser.has_target_brand("Any news at all")


# --- Марки в базе, управляемые командами ---



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
