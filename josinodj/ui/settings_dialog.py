from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QCheckBox, QGroupBox,
    QPushButton, QTextEdit, QLineEdit, QMessageBox,
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
    '2.4.0': (
        '- BPM automático: se detecta y guarda en segundo plano al añadir canciones sin BPM\n'
        '- Play arranca la primera canción de la lista si no hay ninguna activa\n'
        '- YouTube: búsqueda ampliada a 100 resultados\n'
        '- YouTube: filtro por duración (Hasta 10 min / Más de 10 min / Todos)\n'
        '- Corrección: botón "Añadir a lista" se resetea correctamente entre descargas'
    ),
    '2.3.4': (
        '- Corrección: instalador ya no falla con "Infracción al compartir" al actualizar\n'
        '  (el aviso de cierre se muestra antes de lanzar INSTALAR.bat)'
    ),
    '2.3.3': (
        '- Arrastrar canciones desde la búsqueda directamente a la lista\n'
        '- El numpad del PIN ahora acepta teclado (números, Backspace, Enter)\n'
        '- Corrección: cambiar canción durante crossfade actualiza audio y UI correctamente\n'
        '- Corrección: insertar canción en lista durante crossfade ya no confunde la pista actual\n'
        '- Corrección: actualizaciones automáticas muestran barra de progreso y aviso de UAC'
    ),
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
        tabs.addTab(self._make_audio_tab(),    '🔊 Audio')
        # tabs.addTab(self._make_security_tab(), '🔒 Seguridad')  # TODO: habilitar en futuro
        tabs.addTab(self._make_version_tab(),  'ℹ Versión')
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

    # ── Seguridad ─────────────────────────────────────────────────────────

    def _make_security_tab(self) -> QWidget:
        from .pin_dialog import PinDialog, PinEntryDialog, _hash_pw
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # ── PIN de bloqueo ────────────────────────────────────────────────
        pin_grp = QGroupBox('PIN de bloqueo de pantalla')
        pin_l = QVBoxLayout(pin_grp)
        current_pin = self._settings.get('pin_code', '0000')
        pin_info = QLabel(f'PIN actual: {"●" * len(current_pin)}  ({len(current_pin)} dígitos)  |  Por defecto: 0000')
        pin_info.setStyleSheet('color:#666688; font-size:11px;')
        pin_l.addWidget(pin_info)
        btn_change_pin = QPushButton('Cambiar PIN…')
        btn_change_pin.setFixedHeight(30)
        btn_change_pin.clicked.connect(lambda: self._change_pin(pin_info))
        pin_l.addWidget(btn_change_pin)
        layout.addWidget(pin_grp)

        # ── Contraseña maestra ────────────────────────────────────────────
        master_grp = QGroupBox('Contraseña maestra (recuperación del PIN)')
        master_l = QVBoxLayout(master_grp)

        has_master = bool(self._settings.get('pin_master_hash', ''))
        self._master_status = QLabel(
            '✓ Contraseña maestra configurada' if has_master
            else '⚠ Sin contraseña maestra — si olvidas el PIN no podrás recuperarlo')
        self._master_status.setStyleSheet(
            f'color:{"#44aa66" if has_master else "#aa8800"}; font-size:11px;')
        master_l.addWidget(self._master_status)

        note = QLabel(
            'La contraseña maestra te permite resetear el PIN a 0000\n'
            'desde el numpad de bloqueo si alguna vez lo olvidas.')
        note.setWordWrap(True)
        note.setStyleSheet('color:#555566; font-size:11px;')
        master_l.addWidget(note)

        btn_set_master = QPushButton('Establecer / Cambiar contraseña maestra…')
        btn_set_master.setFixedHeight(30)
        btn_set_master.clicked.connect(self._set_master_password)
        master_l.addWidget(btn_set_master)

        btn_clear_master = QPushButton('Quitar contraseña maestra')
        btn_clear_master.setFixedHeight(30)
        btn_clear_master.setStyleSheet('color:#aa4444;')
        btn_clear_master.clicked.connect(self._clear_master_password)
        master_l.addWidget(btn_clear_master)

        layout.addWidget(master_grp)
        layout.addStretch()
        return tab

    def _change_pin(self, pin_info_label=None):
        from .pin_dialog import PinDialog, PinEntryDialog
        # Paso 1: verificar PIN actual
        dlg = PinDialog(self, 'Introduce el PIN actual para continuar', self._settings)
        if not dlg.exec():
            return
        # Paso 2: nuevo PIN
        dlg2 = PinEntryDialog(self, 'Introduce el nuevo PIN (4 dígitos)')
        if not dlg2.exec():
            return
        new_pin = dlg2.pin_value
        # Paso 3: confirmar nuevo PIN
        dlg3 = PinEntryDialog(self, 'Confirma el nuevo PIN')
        if not dlg3.exec():
            return
        if dlg3.pin_value != new_pin:
            QMessageBox.warning(self, 'Error', 'Los PINs no coinciden. No se ha cambiado.')
            return
        self._settings.set('pin_code', new_pin)
        if pin_info_label:
            pin_info_label.setText(
                f'PIN actual: {"●" * len(new_pin)}  ({len(new_pin)} dígitos)  |  Por defecto: 0000')
        QMessageBox.information(self, 'PIN cambiado', 'El PIN se ha cambiado correctamente.')

    def _set_master_password(self):
        from .pin_dialog import _hash_pw
        # Si ya hay contraseña maestra, pedir la actual primero
        if self._settings.get('pin_master_hash', ''):
            old_dlg = _MasterInputDialog(self, 'Introduce la contraseña maestra actual:')
            if not old_dlg.exec():
                return
            from .pin_dialog import _hash_pw as h
            if h(old_dlg.value()) != self._settings.get('pin_master_hash', ''):
                QMessageBox.warning(self, 'Error', 'Contraseña maestra incorrecta.')
                return

        dlg = _MasterInputDialog(self, 'Nueva contraseña maestra:')
        if not dlg.exec() or not dlg.value().strip():
            return
        dlg2 = _MasterInputDialog(self, 'Confirma la nueva contraseña maestra:')
        if not dlg2.exec():
            return
        if dlg.value() != dlg2.value():
            QMessageBox.warning(self, 'Error', 'Las contraseñas no coinciden.')
            return
        self._settings.set('pin_master_hash', _hash_pw(dlg.value()))
        self._master_status.setText('✓ Contraseña maestra configurada')
        self._master_status.setStyleSheet('color:#44aa66; font-size:11px;')
        QMessageBox.information(self, 'Listo', 'Contraseña maestra establecida correctamente.')

    def _clear_master_password(self):
        if not self._settings.get('pin_master_hash', ''):
            QMessageBox.information(self, 'Aviso', 'No hay contraseña maestra configurada.')
            return
        r = QMessageBox.question(self, 'Quitar contraseña maestra',
                                 '¿Seguro que quieres quitar la contraseña maestra?\n'
                                 'Si olvidas el PIN no habrá forma de recuperarlo.',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        self._settings.set('pin_master_hash', '')
        self._master_status.setText(
            '⚠ Sin contraseña maestra — si olvidas el PIN no podrás recuperarlo')
        self._master_status.setStyleSheet('color:#aa8800; font-size:11px;')

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

    def _save(self):  # noqa: E303
        mi = self._master_combo.currentIndex()
        dev = self._dev_indices[mi] if mi < len(self._dev_indices) else None
        self._settings.set('master_device', dev)
        self._engine.set_master_device(dev)

        norm = self._norm_check.isChecked()
        self._settings.set('normalize', norm)
        self._engine.normalize = norm
        self.accept()


class _MasterInputDialog(QDialog):
    """Campo de texto para introducir la contraseña maestra."""

    def __init__(self, parent=None, label: str = 'Contraseña maestra:'):
        super().__init__(parent)
        self.setWindowTitle('Contraseña maestra')
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setFixedWidth(320)
        self.setStyleSheet('QDialog{background:#0d0d18;} QLabel{color:#aaaacc;}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(QLabel(label))

        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.Password)
        self._input.setPlaceholderText('Contraseña…')
        self._input.setStyleSheet(
            'background:#1a1a28; color:#e0e0e0; border:1px solid #3a3a60;'
            'border-radius:6px; padding:6px; font-size:14px;')
        layout.addWidget(self._input)

        row = QHBoxLayout()
        btn_ok = QPushButton('Confirmar')
        btn_ok.setStyleSheet(
            'background:#0d1f0d; color:#44ee88; border:1px solid #1a4a1a;'
            'border-radius:6px; padding:5px; font-size:13px;')
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.setStyleSheet(
            'background:#1a1a28; color:#888; border:1px solid #2a2a40;'
            'border-radius:6px; padding:5px; font-size:13px;')
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        layout.addLayout(row)
        self._input.returnPressed.connect(self.accept)

    def value(self) -> str:
        return self._input.text()
