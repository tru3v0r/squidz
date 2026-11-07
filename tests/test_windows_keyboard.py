import ctypes
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from ctypes import wintypes

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


def test_mouse_button_can_be_held_and_released(monkeypatch):
    mouse_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(mouse_event=mouse_event))

    windows.mouse_button_down("left")
    mouse_event.assert_called_once_with(0x0002, 0, 0, 0, 0)
    windows.mouse_button_up("left")
    assert mouse_event.call_args_list[-1].args == (0x0004, 0, 0, 0, 0)


@pytest.mark.parametrize(("action", "key"), [("play_pause", 0x20), ("fullscreen", 0x46),
                                               ("subtitles", 0x43)])
def test_youtube_actions_use_expected_hotkeys(monkeypatch, action, key):
    keybd_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(keybd_event=keybd_event))

    windows.perform(action)

    assert keybd_event.call_args_list == [call(key, 0, 0, 0), call(key, 0, 2, 0)]


def test_magnetism_pulls_toward_nearby_target_and_respects_zero_strength():
    full_strength = windows._magnetized_delta(0, 0, (0, 0), [(100, 0)], 100)
    assert full_strength[0] > 0
    assert windows._magnetized_delta(0, 0, (0, 0), [(100, 0)], 50)[0] == full_strength[0] / 2
    assert windows._magnetized_delta(1, 2, (0, 0), [(100, 0)], 0) == (1, 2)
    assert windows._magnetized_delta(1, 2, (0, 0), [(200, 0)], 100) == (1, 2)


def test_magnetism_snaps_cursor_to_exact_target_on_path(monkeypatch):
    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = 5, 5
        return True

    set_cursor = Mock(return_value=True)
    mouse_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor),
        SetCursorPos=set_cursor,
        mouse_event=mouse_event,
    ))
    monkeypatch.setattr(windows, "_interaction_targets", lambda _point: [(20, 20)])

    windows.move(10, 10, 50)

    set_cursor.assert_called_once_with(20, 20)
    mouse_event.assert_not_called()


def test_interaction_targets_include_edges_caption_buttons_and_desktop_icons(monkeypatch):
    def get_window_rect(_hwnd, pointer):
        rect = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
        rect.left, rect.top, rect.right, rect.bottom = 0, 0, 500, 400
        return True

    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetForegroundWindow=Mock(return_value=1),
        GetWindowRect=Mock(side_effect=get_window_rect),
        GetSystemMetrics=Mock(side_effect=lambda metric: {30: 40, 31: 20}[metric]),
    ))
    monkeypatch.setattr(windows, "active_process", lambda: "explorer.exe")
    monkeypatch.setattr(windows, "_desktop_icon_centers", lambda: [(900, 700)])

    targets = windows._interaction_targets((250, 200))

    assert (250, 0) in targets
    assert (480, 10) in targets
    assert (440, 10) in targets
    assert (400, 10) in targets
    assert (900, 700) in targets
