import aiosqlite
from datetime import datetime, timezone

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sent_news (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    message_id INTEGER,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("CREATE TABLE IF NOT EXISTS keywords (word TEXT PRIMARY KEY)")
            await db.execute("CREATE TABLE IF NOT EXISTS sources (url TEXT PRIMARY KEY)")
            # Миграция для старых баз: колонка появилась позже самой таблицы
            try:
                await db.execute("ALTER TABLE sent_news ADD COLUMN title_en TEXT")
            except aiosqlite.OperationalError:
                pass  # колонка уже есть
            await db.commit()

    # --- Ключевые слова (живут в базе, чтобы переживать редеплой) ---

    async def seed_keywords(self, words: list):
        """Одноразовое заполнение: если таблица пуста, кладём стартовый список."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM keywords")
            if (await cursor.fetchone())[0] == 0 and words:
                await db.executemany(
                    "INSERT OR IGNORE INTO keywords (word) VALUES (?)",
                    [(w.lower().strip(),) for w in words]
                )
                await db.commit()

    async def get_keywords(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT word FROM keywords ORDER BY word")
            return [row[0] for row in await cursor.fetchall()]

    async def add_keyword(self, word: str) -> bool:
        """Возвращает False, если слово уже было в списке."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT OR IGNORE INTO keywords (word) VALUES (?)", (word.lower().strip(),)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def remove_keyword(self, word: str) -> bool:
        """Возвращает False, если такого слова не было."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM keywords WHERE word = ?", (word.lower().strip(),)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def url_exists(self, url: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM sent_news WHERE url = ?", (url,))
            return await cursor.fetchone() is not None

    async def add_news(self, url: str, title: str, message_id: int, title_en: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO sent_news (url, title, message_id, title_en) VALUES (?, ?, ?, ?)",
                (url, title, message_id, title_en))
            await db.commit()

    async def get_recent_titles(self, since_utc: str) -> list:
        """Английские заголовки постов после since_utc — для дедупликации историй."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT title_en FROM sent_news WHERE posted_at >= ? AND title_en IS NOT NULL",
                (since_utc,))
            return [row[0] for row in await cursor.fetchall()]

    async def get_last_post(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # rowid — добивка на случай двух записей в одну секунду
            cursor = await db.execute("SELECT * FROM sent_news ORDER BY posted_at DESC, rowid DESC LIMIT 1")
            return await cursor.fetchone()

    async def delete_post_from_db(self, url: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sent_news WHERE url = ?", (url,))
            await db.commit()

    # --- RSS-источники (тоже в базе — редактируются из Telegram) ---

    async def seed_sources(self, urls: list):
        """Одноразовое заполнение: если таблица пуста, кладём стартовый список."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM sources")
            if (await cursor.fetchone())[0] == 0 and urls:
                await db.executemany(
                    "INSERT OR IGNORE INTO sources (url) VALUES (?)",
                    [(u.strip(),) for u in urls]
                )
                await db.commit()

    async def get_sources(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT url FROM sources ORDER BY url")
            return [row[0] for row in await cursor.fetchall()]

    async def add_source(self, url: str) -> bool:
        """Возвращает False, если источник уже был в списке."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT OR IGNORE INTO sources (url) VALUES (?)", (url.strip(),)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def remove_source(self, url: str) -> bool:
        """Возвращает False, если такого источника не было."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM sources WHERE url = ?", (url.strip(),))
            await db.commit()
            return cursor.rowcount > 0

    # НОВЫЙ МЕТОД ДЛЯ АДМИНКИ
    async def get_stats(self, today_start: str = None):
        """Статистика. today_start — начало «сегодня» в UTC ('YYYY-MM-DD HH:MM:SS'),
        потому что posted_at хранится в UTC; по умолчанию — полночь по UTC."""
        if today_start is None:
            today_start = datetime.now(timezone.utc).strftime('%Y-%m-%d 00:00:00')
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Всего новостей
            cursor = await db.execute("SELECT COUNT(*) FROM sent_news")
            total_count = (await cursor.fetchone())[0]

            # 2. Новости за сегодня
            cursor = await db.execute(
                "SELECT COUNT(*) FROM sent_news WHERE posted_at >= ?",
                (today_start,)
            )
            today_count = (await cursor.fetchone())[0]

            return {
                "total": total_count,
                "today": today_count
            }