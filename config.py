import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MANAGER_URL = os.getenv("MANAGER_URL")  # Ссылка под постом; если не задана — пост без кнопки

# Список RSS-источников (InsideEVs, Electrek, CarNewsChina)
RSS_URLS = [
    "https://insideevs.com/rss/articles/all/",
    "https://electrek.co/feed/",
    "https://carnewschina.com/feed/"
]

DB_NAME = "news_production.db"
POST_DELAY = 60