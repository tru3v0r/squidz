"""Application composition root."""
import os
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from squidz.infra.storage import load
from squidz.infra.browser import BrowserBridge
from squidz.core.controllers import ControllerManager
from squidz.ui.windows import MainWindow, CSS, load_fonts

def main():
    if os.name != "nt":
        raise SystemExit("squidz requires Windows 10/11")
    app = QApplication(sys.argv)
    load_fonts()
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(CSS)
    try:
        settings = load()
        bridge = BrowserBridge(settings.browser_token, settings.port)
        bridge.start()
        manager = ControllerManager(settings, bridge)
    except Exception as exc:
        QMessageBox.critical(None, "squidz", str(exc))
        return 1
    window = MainWindow(settings, manager)
    manager.settings_requested.connect(window.show_for_device)
    manager.error.connect(lambda message: window.statusBar().showMessage(message, 5000))
    window.show()
    app.aboutToQuit.connect(bridge.stop)
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
