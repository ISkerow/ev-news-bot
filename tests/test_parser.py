from parser import NewsParser


class FakeEntry(dict):
    """Записи feedparser доступны и как dict, и через атрибуты."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


# --- Фильтр по ключевым словам ---

def test_keyword_matches_whole_word():
    assert NewsParser.is_relevant("Tesla cuts EV prices", ["ev"])

def test_keyword_ignores_substring():
    assert not NewsParser.is_relevant("Every level explained", ["ev"])

def test_keyword_case_insensitive():
    assert NewsParser.is_relevant("BYD overtakes rivals", ["byd"])

def test_keyword_multiword_phrase():
    assert NewsParser.is_relevant("Li Auto reports record sales", ["li auto"])

def test_keyword_empty_list():
    assert not NewsParser.is_relevant("Tesla news", [])


# --- Чистка URL для дедупликации ---

def test_clean_url_strips_utm():
    url = "https://electrek.co/2026/07/13/tesla/?utm_source=rss&utm_medium=feed"
    assert NewsParser._clean_url(url) == "https://electrek.co/2026/07/13/tesla/"

def test_clean_url_strips_fbclid_and_fragment():
    url = "https://insideevs.com/news/1/?fbclid=abc#comments"
    assert NewsParser._clean_url(url) == "https://insideevs.com/news/1/"

def test_clean_url_keeps_meaningful_params():
    url = "https://example.com/article?p=987&utm_campaign=x"
    assert NewsParser._clean_url(url) == "https://example.com/article?p=987"

def test_clean_url_untouched_when_clean():
    url = "https://carnewschina.com/2026/07/11/byd-denza-n8/"
    assert NewsParser._clean_url(url) == url


# --- Чистка описания ---

def test_summary_strips_html():
    assert NewsParser._clean_summary("<p>Hello <b>world</b></p>") == "Hello world"

def test_summary_truncates_at_word_boundary():
    text = "word " * 100
    result = NewsParser._clean_summary(text, limit=50)
    assert len(result) <= 51 and result.endswith("…")
    assert not result[:-1].endswith(" wor")  # не режем слово посередине

def test_summary_empty_input():
    assert NewsParser._clean_summary("") == ""
    assert NewsParser._clean_summary(None) == ""


# --- Извлечение картинки ---

def test_image_from_media_content():
    entry = FakeEntry(media_content=[{"url": "https://x.com/a.jpg", "medium": "image"}])
    assert NewsParser._extract_image(entry) == "https://x.com/a.jpg"

def test_image_from_media_thumbnail():
    entry = FakeEntry(media_thumbnail=[{"url": "https://x.com/t.jpg"}])
    assert NewsParser._extract_image(entry) == "https://x.com/t.jpg"

def test_image_from_enclosure():
    entry = FakeEntry(enclosures=[{"href": "https://x.com/e.png", "type": "image/png"}])
    assert NewsParser._extract_image(entry) == "https://x.com/e.png"

def test_image_from_summary_html():
    entry = FakeEntry(summary='<p><img src="https://x.com/s.jpg"></p>')
    assert NewsParser._extract_image(entry) == "https://x.com/s.jpg"

def test_image_missing():
    entry = FakeEntry(summary="<p>no pictures here</p>")
    assert NewsParser._extract_image(entry) is None


# --- Имя источника ---

def test_source_name_known_domain():
    assert NewsParser._source_name("https://insideevs.com/rss/articles/all/") == "InsideEVs"

def test_source_name_strips_www():
    assert NewsParser._source_name("https://www.electrek.co/feed/") == "Electrek"

def test_source_name_unknown_domain_falls_back():
    assert NewsParser._source_name("https://cleantechnica.com/feed/") == "cleantechnica.com"
