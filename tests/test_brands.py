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
