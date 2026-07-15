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
