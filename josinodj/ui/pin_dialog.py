import hashlib
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QPushButton, QLabel,
    QLineEdit, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()


class PinDialog(QDialog):
    """
    Numpad de PIN para desbloquear.
    - Si settings tiene 'pin_code' lo usa, si no usa '0000'.
    - Si settings tiene 'pin_master_hash' muestra enlace de recuperación.
    """

    def __init__(self, parent=None, title='Desbloquear JOSINODJ', settings=None):
        super().__init__(parent)
        self._settings = settings
        self._correct = settings.get('pin_code', '0000') if settings else '0000'
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

        icon = QLabel('🔒')
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet('font-size:38px; margin-bottom:4px;')
        layout.addWidget(icon)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet('color:#aaaacc; font-size:13px;')
        layout.addWidget(title_lbl)

        self._dots = QLabel('○  ○  ○  ○')
        self._dots.setAlignment(Qt.AlignCenter)
        self._dots.setStyleSheet(
            'font-size:30px; color:#6655ff; letter-spacing:4px; margin:8px 0;')
        layout.addWidget(self._dots)

        self._err = QLabel('')
        self._err.setAlignment(Qt.AlignCenter)
        self._err.setStyleSheet('color:#ff4444; font-size:11px; min-height:16px;')
        layout.addWidget(self._err)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, label in enumerate(['1','2','3','4','5','6','7','8','9']):
            r, c = divmod(i, 3)
            grid.addWidget(self._num_btn(label), r, c)
        grid.addWidget(self._del_btn(),    3, 0)
        grid.addWidget(self._num_btn('0'), 3, 1)
        grid.addWidget(self._ok_btn(),     3, 2)
        layout.addLayout(grid)

        cancel = QPushButton('Cancelar')
        cancel.setStyleSheet(
            'color:#333355; border:none; background:transparent; font-size:11px;')
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignCenter)

        # Enlace de recuperación — solo si hay contraseña maestra configurada
        if self._settings and self._settings.get('pin_master_hash', ''):
            recovery = QPushButton('¿Olvidaste el PIN?')
            recovery.setStyleSheet(
                'color:#2a2a55; border:none; background:transparent; font-size:11px;')
            recovery.clicked.connect(self._try_recovery)
            layout.addWidget(recovery, alignment=Qt.AlignCenter)

    # ── button factories ───────────────────────────────────────────────────

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

    # ── logic ──────────────────────────────────────────────────────────────

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
        if self._pin == self._correct:
            self.accept()
        else:
            self._err.setText('PIN incorrecto — inténtalo de nuevo')
            self._pin = ''
            self._refresh()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if Qt.Key_0 <= key <= Qt.Key_9:
            self._digit(str(key - Qt.Key_0))
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._backspace()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        else:
            super().keyPressEvent(event)

    def _try_recovery(self):
        dlg = _MasterPasswordDialog(self)
        if not dlg.exec():
            return
        pw = dlg.password()
        stored_hash = self._settings.get('pin_master_hash', '') if self._settings else ''
        if stored_hash and _hash_pw(pw) == stored_hash:
            # Resetear PIN a 0000
            if self._settings:
                self._settings.set('pin_code', '0000')
            QMessageBox.information(
                self, 'PIN restablecido',
                'El PIN ha sido restablecido a 0000.\n\nYa puedes acceder con 0000.')
            self.accept()
        else:
            QMessageBox.warning(self, 'Error', 'Contraseña maestra incorrecta.')


class _MasterPasswordDialog(QDialog):
    """Diálogo simple para introducir la contraseña maestra (texto, no numpad)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Contraseña maestra')
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setFixedWidth(300)
        self.setStyleSheet('QDialog{background:#0d0d18;} QLabel{color:#aaaacc;}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel('Introduce la contraseña maestra\npara restablecer el PIN a 0000:'))

        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.Password)
        self._input.setPlaceholderText('Contraseña maestra…')
        self._input.setStyleSheet(
            'background:#1a1a28; color:#e0e0e0; border:1px solid #3a3a60;'
            'border-radius:6px; padding:6px; font-size:14px;')
        layout.addWidget(self._input)

        btn_ok = QPushButton('Confirmar')
        btn_ok.setStyleSheet(
            'background:#0d1f0d; color:#44ee88; border:1px solid #1a4a1a;'
            'border-radius:6px; padding:6px; font-size:13px;')
        btn_ok.clicked.connect(self.accept)

        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(
            'background:#1a1a28; color:#888; border:1px solid #2a2a40;'
            'border-radius:6px; padding:6px; font-size:13px;')
        btn_cancel.clicked.connect(self.reject)

        layout.addWidget(btn_ok)
        layout.addWidget(btn_cancel)
        self._input.returnPressed.connect(self.accept)

    def password(self) -> str:
        return self._input.text()


class PinEntryDialog(QDialog):
    """
    Numpad para INTRODUCIR un PIN nuevo (sin validación — acepta cualquier 4 dígitos).
    Devuelve el PIN con .pin_value después de accept().
    """

    def __init__(self, parent=None, title='Introduce el nuevo PIN'):
        super().__init__(parent)
        self.setWindowTitle('Nuevo PIN')
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
        """)
        self._pin = ''
        self.pin_value = ''
        self._setup_ui(title)

    def _setup_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        icon = QLabel('🔑')
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet('font-size:38px; margin-bottom:4px;')
        layout.addWidget(icon)

        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet('color:#aaaacc; font-size:13px;')
        layout.addWidget(lbl)

        self._dots = QLabel('○  ○  ○  ○')
        self._dots.setAlignment(Qt.AlignCenter)
        self._dots.setStyleSheet(
            'font-size:30px; color:#6655ff; letter-spacing:4px; margin:8px 0;')
        layout.addWidget(self._dots)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, label in enumerate(['1','2','3','4','5','6','7','8','9']):
            r, c = divmod(i, 3)
            btn = QPushButton(label)
            btn.setObjectName('numBtn')
            btn.setFixedSize(68, 52)
            btn.clicked.connect(lambda _, d=label: self._digit(d))
            grid.addWidget(btn, r, c)

        del_btn = QPushButton('⌫')
        del_btn.setObjectName('delBtn')
        del_btn.setFixedSize(68, 52)
        del_btn.clicked.connect(self._backspace)
        grid.addWidget(del_btn, 3, 0)

        zero = QPushButton('0')
        zero.setObjectName('numBtn')
        zero.setFixedSize(68, 52)
        zero.clicked.connect(lambda: self._digit('0'))
        grid.addWidget(zero, 3, 1)

        ok_btn = QPushButton('✓')
        ok_btn.setObjectName('okBtn')
        ok_btn.setFixedSize(68, 52)
        ok_btn.clicked.connect(self._confirm)
        grid.addWidget(ok_btn, 3, 2)

        layout.addLayout(grid)

        cancel = QPushButton('Cancelar')
        cancel.setStyleSheet(
            'color:#333355; border:none; background:transparent; font-size:11px;')
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignCenter)

    def _digit(self, d):
        if len(self._pin) < 4:
            self._pin += d
            self._refresh()
            if len(self._pin) == 4:
                self._confirm()

    def _backspace(self):
        self._pin = self._pin[:-1]
        self._refresh()

    def _refresh(self):
        n = len(self._pin)
        self._dots.setText('●  ' * n + '○  ' * (4 - n))

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if Qt.Key_0 <= key <= Qt.Key_9:
            self._digit(str(key - Qt.Key_0))
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._backspace()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        else:
            super().keyPressEvent(event)

    def _confirm(self):
        if len(self._pin) == 4:
            self.pin_value = self._pin
            self.accept()
