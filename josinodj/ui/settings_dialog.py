from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QCheckBox, QGroupBox,
    QPushButton, QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal


class _UpdateChecker(QThread):
    result = Signal(str, str)  # (texto, color)

    def run(self):
        try:
            import urllib.request, json
            from josinodj.utils.updater import _local_version, _parse, API_URL
            req = urllib.request.Request(API_URL, headers={'User-Agent': 'JOSINODJ-updater'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            remote = data.get('tag_name', '').lstrip('v')
            if _parse(remote) > _parse(_local_version()):
                self.result.emit(f'✅ Nueva versión disponible: v{remote}', 'color:green; font-size:12px;')
            else:
                self.result.emit('✓ Tienes la versión más reciente', 'color:#555; font-size:12px;')
        except Exception as e:
            self.result.emit(f'⚠ Error: {e}', 'color:orange; font-size:12px;')


CHANGELOG = {
    '2.2.0': (
        '- Botón de Ayuda con guía completa del programa\n'
        '- Buscador en el móvil para filtrar canciones por título o artista'
    ),
    '2.1.0': (
        '- Desinstalador completamente arreglado\n'
        '- Ahora borra correctamente la carpeta de Program Files\n'
        '- Elimina el acceso directo del escritorio al desinstalar\n'
        '- Funciona desde Aplicaciones de Windows y desde DESINSTALAR.bat\n'
        '- Tamaño del programa visible en Aplicaciones de Windows\n'
        '- Corregido error "El sistema no puede encontrar la ruta especificada"'
    ),
    '2.0.0': (
        '- Control completo desde móvil vía WiFi\n'
        '- Menú contextual con long-press en móvil\n'
        '- Arrastrar y reordenar canciones desde móvil\n'
        '- Siguiente canción visible en móvil\n'
        '- Sistema de actualización automática\n'
        '- QR para conectar móvil fácilmente'
    ),
    '1.0.0': (
        '- Primera versión\n'
        '- Reproducción con shuffle\n'
        '- Marcado de canciones reproducidas\n'
        '- Efectos de DJ (EQ, reverb, etc.)\n'
        '- Modo bloqueo con PIN'
    ),
}


class SettingsDialog(QDialog):
    def __init__(self, settings, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ajustes — JOSINODJ')
        self.setMinimumSize(480, 380)
        self._settings = settings
        self._engine   = engine

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._make_audio_tab(),   '🔊 Audio')
        tabs.addTab(self._make_version_tab(), 'ℹ Versión')
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

    # ── Versión ───────────────────────────────────────────────────────────

    def _make_version_tab(self) -> QWidget:
        from josinodj.utils.updater import _local_version
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ver_grp = QGroupBox('Versión instalada')
        ver_layout = QVBoxLayout(ver_grp)
        ver_label = QLabel(f'<b>JOSINODJ v{_local_version()}</b>')
        ver_label.setStyleSheet('font-size:15px;')
        ver_layout.addWidget(ver_label)
        layout.addWidget(ver_grp)

        log_grp = QGroupBox('Historial de cambios')
        log_layout = QVBoxLayout(log_grp)
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setMaximumHeight(160)
        lines = []
        for ver, changes in CHANGELOG.items():
            lines.append(f'v{ver}:\n{changes}')
        log_text.setPlainText('\n\n'.join(lines))
        log_layout.addWidget(log_text)
        layout.addWidget(log_grp)

        check_row = QHBoxLayout()
        self._check_btn = QPushButton('🔍 Buscar actualizaciones')
        self._check_btn.clicked.connect(self._check_updates)
        self._update_status = QLabel('')
        self._update_status.setStyleSheet('font-size:12px;')
        check_row.addWidget(self._check_btn)
        check_row.addWidget(self._update_status, 1)
        layout.addLayout(check_row)

        layout.addStretch()
        return tab

    def _check_updates(self):
        self._check_btn.setEnabled(False)
        self._update_status.setText('Comprobando...')
        self._update_status.setStyleSheet('color:#555; font-size:12px;')
        self._checker = _UpdateChecker()
        self._checker.result.connect(self._on_check_result)
        self._checker.start()

    def _on_check_result(self, text, style):
        self._update_status.setText(text)
        self._update_status.setStyleSheet(style)
        self._check_btn.setEnabled(True)

    # ── save ─────────────────────────────────────────────────────────────

    def _save(self):
        mi = self._master_combo.currentIndex()
        dev = self._dev_indices[mi] if mi < len(self._dev_indices) else None
        self._settings.set('master_device', dev)
        self._engine.set_master_device(dev)

        norm = self._norm_check.isChecked()
        self._settings.set('normalize', norm)
        self._engine.normalize = norm
        self.accept()
