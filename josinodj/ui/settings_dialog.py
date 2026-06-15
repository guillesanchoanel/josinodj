from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QCheckBox, QGroupBox,
    QPushButton,
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, settings, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ajustes — JOSINODJ')
        self.setMinimumSize(440, 340)
        self._settings = settings
        self._engine   = engine

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._make_audio_tab(), '🔊 Audio')
        layout.addWidget(tabs)

        btns = QHBoxLayout()
        ok = QPushButton('Guardar')
        ok.clicked.connect(self._save)
        cancel = QPushButton('Cancelar')
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    # ── Audio ─────────────────────────────────────────────────────────────

    def _make_audio_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        devices = self._engine.get_devices()
        names   = ['(Predeterminado)'] + [d['name'] for d in devices]
        self._dev_indices = [None] + [d['index'] for d in devices]

        grp = QGroupBox('Dispositivo de salida (altavoces / mezcla master)')
        gl  = QHBoxLayout(grp)
        self._master_combo = QComboBox()
        self._master_combo.addItems(names)
        cur = self._settings.get('master_device')
        if cur in self._dev_indices:
            self._master_combo.setCurrentIndex(self._dev_indices.index(cur))
        gl.addWidget(QLabel('Dispositivo:'))
        gl.addWidget(self._master_combo, 1)
        layout.addWidget(grp)

        note = QLabel('💡 Selecciona la tarjeta de sonido o dispositivo USB con el que quieres que suene la música.')
        note.setWordWrap(True)
        note.setStyleSheet('color:#555555; font-size:11px;')
        layout.addWidget(note)

        norm_grp = QGroupBox('Normalización de volumen')
        nl = QVBoxLayout(norm_grp)
        self._norm_check = QCheckBox('Igualar volumen automáticamente entre canciones')
        self._norm_check.setChecked(self._settings.get('normalize', True))
        nl.addWidget(self._norm_check)
        norm_note = QLabel('Analiza cada canción y ajusta su nivel para que todas suenen al mismo volumen (target -16 dBFS).')
        norm_note.setWordWrap(True)
        norm_note.setStyleSheet('color:#555555; font-size:11px;')
        nl.addWidget(norm_note)
        layout.addWidget(norm_grp)

        layout.addStretch()
        return tab

    # ── Playback ──────────────────────────────────────────────────────────

    def _make_playback_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        misc_grp = QGroupBox('Reproducción')
        miscl = QVBoxLayout(misc_grp)
        self._auto_check = QCheckBox('Auto-mix: reproducir la lista automáticamente')
        self._auto_check.setChecked(self._settings.get('auto_play', True))
        self._shuf_check = QCheckBox('Modo aleatorio por defecto al iniciar')
        self._shuf_check.setChecked(self._settings.get('shuffle', False))
        miscl.addWidget(self._auto_check)
        miscl.addWidget(self._shuf_check)
        layout.addWidget(misc_grp)

        layout.addStretch()
        return tab

    # ── save ─────────────────────────────────────────────────────────────

    def _save(self):
        mi = self._master_combo.currentIndex()
        dev = self._dev_indices[mi] if mi < len(self._dev_indices) else None
        self._settings.set('master_device', dev)
        self._engine.set_master_device(dev)

        self._settings.set('auto_play', self._auto_check.isChecked())
        self._settings.set('shuffle',   self._shuf_check.isChecked())
        norm = self._norm_check.isChecked()
        self._settings.set('normalize', norm)
        self._engine.normalize = norm
        self.accept()
