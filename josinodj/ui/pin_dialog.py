from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QPushButton, QLabel,
)
from PySide6.QtCore import Qt

CORRECT_PIN = '0000'


class PinDialog(QDialog):
    def __init__(self, parent=None, title='Desbloquear JOSINODJ'):
        super().__init__(parent)
        self.setWindowTitle('PIN')
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setFixedWidth(290)
        self.setStyleSheet("""
            QDialog { background:#0d0d18; border:2px solid #3a2080; border-radius:12px; }
            QPushButton#numBtn {
                background:#1a1a28; color:#e0e0e0; font-size:20px; font-weight:600;
                border:1px solid #2a2a40; border-radius:8px;
            }
            QPushButton#numBtn:hover { background:#252535; }
            QPushButton#numBtn:pressed { background:#111120; }
            QPushButton#delBtn {
                background:#1a1018; color:#ff6666; font-size:18px;
                border:1px solid #2a1020; border-radius:8px;
            }
            QPushButton#okBtn {
                background:#0d1f0d; color:#44ee88; font-size:18px;
                border:1px solid #1a4a1a; border-radius:8px;
            }
            QPushButton#okBtn:hover { background:#142814; }
        """)

        self._pin = ''
        self._setup_ui(title)

    def _setup_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Lock icon + title
        icon = QLabel('🔒')
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet('font-size:38px; margin-bottom:4px;')
        layout.addWidget(icon)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet('color:#aaaacc; font-size:13px;')
        layout.addWidget(title_lbl)

        # PIN dots display
        self._dots = QLabel('○  ○  ○  ○')
        self._dots.setAlignment(Qt.AlignCenter)
        self._dots.setStyleSheet(
            'font-size:30px; color:#6655ff; letter-spacing:4px; margin:8px 0;')
        layout.addWidget(self._dots)

        # Error
        self._err = QLabel('')
        self._err.setAlignment(Qt.AlignCenter)
        self._err.setStyleSheet('color:#ff4444; font-size:11px; min-height:16px;')
        layout.addWidget(self._err)

        # Numpad
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, label in enumerate(['1','2','3','4','5','6','7','8','9']):
            r, c = divmod(i, 3)
            btn = self._num_btn(label)
            grid.addWidget(btn, r, c)
        grid.addWidget(self._del_btn(),  3, 0)
        grid.addWidget(self._num_btn('0'), 3, 1)
        grid.addWidget(self._ok_btn(),   3, 2)
        layout.addLayout(grid)

        # Cancel link
        cancel = QPushButton('Cancelar')
        cancel.setStyleSheet(
            'color:#333355; border:none; background:transparent; font-size:11px;')
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignCenter)

    # ── button factories ──────────────────────────────────────────────────

    def _num_btn(self, d: str) -> QPushButton:
        btn = QPushButton(d)
        btn.setObjectName('numBtn')
        btn.setFixedSize(68, 52)
        btn.clicked.connect(lambda _, digit=d: self._digit(digit))
        return btn

    def _del_btn(self) -> QPushButton:
        btn = QPushButton('⌫')
        btn.setObjectName('delBtn')
        btn.setFixedSize(68, 52)
        btn.clicked.connect(self._backspace)
        return btn

    def _ok_btn(self) -> QPushButton:
        btn = QPushButton('✓')
        btn.setObjectName('okBtn')
        btn.setFixedSize(68, 52)
        btn.clicked.connect(self._confirm)
        return btn

    # ── logic ─────────────────────────────────────────────────────────────

    def _digit(self, d: str):
        if len(self._pin) < 4:
            self._pin += d
            self._refresh()
            if len(self._pin) == 4:
                self._confirm()

    def _backspace(self):
        self._pin = self._pin[:-1]
        self._err.setText('')
        self._refresh()

    def _refresh(self):
        n = len(self._pin)
        self._dots.setText('●  ' * n + '○  ' * (4 - n))

    def _confirm(self):
        if self._pin == CORRECT_PIN:
            self.accept()
        else:
            self._err.setText('PIN incorrecto — inténtalo de nuevo')
            self._pin = ''
            self._refresh()
