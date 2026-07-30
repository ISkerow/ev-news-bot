from datetime import datetime, timedelta, timezone

import config
from parser import NewsParser


# --- Похожесть заголовков (одна история с разных сайтов) ---

def test_same_story_different_wording():
    a = "Tesla cuts Model 3 prices in China"
    b = "Tesla Model 3 price cut hits China market"
    assert NewsParser.title_similarity(a, b) >= 0.5

def test_unrelated_stories():
    a = "Tesla cuts Model 3 prices in China"
    b = "BYD opens new battery factory in Brazil"
    assert NewsParser.title_similarity(a, b) < 0.5

def test_similarity_empty_input():
    assert NewsParser.title_similarity("", "Tesla news") == 0.0

def test_stop_words_do_not_inflate_similarity():
    """Служебные слова не должны создавать сходство между разными новостями."""
    a = "The new Tesla factory will have more than you say"
    b = "The new BYD sedan will have more than you say"
    assert NewsParser.title_similarity(a, b) < 0.3

def test_same_story_reaches_ai_candidate_threshold():
    """Реальные формулировки одной истории должны попадать на проверку ИИ."""
    pairs = [
        ("Tesla Model Y Gets A Price Cut In China", "Tesla slashes Model Y prices in China again"),
        ("Xiaomi SU7 sets new Nurburgring record", "Xiaomi SU7 Ultra breaks Nurburgring lap record"),
        ("Nio reports record Q2 deliveries", "Nio deliveries hit record in second quarter"),
    ]
    for a, b in pairs:
        assert NewsParser.title_similarity(a, b) >= config.SIMILARITY_CANDIDATE, (a, b)

def test_opposite_verbs_are_lexically_similar():
    """Лексика НЕ различает starts/halts — поэтому нужна ИИ-проверка кандидатов."""
    score = NewsParser.title_similarity(
        "BYD starts production at Brazil plant", "BYD halts production at Brazil plant"
    )
    assert score >= config.SIMILARITY_CANDIDATE  # уйдёт к ИИ, он и отсеет


# --- Фильтр свежести ---

def test_old_news_filtered(monkeypatch):
    monkeypatch.setattr(config, "MAX_NEWS_AGE_HOURS", 24)
    old = datetime.now(timezone.utc) - timedelta(hours=30)
    fresh = datetime.now(timezone.utc) - timedelta(hours=2)
    assert NewsParser.is_too_old(old)
    assert not NewsParser.is_too_old(fresh)

def test_no_date_counts_as_fresh(monkeypatch):
    monkeypatch.setattr(config, "MAX_NEWS_AGE_HOURS", 24)
    assert not NewsParser.is_too_old(None)

def test_age_filter_disabled(monkeypatch):
    monkeypatch.setattr(config, "MAX_NEWS_AGE_HOURS", 0)
    ancient = datetime.now(timezone.utc) - timedelta(days=365)
    assert not NewsParser.is_too_old(ancient)


# --- Дата публикации из RSS-записи ---

def test_parse_published():
    entry = {"published_parsed": (2026, 7, 15, 10, 30, 0, 0, 0, 0)}
    dt = NewsParser._parse_published(entry)
    assert dt == datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc)

def test_parse_published_missing():
    assert NewsParser._parse_published({}) is None
