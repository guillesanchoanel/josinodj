from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider,
    QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ..audio.engine import AudioEngine
from .waveform_widget import WaveformWidget
from .spectrum_widget import NextWaveformWidget
from .transport_buttons import TransportButton

_TOGGLE_OFF = ('background:#161624;border:1px solid #2a2a40;border-radius:6px;'
               'color:#888899;min-width:30px;min-height:30px;font-size:16px;')
_TOGGLE_ON  = ('background:#1a3a2a;border:1px solid #3a8a3a;border-radius:6px;'
               'color:#44ee88;min-width:30px;min-height:30px;font-size:16px;')


class PlayerBar(QWidget):
    prev_requested    = Signal()
    next_requested    = Signal()
    shuffle_toggled   = Signal(bool)
    seek_requested    = Signal(float)
    fullscreen_toggle = Signal()
    crossfade_changed = Signal(float)

    def __init__(self, engine: AudioEngine, parent=None):
        super().__init__(parent)
        self.setObjectName('playerBar')
        self._engine   = engine
        self._duration = 0.0
        self._seeking  = False
        self._shuffle  = False
        self._setup_ui()
        self._connect_engine()

    def _setup_ui(self):
        self.setFixedHeight(172)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(3)

        # ── Row 1: [LEFT info] [CENTER transport] [RIGHT controls] ───────
        row = QHBoxLayout()
        row.setSpacing(0)

        # ── LEFT: título actual + siguiente ──────────────────────────────
        left_w = QWidget()
        left_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ll = QVBoxLayout(left_w)
        ll.setContentsMargins(0, 0, 16, 0)
        ll.setSpacing(4)
        ll.setAlignment(Qt.AlignVCenter)

        self._title_lbl = QLabel('JOSINODJ')
        self._title_lbl.setStyleSheet(
            'font-size:18px;font-weight:700;color:#ffffff;'
            'font-family:"Segoe UI","Arial",sans-serif;')

        self._next_lbl = QLabel('')
        self._next_lbl.setStyleSheet(
            'font-size:13px;color:#aaaacc;font-weight:500;')

        ll.addStretch()
        ll.addWidget(self._title_lbl)
        ll.addWidget(self._next_lbl)
        ll.addStretch()

        # ── CENTER: transport + tiempo ────────────────────────────────────
        center_w = QWidget()
        center_w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        cl = QVBoxLayout(center_w)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.setAlignment(Qt.AlignHCenter)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setAlignment(Qt.AlignHCenter)

        self._btn_prev = TransportButton('prev')
        self._btn_prev.setToolTip('Anterior  (←)')
        self._btn_prev.clicked.connect(self.prev_requested)

        self._btn_play = TransportButton('play', is_main=True)
        self._btn_play.setToolTip('Play / Pausa  (Espacio)')
        self._btn_play.clicked.connect(self._engine.toggle_pause)

        self._btn_next = TransportButton('next')
        self._btn_next.setToolTip('Siguiente  (→)')
        self._btn_next.clicked.connect(self.next_requested)

        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_play)
        btn_row.addWidget(self._btn_next)

        self._time_lbl = QLabel('0:00 / 0:00')
        self._time_lbl.setStyleSheet(
            'font-family:Consolas,monospace;font-size:12px;color:#555577;')
        self._time_lbl.setAlignment(Qt.AlignCenter)

        cl.addLayout(btn_row)
        cl.addWidget(self._time_lbl)

        # ── RIGHT: [vol encima de CF] + [shuffle a la derecha] ───────────
        right_w = QWidget()
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        rl = QHBoxLayout(right_w)
        rl.setContentsMargins(16, 0, 0, 0)
        rl.setSpacing(8)
        rl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Columna izquierda: vol arriba, CF abajo
        sliders_w = QWidget()
        sliders_w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sliders_l = QVBoxLayout(sliders_w)
        sliders_l.setContentsMargins(0, 0, 0, 0)
        sliders_l.setSpacing(4)
        sliders_l.setAlignment(Qt.AlignVCenter)

        # Fila volumen
        vol_row = QHBoxLayout()
        vol_row.setSpacing(5)
        vol_row.setContentsMargins(0, 0, 0, 0)
        lbl_vol = QLabel('🔊')
        lbl_vol.setStyleSheet('font-size:12px;')
        self._vol = QSlider(Qt.Horizontal)
        self._vol.setObjectName('volSlider')
        self._vol.setRange(0, 100)
        self._vol.setValue(100)
        self._vol.setFixedWidth(90)   # mismo ancho que CF
        self._vol.setToolTip('Volumen')
        self._vol.valueChanged.connect(
            lambda v: setattr(self._engine, 'master_volume', v / 100.0))
        vol_row.addWidget(lbl_vol)
        vol_row.addWidget(self._vol)

        # Fila crossfade
        cf_row = QHBoxLayout()
        cf_row.setSpacing(5)
        cf_row.setContentsMargins(0, 0, 0, 0)
        self._cf_lbl = QLabel('20s')
        self._cf_lbl.setStyleSheet('color:#cc5555;font-size:12px;min-width:28px;font-weight:600;')
        self._cf = QSlider(Qt.Horizontal)
        self._cf.setObjectName('crossfadeSlider')
        self._cf.setRange(0, 30)
        self._cf.setValue(20)
        self._cf.setFixedWidth(90)
        self._cf.setToolTip('Crossfade (segundos)')
        self._cf.valueChanged.connect(self._on_crossfade)
        cf_row.addWidget(self._cf_lbl)
        cf_row.addWidget(self._cf)

        sliders_l.addLayout(vol_row)
        sliders_l.addLayout(cf_row)

        # Botón shuffle: mismo alto que los dos sliders juntos
        self._shuf_btn = QPushButton('⇄')
        self._shuf_btn.setStyleSheet(_TOGGLE_OFF)
        self._shuf_btn.setCheckable(True)
        self._shuf_btn.setMinimumHeight(44)
        self._shuf_btn.setFixedWidth(40)
        self._shuf_btn.setToolTip('Aleatorio')
        self._shuf_btn.toggled.connect(self._on_shuf)

        rl.addWidget(sliders_w)
        rl.addWidget(self._shuf_btn)

        row.addWidget(left_w, 1)
        row.addWidget(center_w, 0, Qt.AlignHCenter)
        row.addWidget(right_w, 1)
        root.addLayout(row)

        # ── Progress slider ───────────────────────────────────────────────
        self._progress = QSlider(Qt.Horizontal)
        self._progress.setObjectName('progressSlider')
        self._progress.setRange(0, 10000)
        self._progress.setValue(0)
        self._progress.setFixedHeight(12)
        self._progress.sliderPressed.connect(self._seek_start)
        self._progress.sliderReleased.connect(self._seek_end)
        root.addWidget(self._progress)

        # ── Waveforms ─────────────────────────────────────────────────────
        self._spectrum = WaveformWidget()
        self._spectrum.seek_clicked.connect(self._on_waveform_seek)
        self._spectrum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._spectrum.setMinimumHeight(36)
        self._spectrum.setMaximumHeight(48)

        self._next_wave = NextWaveformWidget()
        self._next_wave.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._next_wave.setMinimumHeight(24)
        self._next_wave.setMaximumHeight(32)

        root.addWidget(self._spectrum)
        root.addWidget(self._next_wave)

    def _connect_engine(self):
        e = self._engine
        e.position_changed.connect(self._on_position)
        e.duration_changed.connect(self._on_duration)
        e.playback_started.connect(lambda: self._btn_play.set_mode('pause'))
        e.playback_paused.connect(lambda: self._btn_play.set_mode('play'))
        e.playback_stopped.connect(lambda: self._btn_play.set_mode('play'))
        e.waveform_ready.connect(self._spectrum.set_peaks)
        e.next_waveform_ready.connect(self._next_wave.set_peaks)
        e.track_switched.connect(self._next_wave.clear)

    # ── handlers ─────────────────────────────────────────────────────────

    def _on_shuf(self, on: bool):
        self._shuf_btn.setStyleSheet(_TOGGLE_ON if on else _TOGGLE_OFF)
        self._shuffle = on
        self.shuffle_toggled.emit(on)

    def _on_crossfade(self, val: int):
        self._engine.crossfade_duration = float(val)
        self._cf_lbl.setText(f'{val}s')
        self._spectrum.set_cf_ratio(float(val), self._duration)
        self.crossfade_changed.emit(float(val))

    def _on_position(self, pos: float):
        if self._seeking:
            return
        self._update_time(pos)
        if self._duration > 0:
            ratio = pos / self._duration
            self._progress.blockSignals(True)
            self._progress.setValue(int(ratio * 10000))
            self._progress.blockSignals(False)
            self._spectrum.set_position(ratio)
            self._spectrum.set_warning(0 < self._duration - pos <= 15)

    def _on_duration(self, dur: float):
        self._duration = dur
        self._spectrum.set_cf_ratio(float(self._cf.value()), dur)

    def _update_time(self, pos: float):
        def fmt(s):
            m, ss = divmod(int(s), 60)
            return f'{m}:{ss:02d}'
        self._time_lbl.setText(f'{fmt(pos)} / {fmt(self._duration)}')

    def _seek_start(self):
        self._seeking = True

    def _seek_end(self):
        self._seeking = False
        secs = (self._progress.value() / 10000.0) * self._duration
        self._engine.seek(secs)
        self.seek_requested.emit(secs)

    def _on_waveform_seek(self, ratio: float):
        secs = ratio * self._duration
        self._engine.seek(secs)
        self.seek_requested.emit(secs)

    # ── Lock ──────────────────────────────────────────────────────────────

    def lock(self, locked: bool):
        self._btn_prev.setEnabled(not locked)
        self._btn_next.setEnabled(not locked)
        self._cf.setEnabled(not locked)
        self._shuf_btn.setEnabled(not locked)
        self._progress.setEnabled(not locked)
        self._spectrum.setEnabled(not locked)
        if locked:
            self.setStyleSheet(
                'QWidget#playerBar{background:#0d0808;border-top:2px solid #aa2222;}')
        else:
            self.setStyleSheet('')

    # ── Public API ────────────────────────────────────────────────────────

    def set_track(self, track):
        if track is None:
            self._title_lbl.setText('JOSINODJ')
            self._next_lbl.setText('')
            self._next_wave.clear()
            self._spectrum.set_position(0.0)
            self._spectrum.set_warning(False)
            return
        self._title_lbl.setText(track.title or '?')
        self._next_wave.clear()
        self._spectrum.set_position(0.0)
        self._spectrum.set_warning(False)

    def set_next_track(self, track):
        if self._shuffle or track is None:
            self._next_lbl.setText('')
        else:
            self._next_lbl.setText(f'A continuación:  {track.title or ""}')

    def init_crossfade(self, seconds: float):
        self._cf.blockSignals(True)
        self._cf.setValue(int(round(seconds)))
        self._cf_lbl.setText(f'{int(round(seconds))}s')
        self._cf.blockSignals(False)
        self._spectrum.set_cf_ratio(seconds, self._duration)

    @property
    def shuffle_active(self) -> bool:
        return self._shuf_btn.isChecked()

    @property
    def crossfade_duration(self) -> float:
        return float(self._cf.value())

    def set_volume(self, v: float):
        self._vol.setValue(int(round(v * 100)))
