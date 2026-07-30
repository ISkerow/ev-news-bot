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

# Красивые имена источников для подписи в посте (домен -> имя)
SOURCE_NAMES = {
    "insideevs.com": "InsideEVs",
    "electrek.co": "Electrek",
    "carnewschina.com": "CarNewsChina",
}

# Путь к базе; на хостинге с volume задаётся через env (например /data/news_production.db)
DB_NAME = os.getenv("DB_PATH", "news_production.db")
POST_DELAY = 60


def _parse_quiet_hours(value: str):
    """Разбирает строку вида "23-7" в пару часов; кривое значение = отключено."""
    try:
        start, end = value.split("-")
        return int(start) % 24, int(end) % 24
    except ValueError:
        return None


# Тихие часы: посты не выходят с QUIET[0]:00 до QUIET[1]:00 по времени TIMEZONE.
# Пусто или не задано — публикуем круглосуточно.
QUIET_HOURS = os.getenv("QUIET_HOURS", "")
QUIET = _parse_quiet_hours(QUIET_HOURS) if QUIET_HOURS else None
TIMEZONE = os.getenv("TIMEZONE", "UTC")  # IANA-имя, например Asia/Almaty

# ИИ-рерайт постов: ключ задан — включён, не задан — обычный перевод
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Дневной лимит постов (по дню в TIMEZONE); 0 или не задано — без лимита
try:
    MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "0"))
except ValueError:
    MAX_POSTS_PER_DAY = 0

# Не публиковать новости старше N часов; 0 — без ограничения
try:
    MAX_NEWS_AGE_HOURS = int(os.getenv("MAX_NEWS_AGE_HOURS", "24"))
except ValueError:
    MAX_NEWS_AGE_HOURS = 24

# Порог схожести заголовков для отсева дублей одной истории (0..1).
# Работает, когда ИИ-проверка недоступна: ниже 0.6 начинает съедать разные
# новости про один бренд ("starts" vs "halts").
try:
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
except ValueError:
    SIMILARITY_THRESHOLD = 0.7

# С какой схожести пара считается кандидатом в дубли и уходит на проверку ИИ.
# Ниже этого лексика уже уверенно говорит «разные новости» — API не дёргаем.
try:
    SIMILARITY_CANDIDATE = float(os.getenv("SIMILARITY_CANDIDATE", "0.3"))
except ValueError:
    SIMILARITY_CANDIDATE = 0.3

# Запас для новостей, которые уже стоят в очереди: сколько лишних часов им прощаем,
# чтобы они не протухали, пока ждут тихих часов или своей минуты в очереди.
try:
    QUEUE_GRACE_HOURS = int(os.getenv("QUEUE_GRACE_HOURS", "12"))
except ValueError:
    QUEUE_GRACE_HOURS = 12
