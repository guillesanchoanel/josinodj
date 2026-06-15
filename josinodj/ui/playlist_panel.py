import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton,
    QLineEdit, QLabel, QMenu, QFileDialog, QAbstractItemView,
    QHeaderView, QDialog, QCheckBox, QStackedWidget,
)
from PySide6.QtCore import (
    Qt, Signal, QAbstractTableModel, QModelIndex, QMimeData,
)
from PySide6.QtGui import QColor, QFont, QAction

from ..models.track import Track, COLUMN_KEYS, COLUMN_LABELS, COLUMN_WIDTHS, is_audio_file


class PlaylistModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._tracks: list[Track] = []
        self._playing_index = -1
        self._played_set: set[int] = set()
        self._visible = ['title', 'artist', 'bpm', 'key', 'duration', 'genre']

    # ── Qt model interface ────────────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()):
        return len(self._tracks)

    def columnCount(self, parent=QModelIndex()):
        return len(self._visible) + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._tracks):
            return None
        row, col = index.row(), index.column()
        track = self._tracks[row]
        playing = row == self._playing_index
        played = row in self._played_set and not playing

        if role == Qt.DisplayRole:
            if col == 0:
                if playing:
                    return '▶'
                if played:
                    return '✓'
                return str(row + 1)
            return track.get_column(self._visible[col - 1])

        if role == Qt.ForegroundRole:
            if playing:
                return QColor('#a0ffb0')
            if played:
                return QColor('#3a4a5a')
            return QColor('#cccccc')

        if role == Qt.BackgroundRole:
            if playing:
                return QColor('#0d2218')
            if played:
                return QColor('#0d0d10')
            return QColor('#141414') if row % 2 == 0 else QColor('#161616')

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            key = self._visible[col - 1]
            if key in ('bpm', 'key', 'duration', 'year', 'bitrate'):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.UserRole:
            return track

        if role == Qt.FontRole:
            f = QFont()
            if playing:
                f.setBold(True)
            elif played:
                f.setItalic(True)
            return f

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return '#'
            return COLUMN_LABELS.get(self._visible[section - 1], '')
        return None

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.isValid():
            base |= Qt.ItemIsDragEnabled
        return base | Qt.ItemIsDropEnabled

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def mimeTypes(self):
        return ['application/x-josinodj-rows', 'text/uri-list']

    def mimeData(self, indexes):
        mime = QMimeData()
        rows = sorted({i.row() for i in indexes})
        mime.setData('application/x-josinodj-rows', ','.join(map(str, rows)).encode())
        return mime

    def dropMimeData(self, data, action, row, col, parent):
        # row=-1 means drop landed ON a row (not between rows) → use parent.row()
        if row < 0:
            insert_at = parent.row() if parent.isValid() else len(self._tracks)
        else:
            insert_at = row

        if data.hasFormat('application/x-josinodj-rows'):
            rows = [int(r) for r in data.data('application/x-josinodj-rows').data().decode().split(',')]
            rows.sort()
            tracks_to_move = [self._tracks[r] for r in rows]
            adj = sum(1 for r in rows if r < insert_at)
            for r in reversed(rows):
                self._tracks.pop(r)
            insert_at -= adj
            for i, t in enumerate(tracks_to_move):
                self._tracks.insert(insert_at + i, t)
            self.layoutChanged.emit()
            return True

        if data.hasUrls():
            existing = {t.path for t in self._tracks}
            new_tracks = []
            for url in data.urls():
                if url.isLocalFile():
                    p = url.toLocalFile()
                    if is_audio_file(p) and p not in existing:
                        new_tracks.append(self._make_track(p))
                        existing.add(p)
                    elif os.path.isdir(p):
                        for fn in sorted(os.listdir(p)):
                            fp = os.path.join(p, fn)
                            if is_audio_file(fp) and fp not in existing:
                                new_tracks.append(self._make_track(fp))
                                existing.add(fp)
            if new_tracks:
                self.beginInsertRows(QModelIndex(), insert_at, insert_at + len(new_tracks) - 1)
                for i, t in enumerate(new_tracks):
                    self._tracks.insert(insert_at + i, t)
                self.endInsertRows()
                return True

        return False

    def _make_track(self, path: str) -> Track:
        from ..utils.metadata import read_metadata
        try:
            return Track(path=path, **read_metadata(path))
        except Exception:
            return Track(path=path)

    # ── helpers ───────────────────────────────────────────────────────────

    def set_visible_columns(self, cols: list[str]):
        self.beginResetModel()
        self._visible = [c for c in COLUMN_KEYS if c in cols]
        self.endResetModel()

    def set_playing(self, index: int):
        old = self._playing_index
        self._playing_index = index
        for r in [old, index]:
            if 0 <= r < len(self._tracks):
                self.dataChanged.emit(self.index(r, 0), self.index(r, self.columnCount() - 1))

    def mark_played(self, played_set: set[int]):
        new_set = set(played_set)
        # Solo refrescar las filas que cambiaron — no repintar toda la tabla
        changed = new_set.symmetric_difference(self._played_set)
        self._played_set = new_set
        for row in changed:
            if 0 <= row < len(self._tracks):
                self.dataChanged.emit(
                    self.index(row, 0),
                    self.index(row, self.columnCount() - 1)
                )

    def add_track(self, track: Track, pos: int = -1):
        if pos < 0:
            pos = len(self._tracks)
        self.beginInsertRows(QModelIndex(), pos, pos)
        self._tracks.insert(pos, track)
        self.endInsertRows()

    def remove_rows(self, rows: list[int]):
        for r in sorted(rows, reverse=True):
            if 0 <= r < len(self._tracks):
                self.beginRemoveRows(QModelIndex(), r, r)
                self._tracks.pop(r)
                self.endRemoveRows()
        if self._playing_index >= len(self._tracks):
            self._playing_index = len(self._tracks) - 1

    def clear(self):
        self.beginResetModel()
        self._tracks.clear()
        self._playing_index = -1
        self._played_set.clear()
        self.endResetModel()

    @property
    def tracks(self) -> list[Track]:
        return self._tracks

    @property
    def playing_index(self) -> int:
        return self._playing_index

    def sort(self, column: int, order=Qt.AscendingOrder):
        if column <= 0 or column > len(self._visible):
            return
        key = self._visible[column - 1]
        reverse = (order == Qt.DescendingOrder)

        def sort_key(t: Track):
            if key == 'duration': return t.duration
            if key == 'bpm':      return t.bpm or 0.0
            if key == 'bitrate':  return t.bitrate or 0
            return (getattr(t, key, '') or '').lower()

        self.layoutAboutToBeChanged.emit()
        self._tracks.sort(key=sort_key, reverse=reverse)
        self.layoutChanged.emit()

    def to_json(self) -> str:
        return json.dumps([t.to_dict() for t in self._tracks], ensure_ascii=False, indent=2)

    def load_json(self, data: str):
        self.beginResetModel()
        self._tracks = []
        self._playing_index = -1
        self._played_set.clear()
        for d in json.loads(data):
            try:
                self._tracks.append(Track.from_dict(d))
            except Exception:
                pass
        self.endResetModel()


