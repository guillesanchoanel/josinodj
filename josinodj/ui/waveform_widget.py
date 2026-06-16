import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush, QFont


class WaveformWidget(QWidget):
    seek_clicked = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: np.ndarray | None = None
        self._position = 0.0
        self._cf_ratio = 0.0
        self._hover    = -1.0
        self._warning  = False   # True = quedan pocos segundos
        self._blink_on = False   # estado actual del parpadeo

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tick)

        self.setMinimumHeight(44)
        self.setMaximumHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def set_warning(self, active: bool):
        if active == self._warning:
            return
        self._warning = active
        if active:
            self._blink_on = True
            self._blink_timer.start(420)   # parpadeo cada 420 ms
        else:
            self._blink_timer.stop()
            self._blink_on = False
        self.update()

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        self.update()

    def set_peaks(self, peaks: np.ndarray):
        """Recibe picos ya calculados — sin computación, sin tirón."""
        self._peaks = peaks
        self.update()

    def set_audio(self, data: np.ndarray, sr: int):
        if data is None or len(data) == 0:
            self._peaks = None
            self.update()
            return
        mono = np.mean(data, axis=1) if data.ndim > 1 else data
        n = max(400, self.width() or 800)
        w = max(1, len(mono) // n)
        peaks = np.array([np.max(np.abs(mono[i: i + w])) for i in range(0, len(mono) - w, w)], dtype=np.float32)
        mx = peaks.max()
        if mx > 0:
            peaks /= mx
        self._peaks = peaks
        self.update()

    def set_position(self, ratio: float):
        self._position = max(0.0, min(1.0, ratio))
        self.update()

    def set_cf_ratio(self, cf_duration: float, total_duration: float):
        self._cf_ratio = (cf_duration / total_duration) if total_duration > 0 else 0.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._peaks is not None:
            self.seek_clicked.emit(event.position().x() / max(1, self.width()))

    def mouseMoveEvent(self, event):
        self._hover = event.position().x() / max(1, self.width())
        self.update()

    def leaveEvent(self, event):
        self._hover = -1.0
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        mid = h // 2

        # Fondo — rojo oscuro cuando parpadea en modo aviso
        bg = QColor('#1a0505') if (self._warning and self._blink_on) else QColor('#0d0d0d')
        painter.fillRect(0, 0, w, h, bg)

        if self._peaks is not None and len(self._peaks) > 0:
            n = len(self._peaks)
            px = int(self._position * w)
            bar_w = max(1, w // n)

            # Color de barras: rojo vivo en aviso, normal en otro caso
            if self._warning and self._blink_on:
                col_played   = QColor('#dd2222')
                col_unplayed = QColor('#551010')
            else:
                col_played   = QColor('#4a40cc')
                col_unplayed = QColor('#252535')

            for i, peak in enumerate(self._peaks):
                x = int(i * w / n)
                bh = max(2, int(peak * (mid - 3)))
                color = col_played if x < px else col_unplayed
                painter.fillRect(x, mid - bh, bar_w, bh * 2, color)

            # Crossfade zone: red gradient at the end of the track
            if self._cf_ratio > 0:
                cf_x = int((1.0 - self._cf_ratio) * w)
                grad = QLinearGradient(cf_x, 0, w, 0)
                grad.setColorAt(0.0, QColor(220, 60, 40, 0))
                grad.setColorAt(0.5, QColor(220, 60, 40, 55))
                grad.setColorAt(1.0, QColor(220, 60, 40, 110))
                painter.fillRect(cf_x, 0, w - cf_x, h, QBrush(grad))

            if px > 0:
                painter.setPen(QPen(QColor('#00ccff'), 2))
                painter.drawLine(px, 0, px, h)
        if 0.0 <= self._hover <= 1.0:
            hx = int(self._hover * w)
            painter.setPen(QPen(QColor('#ffffff30'), 1))
            painter.drawLine(hx, 0, hx, h)
        painter.end()


# ── Dual waveform ─────────────────────────────────────────────────────────────

class DualWaveformWidget(QWidget):
    """
    Shows current track (top 65%) and next track preview (bottom 35%).
    Highlights crossfade zone at the end of the current track.
    """
    seek_clicked = Signal(float)  # 0.0–1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curr_peaks: np.ndarray | None = None
        self._next_peaks: np.ndarray | None = None
        self._position = 0.0
        self._cf_ratio = 0.0        # crossfade_duration / total_duration
        self._hover = -1.0
        self._is_crossfading = False
        self.setMinimumHeight(72)
        self.setMaximumHeight(88)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    # ── public API ────────────────────────────────────────────────────────

    def set_current_audio(self, data: np.ndarray, sr: int):
        self._curr_peaks = self._make_peaks(data)
        self._next_peaks = None      # clear next when new track starts
        self._position = 0.0
        self.update()

    def set_current_peaks(self, peaks: np.ndarray):
        self._curr_peaks = peaks
        self.update()

    def set_next_peaks(self, peaks: np.ndarray):
        self._next_peaks = peaks
        self.update()

    def clear_next(self):
        self._next_peaks = None
        self.update()

    def set_position(self, ratio: float):
        self._position = max(0.0, min(1.0, ratio))
        # detect crossfade start visually
        self._is_crossfading = (self._next_peaks is not None and
                                self._position >= max(0.0, 1.0 - self._cf_ratio - 0.01))
        self.update()

    def set_cf_ratio(self, cf_duration: float, total_duration: float):
        self._cf_ratio = (cf_duration / total_duration) if total_duration > 0 else 0.0
        self.update()

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_peaks(data: np.ndarray, n: int = 500) -> np.ndarray | None:
        if data is None or len(data) == 0:
            return None
        mono = np.mean(data, axis=1) if data.ndim > 1 else data
        trunc = len(mono) - (len(mono) % n)
        if trunc >= n:
            peaks = np.abs(mono[:trunc]).reshape(n, -1).max(axis=1).astype(np.float32)
        else:
            peaks = np.abs(mono).astype(np.float32)
        mx = peaks.max()
        if mx > 0:
            peaks /= mx
        return peaks

    def _draw_peaks(self, painter: QPainter, peaks: np.ndarray,
                    x0: int, y0: int, w: int, h: int,
                    played_pct: float,
                    col_played: str, col_unplayed: str,
                    cf_start_pct: float = -1.0):
        if peaks is None or len(peaks) == 0:
            return
        mid = y0 + h // 2
        n = len(peaks)
        bar_w = max(1, w // n)
        px = int(played_pct * w)
        cf_x = int(cf_start_pct * w) if cf_start_pct >= 0 else -1

        for i, peak in enumerate(peaks):
            x = x0 + int(i * w / n)
            bh = max(1, int(peak * (h // 2 - 2)))
            if x < x0 + px:
                color = QColor(col_played)
            else:
                color = QColor(col_unplayed)
            painter.fillRect(x, mid - bh, bar_w, bh * 2, color)

        # Crossfade zone gradient overlay
        if cf_x > 0:
            grad = QLinearGradient(x0 + cf_x, y0, x0 + w, y0)
            alpha = 80 if not self._is_crossfading else 120
            grad.setColorAt(0.0, QColor(255, 90, 60, 0))
            grad.setColorAt(0.4, QColor(255, 90, 60, alpha // 2))
            grad.setColorAt(1.0, QColor(255, 90, 60, alpha))
            painter.fillRect(x0 + cf_x, y0, w - cf_x, h, QBrush(grad))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._curr_peaks is not None:
            # Only seek if click is in the top (current track) section
            curr_h = int(self.height() * 0.65)
            if event.position().y() <= curr_h:
                self.seek_clicked.emit(event.position().x() / max(1, self.width()))

    def mouseMoveEvent(self, event):
        self._hover = event.position().x() / max(1, self.width())
        self.update()

    def leaveEvent(self, event):
        self._hover = -1.0
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#0a0a0a'))

        has_next = self._next_peaks is not None
        curr_h = int(h * (0.65 if has_next else 1.0))
        sep = 3 if has_next else 0
        next_h = h - curr_h - sep if has_next else 0

        # ── current track ─────────────────────────────────────────────────
        cf_start = max(0.0, 1.0 - self._cf_ratio) if self._cf_ratio > 0 else -1.0
        self._draw_peaks(
            painter, self._curr_peaks,
            0, 0, w, curr_h,
            played_pct=self._position,
            col_played='#5248d0',
            col_unplayed='#212130',
            cf_start_pct=cf_start,
        )

        # Playhead
        if self._curr_peaks is not None:
            px = int(self._position * w)
            c = QColor('#00e5ff') if not self._is_crossfading else QColor('#ff7050')
            painter.setPen(QPen(c, 2))
            painter.drawLine(px, 0, px, curr_h)

        # ── separator ─────────────────────────────────────────────────────
        if has_next:
            painter.fillRect(0, curr_h, w, sep, QColor('#1a1a2a'))
            # "SIGUIENTE" label
            lbl_x = 4
            lbl_y = curr_h + sep + next_h - 3
            painter.setPen(QColor('#3a3060'))
            painter.setFont(QFont('Segoe UI', 7))
            painter.drawText(lbl_x, lbl_y, 'SIGUIENTE ▶')

        # ── next track ────────────────────────────────────────────────────
        if has_next:
            ny = curr_h + sep
            self._draw_peaks(
                painter, self._next_peaks,
                0, ny, w, next_h,
                played_pct=0.0,
                col_played='#2a1f50',
                col_unplayed='#1e1838',
            )

        # ── hover line ────────────────────────────────────────────────────
        if 0.0 <= self._hover <= 1.0:
            hx = int(self._hover * w)
            painter.setPen(QPen(QColor('#ffffff18'), 1))
            painter.drawLine(hx, 0, hx, h)

        painter.end()
