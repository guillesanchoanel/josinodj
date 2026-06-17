import threading
import shutil
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QApplication,
    QTabWidget, QWidget, QListWidget, QListWidgetItem,
    QAbstractItemView, QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal, QObject


# ── helpers ───────────────────────────────────────────────────────────────────

def _bundled_ffmpeg() -> str | None:
    if hasattr(sys, '_MEIPASS'):
        candidate = os.path.join(sys._MEIPASS, '..', 'ffmpeg.exe')
    else:
        candidate = os.path.join(
            os.path.dirname(__file__), '..', '..', 'assets', 'ffmpeg.exe')
    candidate = os.path.normpath(candidate)
    return candidate if os.path.exists(candidate) else shutil.which('ffmpeg')


def _fmt_dur(secs) -> str:
    if not secs:
        return ''
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


# ── signals ───────────────────────────────────────────────────────────────────

class _Sigs(QObject):
    progress      = Signal(float, str)
    done          = Signal(str)
    error         = Signal(str)
    search_done   = Signal(list)        # list of dicts
    search_error  = Signal(str)


# ── dialog ────────────────────────────────────────────────────────────────────

_BASE_STYLE = """
    QDialog   { background:#0d0d18; }
    QLabel    { color:#cccccc; }
    QTabWidget::pane  { background:#0d0d18; border:1px solid #1e1e38; }
    QTabBar::tab      { background:#111128; color:#666688; padding:7px 18px;
                        border:1px solid #1e1e38; border-bottom:none; border-radius:4px 4px 0 0; }
    QTabBar::tab:selected { background:#0d0d18; color:#e0e0ff; }
    QLineEdit { background:#141428; border:1px solid #2a2a50; border-radius:5px;
                padding:7px 10px; color:#e0e0e0; font-size:13px; }
    QListWidget { background:#0a0a16; border:1px solid #1e1e38; border-radius:5px;
                  color:#cccccc; font-size:12px; outline:none; }
    QListWidget::item { padding:8px 10px; border-bottom:1px solid #111128; }
    QListWidget::item:hover    { background:#15152a; }
    QListWidget::item:selected { background:#1e1e40; color:#ffffff; }
    QProgressBar { background:#151528; border:none; border-radius:4px;
                   height:10px; text-align:center; }
    QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #5a50e0,stop:1 #00ccff); border-radius:4px; }
"""


