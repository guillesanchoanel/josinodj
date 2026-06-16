import random

import os

import threading

import queue as _queue

from PySide6.QtWidgets import (

    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,

    QSplitter, QLabel, QPushButton, QMessageBox, QSlider,

)

from PySide6.QtCore import Qt, QTimer, Signal, QObject

from PySide6.QtGui import QKeySequence, QShortcut, QPixmap, QPainter, QColor





class _AnalysisSignals(QObject):

    """Señales para pasar resultados de análisis del hilo de fondo al hilo principal."""

    done = Signal(str, float, str)   # path, bpm, key





class LockOverlay(QWidget):

    """Pantalla de bloqueo: imagen centrada + click para pedir PIN."""



    unlock_clicked = Signal()



    def __init__(self, icon_path: str, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet('background: transparent;')



        layout = QVBoxLayout(self)

        layout.setAlignment(Qt.AlignCenter)

        layout.setSpacing(12)



        # Imagen grande centrada (ya lleva "BLOQUEADO" en el gráfico)

        self._img_lbl = QLabel()

        self._img_lbl.setAlignment(Qt.AlignCenter)

        if os.path.exists(icon_path):

            px = QPixmap(icon_path).scaled(

                460, 460, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self._img_lbl.setPixmap(px)

        layout.addWidget(self._img_lbl)



        hint_txt = QLabel('Toca aquí para introducir el PIN')

        hint_txt.setAlignment(Qt.AlignCenter)

        hint_txt.setStyleSheet('color:#444455; font-size:13px;')

        layout.addWidget(hint_txt)



    def paintEvent(self, _):

        p = QPainter(self)

        p.fillRect(self.rect(), QColor(8, 8, 18, 230))

        p.end()



    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:

            self.unlock_clicked.emit()



    def resizeEvent(self, event):

        if self.parent():

            self.setGeometry(self.parent().rect())

        super().resizeEvent(event)



from ..audio.engine import AudioEngine

from ..models.track import Track

from .library_panel import LibraryPanel

from .playlist_panel import PlaylistPanel

from .player_bar import PlayerBar

from .settings_dialog import SettingsDialog

from .pin_dialog import PinDialog

from .download_dialog import DownloadDialog

from .mobile_dialog import MobileDialog

from .eq_widget import EQWidget

from .styles import DARK_STYLE

from ..utils.session_manager import SessionManager



PRELOAD_BUFFER = 8.0

_ICON_PATH = os.path.normpath(

    os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icon.png'))

_LOCK_IMG_PATH = os.path.normpath(

    os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'lock.png'))





class MainWindow(QMainWindow):

    def __init__(self, settings):

        super().__init__()

        self._settings = settings

        self._engine   = AudioEngine()

        self._session  = SessionManager()



        self._current_index  = -1

        self._current_path   = ''

        self._auto_mix       = True

        self._shuffle        = False

        self._preload_done   = False

        self._played_indices: set[int] = set()

        self._played_paths:   set[str] = set()   # fuente de verdad por path

        self._locked         = False





        self.setWindowTitle('JOSINODJ')

        self.setMinimumSize(1100, 680)

        self.resize(settings.get('window_width', 1280), settings.get('window_height', 760))

        self.setStyleSheet(DARK_STYLE)



        if os.path.exists(_ICON_PATH):

            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(_ICON_PATH))



        self._setup_ui()

        self._connect_signals()

        self._apply_settings()

        self._setup_shortcuts()



        # Auto-save session every 30 s

        self._save_timer = QTimer()

        self._save_timer.timeout.connect(self._autosave_session)

        self._save_timer.start(30_000)



        # Sync server state + process mobile actions every 100 ms

        self._server_timer = QTimer()

        self._server_timer.timeout.connect(self._sync_server)

        self._server_timer.start(100)



        # Offer session restore after window is shown

        QTimer.singleShot(400, self._offer_session_restore)



    # â”€â”€ UI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _setup_ui(self):

        central = QWidget()

        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        root.setContentsMargins(0, 0, 0, 0)

        root.setSpacing(0)



        self._header = self._make_header()

        root.addWidget(self._header)



        # Dropdown EQ: aparece bajo el botón, se cierra al clicar fuera

        self._eq_dropdown = QWidget(None, Qt.Popup)

        self._eq_dropdown.setStyleSheet(

            'QWidget{background:#080810; border:1px solid #3a2070; border-radius:6px;}')

        _eq_l = QVBoxLayout(self._eq_dropdown)

        _eq_l.setContentsMargins(0, 0, 0, 0)

        _eq_l.addWidget(EQWidget(self._engine))

        self._eq_dropdown.adjustSize()

        self._eq_close_time = 0.0

        self._eq_dropdown.installEventFilter(self)



        self._splitter = QSplitter(Qt.Horizontal)

        self._splitter.setChildrenCollapsible(False)

        self._splitter.setHandleWidth(2)

        self._library  = LibraryPanel(self._settings)

        self._playlist = PlaylistPanel(self._settings)

        self._splitter.addWidget(self._library)

        self._splitter.addWidget(self._playlist)

        self._splitter.setSizes(self._settings.get('splitter_sizes', [300, 980]))

        root.addWidget(self._splitter, 1)



        self._player = PlayerBar(self._engine)

        root.addWidget(self._player)



        self.statusBar()





        # Lock overlay — hijo del widget central, cubre todo

        self._lock_overlay = LockOverlay(_LOCK_IMG_PATH, central)

        self._lock_overlay.unlock_clicked.connect(self._try_unlock)

        self._lock_overlay.hide()



    def _make_header(self) -> QWidget:

        bar = QWidget()

        bar.setFixedHeight(52)

        bar.setStyleSheet(

            'background: qlineargradient(x1:0,y1:0,x2:1,y2:0,'

            'stop:0 #0a0a12, stop:0.5 #0d0d1a, stop:1 #0a0a12);'

            'border-bottom: 1px solid #1e1040;'

        )

        hl = QHBoxLayout(bar)

        hl.setContentsMargins(10, 4, 14, 4)

        hl.setSpacing(8)



        if os.path.exists(_ICON_PATH):

            px = QPixmap(_ICON_PATH).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            icon_lbl = QLabel()

            icon_lbl.setPixmap(px)

            icon_lbl.setFixedSize(40, 40)

            hl.addWidget(icon_lbl)



        logo = QLabel('JOSINO<span style="color:#00d4ff">DJ</span>')

        logo.setTextFormat(Qt.RichText)

        logo.setStyleSheet(

            'font-size:22px; font-weight:900; color:#ffffff;'

            'letter-spacing:2px; font-family:"Segoe UI Black","Arial Black",sans-serif;')

        sub = QLabel('DJ Software')

        sub.setStyleSheet('color:#2a2a4a; font-size:11px; margin-left:4px; margin-top:6px;')



        # Lock indicator (visible only when locked)

        self._lock_banner = QLabel('🔒  BLOQUEADO — Introduce PIN para desbloquear')

        self._lock_banner.setStyleSheet(

            'color:#ff4444; font-size:12px; font-weight:bold; letter-spacing:1px;')

        self._lock_banner.hide()



        # Lock button

        self._lock_btn = QPushButton('🔓')

        self._lock_btn.setFixedSize(36, 30)

        self._lock_btn.setToolTip('Bloquear pantalla (modo fiesta/borrachos)')

        self._lock_btn.setStyleSheet(

            'font-size:16px; background:#111120; border:1px solid #2a2a3a; border-radius:5px;')

        self._lock_btn.clicked.connect(self._toggle_lock)



        self._fs_header_btn = QPushButton('⛶ Pantalla')

        self._fs_header_btn.setFixedHeight(30)

        self._fs_header_btn.setToolTip('Pantalla completa  (F11)')

        self._fs_header_btn.setStyleSheet(

            'font-size:16px; background:#111120; border:1px solid #2a2a3a; border-radius:5px;')

        self._fs_header_btn.clicked.connect(self._toggle_fullscreen)



        self._eq_header_btn = QPushButton('🎚 EQ')

        self._eq_header_btn.setFixedHeight(30)

        self._eq_header_btn.setCheckable(False)

        self._eq_header_btn.setToolTip('Ecualizador de 5 bandas')

        self._eq_header_btn.setStyleSheet(

            'QPushButton{background:#1a1030;border:1px solid #3a2060;'

            'border-radius:5px;color:#9966ff;padding:0 10px;}')

        self._eq_header_btn.clicked.connect(self._toggle_eq_popup)



        btn_mobile = QPushButton('📱 Móvil')

        btn_mobile.setFixedHeight(30)

        btn_mobile.setToolTip('Control remoto desde el móvil via WiFi')

        btn_mobile.setStyleSheet(

            'background:#0d1a2a; border:1px solid #1a3a6a;'

            'border-radius:5px; color:#4488ff; padding:0 10px;')

        btn_mobile.clicked.connect(self._open_mobile)



        btn_download = QPushButton('⬇ YouTube')

        btn_download.setFixedHeight(30)

        btn_download.setToolTip('Descargar audio de YouTube como MP3')

        btn_download.setStyleSheet(

            'background:#0d1f0d; border:1px solid #1a4a1a;'

            'border-radius:5px; color:#44ee88; padding:0 10px;')

        btn_download.clicked.connect(self._open_download)



        btn_settings = QPushButton('⚙ Ajustes')

        btn_settings.setFixedHeight(30)

        btn_settings.clicked.connect(self._open_settings)

        btn_help = QPushButton('? Ayuda')

        btn_help.setFixedHeight(30)

        btn_help.clicked.connect(self._open_help)



        hl.addWidget(logo)

        hl.addWidget(sub)

        hl.addSpacing(16)

        hl.addWidget(self._lock_banner, 1)

        hl.addStretch()

        hl.addWidget(self._lock_btn)

        hl.addWidget(self._fs_header_btn)

        hl.addWidget(self._eq_header_btn)

        hl.addWidget(btn_mobile)

        hl.addWidget(btn_download)

        hl.addWidget(btn_settings)

        hl.addWidget(btn_help)

        return bar



    # â”€â”€ signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _connect_signals(self):

        self._library.add_to_playlist.connect(self._on_add_to_playlist)



        self._playlist.play_requested.connect(self._play_track)

        self._playlist.playlist_changed.connect(self._resync_playing_index)

        self._playlist.playlist_changed.connect(self._update_next_track_display)

        self._playlist.playlist_changed.connect(self._resync_played_indices)

        self._playlist.model.layoutChanged.connect(self._resync_playing_index)

        self._playlist.model.layoutChanged.connect(self._resync_played_indices)

        self._playlist.model.layoutChanged.connect(self._update_next_track_display)

        self._playlist.unplay_requested.connect(self._on_unplay_requested)



        self._player.prev_requested.connect(self._prev_track)

        self._player.next_requested.connect(self._next_track)

        self._player.shuffle_toggled.connect(self._set_shuffle)

        self._player.fullscreen_toggle.connect(self._toggle_fullscreen)

        self._player.crossfade_changed.connect(

            lambda v: self._settings.set('crossfade_duration', v))



        self._engine.track_switched.connect(self._on_track_switched)

        self._engine.track_ended.connect(self._on_track_ended)

        self._engine.position_changed.connect(self._on_position)

        self._engine.decode_error.connect(self._on_decode_error)



    # â”€â”€ playback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _play_track(self, index: int):

        tracks = self._playlist.tracks

        if not tracks or not (0 <= index < len(tracks)):

            return

        track = tracks[index]

        if not self._engine.play_file(track.path):

            # Eliminar de la lista y saltar a la siguiente

            self._playlist._model.remove_rows([index])

            self.statusBar().showMessage(

                f'âŒ Eliminada (no reproducible): {track.title}', 4000)

            remaining = self._playlist.tracks

            if remaining:

                next_idx = min(index, len(remaining) - 1)

                self._play_track(next_idx)

            return

        if 0 <= self._current_index < len(tracks) and self._current_index != index:

            self._mark_played(self._current_index)

        self._current_index = index

        self._current_path  = track.path

        self._playlist.set_playing_index(index)

        self._playlist.mark_played(self._played_indices)

        self._player.set_track(track)

        self._preload_done = False

        self.statusBar().showMessage(f'▶  {track.title}  —  {track.artist}', 3000)

        self._update_next_track_display()



    def _prev_track(self):

        if not self._locked and self._current_index > 0:

            self._play_track(self._current_index - 1)



    def _next_track(self):

        if self._locked:

            return

        tracks = self._playlist.tracks

        if not tracks:

            return

        idx = self._pick_next_index()

        if idx < 0:

            self.statusBar().showMessage('✅  Todas las canciones reproducidas — marca alguna como no reproducida para continuar', 5000)

            return

        self._play_track(idx)



    def _pick_next_index(self) -> int:

        tracks = self._playlist.tracks

        if not tracks:

            return -1

        n = len(tracks)

        if self._shuffle:

            unplayed = [i for i in range(n)

                        if i not in self._played_indices and i != self._current_index]

            if unplayed:

                return random.choice(unplayed)

            # Todas sonadas — resetear y seguir

            self._played_indices.clear()

            others = [i for i in range(n) if i != self._current_index]

            return random.choice(others) if others else 0

        else:

            # Secuencial: buscar la siguiente no reproducida

            for i in range(1, n + 1):

                candidate = (self._current_index + i) % n

                if candidate not in self._played_indices:

                    return candidate

            # Todas reproducidas â†’ parar

            return -1



    def _on_track_switched(self):

        tracks = self._playlist.tracks

        if not tracks:

            return

        if self._current_index >= 0:

            self._mark_played(self._current_index)

        nxt = self._pick_next_index()

        if nxt < 0:

            self.statusBar().showMessage('✅  Todas las canciones reproducidas', 5000)

            return

        self._current_index = nxt

        track = tracks[nxt]

        self._current_path  = track.path

        # UI crítica inmediata (solo 2 filas, rápido)

        self._playlist.set_playing_index(nxt)

        self._player.set_track(track)

        self._preload_done = False

        self.statusBar().showMessage(f'▶  {track.title}  —  {track.artist}', 3000)

        self._update_next_track_display()

        # Diferir mark_played 150ms para no coincidir con el momento del crossfade

        played = set(self._played_indices)

        QTimer.singleShot(150, lambda: self._playlist.mark_played(played))



    def _on_track_ended(self):

        if self._current_index >= 0:

            self._mark_played(self._current_index)

        self._playlist.mark_played(self._played_indices)

        if self._auto_mix:

            idx = self._pick_next_index()

            if idx < 0:

                self.statusBar().showMessage('✅  Todas las canciones reproducidas', 5000)

            else:

                self._play_track(idx)



    def _on_position(self, pos: float):

        if not self._auto_mix:

            return

        dur = self._engine.duration

        if dur <= 0:

            return

        if not self._preload_done and (dur - pos) <= self._engine.crossfade_duration + PRELOAD_BUFFER:

            self._preload_next()



    def _preload_next(self):

        tracks = self._playlist.tracks

        if not tracks:

            return

        nxt = self._pick_next_index()

        if nxt < 0 or nxt == self._current_index:

            return

        self._engine.preload_next_async(tracks[nxt].path)

        self._preload_done = True



    def _set_auto_mix(self, on: bool):

        self._auto_mix = on

        self._settings.set('auto_play', on)



    def _set_shuffle(self, on: bool):

        self._shuffle = on

        self._settings.set('shuffle', on)

        self._playlist.set_shuffle(on)

        self._update_next_track_display()



    # â”€â”€ library â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _on_add_to_playlist(self, track: Track):

        if self._locked:

            return

        self._playlist.add_track(track)

        self.statusBar().showMessage(f'Añadido: {track.title}', 1500)

        if self._current_index < 0:

            self._play_track(0)



    def _update_next_track_display(self):

        """Muestra la siguiente canción en el player bar."""

        if self._shuffle:

            self._player.set_next_track(None)

            return

        nxt = self._pick_next_index()

        tracks = self._playlist.tracks

        if nxt >= 0 and 0 <= nxt < len(tracks):

            self._player.set_next_track(tracks[nxt])

        else:

            self._player.set_next_track(None)



    def _on_unplay_requested(self, rows: list):

        """Desmarcar filas como reproducidas — actualiza lógica Y visual."""

        for r in rows:

            self._played_indices.discard(r)

        # Actualizar visual (modelo de playlist)

        self._playlist.mark_played(self._played_indices)



    def _mark_played(self, index: int):

        """Marca un track como reproducido guardando su path (sobrevive reordenaciones)."""

        tracks = self._playlist.tracks

        if 0 <= index < len(tracks):

            self._played_paths.add(tracks[index].path)

        self._played_indices.add(index)



    def _resync_played_indices(self):

        """Recalcula _played_indices desde _played_paths tras cualquier reordenación."""

        tracks = self._playlist.tracks

        current_paths = {t.path for t in tracks}

        self._played_paths &= current_paths

        self._played_indices = {

            i for i, t in enumerate(tracks)

            if t.path in self._played_paths

        }

        self._playlist.mark_played(self._played_indices)



    def _resync_playing_index(self):

        if not self._current_path:

            return

        idx = self._playlist.find_track_index(self._current_path)

        if idx >= 0 and idx != self._current_index:

            self._current_index = idx

            self._playlist.set_playing_index(idx)



    # â”€â”€ lock mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _toggle_lock(self):

        if self._locked:

            self._try_unlock()

        else:

            self._do_lock()



    def _do_lock(self):

        self._locked = True

        self._lock_btn.setText('🔒')

        self._lock_btn.setStyleSheet(

            'font-size:16px; background:#1a0808; border:1px solid #aa2222;'

            'border-radius:5px; color:#ff4444;')

        self._lock_banner.show()

        self._header.setStyleSheet(

            'background: qlineargradient(x1:0,y1:0,x2:1,y2:0,'

            'stop:0 #120808, stop:0.5 #160a0a, stop:1 #120808);'

            'border-bottom: 2px solid #aa2222;')

        self._library.setEnabled(False)

        self._playlist.setEnabled(False)

        self._player.lock(True)

        self._fs_header_btn.setEnabled(False)

        # Mostrar overlay encima de todo

        self._lock_overlay.setGeometry(self.centralWidget().rect())

        self._lock_overlay.raise_()

        self._lock_overlay.show()

        self.statusBar().showMessage('🔒  Pantalla bloqueada', 0)



    def _try_unlock(self):

        dlg = PinDialog(self)

        if dlg.exec():

            self._do_unlock()



    def _do_unlock(self):

        self._locked = False

        self._lock_overlay.hide()

        self._lock_btn.setText('🔓')

        self._lock_btn.setStyleSheet(

            'font-size:16px; background:#111120; border:1px solid #2a2a3a; border-radius:5px;')

        self._lock_banner.hide()

        self._header.setStyleSheet(

            'background: qlineargradient(x1:0,y1:0,x2:1,y2:0,'

            'stop:0 #0a0a12, stop:0.5 #0d0d1a, stop:1 #0a0a12);'

            'border-bottom: 1px solid #1e1040;')

        self._library.setEnabled(True)

        self._playlist.setEnabled(True)

        self._player.lock(False)

        self._fs_header_btn.setEnabled(True)

        self.statusBar().showMessage('🔓  Desbloqueado', 2000)



    # â”€â”€ session recovery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _autosave_session(self):

        tracks = self._playlist.tracks

        if not tracks:

            return

        self._session.save(

            tracks,

            self._current_index,

            self._engine.position,

            self._playlist._name_edit.text(),

        )



    def _offer_session_restore(self):

        data = self._session.load()

        if not data or not data.get('tracks'):

            return

        saved_at = data.get('saved_at', '')

        n        = len(data['tracks'])

        idx      = data.get('playing_index', 0)

        track_name = ''

        if 0 <= idx < n:

            track_name = data['tracks'][idx].get('title', '')



        msg = (f'Se encontró una sesión anterior guardada el {saved_at}.\n\n'

               f'Lista: {n} canciones\n'

               f'Última canción: {track_name}\n\n'

               f'¿Restaurar?')



        reply = QMessageBox.question(

            self, 'Restaurar sesión', msg,

            QMessageBox.Yes | QMessageBox.No,

            QMessageBox.Yes,

        )

        if reply != QMessageBox.Yes:

            self._session.clear()

            return



        # Restore playlist

        from ..models.track import Track

        for t_dict in data['tracks']:

            try:

                self._playlist.add_track(Track.from_dict(t_dict))

            except Exception:

                pass



        # Restore name

        pname = data.get('playlist_name', '')

        if pname:

            self._playlist._name_edit.setText(pname)



        # Restore playback position

        play_idx = data.get('playing_index', 0)

        position = data.get('position', 0.0)

        if 0 <= play_idx < len(self._playlist.tracks):

            self._play_track(play_idx)

            if position > 2.0:

                QTimer.singleShot(800, lambda: self._engine.seek(position))



        self.statusBar().showMessage('Sesión restaurada', 3000)



    # â”€â”€ misc â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



    def _on_decode_error(self, msg: str):

        pass  # El error se gestiona en _play_track (elimina la canción y avanza)



    def _toggle_fullscreen(self):

        if self._locked:

            return

        if self.isFullScreen():

            self.showNormal()

            self._fs_header_btn.setText('⛶ Pantalla')

        else:

            self.showFullScreen()

            self._fs_header_btn.setText('⛶ Ventana')



    def _toggle_eq_popup(self):

        import time

        # Qt.Popup cierra el widget ANTES de que llegue el click al botón.

        # Si se cerró hace menos de 200ms es que el usuario pulsó el botón

        # para cerrar â†’ no reabrir.

        if time.time() - self._eq_close_time < 0.2:

            return

        if self._eq_dropdown.isVisible():

            self._eq_dropdown.hide()

            return

        btn = self._eq_header_btn

        pos = btn.mapToGlobal(btn.rect().bottomLeft())

        self._eq_dropdown.adjustSize()

        x = pos.x()

        if x + self._eq_dropdown.width() > self.x() + self.width():

            x = self.x() + self.width() - self._eq_dropdown.width() - 4

        self._eq_dropdown.move(x, pos.y() + 4)

        self._eq_dropdown.show()



    def eventFilter(self, obj, event):

        import time

        from PySide6.QtCore import QEvent

        if obj is self._eq_dropdown and event.type() == QEvent.Hide:

            self._eq_close_time = time.time()

        return super().eventFilter(obj, event)





    def _open_mobile(self):

        if self._locked:

            return

        MobileDialog(self).exec()



    def _sync_server(self):

        """Actualiza estado del servidor y procesa acciones del móvil."""

        from ..server import web_server as srv

        tracks = self._playlist.tracks

        track  = tracks[self._current_index] if 0 <= self._current_index < len(tracks) else None

        parts  = []

        if track and track.bpm:  parts.append(f'{track.bpm:.0f} BPM')

        if track and track.key:  parts.append(track.key)

        playlist_data = [

            {'i': i, 'title': t.title, 'artist': t.artist or ''}

            for i, t in enumerate(tracks)

        ]

        nxt_idx   = self._pick_next_index() if not self._shuffle else -1
        nxt_track = tracks[nxt_idx] if 0 <= nxt_idx < len(tracks) else None

        srv.update_state(

            title         = track.title  if track else '',

            artist        = track.artist if track else '',

            bpm           = '  ·  '.join(parts),

            position      = self._engine.position,

            duration      = self._engine.duration,

            playing       = self._engine.is_playing,

            volume        = self._engine.master_volume,

            playlist      = playlist_data,

            current_index = self._current_index,

            played        = list(self._played_indices),

            next_title    = nxt_track.title  if nxt_track else '',

            next_artist   = nxt_track.artist if nxt_track else '',

        )

        # Procesar todas las acciones pendientes del móvil
        while True:

            action = srv.pop_action()

            if action is None:

                break

            if action == 'toggle':

                self._engine.toggle_pause()

            elif action == 'next':

                self._next_track()

            elif action == 'prev':

                self._prev_track()

            elif isinstance(action, tuple) and action[0] == 'volume':

                self._player.set_volume(action[1])

            elif isinstance(action, tuple) and action[0] == 'play_index':

                self._play_track(action[1])

            elif isinstance(action, tuple) and action[0] == 'reorder':

                _, from_idx, to_idx = action

                n = len(tracks)

                if 0 <= from_idx < n and 0 <= to_idx < n and from_idx != to_idx:

                    self._playlist._model.layoutAboutToBeChanged.emit()

                    t = self._playlist._model._tracks

                    t.insert(to_idx, t.pop(from_idx))

                    self._playlist._model.layoutChanged.emit()

                    self._resync_playing_index()

            elif isinstance(action, tuple) and action[0] == 'remove':

                idx = action[1]

                if 0 <= idx < len(tracks):

                    self._playlist._remove_rows([idx])

            elif isinstance(action, tuple) and action[0] == 'unplay':

                idx = action[1]

                if 0 <= idx < len(tracks):

                    self._on_unplay_requested([idx])

                    path = tracks[idx].path

                    self._played_paths.discard(path)

            elif isinstance(action, tuple) and action[0] == 'play_next':

                idx = action[1]

                if 0 <= idx < len(tracks) and idx != self._current_index:

                    self._playlist._play_next([idx])

            elif isinstance(action, tuple) and action[0] == 'move_top':

                idx = action[1]

                if 0 <= idx < len(tracks):

                    self._playlist._move_top([idx])

            elif isinstance(action, tuple) and action[0] == 'move_bottom':

                idx = action[1]

                if 0 <= idx < len(tracks):

                    self._playlist._move_bottom([idx])



    def _open_download(self):

        if self._locked:

            return

        dlg = DownloadDialog(self)

        dlg.file_ready.connect(self._on_downloaded_file)

        dlg.exec()



    def _on_downloaded_file(self, filepath: str):

        import os

        from ..models.track import Track

        from ..utils.metadata import read_metadata

        if not os.path.exists(filepath):

            self.statusBar().showMessage(f'Archivo no encontrado: {filepath}', 4000)

            return

        try:

            track = Track(path=filepath, **read_metadata(filepath))

        except Exception:

            track = Track(path=filepath)

        self._on_add_to_playlist(track)



    def _open_settings(self):

        if self._locked:

            return

        SettingsDialog(self._settings, self._engine, self).exec()



    def _open_help(self):

        from josinodj.ui.help_dialog import HelpDialog

        HelpDialog(self).exec()



    def _apply_settings(self):

        self._auto_mix = self._settings.get('auto_play', True)

        self._shuffle  = self._settings.get('shuffle', False)

        self._playlist.set_shuffle(self._shuffle)

        self._engine.master_volume      = self._settings.get('master_volume', 0.8)

        self._engine.normalize          = self._settings.get('normalize', True)

        cf = self._settings.get('crossfade_duration', 4.0)

        self._engine.crossfade_duration = cf

        self._player.init_crossfade(cf)

        if (dev := self._settings.get('master_device')) is not None:

            self._engine.set_master_device(dev)



    def _setup_shortcuts(self):

        QShortcut(QKeySequence('Space'), self).activated.connect(self._engine.toggle_pause)

        QShortcut(QKeySequence('Right'), self).activated.connect(self._next_track)

        QShortcut(QKeySequence('Left'),  self).activated.connect(self._prev_track)

        QShortcut(QKeySequence('F11'),   self).activated.connect(self._toggle_fullscreen)



    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self._locked:

            self._lock_overlay.setGeometry(self.centralWidget().rect())



    def closeEvent(self, event):

        if self._locked:

            dlg = PinDialog(self, 'Introduce el PIN para cerrar JOSINODJ')

            if dlg.exec():

                self._do_unlock()

            else:

                event.ignore()

                return

        self._engine.stop()

        self._autosave_session()

        self._settings.set('window_width',   self.width())

        self._settings.set('window_height',  self.height())

        self._settings.set('splitter_sizes', self._splitter.sizes())

        event.accept()

