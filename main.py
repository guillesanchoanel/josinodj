import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from josinodj.ui.main_window import MainWindow
from josinodj.utils.settings_manager import SettingsManager

ICON_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('JOSINODJ')
    app.setApplicationDisplayName('JOSINODJ')
    app.setApplicationVersion('1.0.0')

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
