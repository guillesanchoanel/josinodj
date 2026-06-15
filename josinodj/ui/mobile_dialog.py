"""
Control remoto desde móvil.
Modo A — WiFi normal: PC y móvil en la misma red, solo muestra QR con la URL.
Modo B — Sin WiFi:    Activa hotspot en el PC, muestra QR de WiFi + URL.
"""
import subprocess
import socket
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QStackedWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage

HOTSPOT_SSID = 'JOSINODJ'
HOTSPOT_PASS = 'josinodj2024'
HOTSPOT_IP   = '192.168.137.1'
SERVER_PORT  = 8080


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ''


def _has_network() -> bool:
    return bool(_local_ip())


def _enable_hotspot() -> bool:
    try:
        subprocess.run(
            ['netsh', 'wlan', 'set', 'hostednetwork',
             'mode=allow', f'ssid={HOTSPOT_SSID}', f'key={HOTSPOT_PASS}'],
            capture_output=True, timeout=8)
        r = subprocess.run(
            ['netsh', 'wlan', 'start', 'hostednetwork'],
            capture_output=True, timeout=8)
        return r.returncode == 0
    except Exception:
        return False


def _disable_hotspot():
    try:
        subprocess.run(['netsh', 'wlan', 'stop', 'hostednetwork'],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def _qr_pixmap(text: str, size: int) -> QPixmap | None:
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=12, border=4,
                           error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(text)
        qr.make(fit=True)
        img  = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        # Pasar a Qt SIN resize de PIL (PIL resize es pixelado)
        w, h = img.width, img.height
        data = img.tobytes('raw', 'RGB')
        qi   = QImage(data, w, h, w * 3, QImage.Format_RGB888)
        px   = QPixmap.fromImage(qi)
        # Escalar suavemente con Qt
        return px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception:
        return None


_CARD = ('background:#111122; border-radius:8px; padding:2px;')
_BTN_ON  = ('background:#1a2a1a; border:2px solid #3a8a3a;'
            'border-radius:6px; color:#44ee88; font-weight:700;'
            'padding:0 18px; height:34px;')
_BTN_OFF = ('background:#1a1a2a; border:1px solid #2a2a40;'
            'border-radius:6px; color:#555577;'
            'padding:0 18px; height:34px;')


# ── Dialog ────────────────────────────────────────────────────────────────────

class MobileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Control desde móvil  –  JOSINODJ')
        self.setMinimumWidth(500)
        self.setMaximumWidth(620)
        self.resize(520, 700)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet('QDialog{background:#0d0d18;} QLabel{color:#cccccc;}')
        self._hotspot_active = False
        self._mode = 'wifi'   # 'wifi' | 'hotspot'
        self._build_ui()
        self._auto_detect()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(22, 20, 22, 20)

        title = QLabel('📱  Control desde el móvil')
        title.setStyleSheet('font-size:16px; font-weight:700; color:#ffffff;')
        root.addWidget(title)

        # Selector de modo
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self._btn_wifi = QPushButton('📶  Mismo WiFi')
        self._btn_wifi.setFixedHeight(34)
        self._btn_wifi.setCheckable(True)
        self._btn_wifi.clicked.connect(lambda: self._switch('wifi'))

        self._btn_hotspot = QPushButton('🔥  Sin WiFi (Hotspot)')
        self._btn_hotspot.setFixedHeight(34)
        self._btn_hotspot.setCheckable(True)
        self._btn_hotspot.clicked.connect(lambda: self._switch('hotspot'))

        mode_row.addWidget(self._btn_wifi)
        mode_row.addWidget(self._btn_hotspot)
        root.addLayout(mode_row)

        self._status_lbl = QLabel('')
        self._status_lbl.setStyleSheet('font-size:11px; color:#555577;')
        root.addWidget(self._status_lbl)

        # Stack: página WiFi / página Hotspot
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_wifi_page())
        self._stack.addWidget(self._build_hotspot_page())
        root.addWidget(self._stack, 1)

        hint = QLabel('Mientras esta ventana esté abierta el control está activo.')
        hint.setStyleSheet('font-size:10px; color:#1e1e38;')
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        btn_close = QPushButton('Cerrar')
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet(
            'background:#1a1a2a; border:1px solid #2a2a40;'
            'border-radius:5px; color:#666688; padding:0 16px;')
        btn_close.clicked.connect(self.reject)
        root.addWidget(btn_close, alignment=Qt.AlignRight)

    # ── Página modo WiFi normal ───────────────────────────────────────────

    def _build_wifi_page(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(10)

        card = QWidget()
        card.setStyleSheet(_CARD)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(8)

        info = QLabel(
            'PC y móvil deben estar conectados al <b>mismo WiFi</b>.<br>'
            'Escanea el QR con la cámara del móvil para abrir el mando.')
        info.setStyleSheet('font-size:12px; color:#888899;')
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        cl.addWidget(info)

        self._qr_wifi_url = QLabel()
        self._qr_wifi_url.setAlignment(Qt.AlignCenter)
        self._qr_wifi_url.setFixedHeight(260)
        self._qr_wifi_url.setStyleSheet('background:white; border-radius:6px; padding:8px;')
        cl.addWidget(self._qr_wifi_url)

        self._url_wifi_lbl = QLabel()
        self._url_wifi_lbl.setStyleSheet(
            'font-size:15px; font-weight:700; color:#4488ff;'
            'font-family:Consolas,monospace;')
        self._url_wifi_lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(self._url_wifi_lbl)

        vl.addWidget(card)
        return w

    # ── Página modo Hotspot ───────────────────────────────────────────────

    def _build_hotspot_page(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(10)

        card = QWidget()
        card.setStyleSheet(_CARD)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(10)

        step1 = QLabel('① Escanea para conectar el móvil al WiFi del PC:')
        step1.setStyleSheet('font-size:12px; color:#777799; font-weight:600;')
        cl.addWidget(step1)

        self._qr_hs_wifi = QLabel()
        self._qr_hs_wifi.setAlignment(Qt.AlignCenter)
        self._qr_hs_wifi.setFixedHeight(220)
        self._qr_hs_wifi.setStyleSheet('background:white; border-radius:6px; padding:8px;')
        cl.addWidget(self._qr_hs_wifi)

        wifi_info = QLabel(
            f'Red: <b>{HOTSPOT_SSID}</b>  ·  Contraseña: <b>{HOTSPOT_PASS}</b>')
        wifi_info.setStyleSheet('font-size:11px; color:#444466;')
        wifi_info.setTextFormat(Qt.RichText)
        wifi_info.setAlignment(Qt.AlignCenter)
        cl.addWidget(wifi_info)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet('background:#1a1a2a;')
        cl.addWidget(sep)

        step2 = QLabel('② Conectado al WiFi, escanea este QR para abrir el mando:')
        step2.setStyleSheet('font-size:12px; color:#777799; font-weight:600;')
        cl.addWidget(step2)

        self._qr_hs_url = QLabel()
        self._qr_hs_url.setAlignment(Qt.AlignCenter)
        self._qr_hs_url.setFixedHeight(220)
        self._qr_hs_url.setStyleSheet('background:white; border-radius:6px; padding:8px;')
        cl.addWidget(self._qr_hs_url)

        url_lbl = QLabel(f'http://{HOTSPOT_IP}:{SERVER_PORT}')
        url_lbl.setStyleSheet(
            'font-size:14px; font-weight:700; color:#44ee88;'
            'font-family:Consolas,monospace; padding:4px 0;')
        url_lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(url_lbl)

        btn_activate = QPushButton('🔥 Activar hotspot ahora')
        btn_activate.setFixedHeight(34)
        btn_activate.setStyleSheet(
            'background:#1a1060; border:1px solid #3a30aa;'
            'border-radius:5px; color:#aaaaff; font-weight:600;')
        btn_activate.clicked.connect(self._activate_hotspot)
        cl.addWidget(btn_activate)

        self._hs_status = QLabel('')
        self._hs_status.setStyleSheet('font-size:11px; color:#888899;')
        self._hs_status.setAlignment(Qt.AlignCenter)
        self._hs_status.setWordWrap(True)
        cl.addWidget(self._hs_status)

        vl.addWidget(card)
        return w

    # ── Lógica ────────────────────────────────────────────────────────────

    def _auto_detect(self):
        from ..server import web_server as srv
        srv.start(SERVER_PORT)
        # Siempre empieza en WiFi — el usuario cambia a Hotspot si lo necesita
        self._switch('wifi')

    def _switch(self, mode: str):
        self._mode = mode
        is_wifi = (mode == 'wifi')
        self._btn_wifi.setStyleSheet(_BTN_ON if is_wifi else _BTN_OFF)
        self._btn_hotspot.setStyleSheet(_BTN_OFF if is_wifi else _BTN_ON)
        self._stack.setCurrentIndex(0 if is_wifi else 1)

        if is_wifi:
            self._setup_wifi_mode()
        else:
            self._setup_hotspot_mode()

    def _setup_wifi_mode(self):
        ip = _local_ip()
        if not ip:
            self._status_lbl.setText('⚠  No se detectó red WiFi. Usa el modo Hotspot.')
            return
        url = f'http://{ip}:{SERVER_PORT}'
        self._url_wifi_lbl.setText(url)
        self._status_lbl.setText(f'IP del PC en tu red: {ip}')
        px = _qr_pixmap(url, 250)
        if px:
            self._qr_wifi_url.setPixmap(px)
        else:
            self._qr_wifi_url.setText(url)

    def _setup_hotspot_mode(self):
        # Solo muestra los QR, no activa nada automáticamente
        wifi_str = f'WIFI:T:WPA;S:{HOTSPOT_SSID};P:{HOTSPOT_PASS};;'
        px_w = _qr_pixmap(wifi_str, 210)
        if px_w:
            self._qr_hs_wifi.setPixmap(px_w)

        url = f'http://{HOTSPOT_IP}:{SERVER_PORT}'
        px_u = _qr_pixmap(url, 210)
        if px_u:
            self._qr_hs_url.setPixmap(px_u)
        else:
            self._qr_hs_url.setText(url)


    def _activate_hotspot(self):
        self._hs_status.setText('Activando hotspot…')
        ok = _enable_hotspot()
        self._hotspot_active = ok
        if ok:
            self._hs_status.setText('✅  Hotspot activo — conéctate a la red JOSINODJ')
            self._hs_status.setStyleSheet('font-size:11px; color:#44ee88;')
        else:
            self._hs_status.setText(
                '❌  No se pudo activar automáticamente.\n'
                'Ve a: Configuración → Sistema → Zona de acceso móvil → Activar')
            self._hs_status.setStyleSheet('font-size:11px; color:#ff6666;')

    def closeEvent(self, event):
        if self._hotspot_active:
            _disable_hotspot()
        event.accept()

    def reject(self):
        if self._hotspot_active:
            _disable_hotspot()
        super().reject()
