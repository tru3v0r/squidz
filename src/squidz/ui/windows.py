"""Modern Qt configuration window with profile and context editors."""
from __future__ import annotations
import copy
import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
    QScrollArea, QGroupBox, QMessageBox, QFileDialog, QInputDialog, QSystemTrayIcon, QMenu,
    QStyle)
from squidz.core.models import BUTTONS, ACTIONS, Binding, Profile
from squidz.infra.storage import save

CSS = """
QWidget { background:#101722; color:#e8edf6; font: 13px 'Segoe UI'; }
QMainWindow, QDialog { background:#101722; }
QLabel#heading { font-size:24px; font-weight:700; color:#f4f7fc; }
QLabel#muted { color:#9aacc3; }
QGroupBox { border:1px solid #314056; border-radius:12px; margin-top:16px; padding:16px 10px 10px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:16px; padding:0 6px; color:#b9d5ff; }
QPushButton { background:#2765cc; border:0; border-radius:8px; padding:10px 15px; font-weight:600; }
QPushButton:hover { background:#387ce8; }
QPushButton:disabled { background:#344052; color:#7c8ca1; }
QComboBox, QLineEdit, QDoubleSpinBox { background:#1b2839; border:1px solid #384b64; border-radius:7px; padding:7px; min-height:20px; }
QComboBox QAbstractItemView { background:#1b2839; color:#fff; selection-background-color:#2765cc; }
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

class MainWindow(QMainWindow):
    def __init__(self, settings, manager):
        super().__init__()
        self.settings, self.manager = settings, manager
        self.setWindowTitle("squidz · Configuration")
        self.resize(620, 370)
        host = QWidget()
        self.setCentralWidget(host)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)
        title = QLabel("squidz")
        title.setObjectName("heading")
        layout.addWidget(title)
        sub = QLabel("Contrôlez Windows depuis votre manette")
        sub.setObjectName("muted")
        layout.addWidget(sub)
        form = QFormLayout()
        self.devices = QComboBox()
        self.devices.currentIndexChanged.connect(self.device_selected)
        form.addRow("Manette", self.devices)
        self.profiles = QComboBox()
        self.profiles.currentTextChanged.connect(self.profile_selected)
        form.addRow("Profil assigné", self.profiles)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        edit = QPushButton("Modifier le profil")
        edit.clicked.connect(self.edit_profile)
        buttons.addWidget(edit)
        new = QPushButton("+ Nouveau profil")
        new.clicked.connect(self.new_profile)
        buttons.addWidget(new)
        layout.addLayout(buttons)
        info = QLabel("Maintenir HOME 0,8 s pour ouvrir cette fenêtre. Les modifications sont enregistrées automatiquement.")
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        layout.addStretch()
        self.manager.devices_changed.connect(self.refresh)
        self.refresh()
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.SP_ComputerIcon), self)
        menu = QMenu()
        menu.addAction("Configuration", self.show_from_tray)
        menu.addAction("Quitter", QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_from_tray() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def refresh(self, select=None):
        current = select or self.devices.currentData()
        self.devices.blockSignals(True)
        self.devices.clear()
        for key, name in self.settings.known_devices.items():
            connected = key in self.manager.controllers
            self.devices.addItem(("🟢 " if connected else "🔴 ") + name + " · " + key[-8:], key)
        index = self.devices.findData(current)
        self.devices.setCurrentIndex(index if index >= 0 else 0)
        self.devices.blockSignals(False)
        self.device_selected()

    def device_selected(self, *_):
        device = self.devices.currentData()
        self.profiles.blockSignals(True)
        self.profiles.clear()
        self.profiles.addItems(self.settings.profiles)
        assigned = self.settings.assignments.get(device, next(iter(self.settings.profiles)))
        self.profiles.setCurrentText(assigned)
        self.profiles.blockSignals(False)

    def profile_selected(self, name):
        device = self.devices.currentData()
        if device and name:
            self.settings.assignments[device] = name
            save(self.settings)

    def edit_profile(self):
        name = self.profiles.currentText()
        if not name: return
        dialog = ProfileDialog(self.settings.profiles[name], self)
        if dialog.exec() == QDialog.Accepted:
            self.settings.profiles[name] = dialog.profile
            save(self.settings)

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "Nouveau profil", "Nom du profil")
        name = name.strip()
        if ok and name and name not in self.settings.profiles:
            self.settings.profiles[name] = copy.deepcopy(next(iter(self.settings.profiles.values())))
            self.settings.profiles[name].name = name
            save(self.settings)
            self.device_selected()
            self.profiles.setCurrentText(name)

    def show_for_device(self, device):
        self.refresh(device)
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
