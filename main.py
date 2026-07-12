import asyncio
import html
import logging
import sys
from aiogram import Bot, Dispatcher, types, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import Database
from parser import NewsParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("NewsBot")

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

    async def worker(self):
        """Разгребает очередь по одной новости с жестким интервалом."""
        while True:
            if self.paused:
                await asyncio.sleep(5)
                continue
            item = await self.queue.get()
            try:
                if not await self.db.url_exists(item['url']):
                    # Если в RSS не было картинки — пробуем взять og:image со страницы статьи
                    if not item.get('image'):
                        item['image'] = await NewsParser.fetch_og_image(item['url'])

                    title_ru = NewsParser.translate_title(item['title_en'])
                    summary_ru = ""
                    if item.get('summary_en'):
                        summary_ru = NewsParser.translate_title(item['summary_en'])

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

                    # С обложкой — фото-пост; если фото не прошло — обычный текстовый
                    msg = None
                    if item.get('image'):
                        try:
                            msg = await self.bot.send_photo(
                                chat_id=config.CHANNEL_ID,
                                photo=item['image'],
                                caption=text,
                                reply_markup=kb
                            )
                        except Exception as e:
                            logger.warning(f"Фото не отправилось ({e}), публикуем текстом")
                    if msg is None:
                        msg = await self.bot.send_message(
                            chat_id=config.CHANNEL_ID,
                            text=text,
                            reply_markup=kb,
                            disable_web_page_preview=False
                        )

                    await self.db.add_news(item['url'], title_ru, msg.message_id)
                    logger.info(f"✅ Опубликовано: {title_ru}")
            except Exception as e:
                logger.error(f"Ошибка публикации: {e}")
            finally:
                self.queue.task_done()
                # ИСПРАВЛЕНО: Таймер в блоке finally. Интервал выдерживается всегда.
                await asyncio.sleep(config.POST_DELAY)

queue_manager = QueueManager(bot, db)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 Бот запущен. Система автоматизации активна.")

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    stats = await db.get_stats()
    keywords = await db.get_keywords()
    status = "⏸ на паузе" if queue_manager.paused else "▶️ активна"
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего опубликовано: {stats['total']}\n"
        f"Сегодня: {stats['today']}\n"
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
        news = await NewsParser.fetch_rss(keywords)
        added = 0
        for item in news:
            if not await db.url_exists(item['url']):
                await queue_manager.queue.put(item)
                added += 1
        logger.info(f"✅ Найдено новых целевых новостей: {added}")
        await asyncio.sleep(1800)

async def main():
    await db.init_db()
    # Первый запуск: переносим стартовые слова из keywords.json в базу
    await db.seed_keywords(NewsParser.load_keywords())
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