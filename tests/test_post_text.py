from datetime import datetime, timedelta, timezone

import main


def make_manager():
    return main.QueueManager(bot=None, db=None)


def item(**over):
    base = {
        "url": "https://carnewschina.com/2026/10/29/byd-denza-n8/",
        "title_en": "BYD Denza N8 revealed",
        "source": "CarNewsChina",
        "published": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    base.update(over)
    return base


def test_post_has_title_source_age_and_link():
    qm = make_manager()
    text = qm._build_text(item(), "Представлен BYD Denza N8", "Кроссовер получил три мотора.")
    assert "<b>Представлен BYD Denza N8</b>" in text
    assert "Кроссовер получил три мотора." in text
    assert "📰 CarNewsChina" in text
    assert "2 ч назад" in text
    assert "Читать оригинал" in text
    assert "#EV #AutoNews #CarNewsChina" in text


def test_post_without_summary_is_fine():
    qm = make_manager()
    text = qm._build_text(item(), "Заголовок", "")
    assert "Заголовок" in text and "Читать оригинал" in text


def test_caption_limit_shortens_summary(monkeypatch):
    """Длинное описание ужимается, чтобы подпись влезла в лимит фото."""
    qm = make_manager()
    long_summary = "очень длинное описание новости " * 50
    text = qm._build_text(item(), "Заголовок", long_summary, limit=main.CAPTION_LIMIT)
    assert len(text) <= main.CAPTION_LIMIT
    assert "Заголовок" in text          # заголовок не пострадал
    assert "Читать оригинал" in text    # ссылка на месте
    assert text.count("…") == 1         # описание обрезано по-человечески


def test_no_limit_keeps_full_text():
    """Без фото лимит подписи не действует — текст остаётся полным."""
    qm = make_manager()
    long_summary = "длинное описание " * 60
    text = qm._build_text(item(), "Заголовок", long_summary)
    assert len(text) > main.CAPTION_LIMIT


def test_html_special_chars_are_escaped():
    qm = make_manager()
    text = qm._build_text(item(), "Цена < 30 000 $ & скидка", "Плюс <b>бонус</b>")
    assert "&lt; 30 000 $ &amp;" in text
    assert "&lt;b&gt;бонус&lt;/b&gt;" in text
