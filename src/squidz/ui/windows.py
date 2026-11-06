"""Modern Qt configuration window with profile and context editors."""
from __future__ import annotations
import copy
import os
from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QSize, Signal
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
    QScrollArea, QGroupBox, QMessageBox, QFileDialog, QInputDialog, QSystemTrayIcon, QMenu,
    QStyle, QFrame, QGridLayout, QProgressBar, QLayout)
from squidz.core.controllers import battery_percentage
from squidz.core.models import BUTTONS, ACTIONS, Binding, Profile
from squidz.infra.storage import save

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON = ASSETS_DIR / "squid.png"
_LOADED_FONT_PATHS: set[Path] = set()


def load_fonts():
    inter_fonts = ASSETS_DIR / "fonts"
    font_paths = [
        inter_fonts / "Inter-Regular.ttf",
        inter_fonts / "Inter-SemiBold.ttf",
    ]
    if "Super Water" not in QFontDatabase.families():
        local_fonts = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
        font_paths.extend((
            local_fonts / "SuperWater-PVoOm.ttf",
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "SuperWater-PVoOm.ttf",
        ))

    for font_path in font_paths:
        if font_path in _LOADED_FONT_PATHS or not font_path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            if font_path.parent == inter_fonts:
                raise RuntimeError(f"Unable to load bundled font: {font_path}")
            continue
        _LOADED_FONT_PATHS.add(font_path)