# ── Column selector ───────────────────────────────────────────────────────────

class ColumnSelectorDialog(QDialog):
    def __init__(self, visible: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle('Columnas visibles')
        self.setMinimumWidth(260)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Selecciona las columnas a mostrar:'))
        self._checks: dict[str, QCheckBox] = {}
        for key in COLUMN_KEYS:
            cb = QCheckBox(COLUMN_LABELS.get(key, key))
            cb.setChecked(key in visible)
            self._checks[key] = cb
            layout.addWidget(cb)
        btns = QHBoxLayout()
        ok = QPushButton('Aplicar')
        ok.clicked.connect(self.accept)
        cancel = QPushButton('Cancelar')
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    def get_visible(self) -> list[str]:
        return [k for k, cb in self._checks.items() if cb.isChecked()]


# ── Main playlist widget ──────────────────────────────────────────────────────

class PlaylistPanel(QWidget):
    play_requested    = Signal(int)
    playlist_changed  = Signal()
    unplay_requested  = Signal(list)  # filas a desmarcar como reproducidas

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName('playlistPanel')
        self._settings = settings
        self._current_path = ''
        self._row_font_size = settings.get('playlist_font_size', 13)
        self._sort_col   = -1
        self._sort_order = Qt.AscendingOrder
        self._model = PlaylistModel()
        self._model.set_visible_columns(settings.get('visible_columns', ['title', 'artist', 'bpm', 'key', 'duration']))
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName('playlistToolbar')
        toolbar.setFixedHeight(44)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(10, 0, 10, 0)
        tl.setSpacing(6)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('Sin título')
        self._name_edit.setMaximumWidth(180)

        btn_open = QPushButton('📂 Abrir')
        btn_open.setFixedHeight(28)
        btn_open.clicked.connect(self._open_playlist)
        btn_save = QPushButton('💾 Guardar')
        btn_save.setFixedHeight(28)
        btn_save.clicked.connect(self._save_playlist)
        btn_cols = QPushButton('👁 Columnas')
        btn_cols.setFixedHeight(28)
        btn_cols.clicked.connect(self._choose_columns)
        btn_clear = QPushButton('🗑')
        btn_clear.setFixedHeight(28)
        btn_clear.setToolTip('Vaciar lista')
        btn_clear.clicked.connect(self._clear_playlist)

        _btn_style = (
            'font-size:12px; font-weight:600; padding:0 10px;'
            'background:#1a1a2a; border:1px solid #2a2a40;'
            'border-radius:4px; color:#9999bb;'
        )

        btn_goto = QPushButton('📍 Ir a actual')
        btn_goto.setFixedHeight(28)
        btn_goto.setToolTip('Desplazar la lista hasta la canción que está sonando')
        btn_goto.setStyleSheet(_btn_style)
        btn_goto.clicked.connect(self._scroll_to_playing)

        btn_minus = QPushButton('A  −')
        btn_minus.setFixedHeight(28)
        btn_minus.setToolTip('Reducir tamaño del texto de la lista')
        btn_minus.setStyleSheet(_btn_style)
        btn_minus.clicked.connect(self._font_smaller)

        btn_plus = QPushButton('A  +')
        btn_plus.setFixedHeight(28)
        btn_plus.setToolTip('Aumentar tamaño del texto de la lista')
        btn_plus.setStyleSheet(_btn_style)
        btn_plus.clicked.connect(self._font_larger)

        tl.addWidget(QLabel('Lista:'))
        tl.addWidget(self._name_edit)
        tl.addWidget(btn_open)
        tl.addWidget(btn_save)
        tl.addStretch()
        tl.addWidget(btn_goto)
        tl.addWidget(btn_minus)
        tl.addWidget(btn_plus)
        tl.addWidget(btn_cols)
        tl.addWidget(btn_clear)

        layout.addWidget(toolbar)

        # Search bar
        search_bar = QWidget()
        search_bar.setFixedHeight(36)
        sl = QHBoxLayout(search_bar)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText('🔍 Filtrar lista…')
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_table)
        sl.addWidget(self._search)
        layout.addWidget(search_bar)

        # Table
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setDragDropMode(QAbstractItemView.DragDrop)
        self._table.setDefaultDropAction(Qt.MoveAction)
        self._table.setAcceptDrops(True)
        self._table.setDragEnabled(True)
        self._table.setDropIndicatorShown(True)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSortIndicatorShown(False)
        self._apply_column_widths()

        # Apply saved font size
        self._apply_font_size()

        # Splash vacío (se muestra cuando no hay canciones)
        self._splash = self._make_splash()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._splash)   # index 0
        self._stack.addWidget(self._table)    # index 1
        self._stack.setCurrentIndex(0)

        layout.addWidget(self._stack, 1)

        # Footer
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 2, 10, 2)
        self._count_lbl = QLabel('0 canciones')
        self._count_lbl.setStyleSheet('color: #444444; font-size: 11px;')
        self._played_lbl = QLabel('')
        self._played_lbl.setStyleSheet('color: #333355; font-size: 11px;')
        self._dur_lbl = QLabel('')
        self._dur_lbl.setStyleSheet('color: #444444; font-size: 11px;')
        fl.addWidget(self._count_lbl)
        fl.addSpacing(12)
        fl.addWidget(self._played_lbl)
        fl.addStretch()
        fl.addWidget(self._dur_lbl)
        layout.addWidget(footer)

        self._model.layoutChanged.connect(self._update_status)
        self._model.layoutChanged.connect(lambda: self._filter_table(self._search.text()))
        self._model.rowsInserted.connect(self._update_status)
        self._model.rowsInserted.connect(lambda *_: self._filter_table(self._search.text()))
        self._model.rowsRemoved.connect(self._update_status)
        # modelReset se emite al cargar una lista con load_json
        self._model.modelReset.connect(self._update_status)
        self._model.modelReset.connect(lambda: self._filter_table(self._search.text()))

    def _apply_column_widths(self):
        self._table.setColumnWidth(0, 36)
        for i, key in enumerate(self._model._visible):
            self._table.setColumnWidth(i + 1, COLUMN_WIDTHS.get(key, 100))

    # ── actions ───────────────────────────────────────────────────────────

    def set_shuffle(self, active: bool):
        self._shuffle_active = active

    def _scroll_to_playing(self):
        idx = self._model.playing_index
        if 0 <= idx < self._model.rowCount():
            self._table.scrollTo(
                self._model.index(idx, 0),
                QAbstractItemView.PositionAtCenter)

    def _play_next(self, rows: list[int]):
        """Mueve las canciones seleccionadas justo después de la que está sonando."""
        current = self._model.playing_index
        if current < 0:
            return
        # Guardar las canciones a mover (excluyendo la que suena)
        rows = sorted([r for r in rows if r != current])
        if not rows:
            return
        tracks_to_move = [self._model._tracks[r] for r in rows]
        # Guardar path de la canción actual para encontrarla después del pop
        current_path = self._model._tracks[current].path
        # Eliminar filas
        self._model.remove_rows(rows)
        # Encontrar nueva posición de la canción actual
        new_current = next(
            (i for i, t in enumerate(self._model._tracks) if t.path == current_path), 0)
        # Insertar justo después
        insert_at = new_current + 1
        for i, t in enumerate(tracks_to_move):
            self._model.add_track(t, insert_at + i)
        self.playlist_changed.emit()

    def _on_header_clicked(self, col: int):
        if col == 0:
            return
        if self._sort_col == col:
            self._sort_order = (Qt.DescendingOrder
                                if self._sort_order == Qt.AscendingOrder
                                else Qt.AscendingOrder)
        else:
            self._sort_col   = col
            self._sort_order = Qt.AscendingOrder
        self._table.horizontalHeader().setSortIndicator(self._sort_col, self._sort_order)
        self._model.sort(self._sort_col, self._sort_order)

    def _on_double_click(self, index: QModelIndex):
        self.play_requested.emit(index.row())

    def _context_menu(self, pos):
        rows = sorted({i.row() for i in self._table.selectedIndexes()})
        if not rows:
            return
        menu = QMenu(self)
        act_play = QAction('▶ Reproducir', self)
        act_play.triggered.connect(lambda: self.play_requested.emit(rows[0]))
        act_next = QAction('⏭ Reproducir a continuación', self)
        act_next.triggered.connect(lambda: self._play_next(rows))
        if getattr(self, '_shuffle_active', False):
            act_next.setEnabled(False)
            act_next.setText('⏭ Reproducir a continuación  (desactiva aleatorio primero)')
        act_rem = QAction('Eliminar de lista', self)
        act_rem.triggered.connect(lambda: self._remove_rows(rows))
        act_top = QAction('⬆ Mover al inicio', self)
        act_top.triggered.connect(lambda: self._move_top(rows))
        act_bot = QAction('⬇ Mover al final', self)
        act_bot.triggered.connect(lambda: self._move_bottom(rows))
        act_mark_unplayed = QAction('↩ Marcar como no reproducida', self)
        act_mark_unplayed.triggered.connect(lambda: self._unmark_played(rows))

        menu.addAction(act_play)
        menu.addAction(act_next)
        menu.addSeparator()
        menu.addAction(act_top)
        menu.addAction(act_bot)
        menu.addSeparator()
        menu.addAction(act_mark_unplayed)
        menu.addAction(act_rem)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _remove_rows(self, rows):
        self._model.remove_rows(rows)
        self.playlist_changed.emit()

    def _move_top(self, rows):
        tracks = [self._model.tracks[r] for r in sorted(rows)]
        self._model.remove_rows(sorted(rows))
        for i, t in enumerate(tracks):
            self._model.add_track(t, i)
        self.playlist_changed.emit()

    def _move_bottom(self, rows):
        tracks = [self._model.tracks[r] for r in sorted(rows)]
        self._model.remove_rows(sorted(rows))
        for t in tracks:
            self._model.add_track(t)
        self.playlist_changed.emit()

    def _unmark_played(self, rows):
        # Emitir señal para que main_window actualice _played_indices (lógica)
        self.unplay_requested.emit(list(rows))

    def _choose_columns(self):
        dlg = ColumnSelectorDialog(self._model._visible, self)
        if dlg.exec():
            cols = dlg.get_visible()
            self._model.set_visible_columns(cols)
            self._settings.set('visible_columns', cols)
            self._apply_column_widths()

    def _new_playlist(self):
        self._model.clear()
        self._name_edit.setText('')
        self._current_path = ''
        self.playlist_changed.emit()

    def _open_playlist(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir lista', '', 'JOSINODJ Playlist (*.jdj);;JSON (*.json)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._model.load_json(f.read())
            self._current_path = path
            self._name_edit.setText(os.path.splitext(os.path.basename(path))[0])
            self.playlist_changed.emit()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error', f'No se pudo abrir: {e}')

    def _save_playlist(self):
        path = self._current_path
        if not path:
            dlg = QFileDialog(self, 'Guardar lista de reproducción')
            dlg.setAcceptMode(QFileDialog.AcceptSave)
            dlg.setDefaultSuffix('jdj')
            dlg.setNameFilter('JOSINODJ Playlist (*.jdj)')
            if not dlg.exec():
                return
            path = dlg.selectedFiles()[0]
        if not path:
            return
        if not path.endswith('.jdj'):
            path += '.jdj'
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._model.to_json())
            self._current_path = path
            name = os.path.splitext(os.path.basename(path))[0]
            self._name_edit.setText(name)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, 'Lista guardada',
                f'Lista guardada correctamente:\n{path}')
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Error al guardar', f'No se pudo guardar:\n{e}')

    def _clear_playlist(self):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, 'Vaciar', '¿Vaciar la lista?') == QMessageBox.Yes:
            self._model.clear()
            self.playlist_changed.emit()

    def _make_splash(self) -> QWidget:
        import os
        from PySide6.QtGui import QPixmap
        w = QWidget()
        w.setStyleSheet('background-color:#0d0d14;')
        vl = QVBoxLayout(w)
        vl.setAlignment(Qt.AlignCenter)
        vl.setSpacing(14)

        icon_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icon.png'))
        if os.path.exists(icon_path):
            px = QPixmap(icon_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_lbl = QLabel()
            img_lbl.setPixmap(px)
            img_lbl.setAlignment(Qt.AlignCenter)
            vl.addWidget(img_lbl)

        title = QLabel('JOSINO<span style="color:#00d4ff">DJ</span>')
        title.setTextFormat(Qt.RichText)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            'font-size:28px; font-weight:900; color:#ffffff;'
            'letter-spacing:3px; font-family:"Segoe UI Black","Arial Black",sans-serif;'
        )
        vl.addWidget(title)

        hint = QLabel('Abre una carpeta o arrastra canciones aquí')
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet('color:#333355; font-size:13px;')
        vl.addWidget(hint)

        w.setAcceptDrops(True)
        w.dragEnterEvent = lambda e: e.acceptProposedAction() if e.mimeData().hasUrls() else None
        w.dropEvent = self._on_splash_drop
        return w

    def _on_splash_drop(self, event):
        from ..models.track import Track, is_audio_file
        from ..utils.metadata import read_metadata
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = url.toLocalFile()
                if is_audio_file(p):
                    try:
                        track = Track(path=p, **read_metadata(p))
                    except Exception:
                        track = Track(path=p)
                    self._model.add_track(track)
        self.playlist_changed.emit()

    def _font_larger(self):
        if self._row_font_size < 26:
            self._row_font_size += 2
            self._apply_font_size()
            self._settings.set('playlist_font_size', self._row_font_size)

    def _font_smaller(self):
        if self._row_font_size > 9:
            self._row_font_size -= 2
            self._apply_font_size()
            self._settings.set('playlist_font_size', self._row_font_size)

    def _apply_font_size(self):
        size = self._row_font_size
        self._table.setStyleSheet(f'QTableView {{ font-size: {size}px; }}')
        row_h = size + 10
        self._table.verticalHeader().setDefaultSectionSize(row_h)
        for row in range(self._model.rowCount()):
            self._table.setRowHeight(row, row_h)

    def _filter_table(self, text: str):
        text = text.lower().strip()
        for row in range(self._model.rowCount()):
            track = self._model.tracks[row]
            match = (not text
                     or text in track.title.lower()
                     or text in track.artist.lower()
                     or text in track.album.lower()
                     or text in track.genre.lower())
            self._table.setRowHidden(row, not match)

    def _update_status(self):
        n = len(self._model.tracks)
        self._stack.setCurrentIndex(0 if n == 0 else 1)
        self._count_lbl.setText(f'{n} canción{"es" if n != 1 else ""}')
        played = len(self._model._played_set)
        if played:
            self._played_lbl.setText(f'✓ {played} reproducida{"s" if played != 1 else ""}')
        else:
            self._played_lbl.setText('')
        total = sum(t.duration for t in self._model.tracks)
        m, s = divmod(int(total), 60)
        h, m = divmod(m, 60)
        if h:
            self._dur_lbl.setText(f'{h}h {m}m {s}s')
        elif m:
            self._dur_lbl.setText(f'{m}m {s}s')
        else:
            self._dur_lbl.setText(f'{s}s' if s else '')

    # ── public API ────────────────────────────────────────────────────────

    def add_track(self, track: Track, pos: int = -1):
        # Evitar duplicados — no añadir si ya está en la lista
        if any(t.path == track.path for t in self._model.tracks):
            return
        self._model.add_track(track, pos)
        self.playlist_changed.emit()

    def set_playing_index(self, index: int):
        self._model.set_playing(index)
        if 0 <= index < self._model.rowCount():
            self._table.scrollTo(
                self._model.index(index, 0),
                QAbstractItemView.EnsureVisible)

    def mark_played(self, played_set: set[int]):
        self._model.mark_played(played_set)
        self._update_status()

    def find_track_index(self, path: str) -> int:
        for i, t in enumerate(self._model.tracks):
            if t.path == path:
                return i
        return -1

    def update_track_analysis(self, path: str, bpm: float, key: str):
        """Actualiza BPM y tono de un track por path y refresca su fila."""
        for i, t in enumerate(self._model.tracks):
            if t.path == path:
                if bpm > 0:
                    t.bpm = bpm
                if key:
                    t.key = key
                self._model.dataChanged.emit(
                    self._model.index(i, 0),
                    self._model.index(i, self._model.columnCount() - 1),
                )
                break

    @property
    def tracks(self) -> list[Track]:
        return self._model.tracks

    @property
    def playing_index(self) -> int:
        return self._model.playing_index

    @property
    def model(self):
        return self._model
