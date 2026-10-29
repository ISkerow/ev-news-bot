from config import _db_path


def test_db_path_prefers_db_path(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/data/news.db")
    monkeypatch.setenv("DATABASE_URL", "/other/place.db")
    assert _db_path() == "/data/news.db"


def test_db_path_falls_back_to_database_url(monkeypatch):
    """На хостинге переменную назвали DATABASE_URL — понимаем и такое имя."""
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "/data/news_production.db")
    assert _db_path() == "/data/news_production.db"


def test_db_path_understands_sqlite_url(monkeypatch):
    """Запись в стиле SQLAlchemy — достаём из неё путь к файлу."""
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///news.db")
    assert _db_path() == "news.db"


def test_db_path_understands_absolute_sqlite_url(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/news_production.db")
    assert _db_path() == "/data/news_production.db"


def test_db_path_ignores_database_urls(monkeypatch):
    """Адрес чужой СУБД — не путь к нашему файлу, берём значение по умолчанию."""
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    assert _db_path() == "news_production.db"


def test_db_path_default(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _db_path() == "news_production.db"
