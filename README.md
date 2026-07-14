# EV News Bot

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0)
![License](https://img.shields.io/badge/license-MIT-green)

Telegram bot that monitors EV industry news from RSS feeds (InsideEVs, Electrek, CarNewsChina), filters them by keywords, translates titles to Russian, and auto-posts to a Telegram channel — fully unattended.

## Features

- **Resilient fetching** — 3 retries per feed with exponential backoff, 30s timeout, separate handling for timeouts, network errors, and malformed XML. One dead source never blocks the others.
- **Translation fallback chain** — Google Translate → MyMemory → original English title. A translator outage never drops a post.
- **Rich post cards** — cover image (RSS media tags with `og:image` fallback), translated summary, source attribution and hashtags; degrades gracefully to a text post if no image is available.
- **Smart keyword filter** — case-insensitive word-boundary regex, so `ev` matches "EV sales" but not "every" or "level". Keywords are stored in the database and editable from Telegram at runtime — no restart needed.
- **Deduplication** — SQLite (async via `aiosqlite`) keyed by normalized article URL (tracking parameters like `utm_*` are stripped first). Restarts and overlapping feeds never cause reposts.
- **Rate-limited posting queue** — strict 60s interval between posts; if Telegram ever responds with a flood limit, the bot waits exactly as long as Telegram asks and retries.
- **Lead generation** — configurable inline button under every post (link to a manager / order page).
- **Admin tools** — a control panel right in Telegram: `/stats` (posts, queue, filter status), `/keywords`, `/add_kw`, `/del_kw` (manage the filter live), `/sources`, `/add_source`, `/del_source` (manage RSS feeds live — a new feed is validated before it is saved), `/pause` / `/resume` (hold publishing without stopping the bot), `/delete_last` (remove the latest post from the channel and the database).

## How it works

```
RSS feeds ──> keyword filter ──> dedup check ──> queue ──> translate ──> post to channel
   (every 30 min)                  (SQLite)         (1 post / 60 s)
```

## Quick start

```bash
git clone https://github.com/ISkerow/ev-news-bot.git
cd ev-news-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python main.py
```

## Configuration

All secrets are set via environment variables (`.env` is supported):

| Variable      | Required | Description                                                        |
|---------------|----------|--------------------------------------------------------------------|
| `BOT_TOKEN`   | yes      | Bot token from [@BotFather](https://t.me/BotFather)                |
| `CHANNEL_ID`  | yes      | Target channel ID (e.g. `-1001234567890`); the bot must be an admin |
| `ADMIN_ID`    | yes      | Telegram user ID allowed to run admin commands                     |
| `MANAGER_URL` | no       | Link for the inline button under posts; omit to post without a button |
| `DB_PATH`     | no       | Database file location (default `news_production.db`); point it at a mounted volume in production |

Tuning lives in [config.py](config.py): posting interval (`POST_DELAY`), database name. RSS sources and the keyword filter are managed from Telegram at runtime; `RSS_URLS` in [config.py](config.py) and [keywords.json](keywords.json) only seed the initial lists on first run.

## Project structure

```
├── main.py           # entry point: dispatcher, posting queue, parse scheduler
├── parser.py         # RSS fetching with retries, keyword filter, translation chain
├── database.py       # async SQLite layer: deduplication, post log
├── config.py         # env-based configuration
├── keywords.json     # keyword filter (hot-reloaded)
└── requirements.txt
```

## Deployment

The bot uses long polling — no webhooks, ports, or reverse proxy needed. It runs anywhere Python runs: a VPS (`python main.py` under systemd), Railway (deploy as a worker with start command `python main.py`), or Docker.

### Railway

Deploy from this GitHub repo — the `Procfile` provides the start command. Set the environment variables from the table above, attach a volume mounted at `/data`, and set `DB_PATH=/data/news_production.db` so deduplication survives redeploys.

### Docker

```bash
docker build -t ev-news-bot .
docker run -d --name ev-news-bot \
  --env-file .env \
  -e DB_PATH=/data/news_production.db \
  -v ev_news_data:/data \
  --restart unless-stopped \
  ev-news-bot
```

The named volume `ev_news_data` keeps the SQLite database across container restarts and rebuilds.

## License

MIT — see [LICENSE](LICENSE).
