from urllib.parse import unquote

import config
import main


def button(kb):
    """Достаёт первую кнопку из клавиатуры."""
    return kb.inline_keyboard[0][0]


def test_whatsapp_button_has_phone_and_ready_message(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "77011234567")
    monkeypatch.setattr(config, "WHATSAPP_MESSAGE", "Здравствуйте! Новость: «{title}». Цена?")
    monkeypatch.setattr(config, "BUTTON_TEXT", "🚗 Узнать цену / Тест-драйв")

    b = button(main.QueueManager._build_keyboard("Представлен BYD Denza N8"))
    assert b.text == "🚗 Узнать цену / Тест-драйв"
    assert b.url.startswith("https://wa.me/77011234567?text=")
    # Заголовок новости подставлен, текст читается после раскодирования
    assert "Новость: «Представлен BYD Denza N8». Цена?" in unquote(b.url)


def test_phone_is_cleaned_of_plus_and_spaces(monkeypatch):
    """Менеджер может записать номер как +7 (701) 123-45-67 — приводим к цифрам."""
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "+7 (701) 123-45-67")
    b = button(main.QueueManager._build_keyboard("Любая новость"))
    assert b.url.startswith("https://wa.me/77011234567?text=")


def test_cyrillic_and_spaces_are_encoded(monkeypatch):
    """В ссылке не должно быть сырых пробелов и кириллицы — Telegram такую не примет."""
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "77011234567")
    monkeypatch.setattr(config, "WHATSAPP_MESSAGE", "Здравствуйте, хочу {title}")
    url = button(main.QueueManager._build_keyboard("Zeekr 001")).url
    assert " " not in url
    assert all(ord(c) < 128 for c in url)


def test_falls_back_to_manager_url(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "")
    monkeypatch.setattr(config, "MANAGER_URL", "https://t.me/manager")
    assert button(main.QueueManager._build_keyboard("Новость")).url == "https://t.me/manager"


def test_no_button_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "")
    monkeypatch.setattr(config, "MANAGER_URL", "")
    assert main.QueueManager._build_keyboard("Новость") is None


# --- Вторая кнопка: Telegram ---

def test_two_buttons_in_one_row(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "77011234567")
    monkeypatch.setattr(config, "TELEGRAM_USERNAME", "ev_manager")
    monkeypatch.setattr(config, "WHATSAPP_MESSAGE", "Новость: {title}")
    kb = main.QueueManager._build_keyboard("Zeekr 001")
    assert len(kb.inline_keyboard) == 1           # один ряд
    assert len(kb.inline_keyboard[0]) == 2        # две кнопки
    wa, tg = kb.inline_keyboard[0]
    assert wa.url.startswith("https://wa.me/77011234567?text=")
    assert tg.url.startswith("https://t.me/ev_manager?text=")
    # Текст заявки одинаковый в обеих кнопках
    assert unquote(wa.url.split("text=")[1]) == unquote(tg.url.split("text=")[1]) == "Новость: Zeekr 001"


def test_username_at_sign_is_stripped(monkeypatch):
    """Ник можно записать как @ev_manager — лишнюю собачку убираем."""
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "")
    monkeypatch.setattr(config, "TELEGRAM_USERNAME", "@ev_manager")
    kb = main.QueueManager._build_keyboard("Новость")
    assert kb.inline_keyboard[0][0].url.startswith("https://t.me/ev_manager?text=")


def test_only_whatsapp_when_username_empty(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "77011234567")
    monkeypatch.setattr(config, "TELEGRAM_USERNAME", "")
    kb = main.QueueManager._build_keyboard("Новость")
    assert len(kb.inline_keyboard[0]) == 1
    assert "wa.me" in kb.inline_keyboard[0][0].url


def test_only_telegram_when_phone_empty(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PHONE", "")
    monkeypatch.setattr(config, "TELEGRAM_USERNAME", "ev_manager")
    kb = main.QueueManager._build_keyboard("Новость")
    assert len(kb.inline_keyboard[0]) == 1
    assert "t.me" in kb.inline_keyboard[0][0].url
