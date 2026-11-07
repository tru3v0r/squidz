import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QMessageBox, QPushButton, QScrollArea,
    QSlider, QWidget,
)

from squidz.core.models import Settings
from squidz.ui.windows import (
    CSS, ControllerSlot, DebugWindow, MainWindow, ProfileCreationDialog, ProfileDialog,
    SettingsDialog, load_fonts,
)


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


def test_controller_battery_animates_from_empty_through_percentage_colors():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()

    slot.configure("guid#1", "Controller", True, "full", ["Default"], None, True, 1)

    assert slot.battery_bar.value() == 0
    assert slot.battery_animation.state().name == "Running"
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration() // 2)
    assert slot.battery_bar.value() == 50
    assert "#ffc21c" in slot.battery_bar.styleSheet()
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration())
    assert slot.battery_bar.value() == 100
    assert "#00c96b" in slot.battery_bar.styleSheet()


def test_controller_battery_only_animates_when_connection_starts():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()

    slot.configure("guid#1", "Controller", True, "low", ["Default"], None, True, 1)
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration())
    slot.configure("guid#1", "Controller", True, "medium", ["Default"], None, True, 1)

    assert slot.battery_bar.value() == 60
    assert slot.battery_animation.state().name == "Stopped"


def test_inter_font_is_loaded_from_assets():
    app = QApplication.instance() or QApplication([])
    load_fonts()

    from PySide6.QtGui import QFont, QFontInfo

    assert QFontInfo(QFont("Inter 18pt", 12)).exactMatch()


def test_profile_dialog_exposes_magnet_strength_slider():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = ProfileDialog(Settings.defaults().profiles["Valentin"])
    slider = dialog.findChild(QSlider, "magnetStrength")

    assert slider is not None
    assert slider.value() == 50
    slider.setValue(72)
    assert dialog.profile.magnet_strength == 72


def test_profile_dialog_scroll_area_keeps_dark_theme_without_white_background():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = ProfileDialog(Settings.defaults().profiles["Valentin"])
    dialog.show()
    app.processEvents()

    viewport = dialog.findChild(QScrollArea, "profileScroll")
    assert viewport is not None
    image = dialog.grab().toImage()
    point = viewport.viewport().mapTo(
        dialog, QPoint(3, 3))

    assert image.pixelColor(point) == QColor("#223d68")
    dialog.close()


def test_controller_name_wraps_onto_multiple_lines_when_needed():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()
    slot.name.setText("Nintendo Switch Pro Controller with an extra-long name")
    slot.show()
    app.processEvents()

    assert slot.name.wordWrap()
    assert slot.name.height() > 27
    slot.close()


def test_primary_controller_crown_is_centered_on_controller():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()
    artwork = slot.artwork
    artwork.set_state(True, True)
    artwork.show()
    app.processEvents()
    image = artwork.grab().toImage()
    crown_pixels = [
        (x, y)
        for y in range(50)
        for x in range(image.width())
        if (color := image.pixelColor(x, y)).red() > 200
        and color.green() > 150
        and color.blue() < 120
    ]

    assert crown_pixels
    crown_center = (min(x for x, _ in crown_pixels) + max(x for x, _ in crown_pixels)) / 2
    assert abs(crown_center - artwork.width() / 2) <= 1
    artwork.close()


def test_settings_dialog_separates_general_and_profile_options():
    app = QApplication.instance() or QApplication([])
    settings = Settings.defaults()
    dialog = SettingsDialog(settings)
    startup = dialog.findChild(QCheckBox, "startupEnabled")
    minimized = dialog.findChild(QCheckBox, "startMinimized")

    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["Général", "Profils"]
    assert startup is not None
    assert minimized is not None
    assert not minimized.isEnabled()
    startup.setChecked(True)
    assert minimized.isEnabled()
    startup.setChecked(False)
    assert not minimized.isEnabled()
    assert dialog.profile_editor.findChild(QCheckBox, "startupEnabled") is None


def test_debug_window_has_five_independent_opt_in_event_sources(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    window = DebugWindow()
    started = []
    monkeypatch.setattr(
        window.sources, "set_enabled",
        lambda source, enabled: started.append((source, enabled)))

    assert [window.source_buttons[source].text()
            for source, _ in window.SOURCES] == [
                "SetWindowsHookEx", "SetWinEventHook", "UIA", "Raw Input", "ETW"]
    assert all(button.isCheckable() for button in window.source_buttons.values())
    window.source_buttons["set_windows_hook"].click()
    window.source_buttons["set_windows_hook"].click()
    assert started == [
        ("set_windows_hook", True),
        ("set_windows_hook", False),
    ]
    window.append_event("uia", "focus changed")
    assert "[UIA] focus changed" in window.event_list.toPlainText()
    window.close()


def test_settings_general_has_debug_window_button():
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())

    assert dialog.debug_button.text() == "Debug Window"
    assert dialog.findChild(QPushButton, "openDebugWindow") is dialog.debug_button
    dialog.debug_button.click()
    assert dialog.debug_window.isVisible()
    dialog.debug_window.close()


