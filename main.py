import asyncio
import html
import logging
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, types, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramRetryAfter

import config
from database import Database
from parser import NewsParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("NewsBot")

# Часовой пояс для тихих часов; при опечатке в TIMEZONE не падаем, а работаем по UTC
try:
    TZ = ZoneInfo(config.TIMEZONE)
except Exception:
    logging.getLogger("NewsBot").warning(f"Неизвестный часовой пояс «{config.TIMEZONE}», используем UTC")
    TZ = ZoneInfo("UTC")


def today_start_utc() -> str:
    """Начало сегодняшнего дня в TIMEZONE, переведённое в UTC (формат как в базе)."""
    day_start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def is_quiet_now(hour: int = None) -> bool:
    """Сейчас тихие часы? (hour подставляется в тестах)"""
    if config.QUIET is None:
        return False
    if hour is None:
        hour = datetime.now(TZ).hour
    start, end = config.QUIET
    if start <= end:  # дневное окно, например 13-17
        return start <= hour < end
    return hour >= start or hour < end  # окно через полночь, например 23-7


bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
db = Database(config.DB_NAME)

class QueueManager:
    def __init__(self, bot: Bot, db: Database):
        self.queue = asyncio.Queue()
        self.bot = bot
        self.db = db
        self.paused = False
        self._quiet_logged = False
        self._limit_logged = False

    async def _send_post(self, item: dict, text: str, kb):
        """С обложкой — фото-пост, иначе текстовый. Флуд-лимит пробрасываем наверх."""
        if item.get('image'):
            try:
                return await self.bot.send_photo(
                    chat_id=config.CHANNEL_ID,
                    photo=item['image'],
                    caption=text,
                    reply_markup=kb
                )
            except TelegramRetryAfter:
                raise
            except Exception as e:
                logger.warning(f"Фото не отправилось ({e}), публикуем текстом")
        return await self.bot.send_message(
            chat_id=config.CHANNEL_ID,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=False
        )

    async def worker(self):
        """Разгребает очередь по одной новости с жестким интервалом."""
        while True:
            if self.paused:
                await asyncio.sleep(5)
                continue
            if is_quiet_now():
                if not self._quiet_logged:
                    logger.info(f"🌙 Тихие часы ({config.QUIET_HOURS}) — новости копятся в очереди")
                    self._quiet_logged = True
                await asyncio.sleep(60)
                continue
            self._quiet_logged = False
            if config.MAX_POSTS_PER_DAY > 0:
                stats = await self.db.get_stats(today_start_utc())
                if stats['today'] >= config.MAX_POSTS_PER_DAY:
                    if not self._limit_logged:
                        logger.info(f"Дневной лимит ({config.MAX_POSTS_PER_DAY} постов) исчерпан — ждём завтра")
                        self._limit_logged = True
                    await asyncio.sleep(600)
                    continue
                self._limit_logged = False
            item = await self.queue.get()
            attempted = False  # была ли реальная отправка (дубликаты не тормозят очередь)
            try:
                if not await self.db.url_exists(item['url']):
                    attempted = True
                    # Если в RSS не было картинки — пробуем взять og:image со страницы статьи
                    if not item.get('image'):
                        item['image'] = await NewsParser.fetch_og_image(item['url'])

                    # Цепочка: ИИ-рерайт (если настроен) → обычный перевод
                    rewritten = await NewsParser.rewrite_with_ai(
                        item['title_en'], item.get('summary_en', '')
                    )
                    if rewritten:
                        title_ru = rewritten['title']
                        summary_ru = rewritten['summary']
                    else:
                        # Переводчик синхронный (requests) — уводим в поток, чтобы не морозить event loop
                        title_ru = await asyncio.to_thread(NewsParser.translate_title, item['title_en'])
                        summary_ru = ""
                        if item.get('summary_en'):
                            summary_ru = await asyncio.to_thread(NewsParser.translate_title, item['summary_en'])

                    # Кнопка лидогенерации; без MANAGER_URL пост уходит без кнопки
                    kb = None
                    if config.MANAGER_URL:
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚗 Консультация менеджера", url=config.MANAGER_URL)]
                        ])

                    # Экранируем < > & — иначе Telegram отклонит HTML-разметку
                    source = item.get('source', '')
                    parts = [f"<b>{html.escape(title_ru, quote=False)}</b>"]
                    if summary_ru:
                        parts.append(html.escape(summary_ru, quote=False))
                    footer = f"<a href='{item['url']}'>Читать оригинал</a>"
                    if source:
                        footer = f"📰 {source} · {footer}"
                    parts.append(footer)
                    source_tag = ''.join(c for c in source if c.isalnum())
                    parts.append("#EV #AutoNews" + (f" #{source_tag}" if source_tag else ""))
                    text = "\n\n".join(parts)

                    # Флуд-лимит: Telegram сам называет паузу — ждём и повторяем один раз
                    try:
                        msg = await self._send_post(item, text, kb)
                    except TelegramRetryAfter as e:
                        logger.warning(f"Флуд-лимит Telegram: ждём {e.retry_after} сек и повторяем")
                        await asyncio.sleep(e.retry_after + 1)
                        msg = await self._send_post(item, text, kb)

                    await self.db.add_news(item['url'], title_ru, msg.message_id)
                    logger.info(f"✅ Опубликовано: {title_ru}")
            except Exception as e:
                logger.error(f"Ошибка публикации: {e}")
            finally:
                self.queue.task_done()
                # Интервал держим после каждой попытки отправки (успех или ошибка),
                # а пропущенные дубликаты очередь не тормозят
                if attempted:
                    await asyncio.sleep(config.POST_DELAY)

