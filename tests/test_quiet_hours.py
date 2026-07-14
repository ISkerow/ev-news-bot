import config
import main
from config import _parse_quiet_hours


# --- Разбор строки из .env ---

def test_parse_night_window():
    assert _parse_quiet_hours("23-7") == (23, 7)

def test_parse_day_window():
    assert _parse_quiet_hours("13-17") == (13, 17)

def test_parse_garbage_disables():
    assert _parse_quiet_hours("мусор") is None
    assert _parse_quiet_hours("23-7-5") is None
    assert _parse_quiet_hours("23") is None


# --- Логика окна ---

def test_window_over_midnight(monkeypatch):
    monkeypatch.setattr(config, "QUIET", (23, 7))
    assert not main.is_quiet_now(22)
    assert main.is_quiet_now(23)
    assert main.is_quiet_now(0)
    assert main.is_quiet_now(6)
    assert not main.is_quiet_now(7)
    assert not main.is_quiet_now(12)

def test_window_daytime(monkeypatch):
    monkeypatch.setattr(config, "QUIET", (13, 17))
    assert not main.is_quiet_now(12)
    assert main.is_quiet_now(13)
    assert main.is_quiet_now(16)
    assert not main.is_quiet_now(17)

def test_disabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "QUIET", None)
    assert not main.is_quiet_now(3)
