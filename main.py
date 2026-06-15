import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from josinodj.ui.main_window import MainWindow
from josinodj.utils.settings_manager import SettingsManager
from josinodj.utils.updater import check_and_update, _local_version

ICON_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('JOSINODJ')
    app.setApplicationDisplayName('JOSINODJ')
    app.setApplicationVersion(_local_version())

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # Comprobar actualizaciones antes de abrir la ventana principal
    if check_and_update():
        sys.exit(0)

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
