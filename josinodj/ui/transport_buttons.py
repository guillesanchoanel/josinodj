"""
Transport buttons dibujados con QPainter.
Sin emojis ni iconos externos — formas geométricas puras, escalables y consistentes.
"""
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPolygonF, QLinearGradient, QPen


class TransportButton(QPushButton):
    """
    Botón dibujado a mano.
    mode: 'play' | 'pause' | 'prev' | 'next'
    is_main: True = botón grande con fondo coloreado
    """

    def __init__(self, mode: str, is_main: bool = False, parent=None):
        super().__init__(parent)
        self._mode    = mode
        self._is_main = is_main
        self._hover   = False
        self._pressed = False

        size = 58 if is_main else 42
        self.setFixedSize(size, size)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    # ── mode switch ───────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        if self._mode != mode:
            self._mode = mode
            self.update()

    # ── hover / press tracking ────────────────────────────────────────────

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, e):
        self._pressed = True
        self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(e)

    # ── paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 2

        # ── background ────────────────────────────────────────────────────
        if self._is_main:
            if self._pressed:
                c1, c2 = QColor('#3528b0'), QColor('#5030a0')
            elif self._hover:
                c1, c2 = QColor('#7060f8'), QColor('#a050e8')
            else:
                c1, c2 = QColor('#5a50e0'), QColor('#8040cc')
            grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        else:
            if self._pressed:
                bg = QColor('#1a1a2e')
            elif self._hover:
                bg = QColor('#20203a')
            else:
                bg = QColor(0, 0, 0, 0)
            if not bg.alpha() == 0:
                p.setBrush(bg)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 10, 10)

        # ── symbol ────────────────────────────────────────────────────────
        if self._is_main:
            sym = QColor('#ffffff')
        elif self._hover:
            sym = QColor('#d0d0ff')
        else:
            sym = QColor('#7878aa')

        p.setBrush(sym)
        p.setPen(Qt.NoPen)

        if self._mode == 'play':
            self._draw_play(p, cx, cy, r)
        elif self._mode == 'pause':
            self._draw_pause(p, cx, cy, r)
        elif self._mode == 'prev':
            self._draw_prev(p, cx, cy, r)
        elif self._mode == 'next':
            self._draw_next(p, cx, cy, r)

        p.end()

    # ── shape drawers ─────────────────────────────────────────────────────

    def _draw_play(self, p: QPainter, cx, cy, r):
        s = r * 0.48
        # Slightly right-offset so triangle looks optically centered
        ox = s * 0.12
        p.drawPolygon(QPolygonF([
            QPointF(cx - s * 0.75 + ox, cy - s),
            QPointF(cx - s * 0.75 + ox, cy + s),
            QPointF(cx + s * 0.85 + ox, cy),
        ]))

    def _draw_pause(self, p: QPainter, cx, cy, r):
        s   = r * 0.45
        bw  = s * 0.42
        gap = s * 0.36
        for sign in (-1, 1):
            x = cx + sign * (gap / 2 + (bw / 2 if sign > 0 else -bw / 2)) - (bw / 2 if sign < 0 else 0)
            # Simpler: left bar and right bar
        # Left bar
        p.drawRoundedRect(
            QRectF(cx - gap / 2 - bw, cy - s, bw, s * 2), 2, 2)
        # Right bar
        p.drawRoundedRect(
            QRectF(cx + gap / 2, cy - s, bw, s * 2), 2, 2)

    def _draw_prev(self, p: QPainter, cx, cy, r):
        s  = r * 0.40
        bw = s * 0.32
        # Total group width = bw + gap + triangle_width = bw + 0.15*s + 1.4*s
        total_w = bw + s * 0.18 + s * 1.4
        ox = total_w / 2 - bw  # shift left so group is centered
        # Vertical bar (left side)
        bar_x = cx - ox - bw
        p.drawRoundedRect(QRectF(bar_x, cy - s, bw, s * 2), 2, 2)
        # Triangle pointing left
        tx = bar_x + bw + s * 0.18
        p.drawPolygon(QPolygonF([
            QPointF(tx + s * 1.4, cy - s),
            QPointF(tx + s * 1.4, cy + s),
            QPointF(tx,           cy),
        ]))

    def _draw_next(self, p: QPainter, cx, cy, r):
        s  = r * 0.40
        bw = s * 0.32
        total_w = bw + s * 0.18 + s * 1.4
        ox = total_w / 2
        # Triangle pointing right
        tx = cx - ox
        p.drawPolygon(QPolygonF([
            QPointF(tx,             cy - s),
            QPointF(tx,             cy + s),
            QPointF(tx + s * 1.4,  cy),
        ]))
        # Vertical bar (right side)
        bar_x = tx + s * 1.4 + s * 0.18
        p.drawRoundedRect(QRectF(bar_x, cy - s, bw, s * 2), 2, 2)
