import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont


class SpectrumWidget(QWidget):
    """Real-time FFT spectrum analyzer — fed with audio samples each frame."""

    BARS   = 52
    FFT_N  = 2048
    DECAY  = 0.76

    def __init__(self, label: str = 'ACTUAL  ▶', parent=None):
        super().__init__(parent)
        self._label = label
        self._bars  = np.zeros(self.BARS, dtype=np.float32)
        self._peaks = np.zeros(self.BARS, dtype=np.float32)
        self._hold  = np.zeros(self.BARS, dtype=np.int32)
        self._bins  = self._build_bins()
        self._window = np.hanning(self.FFT_N).astype(np.float32)
        self.setMinimumHeight(56)

    # ── frequency bin mapping (log scale, 30 Hz – 18 kHz) ────────────────

    def _build_bins(self) -> list[np.ndarray]:
        freqs = np.fft.rfftfreq(self.FFT_N, 1.0 / 44100)
        edges = np.logspace(np.log10(30), np.log10(18000), self.BARS + 1)
        bins = []
        for i in range(self.BARS):
            idx = np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0]
            if len(idx) == 0:
                idx = np.array([np.argmin(np.abs(freqs - (edges[i] + edges[i + 1]) / 2))])
            bins.append(idx)
        return bins

    # ── public API ────────────────────────────────────────────────────────

    def update_spectrum(self, samples: np.ndarray):
        n = self.FFT_N
        if len(samples) >= n:
            buf = samples[-n:].astype(np.float32)
        else:
            buf = np.zeros(n, dtype=np.float32)
            buf[-len(samples):] = samples

        mag  = np.abs(np.fft.rfft(buf * self._window))
        db   = 20.0 * np.log10(mag + 1e-8)
        norm = np.clip((db + 90.0) / 90.0, 0.0, 1.0).astype(np.float32)

        new = np.array([norm[idx].max() for idx in self._bins], dtype=np.float32)
        self._bars = np.maximum(self._bars * self.DECAY, new)

        # Peak hold
        rising = new > self._peaks
        self._peaks[rising] = new[rising]
        self._hold[rising]  = 24
        self._hold[~rising] = np.maximum(self._hold[~rising] - 1, 0)
        self._peaks[(~rising) & (self._hold == 0)] = np.maximum(
            self._peaks[(~rising) & (self._hold == 0)] - 0.016, 0)

        self.update()

    def decay(self):
        self._bars  *= self.DECAY * 0.55
        self._peaks  = np.maximum(self._peaks - 0.025, 0)
        self.update()

    def reset(self):
        self._bars[:]  = 0
        self._peaks[:] = 0
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#060610'))

        n   = self.BARS
        bwf = w / n
        gap = max(1, int(bwf * 0.13))
        bw  = max(2, int(bwf - gap))

        for i in range(n):
            val = float(self._bars[i])
            if val < 0.004:
                continue
            x  = int(i * bwf) + gap // 2
            bh = max(2, int(val * (h - 7)))
            y  = h - bh - 3

            # Cyan → green → yellow → red gradient
            if val < 0.45:
                t  = val / 0.45
                r, g, b = int(t * 20), int(160 + t * 70), int(220 - t * 80)
            elif val < 0.72:
                t  = (val - 0.45) / 0.27
                r, g, b = int(20 + t * 230), int(230 - t * 60), int(140 - t * 110)
            else:
                t  = min((val - 0.72) / 0.28, 1.0)
                r, g, b = 250, int(170 - t * 170), int(30 - t * 30)

            painter.fillRect(x, y, bw, bh, QColor(r, g, b))

            # Peak dot
            pv = float(self._peaks[i])
            if pv > 0.04:
                py = h - int(pv * (h - 7)) - 4
                painter.fillRect(x, py, bw, 2, QColor(255, 255, 200, 190))

        # Label bottom-left
        if self._label:
            painter.setPen(QColor('#25254a'))
            painter.setFont(QFont('Segoe UI', 7))
            painter.drawText(5, h - 3, self._label)

        # Top border
        painter.setPen(QPen(QColor('#0f0f20'), 1))
        painter.drawLine(0, 0, w, 0)
        painter.end()


# ── Next track static waveform ────────────────────────────────────────────────

class NextWaveformWidget(QWidget):
    """Shows a static waveform overview of the preloaded next track."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: np.ndarray | None = None
        self.setMinimumHeight(56)

    def set_peaks(self, peaks: np.ndarray | None):
        self._peaks = peaks
        self.update()

    def clear(self):
        self._peaks = None
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#06060f'))
        mid = h // 2

        if self._peaks is not None and len(self._peaks) > 0:
            n   = len(self._peaks)
            bw  = max(1, w // n)
            for i, peak in enumerate(self._peaks):
                x  = int(i * w / n)
                bh = max(1, int(peak * (mid - 4)))
                painter.fillRect(x, mid - bh, bw, bh * 2, QColor('#2d2060'))
        else:
            painter.setPen(QColor('#1c1c30'))
            painter.setFont(QFont('Segoe UI', 9))
            painter.drawText(0, 0, w, h, Qt.AlignCenter, 'Sin siguiente canción')

        # Label
        painter.setPen(QColor('#25254a'))
        painter.setFont(QFont('Segoe UI', 7))
        painter.drawText(5, h - 3, 'SIGUIENTE  ▷')

        # Top + left borders
        painter.setPen(QPen(QColor('#0f0f20'), 1))
        painter.drawLine(0, 0, w, 0)
        painter.setPen(QPen(QColor('#111122'), 1))
        painter.drawLine(0, 0, 0, h)
        painter.end()
