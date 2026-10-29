from datetime import datetime, timedelta, timezone

import config
import main
from parser import NewsParser


def make_manager():
    return main.QueueManager(bot=None, db=None)


def item():
    return {
        "url": "https://carnewschina.com/2026/10/29/byd-denza-n8/",
        "title_en": "BYD Denza N8 revealed",
        "source": "CarNewsChina",
        "published": datetime.now(timezone.utc) - timedelta(hours=2),
    }


def test_cta_is_the_last_line(monkeypatch):
    """Призыв стоит в самом конце — прямо над кнопкой заявки."""
    monkeypatch.setattr(config, "CTA_TEXT", "Напишите нам — подберём комплектацию.")
    text = make_manager()._build_text(item(), "Заголовок", "Описание.")
    assert text.strip().endswith("Напишите нам — подберём комплектацию.")


def test_cta_survives_caption_shortening(monkeypatch):
    """При нехватке места режется описание, а призыв остаётся целым."""
    monkeypatch.setattr(config, "CTA_TEXT", "Напишите нам — подберём комплектацию.")
    long_summary = "очень длинное описание новости " * 50
    text = make_manager()._build_text(item(), "Заголовок", long_summary, limit=main.CAPTION_LIMIT)
    assert len(text) <= main.CAPTION_LIMIT
    assert text.strip().endswith("Напишите нам — подберём комплектацию.")
    assert "Заголовок" in text


def test_empty_cta_leaves_no_blank_tail(monkeypatch):
    monkeypatch.setattr(config, "CTA_TEXT", "")
    text = make_manager()._build_text(item(), "Заголовок", "Описание.")
    assert text.endswith("#CarNewsChina")


def test_prompt_forbids_prices_and_availability():
    """ИИ запрещено писать про цены и наличие в Казахстане — это ответственность салона."""
    prompt = NewsParser.REWRITE_PROMPT.lower()
    for word in ("наличи", "цен", "казахстан", "алматы", "рассрочк"):
        assert word in prompt


def test_prompt_forbids_ai_written_calls_to_action():
    assert "призыв к действию добавляется отдельно" in NewsParser.REWRITE_PROMPT
