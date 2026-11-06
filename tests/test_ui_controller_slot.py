import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from squidz.core.models import Settings
from squidz.ui.windows import CSS, ControllerSlot, MainWindow, load_fonts


def test_controller_slot_marks_primary_and_requests_transfer():
    app = QApplication.instance() or QApplication([])
    load_fonts()
    slot = ControllerSlot()
    requested = []
    slot.set_primary_requested.connect(requested.append)

    slot.configure("guid#1", "Controller 2", True, "medium", ["Default"], "Default", False, 2)

    assert slot.artwork.primary is False
    assert not slot.set_primary.isHidden()
    assert slot.battery.text() == "~60%"
    assert slot.profile_picker.currentData() == "Default"
    slot.set_primary.click()
    assert requested == ["guid#1"]

    slot.configure("guid#1", "Controller 2", True, "full", ["Default"], "Default", True, 2)

    assert slot.artwork.primary is True
    assert slot.set_primary.isHidden()


def test_inter_font_is_loaded_from_assets():
    app = QApplication.instance() or QApplication([])
    load_fonts()

    from PySide6.QtGui import QFont, QFontInfo

    assert QFontInfo(QFont("Inter 18pt", 12)).exactMatch()


def test_main_window_lists_known_controllers_and_scrolls_overflow(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    monkeypatch.setattr("squidz.ui.windows.save", lambda _settings: None)

    settings = Settings.defaults()
    connected_key = "connected#0"
    settings.primary_device = connected_key
    settings.known_devices = {
        connected_key: "Connected controller",
        **{f"known#{index}": f"Known controller {index}" for index in range(6)},
    }

    class Signal:
        def connect(self, _callback):
            pass

    manager = SimpleNamespace(
        controllers={connected_key: SimpleNamespace(name="Connected controller")},
        power_levels={connected_key: "full"},
        devices_changed=Signal(),
    )
    window = MainWindow(settings, manager)
    window.show()
    app.processEvents()

    assert len(window.slots) == len(settings.known_devices)
    assert [slot.name.text() for slot in window.slots] == list(settings.known_devices.values())
    assert window.slots[0].artwork.connected
    assert not window.slots[1].artwork.connected
    assert window.controller_scroll.horizontalScrollBar().maximum() > 0
    assert window.previous_controllers[1].isHidden()
    assert not window.next_controllers[1].isHidden()

    window.next_controllers[1].click()
    app.processEvents()
    assert window.controller_scroll.horizontalScrollBar().value() > 0
    assert not window.previous_controllers[1].isHidden()

    scrollbar = window.controller_scroll.horizontalScrollBar()
    while scrollbar.value() < scrollbar.maximum():
        window.next_controllers[1].click()
        app.processEvents()
    assert scrollbar.value() == scrollbar.maximum()
    assert window.next_controllers[1].isHidden()
    while scrollbar.value() > 0:
        window.previous_controllers[1].click()
        app.processEvents()
    assert window.controller_scroll.horizontalScrollBar().value() == 0
    assert window.previous_controllers[1].isHidden()

    window.tray.hide()
    window._battery_timer.stop()
    window.close()
