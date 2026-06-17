import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QAbstractItemView, QHeaderView, QFileDialog, QMenu, QTreeWidget,
    QTreeWidgetItem, QSplitter,
)
from PySide6.QtCore import Qt, Signal, QRunnable, QThreadPool, QObject, QUrl, QMimeData
from PySide6.QtGui import QAction, QDrag

from ..models.track import Track, is_audio_file

_SKIP = {
    'appdata', 'programdata', 'program files', 'program files (x86)',
    'windows', 'system32', 'syswow64', '$recycle.bin',
}


# ── Drag-capable table ────────────────────────────────────────────────────────

class _DragTable(QTableWidget):
    """QTableWidget that produces text/uri-list mime data when dragging rows."""

    def startDrag(self, supported_actions):
        seen, tracks = set(), []
        for item in self.selectedItems():
            r = item.row()
            if r not in seen:
                seen.add(r)
                track = self.item(r, 0).data(Qt.UserRole)
                if track:
                    tracks.append(track)
        if not tracks:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(t.path) for t in tracks])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)


# ── Signals ───────────────────────────────────────────────────────────────────

class _Sigs(QObject):
    track_ready = Signal(object)
    done        = Signal(int)


# ── Loaders ───────────────────────────────────────────────────────────────────

class _AllFilesLoader(QRunnable):
    """Carga todos los archivos de audio de folder y subcarpetas."""
    def __init__(self, root: str, signals: _Sigs, generation: int):
        super().__init__()
        self._root = root
        self.signals = signals
        self._gen = generation

    def run(self):
        from ..utils.metadata import read_metadata
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = sorted(
                d for d in dirnames
                if not d.startswith('.')
                and d.lower() not in _SKIP
            )
            for fn in sorted(filenames):
                if not is_audio_file(fn):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    track = Track(path=fp, **read_metadata(fp))
                except Exception:
                    track = Track(path=fp)
                self.signals.track_ready.emit(track)
        self.signals.done.emit(self._gen)


# ── Panel ─────────────────────────────────────────────────────────────────────

