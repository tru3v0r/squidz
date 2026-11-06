from unittest.mock import Mock

import pytest

from squidz.infra import windows


def test_open_keyboard_uses_windows_shell_to_launch_keyboard(tmp_path, monkeypatch):
    keyboard = tmp_path / "Windows" / "System32" / "osk.exe"
    keyboard.parent.mkdir(parents=True)
    keyboard.touch()
    startfile = Mock()
    monkeypatch.setenv("WINDIR", str(tmp_path / "Windows"))
    monkeypatch.setattr(windows.os, "startfile", startfile)

    windows.open_keyboard()

    startfile.assert_called_once_with(str(keyboard))


def test_open_keyboard_reports_missing_windows_keyboard(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDIR", str(tmp_path))
    startfile = Mock()
    monkeypatch.setattr(windows.os, "startfile", startfile)

    with pytest.raises(FileNotFoundError, match="Windows on-screen keyboard not found"):
        windows.open_keyboard()
    startfile.assert_not_called()
