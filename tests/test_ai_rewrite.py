import config
from parser import NewsParser


async def test_rewrite_disabled_without_key(monkeypatch):
    """Ключ не задан → рерайт молча выключен, бот работает по старой цепочке."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert await NewsParser.rewrite_with_ai("Tesla cuts prices", "Some summary") is None
