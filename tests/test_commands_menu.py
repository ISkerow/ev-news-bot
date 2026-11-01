"""Меню команд: полнота списка и то, что его видит только админ."""
from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault

import config
import main
from test_admin_access import registered_commands


def test_menu_covers_every_command():
    """Каждая команда бота есть в меню — иначе её не найти по «/»."""
    in_menu = {c.command for c in main.ADMIN_COMMANDS}
    missing = set(registered_commands()) - in_menu
    assert not missing, f"нет в меню: {missing}"


def test_menu_has_no_phantom_commands():
    """И наоборот: в меню нет команд, которых бот не понимает."""
    extra = {c.command for c in main.ADMIN_COMMANDS} - set(registered_commands())
    assert not extra, f"в меню лишнее: {extra}"


def test_all_descriptions_are_russian_and_short():
    for c in main.ADMIN_COMMANDS:
        assert c.description, f"/{c.command} без описания"
        assert len(c.description) <= 60, f"/{c.command}: описание слишком длинное"
        assert any("а" <= ch.lower() <= "я" for ch in c.description), \
            f"/{c.command}: описание не на русском"


async def test_menu_is_private_to_admin(monkeypatch):
    """Админу — полный список, всем остальным — пусто."""
    monkeypatch.setattr(config, "ADMIN_ID", 4242)
    calls = []

    async def fake_set(commands, scope=None):
        calls.append((len(commands), scope))
    monkeypatch.setattr(main.bot, "set_my_commands", fake_set)

    await main.setup_commands()

    assert len(calls) == 2
    (default_count, default_scope), (admin_count, admin_scope) = calls
    assert default_count == 0 and isinstance(default_scope, BotCommandScopeDefault)
    assert admin_count == len(main.ADMIN_COMMANDS)
    assert isinstance(admin_scope, BotCommandScopeChat) and admin_scope.chat_id == 4242


async def test_no_menu_without_admin_id(monkeypatch):
    """ADMIN_ID не задан — меню не трогаем, чтобы не открыть его всем."""
    monkeypatch.setattr(config, "ADMIN_ID", 0)
    called = []
    monkeypatch.setattr(main.bot, "set_my_commands",
                        lambda *a, **k: called.append(1))
    await main.setup_commands()
    assert called == []


async def test_startup_survives_telegram_error(monkeypatch):
    """Телеграм не дал выставить меню — бот всё равно запускается."""
    monkeypatch.setattr(config, "ADMIN_ID", 4242)

    async def failing(*a, **k):
        raise RuntimeError("Bad Request: chat not found")
    monkeypatch.setattr(main.bot, "set_my_commands", failing)

    await main.setup_commands()  # не должно выбросить исключение
