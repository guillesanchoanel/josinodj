from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSlider, QLabel, QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from ..audio.equalizer import EQ_BANDS, N_BANDS

_COLORS = ['#5b8cff', '#7ecfff', '#aaffaa', '#ffcc55', '#ff7070']


class EQWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._eq = engine.eq
        self._sliders: list[QSlider] = []
        self._db_lbls: list[QLabel]  = []
        self.setMinimumWidth(320)
        self.setStyleSheet('QWidget { background: #080810; }')
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # ── Cabecera ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel('ECUALIZADOR  5 BANDAS')
        title.setStyleSheet(
            'color:#555577; font-size:10px; font-weight:bold; letter-spacing:2px;')

        self._on_btn = QPushButton('ON')
        self._on_btn.setCheckable(True)
        self._on_btn.setChecked(False)   # OFF por defecto
        self._on_btn.setFixedHeight(26)
        self._on_btn.setMinimumWidth(46)
        self._on_btn.setStyleSheet(
            'QPushButton{background:#1a1a1a;border:1px solid #2a2a2a;'
            'border-radius:4px;color:#444444;font-size:11px;font-weight:bold;padding:0 8px;}'
            'QPushButton:checked{background:#0d2218;border:1px solid #1a5c38;color:#44ee88;}')
        self._on_btn.toggled.connect(lambda v: setattr(self._eq, 'enabled', v))
        self._eq.enabled = False   # sincronizar estado inicial

        flat_btn = QPushButton('FLAT')
        flat_btn.setFixedHeight(26)
        flat_btn.setMinimumWidth(52)
        flat_btn.setStyleSheet(
            'background:#141428;border:1px solid #2a2a50;'
            'border-radius:4px;color:#666699;font-size:11px;font-weight:bold;padding:0 8px;')
        flat_btn.clicked.connect(self._flat)

        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._on_btn)
        hdr.addSpacing(4)
        hdr.addWidget(flat_btn)
        root.addLayout(hdr)

        # ── Bandas ────────────────────────────────────────────────────────
        bands = QHBoxLayout()
        bands.setSpacing(6)

        for i, (freq, Q, name) in enumerate(EQ_BANDS):
            col = QVBoxLayout()
            col.setSpacing(3)
            col.setAlignment(Qt.AlignHCenter)

            db_lbl = QLabel('0 dB')
            db_lbl.setAlignment(Qt.AlignCenter)
            db_lbl.setStyleSheet(
                f'color:{_COLORS[i]}; font-size:11px; font-weight:600;'
                f'min-width:46px;')
            self._db_lbls.append(db_lbl)

            sl = QSlider(Qt.Vertical)
            sl.setRange(-120, 120)
            sl.setValue(0)
            sl.setFixedHeight(90)
            sl.setFixedWidth(30)
            sl.setTickPosition(QSlider.TicksBothSides)
            sl.setTickInterval(40)
            sl.setStyleSheet(f"""
                QSlider::groove:vertical {{
                    width:4px; background:#1a1a2a; border-radius:2px;
                }}
                QSlider::handle:vertical {{
                    background:{_COLORS[i]};
                    width:16px; height:16px; border-radius:8px;
                    margin:0 -6px;
                }}
                QSlider::sub-page:vertical {{
                    background:{_COLORS[i]}55; border-radius:2px;
                }}
                QSlider::add-page:vertical {{
                    background:{_COLORS[i]}22; border-radius:2px;
                }}
            """)
            self._sliders.append(sl)
            sl.valueChanged.connect(lambda v, b=i: self._changed(b, v))

            hz_str = f'{freq}Hz' if freq < 1000 else f'{freq//1000}kHz'
            freq_lbl = QLabel(hz_str)
            freq_lbl.setAlignment(Qt.AlignCenter)
            freq_lbl.setStyleSheet('color:#8888aa; font-size:10px; min-width:46px;')

            name_lbl = QLabel(name)
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setStyleSheet('color:#aaaacc; font-size:10px; font-weight:600; min-width:46px;')

            col.addWidget(db_lbl)
            col.addWidget(sl, alignment=Qt.AlignHCenter)
            col.addWidget(freq_lbl)
            col.addWidget(name_lbl)
            bands.addLayout(col)

        root.addLayout(bands)

    def _changed(self, band: int, value: int):
        dB = value / 10.0
        self._eq.set_gain(band, dB)
        sign = '+' if dB >= 0 else ''
        self._db_lbls[band].setText(f'{sign}{dB:.1f}')

    def _flat(self):
        self._eq.reset()
        for sl in self._sliders:
            sl.blockSignals(True)
            sl.setValue(0)
            sl.blockSignals(False)
        for lbl in self._db_lbls:
            lbl.setText('0 dB')
