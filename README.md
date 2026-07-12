# EV News Bot

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0)
![License](https://img.shields.io/badge/license-MIT-green)

Telegram bot that monitors EV industry news from RSS feeds (InsideEVs, Electrek, CarNewsChina), filters them by keywords, translates titles to Russian, and auto-posts to a Telegram channel — fully unattended.

## Features

- **Resilient fetching** — 3 retries per feed with exponential backoff, 30s timeout, separate handling for timeouts, network errors, and malformed XML. One dead source never blocks the others.
- **Translation fallback chain** — Google Translate → MyMemory → original English title. A translator outage never drops a post.
- **Smart keyword filter** — case-insensitive word-boundary regex, so `ev` matches "EV sales" but not "every" or "level". Keywords live in `keywords.json` and are hot-reloaded each cycle — no restart needed.
- **Deduplication** — SQLite (async via `aiosqlite`) keyed by article URL. Restarts and overlapping feeds never cause reposts.
- **Rate-limited posting queue** — strict 60s interval between posts, safe against Telegram flood limits.
- **Lead generation** — configurable inline button under every post (link to a manager / order page).
- **Admin tools** — `/delete_last` removes the latest post from both the channel and the database.

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

Tuning lives in [config.py](config.py): RSS source list, posting interval (`POST_DELAY`), database name. Keyword filter is edited in [keywords.json](keywords.json) at runtime.

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

## License

MIT — see [LICENSE](LICENSE).
