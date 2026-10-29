import main
from parser import NewsParser


def item(title="BYD now has 1.02 million workers"):
    return {"url": "https://a.com/1", "title_en": title, "summary_en": ""}


def make_manager():
    return main.QueueManager(bot=None, db=None)


async def test_boring_news_is_skipped(monkeypatch):
    """Корпоративная новость не идёт в канал автосалона."""
    monkeypatch.setattr(NewsParser, "is_interesting_for_buyer",
                        staticmethod(lambda *a, **k: _value(False)))
    qm = make_manager()
    assert await qm._is_interesting(item()) is False
    assert "https://a.com/1" in qm.skipped  # второй раз из лент её уже не возьмём


async def test_interesting_news_passes(monkeypatch):
    monkeypatch.setattr(NewsParser, "is_interesting_for_buyer",
                        staticmethod(lambda *a, **k: _value(True)))
    qm = make_manager()
    assert await qm._is_interesting(item("Deepal S07 EREV review")) is True
    assert qm.skipped == set()


async def test_publishes_when_ai_unavailable(monkeypatch):
    """ИИ молчит — лучше опубликовать, чем оставить канал пустым."""
    monkeypatch.setattr(NewsParser, "is_interesting_for_buyer",
                        staticmethod(lambda *a, **k: _value(None)))
    qm = make_manager()
    assert await qm._is_interesting(item()) is True


def test_prompt_covers_both_lists():
    p = NewsParser.INTEREST_PROMPT.lower()
    for word in ("новую модель", "характеристики", "цены на автомобиль", "тест-драйв"):
        assert word in p
    for word in ("финансы", "численность сотрудников", "строительство заводов", "политику"):
        assert word in p


async def _value(v):
    return v
