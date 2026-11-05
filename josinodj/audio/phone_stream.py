"""
Retransmite al móvil (por WiFi) lo mismo que suena en el portátil.

El callback de audio del motor llama a `tap()` con cada bloque ya mezclado
(crossfade, EQ, volumen). Un hilo aparte lo codifica a MP3 y lo reparte a
los móviles conectados a /stream. El móvil lo suelta por su Bluetooth.

Mientras haya algún móvil escuchando, el motor silencia la salida local
(ver `local_muted`), así no suena a la vez en el portátil.
"""
import queue
import threading
import time

import numpy as np

_SR = 44100
_CH = 2

_in_q: queue.Queue = queue.Queue(maxsize=200)   # bloques float32 del callback
_listeners: list[queue.Queue] = []
_lock = threading.Lock()
_worker: threading.Thread | None = None


def listener_count() -> int:
    with _lock:
        return len(_listeners)


def local_muted() -> bool:
    """True si la música debe sonar solo en el móvil."""
    return listener_count() > 0


def tap(block: np.ndarray):
    """Llamado desde el callback de audio. Nunca bloquea."""
    if not _listeners:
        return
    try:
        _in_q.put_nowait(block.copy())
    except queue.Full:
        pass


def _make_encoder():
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(192)
    enc.set_in_sample_rate(_SR)
    enc.set_channels(_CH)
    enc.set_quality(5)
    return enc


def _run():
    enc = _make_encoder()
    last = time.monotonic()
    while True:
        if not _listeners:
            # Nadie escucha: vaciar y dormir
            while not _in_q.empty():
                _in_q.get_nowait()
            time.sleep(0.2)
            last = time.monotonic()
            continue
        try:
            block = _in_q.get(timeout=0.15)
            last = time.monotonic()
        except queue.Empty:
            # Motor parado (stop / sin canción): mandar silencio para que el
            # navegador no corte la conexión ni se quede esperando.
            now = time.monotonic()
            n = min(int((now - last) * _SR), _SR)   # silencio = tiempo transcurrido
            last = now
            if n <= 0:
                continue
            block = np.zeros((n, _CH), dtype=np.float32)
        pcm = (np.clip(block, -1.0, 1.0) * 32767).astype('<i2').tobytes()
        data = enc.encode(pcm)
        if not data:
            continue
        with _lock:
            for q in _listeners:
                try:
                    q.put_nowait(bytes(data))
                except queue.Full:
                    # Móvil que no da abasto: tirar lo viejo para no acumular retraso
                    try:
                        while True:
                            q.get_nowait()
                    except queue.Empty:
                        pass


def _ensure_worker():
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, daemon=True, name='phone-stream')
        _worker.start()


def stream_generator():
    """Generador para la respuesta HTTP /stream (un móvil)."""
    _ensure_worker()
    q: queue.Queue = queue.Queue(maxsize=100)
    with _lock:
        _listeners.append(q)
    try:
        while True:
            try:
                yield q.get(timeout=5)
            except queue.Empty:
                continue
    finally:
        with _lock:
            if q in _listeners:
                _listeners.remove(q)
