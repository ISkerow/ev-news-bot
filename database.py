import aiosqlite
from datetime import datetime

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
            await db.commit()

    async def url_exists(self, url: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM sent_news WHERE url = ?", (url,))
            return await cursor.fetchone() is not None

    async def add_news(self, url: str, title: str, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO sent_news (url, title, message_id) VALUES (?, ?, ?)",
                             (url, title, message_id))
            await db.commit()

    async def get_last_post(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sent_news ORDER BY posted_at DESC LIMIT 1")
            return await cursor.fetchone()

    async def delete_post_from_db(self, url: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sent_news WHERE url = ?", (url,))
            await db.commit()

    # НОВЫЙ МЕТОД ДЛЯ АДМИНКИ
    async def get_stats(self):
        """Возвращает статистику по базе данных."""
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Всего новостей
            cursor = await db.execute("SELECT COUNT(*) FROM sent_news")
            total_count = (await cursor.fetchone())[0]

            # 2. Новости за сегодня
            today_date = datetime.now().strftime('%Y-%m-%d')
            cursor = await db.execute(
                "SELECT COUNT(*) FROM sent_news WHERE date(posted_at) = ?",
                (today_date,)
            )
            today_count = (await cursor.fetchone())[0]

            return {
                "total": total_count,
                "today": today_count
            }