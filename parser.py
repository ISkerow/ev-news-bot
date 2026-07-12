import re
import ssl
import json
import asyncio
import logging
import functools
import aiohttp
import feedparser
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator
import config

logger = logging.getLogger("NewsBot")

# Настройки сети
REQUEST_TIMEOUT = 30   # секунд на один запрос
MAX_ATTEMPTS = 3       # попыток на каждый URL
RETRY_BASE_DELAY = 2   # задержка растёт экспоненциально: 2, 4, 8 сек

# Трекинговые параметры, не влияющие на содержимое страницы
TRACKING_PARAMS = {"fbclid", "gclid", "yclid", "igshid", "mc_cid", "mc_eid", "ref"}


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
    def _clean_url(url: str) -> str:
        """Убирает трекинговые метки (utm_* и пр.) и якорь — иначе одна и та же
        статья с разными метками выглядит для дедупликации как разные."""
        parts = urlparse(url)
        query = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
        ]
        return urlunparse(parts._replace(query=urlencode(query), fragment=""))

    @staticmethod
    def _clean_summary(html: str, limit: int = 200) -> str:
        """Убирает HTML-теги из описания и обрезает до limit символов по слову."""
        text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0] + "…"

    @staticmethod
    def _extract_image(entry) -> str | None:
        """Ищет обложку статьи: media-теги RSS, вложения, затем <img> в тексте."""
        for media in entry.get("media_content", []):
            if media.get("url") and media.get("medium", "image") == "image":
                return media["url"]
        for thumb in entry.get("media_thumbnail", []):
            if thumb.get("url"):
                return thumb["url"]
        for enc in entry.get("enclosures", []):
            if enc.get("href") and enc.get("type", "").startswith("image/"):
                return enc["href"]
        html = ""
        if entry.get("content"):
            html = entry.content[0].get("value", "")
        html = html or entry.get("summary", "")
        img = BeautifulSoup(html, "html.parser").find("img")
        if img and img.get("src"):
            return img["src"]
        return None

    @staticmethod
    async def fetch_og_image(article_url: str) -> str | None:
        """Достаёт обложку (og:image) со страницы статьи — для лент без картинок в RSS."""
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                async with session.get(article_url, ssl=ssl_ctx, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    page = await resp.text()
            tag = BeautifulSoup(page, "html.parser").find("meta", property="og:image")
            if tag and tag.get("content"):
                return tag["content"]
        except Exception as e:
            logger.warning(f"og:image не получен для {article_url}: {e}")
        return None

    @staticmethod
    def _source_name(feed_url: str) -> str:
        """Имя источника по домену; для неизвестных доменов — сам домен."""
        domain = urlparse(feed_url).netloc.removeprefix("www.")
        return config.SOURCE_NAMES.get(domain, domain)

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
    async def fetch_rss(keywords: list = None) -> list:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        headers = {"User-Agent": "Mozilla/5.0"}

        all_items = []
        if keywords is None:
            keywords = NewsParser.load_keywords()  # Фоллбэк: слова из JSON-файла

        async with aiohttp.ClientSession(headers=headers) as session:
            for url in config.RSS_URLS:
                logger.info(f"Парсинг источника: {url}")
                feed = await NewsParser._fetch_feed(session, url, ssl_ctx)
                if feed is None:
                    continue

                source = NewsParser._source_name(url)
                source_items = []
                for entry in feed.entries[:20]:  # Берем последние 20 с каждого сайта
                    if NewsParser.is_relevant(entry.title, keywords):
                        source_items.append({
                            "title_en": entry.title,
                            "url": NewsParser._clean_url(entry.link),
                            "summary_en": NewsParser._clean_summary(entry.get("summary", "")),
                            "image": NewsParser._extract_image(entry),
                            "source": source,
                        })

                all_items.extend(source_items)
                logger.info(f"Найдено {len(source_items)} подходящих новостей на {url}")

        # Разворачиваем, чтобы старые шли первыми в очередь
        return list(reversed(all_items))
