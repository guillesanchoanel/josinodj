"""
Diálogo que escanea una carpeta, detecta BPM con librosa
y lo escribe en los archivos de audio.
"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal

from ..models.track import is_audio_file


class _ScanWorker(QThread):
    progress = Signal(int, int, str)   # actual, total, mensaje
    finished = Signal(int, int, int)   # actualizados, ya_ok, fallidos

    def __init__(self, folder: str):
        super().__init__()
        self._folder = folder
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        from ..utils.bpm_writer import detect_bpm, write_bpm
        from ..utils.metadata import read_metadata

        files = []
        for dirpath, dirnames, filenames in os.walk(self._folder):
            dirnames[:] = sorted(
                d for d in dirnames
                if not d.startswith('.')
                and d.lower() not in {'appdata', 'programdata', 'program files',
                                      'program files (x86)', 'windows', 'system32',
                                      'syswow64', '$recycle.bin'}
            )
            for fn in sorted(filenames):
                if is_audio_file(fn):
                    files.append(os.path.join(dirpath, fn))

        total = len(files)
        updated = 0
        already_ok = 0
        failed = 0

        for i, fp in enumerate(files):
            if self._cancel:
                break

            name = os.path.basename(fp)
            self.progress.emit(i, total, name)

            try:
                meta = read_metadata(fp)
                existing_bpm = meta.get('bpm', 0.0)

                detected = detect_bpm(fp)
                if detected <= 0:
                    failed += 1
                    continue

                # Actualizar si: no tiene BPM, o difiere más de un 3%
                if existing_bpm > 0:
                    diff = abs(detected - existing_bpm) / existing_bpm
                    if diff < 0.03:
                        already_ok += 1
                        continue

                if write_bpm(fp, detected):
                    updated += 1
                else:
                    failed += 1

            except Exception:
                failed += 1

        self.progress.emit(total, total, '')
        self.finished.emit(updated, already_ok, failed)


class BpmScanDialog(QDialog):
    def __init__(self, folder: str, parent=None):
        super().__init__(parent)
        self._folder = folder
        self._worker = None
        self.setWindowTitle('Analizar BPM')
        self.setMinimumWidth(480)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self._on_reload = None   # callback para recargar la biblioteca al terminar
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        self._lbl = QLabel(f'Escaneando: {self._folder}')
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet('font-size:11px; color:#aaaacc;')
        lay.addWidget(self._lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        lay.addWidget(self._bar)

        self._file_lbl = QLabel('Preparando…')
        self._file_lbl.setStyleSheet('font-size:11px; color:#888899;')
        self._file_lbl.setWordWrap(True)
        lay.addWidget(self._file_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(120)
        self._log.setStyleSheet(
            'background:#0a0a14; color:#888899; font-size:11px;'
            'border:1px solid #222233; border-radius:4px;'
        )
        lay.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._btn_cancel = QPushButton('Cancelar')
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_close = QPushButton('Cerrar')
        self._btn_close.clicked.connect(self.accept)
        self._btn_close.setEnabled(False)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_close)
        lay.addLayout(btn_row)

    def start(self, on_reload=None):
        self._on_reload = on_reload
        self._worker = _ScanWorker(self._folder)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self.show()

    def _on_progress(self, current: int, total: int, name: str):
        if total > 0:
            pct = int(current / total * 100)
            self._bar.setValue(pct)
            self._bar.setFormat(f'{current} / {total}  ({pct}%)')
        if name:
            self._file_lbl.setText(f'Analizando: {name}')

    def _on_finished(self, updated: int, already_ok: int, failed: int):
        self._file_lbl.setText('Análisis completado.')
        self._bar.setValue(100)
        self._btn_cancel.setEnabled(False)
        self._btn_close.setEnabled(True)
        total = updated + already_ok + failed
        msg = (
            f'<b>Completado — {total} canciones analizadas</b><br>'
            f'✅ Actualizadas: <b>{updated}</b><br>'
            f'✓ Ya tenían BPM correcto: <b>{already_ok}</b><br>'
        )
        if failed:
            msg += f'⚠ No se pudo analizar: <b>{failed}</b>'
        self._log.setHtml(msg)
        if self._on_reload:
            self._on_reload()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._btn_cancel.setEnabled(False)
            self._file_lbl.setText('Cancelando…')
        else:
            self.reject()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