class LibraryPanel(QWidget):
    add_to_playlist = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName('libraryPanel')
        self._settings       = settings
        self._master         = ''
        self._current_folder = ''
        self._pool           = QThreadPool.globalInstance()
        self._gen            = 0
        self._active_sigs: set = set()
        self._setup_ui()
        self._restore_master()

    # ── UI ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Carpeta madre
        top = QWidget()
        top.setFixedHeight(44)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.setSpacing(6)
        self._master_lbl = QLabel('Sin carpeta')
        self._master_lbl.setStyleSheet('color:#444466; font-size:11px;')
        btn_change = QPushButton('📁 Elegir')
        btn_change.setFixedHeight(28)
        btn_change.setToolTip('Seleccionar carpeta madre de música')
        btn_change.clicked.connect(self._choose_master)
        tl.addWidget(self._master_lbl, 1)
        tl.addWidget(btn_change)
        layout.addWidget(top)

        # ── Splitter: árbol arriba / pistas abajo (redimensionable) ─────────
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)

        # Sección árbol
        tree_w = QWidget()
        tree_l = QVBoxLayout(tree_w)
        tree_l.setContentsMargins(0, 0, 0, 0)
        tree_l.setSpacing(0)

        sf_hdr = QLabel('CARPETAS')
        sf_hdr.setObjectName('sectionHdr')
        tree_l.addWidget(sf_hdr)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(40)
        self._tree.setStyleSheet(
            'QTreeWidget{background:#0f0f0f; border:none;}'
            'QTreeWidget::item{padding:4px 6px; color:#aaaacc;}'
            'QTreeWidget::item:hover{background:#181828;}'
            'QTreeWidget::item:selected{background:#1c2f4a; color:#ffffff;}'
            'QTreeWidget::branch{background:#0f0f0f;}'
        )
        self._tree.itemClicked.connect(self._on_tree_click)
        tree_l.addWidget(self._tree)

        splitter.addWidget(tree_w)

        # Sección pistas
        tracks_w = QWidget()
        tracks_l = QVBoxLayout(tracks_w)
        tracks_l.setContentsMargins(0, 0, 0, 0)
        tracks_l.setSpacing(0)

        tracks_hdr = QWidget()
        thl = QHBoxLayout(tracks_hdr)
        thl.setContentsMargins(8, 3, 8, 3)
        thl.setSpacing(6)
        tracks_lbl = QLabel('PISTAS')
        tracks_lbl.setObjectName('sectionHdr')
        thl.addWidget(tracks_lbl)
        thl.addStretch()
        btn_add_all = QPushButton('📂 Añadir todo')
        btn_add_all.setFixedHeight(24)
        btn_add_all.setStyleSheet('font-size:11px; padding:2px 8px;')
        btn_add_all.setToolTip('Añadir todas las pistas visibles a la lista')
        btn_add_all.clicked.connect(self._add_all_visible)
        thl.addWidget(btn_add_all)
        tracks_l.addWidget(tracks_hdr)

        sb = QWidget()
        sb.setFixedHeight(34)
        sl = QHBoxLayout(sb)
        sl.setContentsMargins(6, 3, 6, 3)
        self._search = QLineEdit()
        self._search.setPlaceholderText('🔍 Buscar pistas…')
        self._search.textChanged.connect(self._filter)
        self._search.setClearButtonEnabled(True)
        sl.addWidget(self._search)
        tracks_l.addWidget(sb)

        self._table = _DragTable(0, 4)
        self._table.setHorizontalHeaderLabels(['Título', 'Artista', 'Carpeta', 'Dur.'])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(3, 48)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setDragEnabled(True)
        self._table.setDragDropMode(QAbstractItemView.DragOnly)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._track_ctx)
        tracks_l.addWidget(self._table, 1)

        splitter.addWidget(tracks_w)
        splitter.setSizes([200, 400])
        layout.addWidget(splitter, 1)

        self._loading_lbl = QLabel('Cargando…')
        self._loading_lbl.setAlignment(Qt.AlignCenter)
        self._loading_lbl.setStyleSheet('color:#444444; font-size:12px; padding:12px;')
        self._loading_lbl.setWordWrap(True)
        self._loading_lbl.hide()
        layout.addWidget(self._loading_lbl)

        self._count_lbl = QLabel('')
        self._count_lbl.setStyleSheet('color:#333344; font-size:11px; padding:2px 8px;')
        self._count_lbl.setAlignment(Qt.AlignRight)
        layout.addWidget(self._count_lbl)

    # ── Master folder ─────────────────────────────────────────────────────

    def _choose_master(self):
        folder = QFileDialog.getExistingDirectory(self, 'Carpeta de música')
        if not folder:
            return
        self._master = folder
        self._settings.set('master_folder', folder)
        folders = self._settings.get('music_folders', [])
        if folder not in folders:
            folders.insert(0, folder)
            self._settings.set('music_folders', folders)
        self._populate_tree()
        self._load(folder)

    def _restore_master(self):
        master = self._settings.get('master_folder', '')
        if not master:
            folders = self._settings.get('music_folders', [])
            master = folders[0] if folders else ''
        if master and os.path.isdir(master):
            self._master = master
            self._populate_tree()
            self._load(master)

    # ── Folder tree ───────────────────────────────────────────────────────

    def _populate_tree(self):
        self._tree.clear()
        if not self._master:
            return
        name = os.path.basename(self._master)
        self._master_lbl.setText(f'📁  {name}')

        root = QTreeWidgetItem(self._tree)
        root.setText(0, f'🎵  Todas — {name}')
        root.setData(0, Qt.UserRole, self._master)
        self._add_tree_children(root, self._master)
        root.setExpanded(True)
        self._tree.setCurrentItem(root)

    def _add_tree_children(self, parent: QTreeWidgetItem, folder: str):
        try:
            entries = sorted(os.listdir(folder))
        except Exception:
            return
        for e in entries:
            fp = os.path.join(folder, e)
            if os.path.isdir(fp) and not e.startswith('.') \
                    and e.lower() not in _SKIP:
                item = QTreeWidgetItem(parent)
                item.setText(0, f'📂  {e}')
                item.setData(0, Qt.UserRole, fp)
                self._add_tree_children(item, fp)

    def _on_tree_click(self, item: QTreeWidgetItem, col: int):
        self._search.clear()
        path = item.data(0, Qt.UserRole)
        if path:
            self._load(path)

    # ── Load ──────────────────────────────────────────────────────────────

    def _make_sigs(self) -> _Sigs:
        """Crea signals con generation check integrado para ignorar cargas obsoletas."""
        sigs = _Sigs()
        gen  = self._gen
        self._active_sigs.add(sigs)

        def on_track(track, g=gen):
            if g == self._gen:
                self._add_row(track)

        def on_done(g, s=sigs):
            self._active_sigs.discard(s)
            if g == self._gen:
                self._loading_lbl.hide()
                if self._search.text():
                    self._filter(self._search.text())
                self._update_count()

        sigs.track_ready.connect(on_track)
        sigs.done.connect(on_done)
        return sigs

    def _load(self, folder: str):
        """Inicia carga recursiva. Cancela (ignora) cualquier carga anterior."""
        self._current_folder = folder
        self._gen += 1
        self._table.setRowCount(0)
        self._count_lbl.setText('')
        self._loading_lbl.setText('Cargando…')
        self._loading_lbl.show()
        self._pool.start(_AllFilesLoader(folder, self._make_sigs(), self._gen))

    def _add_row(self, track: Track):
        row = self._table.rowCount()
        self._table.insertRow(row)
        folder_name = os.path.basename(os.path.dirname(track.path))
        for col, text in enumerate([track.title, track.artist,
                                     folder_name, track.duration_str]):
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, track)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, col, item)
        self._table.setRowHeight(row, 24)

    # ── Search + count ────────────────────────────────────────────────────

    def _filter(self, text: str):
        text = text.lower().strip()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            t: Track = item.data(Qt.UserRole)
            folder_name = os.path.basename(os.path.dirname(t.path)).lower()
            match = (not text
                     or text in t.title.lower()
                     or text in t.artist.lower()
                     or text in t.album.lower()
                     or text in folder_name)
            self._table.setRowHidden(row, not match)
        self._update_count()

    def _update_count(self):
        total   = self._table.rowCount()
        visible = sum(1 for r in range(total) if not self._table.isRowHidden(r))
        if visible == total:
            self._count_lbl.setText(f'{total} pista{"s" if total != 1 else ""}')
        else:
            self._count_lbl.setText(f'{visible} de {total} pistas')

    # ── Context menu + actions ────────────────────────────────────────────

    def _selected_tracks(self) -> list[Track]:
        seen, result = set(), []
        for item in self._table.selectedItems():
            t: Track = item.data(Qt.UserRole)
            if t and t.path not in seen:
                seen.add(t.path)
                result.append(t)
        return result

    def _on_double_click(self, index):
        item = self._table.item(index.row(), 0)
        if item:
            self.add_to_playlist.emit(item.data(Qt.UserRole))

    def _track_ctx(self, pos):
        tracks = self._selected_tracks()
        if not tracks:
            return
        menu = QMenu(self)
        act = QAction(f'Añadir {len(tracks)} a la lista', self)
        act.triggered.connect(lambda: [self.add_to_playlist.emit(t) for t in tracks])
        menu.addAction(act)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _add_all_visible(self):
        for row in range(self._table.rowCount()):
            if not self._table.isRowHidden(row):
                item = self._table.item(row, 0)
                if item:
                    self.add_to_playlist.emit(item.data(Qt.UserRole))

