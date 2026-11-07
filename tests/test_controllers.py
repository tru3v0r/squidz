import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QObject

from squidz.core.controllers import ControllerManager, battery_percentage
from squidz.core.models import Settings


@pytest.mark.parametrize(
    ("level", "percentage"),
    [
        ("empty", 0),
        ("LOW", 20),
        ("medium", 60),
        ("full", 100),
        ("max", 100),
        ("wired", None),
        ("unknown", None),
    ],
)
def test_battery_percentage(level, percentage):
    assert battery_percentage(level) == percentage


def test_left_click_is_held_until_controller_button_release(monkeypatch):
    manager = ControllerManager.__new__(ControllerManager)
    QObject.__init__(manager)
    manager.settings = Settings.defaults()
    manager.bridge = SimpleNamespace(domain=lambda _app: "")
    manager.pressed = {}
    manager.long_handled = set()
    manager.held_actions = {}
    manager.click_presses = set()
    mouse_down = Mock()
    mouse_up = Mock()
    monkeypatch.setattr("squidz.core.controllers.windows.active_process", lambda: "")
    monkeypatch.setattr("squidz.core.controllers.windows.mouse_button_down", mouse_down)
    monkeypatch.setattr("squidz.core.controllers.windows.mouse_button_up", mouse_up)
    monkeypatch.setattr("squidz.core.controllers.windows.perform", Mock())

    manager._press_button("controller#0", "a", 1.0)
    mouse_down.assert_called_once_with("left")
    mouse_up.assert_not_called()

    manager._release_button("controller#0", "a")
    mouse_up.assert_called_once_with("left")
