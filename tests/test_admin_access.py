"""Проверка прав: команды управления доступны только владельцу ADMIN_ID.

Тест проходит по всем командам, зарегистрированным в боте, и вызывает каждую
от имени постороннего. Если кто-то добавит новую команду и забудет проверку
прав — этот тест упадёт.
"""
import inspect

import pytest
from aiogram.filters import CommandObject

import config
import main

STRANGER_ID = 999_000_111          # заведомо не админ
PUBLIC = {"start"}                 # приветствие: отвечает всем, ничего не меняет


class FakeUser:
    def __init__(self, uid):
        self.id = uid


class FakeMessage:
    """Запоминает ответы бота вместо отправки в Telegram."""
    def __init__(self, uid):
        self.from_user = FakeUser(uid)
        self.replies = []

    async def answer(self, text, **kwargs):
        self.replies.append(text)
        return None


class CountingDB:
    """Любая попытка что-то изменить здесь будет засчитана."""
    def __init__(self):
        self.writes = 0

    async def add_keyword(self, w): self.writes += 1; return True
    async def remove_keyword(self, w): self.writes += 1; return True
    async def add_source(self, u): self.writes += 1; return True
    async def remove_source(self, u): self.writes += 1; return True
    async def delete_post_from_db(self, u): self.writes += 1
    async def get_keywords(self): return ["byd"]
    async def get_sources(self): return ["https://feed/"]
    async def get_stats(self, *a): return {"total": 1, "today": 1}
    async def get_last_post(self): return {"url": "u", "title": "t", "message_id": 1}


def registered_commands():
    """Все команды бота: имя -> функция-обработчик."""
    found = {}
    for handler in main.router.message.handlers:
        for f in handler.filters or []:
            commands = getattr(f.callback, "commands", None)
            if commands:
                found[commands[0]] = handler.callback
    return found


async def call(handler, message):
    """Вызывает обработчик, подставляя аргументы по его сигнатуре."""
    kwargs = {}
    for name in inspect.signature(handler).parameters:
        if name == "command":
            kwargs[name] = CommandObject(prefix="/", command="x", args="тест")
    return await handler(message, **kwargs)


def test_every_command_is_discovered():
    """Сам тест бесполезен, если он не видит команды — проверяем, что видит."""
    commands = registered_commands()
    assert {"stats", "keywords", "add_kw", "del_kw", "sources", "add_source",
            "del_source", "pause", "resume", "delete_last"} <= set(commands)


@pytest.mark.parametrize("name", sorted(set(registered_commands()) - PUBLIC))
async def test_stranger_gets_nothing(name, monkeypatch):
    """Посторонний не получает данных и не может ничего изменить."""
    db = CountingDB()
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main.queue_manager, "db", db)
    monkeypatch.setattr(config, "ADMIN_ID", 12345)      # админ — не наш гость
    paused_before = main.queue_manager.paused

    message = FakeMessage(STRANGER_ID)
    await call(registered_commands()[name], message)

    assert message.replies == [], f"/{name} ответил постороннему: {message.replies}"
    assert db.writes == 0, f"/{name} изменил данные по запросу постороннего"
    assert main.queue_manager.paused == paused_before, f"/{name} переключил публикацию"


@pytest.mark.parametrize("name", sorted(set(registered_commands()) - PUBLIC))
async def test_admin_is_served(name, monkeypatch):
    """Обратная проверка: владельцу бот отвечает (иначе тест выше ничего не значит)."""
    db = CountingDB()
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main.queue_manager, "db", db)
    monkeypatch.setattr(config, "ADMIN_ID", STRANGER_ID)  # теперь гость — админ

    message = FakeMessage(STRANGER_ID)
    await call(registered_commands()[name], message)

    assert message.replies, f"/{name} не ответил даже админу"
