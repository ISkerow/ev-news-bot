import re
import ssl
import json
import asyncio
import logging
import functools
import aiohttp
import feedparser
from deep_translator import GoogleTranslator, MyMemoryTranslator
import config

logger = logging.getLogger("NewsBot")

# Настройки сети
REQUEST_TIMEOUT = 30   # секунд на один запрос
MAX_ATTEMPTS = 3       # попыток на каждый URL
RETRY_BASE_DELAY = 2   # задержка растёт экспоненциально: 2, 4, 8 сек


class NewsParser:
    @staticmethod
    def load_keywords() -> list:
        """Загружает ключевые слова из JSON файла."""
        try:
            with open("keywords.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("keywords", [])
        except Exception as e:
            logger.error(f"Ошибка загрузки keywords.json: {e}")
            # Резервный список, если файл потерян
            return ["ev", "tesla", "byd"]

    @staticmethod
    def translate_title(text: str) -> str:
        # Основной переводчик — Google Translate
        try:
            result = GoogleTranslator(source="auto", target="ru").translate(text)
            if result:
                logger.info("Перевод выполнен через Google Translate")
                return result
            logger.warning("Google Translate вернул пустой результат")
        except Exception as e:
            logger.warning(f"Google Translate не сработал: {e}")

        # Запасной переводчик — MyMemory (не умеет auto, источники англоязычные)
        try:
            result = MyMemoryTranslator(source="english", target="russian").translate(text)
            if result:
                logger.info("Перевод выполнен через MyMemory (fallback)")
                return result
            logger.warning("MyMemory вернул пустой результат")
        except Exception as e:
            logger.warning(f"MyMemory не сработал: {e}")

        # Оба переводчика упали — публикуем оригинал, чтобы не терять новость
        logger.error(f"Перевод не удался, публикуем оригинал: {text}")
        return text

    @staticmethod
    @functools.lru_cache(maxsize=8)
    def _build_pattern(keywords: tuple) -> re.Pattern:
        """Собирает один regex из всех ключевых слов с границами слов."""
        escaped = (re.escape(kw) for kw in keywords if kw.strip())
        return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)

    @staticmethod
    def is_relevant(title: str, keywords: list) -> bool:
        if not keywords:
            return False
        # Границы слов: "ev" совпадёт в "EV sales", но не в "every" или "level"
        return bool(NewsParser._build_pattern(tuple(keywords)).search(title))

    @staticmethod
    async def _fetch_feed(session: aiohttp.ClientSession, url: str, ssl_ctx: ssl.SSLContext):
        """Скачивает и парсит RSS с ретраями. Возвращает feed или None."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with session.get(url, ssl=ssl_ctx, timeout=REQUEST_TIMEOUT) as response:
                    if response.status != 200:
                        logger.warning(
                            f"[{url}] статус {response.status} (попытка {attempt}/{MAX_ATTEMPTS})"
                        )
                        raise aiohttp.ClientResponseError(
                            response.request_info, response.history,
                            status=response.status, message="bad status",
                        )
                    content = await response.text()

                feed = feedparser.parse(content)
                # feedparser не бросает исключений — проверяем флаг bozo
                if feed.bozo and not feed.entries:
                    logger.warning(
                        f"[{url}] невалидный XML: {feed.bozo_exception} (попытка {attempt}/{MAX_ATTEMPTS})"
                    )
                else:
                    return feed

            except asyncio.TimeoutError:
                logger.warning(f"[{url}] таймаут {REQUEST_TIMEOUT} сек (попытка {attempt}/{MAX_ATTEMPTS})")
            except aiohttp.ClientError as e:
                logger.warning(f"[{url}] сетевая ошибка: {e} (попытка {attempt}/{MAX_ATTEMPTS})")
            except Exception as e:
                logger.error(f"[{url}] неожиданная ошибка: {e} (попытка {attempt}/{MAX_ATTEMPTS})")

            if attempt < MAX_ATTEMPTS:
                delay = RETRY_BASE_DELAY ** attempt  # 2, 4 сек между попытками
                await asyncio.sleep(delay)

        logger.error(f"[{url}] источник недоступен после {MAX_ATTEMPTS} попыток, пропускаем")
        return None

    @staticmethod
    async def fetch_rss() -> list:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        headers = {"User-Agent": "Mozilla/5.0"}

        all_items = []
        keywords = NewsParser.load_keywords()  # Загружаем свежие фильтры

        async with aiohttp.ClientSession(headers=headers) as session:
            for url in config.RSS_URLS:
                logger.info(f"Парсинг источника: {url}")
                feed = await NewsParser._fetch_feed(session, url, ssl_ctx)
                if feed is None:
                    continue

                source_items = []
                for entry in feed.entries[:20]:  # Берем последние 20 с каждого сайта
                    if NewsParser.is_relevant(entry.title, keywords):
                        source_items.append({
                            "title_en": entry.title,
                            "url": entry.link
                        })

                all_items.extend(source_items)
                logger.info(f"Найдено {len(source_items)} подходящих новостей на {url}")

        # Разворачиваем, чтобы старые шли первыми в очередь
        return list(reversed(all_items))
