import os

# Фейковый токен: в CI нет .env, а main.py при импорте создаёт Bot(token=...).
# setdefault не перекрывает настоящий токен при локальном запуске.
os.environ.setdefault("BOT_TOKEN", "123456789:TEST-TOKEN-ONLY-FOR-CI-aaaaaaaaaaa")