def action_icon(kind: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    if kind == "profiles":
        painter.drawEllipse(5, 3, 7, 7)
        painter.drawEllipse(14, 5, 6, 6)
        painter.drawRoundedRect(2, 11, 13, 10, 5, 5)
        painter.drawRoundedRect(13, 12, 9, 9, 4, 4)
    elif kind == "settings":
        painter.setPen(QPen(QColor("#ffffff"), 2.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(6, 6, 12, 12)
        painter.drawEllipse(10, 10, 4, 4)
        for angle in range(0, 360, 45):
            painter.save()
            painter.translate(12, 12)
            painter.rotate(angle)
            painter.drawLine(0, -8, 0, -10)
            painter.restore()
    painter.end()
    return QIcon(pixmap)


CSS = """
QWidget { color:#f5f7fb; font: 10pt 'Inter 18pt'; }
QMainWindow, QDialog { background:#223d68; }
QWidget#mainSurface { background:#223d68; border:1px solid #627895; }
QLabel#brand { color:#3989cf; font: 44pt 'Super Water'; }
QLabel#controllerName { color:#f4f6fb; font: 11pt 'Inter 18pt'; }
QLabel#controllerName[connected="false"] { color:#5b7192; }
QLabel#batteryLabel { color:#f4f6fb; font: 10pt 'Inter 18pt'; }
QPushButton#windowControl { color:#9cb4d3; background:transparent; border:0; font: 22pt 'Inter 18pt'; padding:0; }
QPushButton#windowControl:hover { color:#ffffff; }
QPushButton#profilePicker { color:#ffffff; background:#20527b; border:1.5px solid #3187c7; border-radius:8px; padding:5px 12px; text-align:left; min-height:22px; }
QPushButton#profilePicker:hover { background:#28618e; }
QComboBox#profilePicker { color:#ffffff; background:#20527b; border:1.5px solid #3187c7; border-radius:8px; padding:5px 10px; min-height:22px; }
QComboBox#profilePicker QAbstractItemView { color:#ffffff; background:#20527b; selection-background-color:#3187c7; }
QPushButton#primaryAction { color:#ffffff; background:#20527b; border:2px solid #3187c7; border-radius:9px; font: 17pt 'Inter 18pt'; }
QPushButton#primaryAction:hover { background:#28618e; border-color:#54a5e0; }
QPushButton#setPrimary { color:#ffffff; background:#20527b; border:2px solid #3187c7; border-radius:8px; font: 10pt 'Inter 18pt'; padding:5px 10px; }
QPushButton#setPrimary:hover { background:#28618e; }
QFrame#separator { color:#3e5e8b; background:#3e5e8b; border:0; }
QGroupBox { border:1px solid #4d6c95; border-radius:12px; margin-top:16px; padding:16px 10px 10px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:16px; padding:0 6px; color:#b9d5ff; }
QPushButton { background:#20527b; border:1px solid #3187c7; border-radius:8px; padding:8px 14px; }
QPushButton:hover { background:#28618e; }
QPushButton:disabled { background:#2b4265; color:#7186a4; }
QComboBox, QLineEdit, QDoubleSpinBox { background:#1b355b; border:1px solid #4b6c97; border-radius:7px; padding:7px; min-height:20px; }
QComboBox QAbstractItemView { background:#1b355b; color:#fff; selection-background-color:#2765cc; }
QScrollArea { border:0; }
"""

class ProfileDialog(QDialog):
    def __init__(self, profile: Profile, parent=None):
        super().__init__(parent)
        self.profile = copy.deepcopy(profile)
        self.setWindowTitle("Modifier le profil — " + profile.name)
        self.resize(790, 680)
        root = QVBoxLayout(self)
        title = QLabel("Raccourcis · " + profile.name)
        title.setObjectName("heading")
        root.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        self.sections = QVBoxLayout(host)
        scroll.setWidget(host)
        root.addWidget(scroll)
        self.draw()
        controls = QHBoxLayout()
        add_app = QPushButton("+ Ajouter un programme")
        add_app.clicked.connect(self.add_app)
        add_site = QPushButton("+ Ajouter un site web")
        add_site.clicked.connect(self.add_site)
        controls.addWidget(add_app)
        controls.addWidget(add_site)
        root.addLayout(controls)
        save_btn = QPushButton("Enregistrer le profil")
        save_btn.clicked.connect(self.accept)
        root.addWidget(save_btn)

    def draw(self):
        while self.sections.count():
            item = self.sections.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._section("Général", self.profile.global_bindings)
        for name, bindings in self.profile.apps.items():
            self._section("Programme · " + name, bindings)
        for name, bindings in self.profile.sites.items():
            self._section("Site web · " + name, bindings)
        group = QGroupBox("Sensibilité")
        layout = QFormLayout(group)
        for label, attr, low, high in (("Souris", "mouse_speed", 1, 50), ("Molette", "scroll_speed", .1, 15), ("Zone morte", "deadzone", 0, .9)):
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setSingleStep(.05 if attr == "deadzone" else .5)
            spin.setValue(getattr(self.profile, attr))
            spin.valueChanged.connect(lambda value, key=attr: setattr(self.profile, key, value))
            layout.addRow(label, spin)
        self.sections.addWidget(group)

    def _section(self, name: str, bindings: dict[str, Binding]):
        group = QGroupBox(name)
        layout = QVBoxLayout(group)
        for button in sorted(bindings, key=lambda b: BUTTONS.index(b)):
            row = QHBoxLayout()
            label = QLabel(button.upper())
            label.setFixedWidth(100)
            row.addWidget(label)
            combo = QComboBox()
            combo.addItems(ACTIONS)
            combo.setCurrentText(bindings[button].action)
            combo.currentTextChanged.connect(lambda action, b=button: setattr(bindings[b], "action", action))
            row.addWidget(combo, 2)
            keys = QLineEdit(bindings[button].keys)
            keys.setPlaceholderText("ctrl+shift+t (pour key_combo)")
            keys.textChanged.connect(lambda text, b=button: setattr(bindings[b], "keys", text))
            row.addWidget(keys, 2)
            remove = QPushButton("×")
            remove.setFixedWidth(38)
            remove.clicked.connect(lambda _, b=button, d=bindings: self._remove(d, b))
            row.addWidget(remove)
            layout.addLayout(row)
        remaining = [b for b in BUTTONS if b not in bindings]
        if remaining:
            add = QPushButton("+ Ajouter une touche")
            add.clicked.connect(lambda: self.add_binding(bindings))
            layout.addWidget(add)
        self.sections.addWidget(group)

    def _remove(self, bindings, button):
        bindings.pop(button, None)
        self.draw()

    def add_binding(self, bindings):
        remaining = [b for b in BUTTONS if b not in bindings]
        button, ok = QInputDialog.getItem(self, "Ajouter une touche", "Bouton", remaining, 0, False)
        if ok and button:
            bindings[button] = Binding()
            self.draw()

    def add_app(self):
        # Standard Windows file picker; selecting the executable is more reliable than
        # enumerating uninstall registry entries (portable apps are supported too).
        filename, _ = QFileDialog.getOpenFileName(self, "Sélectionner un programme installé", os.environ.get("ProgramFiles", "C:\\Program Files"), "Applications (*.exe)")
        if filename:
            self.profile.apps.setdefault(Path(filename).name.lower(), {})
            self.draw()

    def add_site(self):
        domain, ok = QInputDialog.getText(self, "Ajouter un site web", "Domaine (ex. youtube.com)")
        domain = domain.strip().lower().removeprefix("www.")
        if ok and domain and "." in domain and "/" not in domain and " " not in domain:
            self.profile.sites.setdefault(domain, {})
            self.draw()

class DraggableHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)


class ControllerArtwork(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = False
        self.primary = False

    def set_state(self, connected: bool, primary: bool):
        self.connected = connected
        self.primary = primary
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min((self.width() - 18) / 160, (self.height() - 25) / 116)
        painter.translate((self.width() - 160 * scale) / 2, 18)
        painter.scale(scale, scale)
        painter.setOpacity(1.0 if self.connected else 0.13)

        body = QPainterPath()
        body.moveTo(34, 13)
        body.cubicTo(24, 13, 17, 20, 14, 32)
        body.lineTo(2, 76)
        body.cubicTo(-1, 91, 6, 103, 16, 102)
        body.cubicTo(22, 101, 33, 88, 43, 78)
        body.cubicTo(47, 74, 52, 72, 59, 72)
        body.lineTo(101, 72)
        body.cubicTo(108, 72, 113, 75, 118, 80)
        body.lineTo(141, 102)
        body.cubicTo(151, 108, 160, 98, 158, 81)
        body.lineTo(146, 33)
        body.cubicTo(143, 20, 136, 13, 126, 13)
        body.cubicTo(117, 13, 111, 19, 103, 19)
        body.lineTo(57, 19)
        body.cubicTo(49, 19, 42, 13, 34, 13)
        body.closeSubpath()
        painter.setPen(QPen(QColor("#07090d"), 7, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor("#55565b"))
        painter.drawPath(body)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#898b8e"))
        painter.drawRoundedRect(48, 47, 6, 20, 2, 2)
        painter.drawRoundedRect(41, 54, 20, 6, 2, 2)
        painter.drawEllipse(35, 36, 13, 13)
        painter.drawEllipse(79, 57, 15, 15)
        painter.setBrush(QColor("#ededed"))
        painter.drawEllipse(69, 34, 9, 9)

        for x, y, color in (
            (112, 33, "#ffd22e"),
            (122, 42, "#ed4b48"),
            (112, 52, "#10c96b"),
            (102, 42, "#39a9ed"),
        ):
            painter.setBrush(QColor(color))
            painter.drawEllipse(x, y, 7, 7)
        if self.connected and self.primary:
            crown = QPainterPath()
            crown.moveTo(76, 24)
            crown.lineTo(73, 8)
            crown.lineTo(82, 15)
            crown.lineTo(89, 4)
            crown.lineTo(97, 15)
            crown.lineTo(105, 8)
            crown.lineTo(102, 24)
            crown.closeSubpath()
            painter.setPen(QPen(QColor("#8b6000"), 1.5))
            painter.setBrush(QColor("#ffd54a"))
            painter.drawPath(crown)
            painter.drawRoundedRect(76, 24, 26, 5, 1, 1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ec514b"))
            painter.drawEllipse(87, 16, 4, 4)
            painter.setBrush(QColor("#39a9ed"))
            painter.drawEllipse(78, 18, 3, 3)
            painter.drawEllipse(97, 18, 3, 3)


class ControllerSlot(QWidget):
    profile_changed = Signal(str, str)
    set_primary_requested = Signal(str)
    WIDTH = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_key = ""
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.artwork = ControllerArtwork()
        self.artwork.setFixedSize(180, 138)
        layout.addWidget(self.artwork, 0, Qt.AlignmentFlag.AlignHCenter)

        self.name = QLabel()
        self.name.setObjectName("controllerName")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name.setFixedHeight(27)
        layout.addWidget(self.name)

        self.battery = QLabel()
        self.battery.setObjectName("batteryLabel")
        self.battery.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery.setFixedHeight(22)
        layout.addWidget(self.battery)

        self.battery_bar = QProgressBar()
        self.battery_bar.setTextVisible(False)
        self.battery_bar.setFixedSize(112, 7)
        layout.addWidget(self.battery_bar, 0, Qt.AlignmentFlag.AlignHCenter)

        self.profile_picker = QComboBox()
        self.profile_picker.setObjectName("profilePicker")
        self.profile_picker.currentIndexChanged.connect(self._profile_selected)
        layout.addWidget(self.profile_picker, 0, Qt.AlignmentFlag.AlignHCenter)

        self.set_primary = QPushButton("SET PRIMARY")
        self.set_primary.setObjectName("setPrimary")
        self.set_primary.setFixedSize(136, 35)
        self.set_primary.clicked.connect(self._request_primary)
        layout.addWidget(self.set_primary, 0, Qt.AlignmentFlag.AlignHCenter)

    def configure(self, key: str | None, name: str, connected: bool,
                  power_level: str, profiles: list[str], assigned: str | None,
                  primary: bool, connected_count: int):
        self.device_key = key or ""
        self.artwork.set_state(connected, primary)
        self.name.setText(name)
        self.name.setProperty("connected", connected)
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)
        self.battery.setVisible(connected)
        self.battery_bar.setVisible(connected)
        self.profile_picker.setVisible(connected)
        self.set_primary.setVisible(connected and connected_count > 1 and not primary)
        if connected:
            self.update_battery(power_level)
            self.profile_picker.blockSignals(True)
            self.profile_picker.clear()
            self.profile_picker.addItem("By default", "")
            for profile in profiles:
                self.profile_picker.addItem(profile, profile)
            index = self.profile_picker.findData(assigned or "")
            self.profile_picker.setCurrentIndex(max(index, 0))
            self.profile_picker.blockSignals(False)

    def update_battery(self, power_level: str):
        if power_level == "wired":
            label, percentage, color = "Wired", 100, "#00c96b"
        else:
            percentage = battery_percentage(power_level)
            if percentage is None:
                label, color = "—", "#7587a3"
            else:
                label = f"{percentage}%" if power_level in ("empty", "full", "max") else f"~{percentage}%"
                color = "#00c96b" if percentage >= 80 else "#ffc21c" if percentage >= 50 else "#f26945"
        self.battery.setText(label)
        self.battery_bar.setValue(percentage or 0)
        self.battery_bar.setStyleSheet(
            f"QProgressBar {{ background:#17345e; border:0; border-radius:3px; }}"
            f"QProgressBar::chunk {{ background:{color}; border-radius:3px; }}")

    def _profile_selected(self, index: int):
        if self.device_key and index >= 0:
            self.profile_changed.emit(self.device_key, str(self.profile_picker.currentData() or ""))

    def _request_primary(self):
        if self.device_key:
            self.set_primary_requested.emit(self.device_key)


class MainWindow(QMainWindow):
    def __init__(self, settings, manager):
        super().__init__()
        load_fonts()
        self.settings, self.manager = settings, manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle("squidz")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setMinimumSize(960, 550)
        self.resize(1100, 605)
        surface = QWidget()
        surface.setObjectName("mainSurface")
        self.setCentralWidget(surface)
        root = QVBoxLayout(surface)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = DraggableHeader()
        header.setFixedHeight(92)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 0)
        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(2, 1)
        logo = QWidget()
        logo_layout = QHBoxLayout(logo)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(5)
        mark = QLabel()
        mark.setPixmap(QPixmap(str(APP_ICON)).scaled(
            38, 38, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        logo_layout.addWidget(mark)
        brand = QLabel("squidz")
        brand.setObjectName("brand")
        logo_layout.addWidget(brand)
        header_layout.addWidget(logo, 0, 1, Qt.AlignmentFlag.AlignCenter)
        controls = QHBoxLayout()
        controls.setSpacing(16)
        minimize = QPushButton("−")
        minimize.setObjectName("windowControl")
        minimize.setFixedSize(34, 30)
        minimize.clicked.connect(self.showMinimized)
        close = QPushButton("×")
        close.setObjectName("windowControl")
        close.setFixedSize(34, 30)
        close.clicked.connect(self.close)
        controls.addWidget(minimize)
        controls.addWidget(close)
        header_layout.addLayout(controls, 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addWidget(header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(10, 20, 10, 8)
        body_layout.setSpacing(0)

        self.previous_controllers = self._controller_nav_button("‹")
        self.previous_controllers[1].clicked.connect(lambda: self._scroll_controllers(-1))
        body_layout.addWidget(self.previous_controllers[0], 0, Qt.AlignmentFlag.AlignVCenter)

        self.controller_scroll = QScrollArea()
        self.controller_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.controller_scroll.setWidgetResizable(False)
        self.controller_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.controller_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.controller_scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.controller_content = QWidget()
        self.controller_content_layout = QHBoxLayout(self.controller_content)
        self.controller_content_layout.setContentsMargins(0, 0, 0, 0)
        self.controller_content_layout.setSpacing(0)
        self.controller_content_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.controller_scroll.setWidget(self.controller_content)
        body_layout.addWidget(self.controller_scroll, 1)

        self.next_controllers = self._controller_nav_button("›")
        self.next_controllers[1].clicked.connect(lambda: self._scroll_controllers(1))
        body_layout.addWidget(self.next_controllers[0], 0, Qt.AlignmentFlag.AlignVCenter)
        self.slots = []
        body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        horizontal_scroll = self.controller_scroll.horizontalScrollBar()
        horizontal_scroll.valueChanged.connect(self._update_controller_navigation)
        horizontal_scroll.rangeChanged.connect(self._update_controller_navigation)
        self.previous_controllers[1].hide()
        self.next_controllers[1].hide()
        root.addWidget(body, 1)

        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFixedHeight(1)
        separator_layout = QHBoxLayout()
        separator_layout.setContentsMargins(22, 0, 22, 0)
        separator_layout.addWidget(separator)
        root.addLayout(separator_layout)

        footer = QWidget()
        footer.setFixedHeight(118)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 27, 0, 27)
        footer_layout.setSpacing(38)
        footer_layout.addStretch()
        manage = QPushButton("Manage profiles")
        manage.setObjectName("primaryAction")
        manage.setFixedSize(280, 52)
        manage.setIcon(action_icon("profiles"))
        manage.setIconSize(QSize(24, 24))
        manage.clicked.connect(self.manage_profiles)
        settings_button = QPushButton("Settings")
        settings_button.setObjectName("primaryAction")
        settings_button.setFixedSize(280, 52)
        settings_button.setIcon(action_icon("settings"))
        settings_button.setIconSize(QSize(24, 24))
        settings_button.clicked.connect(self.open_settings)
        footer_layout.addWidget(manage)
        footer_layout.addWidget(settings_button)
        footer_layout.addStretch()
        root.addWidget(footer)

        self._known_snapshot = None
        self._primary_snapshot = None
        self.manager.devices_changed.connect(self.refresh)
        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(1000)
        self._battery_timer.timeout.connect(self.refresh_battery)
        self._battery_timer.start()
        self.refresh()

        app = QApplication.instance()
        if app is None:
            raise RuntimeError("MainWindow requires a running QApplication")
        app.setWindowIcon(QIcon(str(APP_ICON)))
        self.tray = QSystemTrayIcon(QIcon(str(APP_ICON)), self)
        menu = QMenu()
        menu.addAction("Configuration", self.show_from_tray)
        menu.addAction("Quitter", app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_from_tray()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def refresh(self, *_):
        connected = list(self.manager.controllers)
        if connected and self.settings.primary_device not in connected:
            self.settings.primary_device = connected[0]
        known_before = dict(self.settings.known_devices)
        for key in connected:
            self.settings.known_devices.setdefault(key, getattr(self.manager.controllers[key], "name", key))

        disconnected = [
            (key, name) for key, name in self.settings.known_devices.items()
            if key not in self.manager.controllers
        ]
        entries = [
            (key, self.settings.known_devices.get(
                key, getattr(self.manager.controllers[key], "name", key)), True)
            for key in connected
        ]
        entries.extend((key, name, False) for key, name in disconnected)

        while len(self.slots) > len(entries):
            slot = self.slots.pop()
            self.controller_content_layout.removeWidget(slot)
            slot.deleteLater()
        while len(self.slots) < len(entries):
            slot = ControllerSlot()
            slot.profile_changed.connect(self.profile_selected)
            slot.set_primary_requested.connect(self.set_primary)
            self.slots.append(slot)
            self.controller_content_layout.addWidget(slot)

        profile_names = list(self.settings.profiles)
        connected_count = len(connected)
        for slot, (key, name, is_connected) in zip(self.slots, entries):
            power = self.manager.power_levels.get(key, "unknown") if key else "unknown"
            assigned = self.settings.assignments.get(key) if key else None
            slot.configure(
                key, name, is_connected, power, profile_names, assigned,
                key == self.settings.primary_device, connected_count)

        self.controller_content.adjustSize()
        self.controller_content.updateGeometry()
        QTimer.singleShot(0, self._update_controller_navigation)

        if (self._known_snapshot != self.settings.known_devices
                or self._primary_snapshot != self.settings.primary_device):
            save(self.settings)
            self._known_snapshot = dict(self.settings.known_devices)
            self._primary_snapshot = self.settings.primary_device
        elif known_before != self.settings.known_devices:
            save(self.settings)

    @staticmethod
    def _controller_nav_button(label: str) -> tuple[QWidget, QPushButton]:
        container = QWidget()
        container.setFixedWidth(42)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(label)
        button.setObjectName("windowControl")
        button.setFixedSize(38, 58)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        return container, button

    def _scroll_controllers(self, direction: int):
        scrollbar = self.controller_scroll.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() + direction * ControllerSlot.WIDTH)

    def _update_controller_navigation(self, *_):
        scrollbar = self.controller_scroll.horizontalScrollBar()
        has_overflow = scrollbar.maximum() > 0
        self.previous_controllers[1].setVisible(has_overflow and scrollbar.value() > 0)
        self.next_controllers[1].setVisible(has_overflow and scrollbar.value() < scrollbar.maximum())

    def refresh_battery(self):
        for slot in self.slots:
            if slot.device_key:
                slot.update_battery(self.manager.power_levels.get(slot.device_key, "unknown"))

    def profile_selected(self, key: str, profile: str):
        if profile:
            self.settings.assignments[key] = profile
        else:
            self.settings.assignments.pop(key, None)
        save(self.settings)

    def set_primary(self, key: str):
        if key in self.manager.controllers:
            self.settings.primary_device = key
            save(self.settings)
            self._primary_snapshot = key
            self.refresh()

    def manage_profiles(self):
        create_option = "+ Create profile"
        options = [*self.settings.profiles, create_option]
        choice, accepted = QInputDialog.getItem(
            self, "Manage profiles", "Select a profile to edit", options, 0, False)
        if not accepted:
            return
        if choice == create_option:
            self.new_profile()
            return
        self.edit_profile(choice)

    def edit_profile(self, name: str | None = None):
        if name is None:
            device = self.settings.primary_device
            name = self.settings.assignments.get(device) if device else None
            name = name or next(iter(self.settings.profiles))
        profile = self.settings.profiles.get(name)
        if profile is None:
            return
        dialog = ProfileDialog(profile, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.profiles[name] = dialog.profile
            save(self.settings)

    def open_settings(self):
        self.edit_profile()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "New profile", "Profile name")
        name = name.strip()
        if ok and name and name not in self.settings.profiles:
            self.settings.profiles[name] = copy.deepcopy(next(iter(self.settings.profiles.values())))
            self.settings.profiles[name].name = name
            save(self.settings)
            self.refresh()

    def show_for_device(self, device):
        self.refresh()
        self.show_from_tray()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()