class DownloadDialog(QDialog):
    file_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Descargar de YouTube  –  JOSINODJ')
        self.setMinimumSize(560, 480)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet(_BASE_STYLE)

        self._sigs        = _Sigs()
        self._cancelled   = False
        self._last_file   = ''
        self._dl_url      = ''     # URL que se está descargando actualmente
        self._all_results = []     # resultados sin filtrar

        self._sigs.progress.connect(self._on_progress)
        self._sigs.done.connect(self._on_done)
        self._sigs.error.connect(self._on_error)
        self._sigs.search_done.connect(self._on_search_results)
        self._sigs.search_error.connect(self._on_search_error)

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        title = QLabel('🎵  Descargar audio de YouTube')
        title.setStyleSheet('font-size:16px; font-weight:700; color:#ffffff;')
        root.addWidget(title)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_search_tab(), '🔍  Buscar en YouTube')
        self._tabs.addTab(self._build_url_tab(),    '🔗  Pegar enlace')
        root.addWidget(self._tabs, 1)

        # Progress (shared)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(10)
        self._bar.setTextVisible(False)
        root.addWidget(self._bar)

        self._status = QLabel(' ')
        self._status.setStyleSheet('font-size:12px; color:#666688; min-height:16px;')
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._btn_close = QPushButton('Cerrar')
        self._btn_close.setFixedHeight(34)
        self._btn_close.setStyleSheet(
            'background:#1a1a2a; border:1px solid #2a2a40;'
            'border-radius:5px; color:#888899; padding:0 16px;')
        self._btn_close.clicked.connect(self.reject)

        self._btn_add = QPushButton('➕ Añadir a la lista')
        self._btn_add.setFixedHeight(34)
        self._btn_add.setStyleSheet(
            'background:#0d2218; border:1px solid #1a5c38;'
            'border-radius:5px; color:#44ee88; padding:0 16px;')
        self._btn_add.hide()
        self._btn_add.clicked.connect(self._add_to_playlist)

        btn_row.addWidget(self._btn_close)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_add)
        root.addLayout(btn_row)

    # ── Search tab ────────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 12, 0, 0)

        # Search bar
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText('Busca artista, canción, mix…')
        self._search_edit.returnPressed.connect(self._do_search)
        self._btn_search = QPushButton('Buscar')
        self._btn_search.setFixedSize(80, 36)
        self._btn_search.setStyleSheet(
            'background:#1a1060; border:1px solid #3a30aa;'
            'border-radius:5px; color:#aaaaff; font-weight:600;')
        self._btn_search.clicked.connect(self._do_search)
        search_row.addWidget(self._search_edit)
        search_row.addWidget(self._btn_search)
        layout.addLayout(search_row)

        # Duration filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(16)
        filter_lbl = QLabel('Duración:')
        filter_lbl.setStyleSheet('color:#666688; font-size:11px;')
        _rb_style = 'color:#aaaacc; font-size:11px;'
        self._rb_short  = QRadioButton('Hasta 10 min')
        self._rb_long   = QRadioButton('Más de 10 min')
        self._rb_all    = QRadioButton('Todos')
        for rb in (self._rb_short, self._rb_long, self._rb_all):
            rb.setStyleSheet(_rb_style)
        self._rb_short.setChecked(True)
        self._dur_group = QButtonGroup(self)
        self._dur_group.addButton(self._rb_short, 0)
        self._dur_group.addButton(self._rb_long,  1)
        self._dur_group.addButton(self._rb_all,   2)
        self._dur_group.buttonClicked.connect(self._apply_dur_filter)
        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._rb_short)
        filter_row.addWidget(self._rb_long)
        filter_row.addWidget(self._rb_all)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Results list
        self._results = QListWidget()
        self._results.setSelectionMode(QAbstractItemView.SingleSelection)
        self._results.setAlternatingRowColors(False)
        self._results.itemDoubleClicked.connect(self._on_result_double_click)
        self._results.setToolTip('Doble clic para descargar')

        hint = QLabel('Pulsa dos veces sobre una canción para descargarla')
        hint.setStyleSheet('color:#333355; font-size:11px;')
        hint.setAlignment(Qt.AlignCenter)
        self._results_hint = hint

        layout.addWidget(self._results, 1)
        layout.addWidget(hint)
        return w

    # ── URL tab ───────────────────────────────────────────────────────────

    def _build_url_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 12, 0, 0)

        layout.addWidget(QLabel('Pega aquí el enlace de YouTube:'))
        url_row = QHBoxLayout()
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText('https://www.youtube.com/watch?v=...')
        self._url_edit.returnPressed.connect(self._start_url_download)
        btn_paste = QPushButton('📋 Pegar')
        btn_paste.setFixedHeight(36)
        btn_paste.setStyleSheet(
            'background:#1e1e38; border:1px solid #2a2a50;'
            'border-radius:5px; color:#aaaacc; padding:0 10px;')
        btn_paste.clicked.connect(
            lambda: self._url_edit.setText(QApplication.clipboard().text()))
        url_row.addWidget(self._url_edit)
        url_row.addWidget(btn_paste)
        layout.addLayout(url_row)

        dest_lbl = QLabel(f'📁  Se guardará en:  {Path.home() / "Downloads"}')
        dest_lbl.setStyleSheet('font-size:11px; color:#444466;')
        layout.addWidget(dest_lbl)

        self._btn_dl = QPushButton('⬇  Descargar')
        self._btn_dl.setFixedHeight(36)
        self._btn_dl.setStyleSheet(
            'background:#1a1060; border:1px solid #3a30aa;'
            'border-radius:5px; color:#aaaaff; font-weight:600;')
        self._btn_dl.clicked.connect(self._start_url_download)
        layout.addWidget(self._btn_dl, alignment=Qt.AlignLeft)
        layout.addStretch()
        return w

    # ── Search logic ──────────────────────────────────────────────────────

    def _do_search(self):
        query = self._search_edit.text().strip()
        if not query:
            return
        self._results.clear()
        self._results.addItem('Buscando…')
        self._btn_search.setEnabled(False)
        self._status.setText('')
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str):
        try:
            import yt_dlp
            opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f'ytsearch100:{query}', download=False)
            entries = data.get('entries', []) if data else []
            results = []
            for e in entries:
                if not e:
                    continue
                results.append({
                    'title':    e.get('title', '?'),
                    'duration': e.get('duration'),
                    'uploader': e.get('uploader') or e.get('channel', ''),
                    'url':      e.get('url') or e.get('webpage_url', ''),
                    'id':       e.get('id', ''),
                })
            self._sigs.search_done.emit(results)
        except Exception as ex:
            self._sigs.search_error.emit(str(ex))

    def _on_search_results(self, results: list):
        self._all_results = results
        self._btn_search.setEnabled(True)
        self._apply_dur_filter()

    def _apply_dur_filter(self, _btn=None):
        mode = self._dur_group.checkedId()   # 0=corto, 1=largo, 2=todos
        self._results.clear()
        filtered = []
        for r in self._all_results:
            d = r.get('duration') or 0
            if mode == 0 and d > 600:    # Hasta 10 min: excluir largos
                continue
            if mode == 1 and (d == 0 or d <= 600):  # Más de 10 min: excluir cortos y sin duración
                continue
            filtered.append(r)
        if not filtered:
            self._results.addItem('Sin resultados con este filtro.')
            return
        for r in filtered:
            dur = _fmt_dur(r['duration'])
            line1 = r['title']
            line2 = f"  {r['uploader']}  ·  {dur}" if dur else f"  {r['uploader']}"
            item = QListWidgetItem()
            item.setText(f"{line1}\n{line2}")
            item.setData(Qt.UserRole, r['url'])
            item.setData(Qt.UserRole + 1, r['id'])
            self._results.addItem(item)

    def _on_search_error(self, msg: str):
        self._results.clear()
        self._btn_search.setEnabled(True)
        self._status.setText(f'❌  Error al buscar: {msg[:120]}')

    def _on_result_double_click(self, item: QListWidgetItem):
        url = item.data(Qt.UserRole)
        vid_id = item.data(Qt.UserRole + 1)
        if vid_id:
            url = f'https://www.youtube.com/watch?v={vid_id}'
        if url:
            self._status.setText(f'Descargando:  {item.text().splitlines()[0]}')
            self._results.setEnabled(False)
            self._btn_search.setEnabled(False)
            self._start_download(url)

    # ── Download logic ────────────────────────────────────────────────────

    def _start_url_download(self):
        url = self._url_edit.text().strip()
        if not url:
            self._status.setText('⚠  Introduce un enlace.')
            return
        if not url.startswith('http'):
            self._status.setText('⚠  El enlace no parece válido.')
            return
        self._btn_dl.setEnabled(False)
        self._start_download(url)

    def _start_download(self, url: str):
        try:
            import yt_dlp  # noqa
        except ImportError:
            self._status.setText('⚠  yt-dlp no está instalado. Ejecuta: pip install yt-dlp')
            return
        self._bar.setValue(0)
        self._btn_add.hide()
        self._last_file = ''
        self._cancelled = False
        self._dl_url    = url
        threading.Thread(target=self._worker, args=(url,), daemon=True).start()

    def _worker(self, url: str):
        import yt_dlp
        dl_dir = Path.home() / 'Downloads'
        dl_dir.mkdir(exist_ok=True)
        ffmpeg_path = _bundled_ffmpeg()

        opts = {
            'format':   'bestaudio/best',
            'outtmpl':  str(dl_dir / '%(title)s.%(ext)s'),
            'quiet':    True,
            'no_warnings': True,
            'progress_hooks': [self._hook],
            'postprocessors': [{
                'key':             'FFmpegExtractAudio',
                'preferredcodec':  'mp3',
                'preferredquality': '192',
            }],
        }
        if ffmpeg_path:
            opts['ffmpeg_location'] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info     = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
            mp3 = Path(filepath).with_suffix('.mp3')
            if mp3.exists() and mp3.stat().st_size > 0:
                filepath = str(mp3)
                for leftover in Path(filepath).parent.glob(
                        Path(mp3).stem + '.*'):
                    if leftover.suffix.lower() != '.mp3' and leftover.exists():
                        try:
                            leftover.unlink()
                        except Exception:
                            pass
            self._sigs.done.emit(filepath)
        except Exception as e:
            self._sigs.error.emit(str(e))

    def _hook(self, d: dict):
        if self._cancelled:
            raise Exception('Cancelado')
        if d['status'] == 'downloading':
            total   = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            current = d.get('downloaded_bytes', 0)
            pct     = (current / total * 100) if total > 0 else 0
            speed   = d.get('_speed_str', '').strip()
            eta     = d.get('_eta_str', '').strip()
            txt     = f'Descargando…  {pct:.0f}%'
            if speed: txt += f'  ·  {speed}'
            if eta:   txt += f'  ·  ETA {eta}'
            self._sigs.progress.emit(pct, txt)
        elif d['status'] == 'finished':
            self._sigs.progress.emit(99, 'Convirtiendo a MP3…')

    # ── signal handlers ───────────────────────────────────────────────────

    def _on_progress(self, pct: float, txt: str):
        self._bar.setValue(int(pct))
        self._status.setText(txt)

    def _on_done(self, filepath: str):
        self._last_file = filepath
        self._bar.setValue(100)
        self._status.setText(f'✅  {Path(filepath).name}')
        # Re-enable controls
        self._btn_dl.setEnabled(True)
        self._results.setEnabled(True)
        self._btn_search.setEnabled(True)
        self._btn_add.setText('➕ Añadir a la lista')
        self._btn_add.setEnabled(True)
        self._btn_add.show()

    def _on_error(self, msg: str):
        self._bar.setValue(0)
        self._status.setText(f'❌  {msg[:200]}')
        self._btn_dl.setEnabled(True)
        self._results.setEnabled(True)
        self._btn_search.setEnabled(True)

    def _add_to_playlist(self):
        if self._last_file:
            self.file_ready.emit(self._last_file)
            self._btn_add.setText('✓ Añadido')
            self._btn_add.setEnabled(False)