def test_settings_dialog_edits_each_profile_and_styles_profile_selector():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    settings = Settings.defaults()
    dialog = SettingsDialog(settings)
    selector = dialog.findChild(QComboBox, "settingsProfilePicker")

    assert selector is not None
    assert selector.view().styleSheet().find("#1b355b") >= 0
    slider = dialog.profile_editor.findChild(QSlider, "magnetStrength")
    assert slider is not None
    slider.setValue(73)
    selector.setCurrentIndex(1)

    assert dialog.profiles["Valentin"].magnet_strength == 73
    assert dialog.profile_editor.profile.name == "Invité 1"


def test_profile_creation_dialog_has_name_and_model_and_confirms_cancel(monkeypatch):
    app = QApplication.instance() or QApplication([])
    dialog = ProfileCreationDialog(["Valentin", "Invité 1"])
    dialog.show()
    app.processEvents()
    assert dialog.name_input.objectName() == "newProfileName"
    assert dialog.model_picker.objectName() == "profileModel"
    assert dialog.create_button.text() == "Créer le profil"
    assert dialog.cancel_button.text() == "Annuler"
    assert not dialog.create_button.isEnabled()
    dialog.name_input.setText("Nouveau")
    assert dialog.create_button.isEnabled()
    dialog.name_input.setText("Valentin")
    assert not dialog.create_button.isEnabled()
    dialog.name_input.setText("Nouveau")

    prompts = []

    def decline_cancel(_parent, _title, text, *_args):
        prompts.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr("squidz.ui.windows.QMessageBox.question", decline_cancel)
    dialog.cancel_button.click()
    assert dialog.isVisible()
    assert prompts == ["Êtes-vous sûre de vouloir annuler la création du profil en cours ?"]

    monkeypatch.setattr(
        "squidz.ui.windows.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.Yes)
    dialog.cancel_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_settings_add_profile_copies_selected_model(monkeypatch):
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())

    def accept_creation(creation):
        creation.name_input.setText("Custom")
        creation.model_picker.setCurrentText("Invité 1")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ProfileCreationDialog, "exec", accept_creation)
    dialog.add_profile()

    assert "Custom" in dialog.profiles
    assert dialog.profile_picker.currentText() == "Custom"
    assert dialog.profile_editor.profile.name == "Custom"
    assert dialog.profile_editor.profile.dump() == dialog.profiles["Invité 1"].dump() | {
        "name": "Custom"
    }


def test_settings_save_keeps_active_profile_editor_changes():
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())
    slider = dialog.profile_editor.findChild(QSlider, "magnetStrength")
    assert slider is not None
    slider.setValue(88)
    dialog._accept_settings()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.profiles["Valentin"].magnet_strength == 88


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

    assert window.height() == 550
    assert "font: 13pt" in CSS
    assert len(window.slots) == len(settings.known_devices)
    assert [slot.name.text() for slot in window.slots] == list(settings.known_devices.values())
    assert window.slots[0].artwork.connected
    assert not window.slots[1].artwork.connected
    assert window.tray.contextMenu().objectName() == "trayMenu"
    assert "#1b355b" in window.tray.contextMenu().styleSheet()
    viewport_corner = window.controller_scroll.viewport().mapTo(
        window, QPoint(window.controller_scroll.viewport().width() - 8,
                       window.controller_scroll.viewport().height() - 8))
    assert window.grab().toImage().pixelColor(viewport_corner).name() == "#223d68"
    assert window.controller_scroll.horizontalScrollBar().maximum() > 0
    assert window.previous_controllers[1].isHidden()
    assert not window.next_controllers[1].isHidden()
    footer = window.findChild(QWidget, "bottomButtonBar")
    assert footer is not None
    controller_bottom = window.slots[0].mapTo(
        window, QPoint(0, window.slots[0].height())).y()
    footer_top = footer.mapTo(window, QPoint(0, 0)).y()
    assert footer_top - controller_bottom <= 65
    assert window.slots[0].profile_picker.geometry().top() - window.slots[0].battery_bar.geometry().bottom() >= 9

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

    window.show_debug_window()
    assert window.debug_window.isVisible()
    window.tray.hide()
    window._battery_timer.stop()
    window.close()
    window.debug_window.close()


def test_disconnected_controller_can_be_forgotten(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    monkeypatch.setattr("squidz.ui.windows.save", lambda _settings: None)
    monkeypatch.setattr(
        "squidz.ui.windows.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.Yes)
    settings = Settings.defaults()
    settings.known_devices = {
        "connected#0": "Connected controller",
        "ghost#0": "Disconnected controller",
    }
    settings.assignments["ghost#0"] = "Valentin"

    class Signal:
        def connect(self, _callback):
            pass

    manager = SimpleNamespace(
        controllers={"connected#0": SimpleNamespace(name="Connected controller")},
        power_levels={"connected#0": "full"},
        devices_changed=Signal(),
    )
    window = MainWindow(settings, manager)
    window.show()
    app.processEvents()

    connected_slot, disconnected_slot = window.slots
    assert connected_slot.forget_button.isHidden()
    assert not disconnected_slot.forget_button.isHidden()
    assert disconnected_slot.forget_button.width() == 84

    disconnected_slot.forget_button.click()
    app.processEvents()

    assert "ghost#0" not in settings.known_devices
    assert "ghost#0" not in settings.assignments
    assert len(window.slots) == 1

    window.tray.hide()
    window._battery_timer.stop()
    window.close()
    window.debug_window.close()