queue_manager = QueueManager(bot, db)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 Бот запущен. Система автоматизации активна.")

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    stats = await db.get_stats(today_start_utc())
    keywords = await db.get_keywords()
    if queue_manager.paused:
        status = "⏸ на паузе"
    elif is_quiet_now():
        status = f"🌙 тихие часы ({config.QUIET_HOURS})"
    else:
        status = "▶️ активна"
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего опубликовано: {stats['total']}\n"
        f"Сегодня: {stats['today']}"
        + (f" из {config.MAX_POSTS_PER_DAY}" if config.MAX_POSTS_PER_DAY else "") + "\n"
        f"В очереди: {queue_manager.queue.qsize()}\n"
        f"Ключевых слов: {len(keywords)}\n"
        f"Публикация: {status}"
    )

@router.message(Command("keywords"))
async def cmd_keywords(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    keywords = await db.get_keywords()
    if not keywords:
        return await message.answer("Список ключевых слов пуст.")
    await message.answer("🔑 Ключевые слова:\n" + ", ".join(keywords))

@router.message(Command("add_kw"))
async def cmd_add_kw(message: types.Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Использование: /add_kw слово или фраза")
    word = command.args.lower().strip()
    if await db.add_keyword(word):
        await message.answer(f"✅ Добавлено: «{word}»")
    else:
        await message.answer(f"«{word}» уже в списке.")

@router.message(Command("del_kw"))
async def cmd_del_kw(message: types.Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Использование: /del_kw слово")
    word = command.args.lower().strip()
    if await db.remove_keyword(word):
        await message.answer(f"🗑 Удалено: «{word}»")
    else:
        await message.answer(f"«{word}» нет в списке.")

@router.message(Command("sources"))
async def cmd_sources(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    sources = await db.get_sources()
    if not sources:
        return await message.answer("Список источников пуст.")
    lines = [f"{i}. {html.escape(u)}" for i, u in enumerate(sources, 1)]
    await message.answer("📰 Источники:\n" + "\n".join(lines), disable_web_page_preview=True)

@router.message(Command("add_source"))
async def cmd_add_source(message: types.Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Использование: /add_source https://site.com/feed/")
    url = command.args.strip()
    if not url.startswith("http"):
        url = "https://" + url
    entries = await NewsParser.check_feed(url)
    if entries is None:
        return await message.answer(
            "⚠️ По этой ссылке не нашлась рабочая RSS-лента — источник не добавлен.\n"
            "Проверьте адрес: обычно лента живёт на /feed/ или /rss/."
        )
    if await db.add_source(url):
        await message.answer(f"✅ Источник добавлен и проверен: лента отдаёт {entries} записей.")
    else:
        await message.answer("Этот источник уже в списке.")

@router.message(Command("del_source"))
async def cmd_del_source(message: types.Message, command: CommandObject):
    if message.from_user.id != config.ADMIN_ID:
        return
    arg = (command.args or "").strip()
    if not arg:
        return await message.answer("Использование: /del_source номер из /sources (или URL целиком)")
    if arg.isdigit():
        sources = await db.get_sources()
        idx = int(arg)
        if not 1 <= idx <= len(sources):
            return await message.answer("Нет источника с таким номером — сверьтесь со /sources.")
        arg = sources[idx - 1]
    if await db.remove_source(arg):
        await message.answer(f"🗑 Источник удалён: {html.escape(arg)}", disable_web_page_preview=True)
    else:
        await message.answer("Такого источника нет в списке.")

@router.message(Command("pause"))
async def cmd_pause(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    queue_manager.paused = True
    await message.answer("⏸ Публикация приостановлена. Новости копятся в очереди.")

@router.message(Command("resume"))
async def cmd_resume(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    queue_manager.paused = False
    await message.answer("▶️ Публикация возобновлена.")

@router.message(Command("delete_last"))
async def cmd_delete_last(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return await message.answer("Нет прав.")

    last_post = await db.get_last_post()
    if not last_post:
        return await message.answer("В базе нет отправленных постов.")

    try:
        await bot.delete_message(chat_id=config.CHANNEL_ID, message_id=last_post["message_id"])
        await db.delete_post_from_db(last_post["url"])
        await message.answer(f"🗑 Успешно удалено:\n{last_post['title']}")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при удалении: {e}")

async def scheduled_parser():
    while True:
        logger.info("🔍 Запуск парсинга RSS...")
        keywords = await db.get_keywords()
        sources = await db.get_sources()
        news = await NewsParser.fetch_rss(keywords, sources)
        added = 0
        for item in news:
            if not await db.url_exists(item['url']):
                await queue_manager.queue.put(item)
                added += 1
        logger.info(f"✅ Найдено новых целевых новостей: {added}")
        await asyncio.sleep(1800)

async def main():
    await db.init_db()
    # Первый запуск: переносим стартовые слова и источники в базу
    await db.seed_keywords(NewsParser.load_keywords())
    await db.seed_sources(config.RSS_URLS)
    dp.include_router(router)
    
    asyncio.create_task(queue_manager.worker())
    asyncio.create_task(scheduled_parser())
    
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")