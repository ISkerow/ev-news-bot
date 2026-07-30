import config
from parser import NewsParser


async def test_rewrite_disabled_without_key(monkeypatch):
    """Ключ не задан → рерайт молча выключен, бот работает по старой цепочке."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert await NewsParser.rewrite_with_ai("Tesla cuts prices", "Some summary") is None


async def test_same_story_check_disabled_without_key(monkeypatch):
    """Без ключа проверка дублей возвращает None → решает лексический порог."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert await NewsParser.is_same_story("BYD starts production", "BYD halts production") is None


async def test_same_story_parses_verdict(monkeypatch):
    """Ответ модели разбирается в bool; мусор — в None (тогда решает лексика)."""
    async def fake(prompt, max_tokens, temperature=0.1):
        return fake.reply
    monkeypatch.setattr(NewsParser, "_gemini_request", staticmethod(fake))

    fake.reply = '{"same": true}'
    assert await NewsParser.is_same_story("a", "b") is True
    fake.reply = '{"same": false}'
    assert await NewsParser.is_same_story("a", "b") is False
    fake.reply = "не json"
    assert await NewsParser.is_same_story("a", "b") is None
