from datetime import datetime, timedelta, timezone

import config
import main
from parser import NewsParser


def make_manager():
    return main.QueueManager(bot=None, db=None)


def item():
    return {
        "url": "https://carnewschina.com/2026/10/29/li-i6/",
        "title_en": "Li Auto launches Li i6",
        "source": "CarNewsChina",
        "published": datetime.now(timezone.utc) - timedelta(hours=2),
    }


# --- Распознавание цены ---

def test_detects_yuan():
    assert main.mentions_price("Стоимость составляет 249 800 юаней")


def test_detects_dollars():
    assert main.mentions_price("Цена новинки — 24 700 долларов США")
    assert main.mentions_price("Модель оценили в $24,700")


def test_detects_price_in_title():
    assert main.mentions_price("Li i6 вышел в Китае по цене от 239 800 юаней", "")


def test_currency_word_without_amount_is_not_a_price():
    """Просто слово «доллар» без суммы ценой не считаем."""
    assert not main.mentions_price("Компания оценивает спрос в долларовом выражении")


def test_no_price_no_match():
    assert not main.mentions_price("Кроссовер получил три электромотора и полный привод")


# --- Приписка в посте ---

def test_note_added_when_price_present(monkeypatch):
    monkeypatch.setattr(config, "PRICE_NOTE", "ℹ️ Цена указана для рынка Китая.")
    text = make_manager()._build_text(
        item(), "Li i6 представлен", "Стоимость новинки составляет 249 800 юаней."
    )
    assert "ℹ️ Цена указана для рынка Китая." in text
    # Приписка идёт сразу после описания, до строки с источником
    assert text.index("Цена указана") < text.index("CarNewsChina")


def test_no_note_without_price(monkeypatch):
    monkeypatch.setattr(config, "PRICE_NOTE", "ℹ️ Цена указана для рынка Китая.")
    text = make_manager()._build_text(item(), "Li i6 представлен", "Кроссовер получил три мотора.")
    assert "Цена указана" not in text


def test_note_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "PRICE_NOTE", "")
    text = make_manager()._build_text(item(), "Li i6", "Цена — 249 800 юаней.")
    assert "Цена указана" not in text


def test_ai_is_not_asked_to_write_the_note():
    """Приписку ставит код: в промпте её нет и быть не должно."""
    assert "рынка Китая" not in NewsParser.REWRITE_PROMPT
