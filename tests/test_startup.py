import sys
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from squidz.core.models import Settings
from squidz.infra import startup


def test_startup_command_uses_package_entrypoint_for_python(monkeypatch):
    monkeypatch.delattr(startup.sys, "frozen", raising=False)
    settings = Settings.defaults()
    settings.startup_enabled = True
    settings.start_minimized = True

    assert startup.startup_command(settings) == subprocess.list2cmdline(
        [sys.executable, "-m", "squidz", "--minimized"]
    )


def test_startup_command_uses_executable_when_frozen(monkeypatch):
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    settings = Settings.defaults()
    settings.startup_enabled = True

    assert startup.startup_command(settings) == subprocess.list2cmdline([sys.executable])


def test_configure_startup_registers_command_for_current_user(monkeypatch):
    key = object()
    handle = MagicMock()
    handle.__enter__.return_value = key
    create_key = Mock(return_value=handle)
    set_value = Mock()
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=1,
        KEY_SET_VALUE=2,
        REG_SZ=3,
        CreateKeyEx=create_key,
        SetValueEx=set_value,
    )
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(startup, "os", SimpleNamespace(name="nt"))
    settings = Settings.defaults()
    settings.startup_enabled = True

    startup.configure_startup(settings)

    create_key.assert_called_once_with(
        1, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, 2
    )
    set_value.assert_called_once_with(
        key, "Squidz", 0, 3, startup.startup_command(settings)
    )


def test_configure_startup_removes_existing_registration(monkeypatch):
    key = object()
    handle = MagicMock()
    handle.__enter__.return_value = key
    open_key = Mock(return_value=handle)
    delete_value = Mock()
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=1,
        KEY_SET_VALUE=2,
        OpenKey=open_key,
        DeleteValue=delete_value,
    )
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(startup, "os", SimpleNamespace(name="nt"))

    startup.configure_startup(Settings.defaults())

    open_key.assert_called_once_with(
        1, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, 2
    )
    delete_value.assert_called_once_with(key, "Squidz")
