"""
Ecualizador paramétrico de 5 bandas con filtros biquad peaking.
Procesamiento en tiempo real, puro numpy.
"""
import numpy as np

# (frecuencia_hz, Q, etiqueta)
EQ_BANDS = [
    (60,    0.7,  'Bass'),
    (250,   1.4,  'Low-Mid'),
    (1000,  1.4,  'Mid'),
    (4000,  1.4,  'High-Mid'),
    (12000, 0.7,  'Treble'),
]
N_BANDS = len(EQ_BANDS)


def _lowshelf_coeffs(f0: float, dB: float, fs: int):
    """Low shelf biquad: cuts/boosts all frequencies below f0."""
    if abs(dB) < 0.02:
        return np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])
    A      = 10.0 ** (dB / 40.0)
    w0     = 2.0 * np.pi * f0 / fs
    cos_w0 = np.cos(w0)
    alpha  = np.sin(w0) / 2.0 * np.sqrt(2.0)   # slope S=1
    sqA    = np.sqrt(A)
    b0 =     A * ((A+1) - (A-1)*cos_w0 + 2*sqA*alpha)
    b1 = 2 * A * ((A-1) - (A+1)*cos_w0)
    b2 =     A * ((A+1) - (A-1)*cos_w0 - 2*sqA*alpha)
    a0 =          (A+1) + (A-1)*cos_w0 + 2*sqA*alpha
    a1 =    -2 * ((A-1) + (A+1)*cos_w0)
    a2 =          (A+1) + (A-1)*cos_w0 - 2*sqA*alpha
    return (np.array([b0/a0, b1/a0, b2/a0]),
            np.array([1.0,   a1/a0, a2/a0]))


def _peak_coeffs(f0: float, dB: float, Q: float, fs: int):
    """Coeficientes biquad peaking EQ. Devuelve (b, a) normalizados."""
    if abs(dB) < 0.02:
        return np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])
    A  = 10.0 ** (dB / 40.0)
    w0 = 2.0 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2.0 * Q)
    b0 = 1.0 + alpha * A
    b1 = -2.0 * np.cos(w0)
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha / A
    return (np.array([b0/a0, b1/a0, b2/a0]),
            np.array([1.0,   a1/a0, a2/a0]))


class Equalizer:
    """5-band peaking EQ aplicado en el callback de audio."""

    def __init__(self, sr: int = 44100, channels: int = 2):
        self._sr      = sr
        self._ch      = channels
        self._enabled = True
        self._gains   = [0.0] * N_BANDS   # dB por banda
        # Estados del filtro: (N_BANDS, 2 estados, channels)
        self._z = np.zeros((N_BANDS, 2, channels), dtype=np.float64)
        self._b = []   # coefs b por banda
        self._a = []   # coefs a por banda
        self._refresh()

    # ── API pública ───────────────────────────────────────────────────────

    def set_gain(self, band: int, dB: float):
        self._gains[band] = float(max(-12.0, min(12.0, dB)))
        self._refresh_band(band)

    def reset(self):
        self._gains = [0.0] * N_BANDS
        self._refresh()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, v: bool):
        self._enabled = v

    @property
    def gains(self) -> list[float]:
        return list(self._gains)

    def is_flat(self) -> bool:
        return all(abs(g) < 0.02 for g in self._gains)

    # ── proceso de audio ──────────────────────────────────────────────────

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Aplica EQ al bloque de audio.
        audio: np.ndarray (N, channels) float32
        Devuelve: mismo shape, float32
        """
        if not self._enabled or self.is_flat():
            return audio

        x = audio.astype(np.float64)
        for band in range(N_BANDS):
            if abs(self._gains[band]) < 0.02:
                continue
            b = self._b[band]
            a = self._a[band]
            for ch in range(self._ch):
                x[:, ch], self._z[band, :, ch] = _biquad(
                    b, a, x[:, ch], self._z[band, :, ch])
        return np.clip(x, -1.0, 1.0).astype(np.float32)

    # ── internos ──────────────────────────────────────────────────────────

    def _refresh(self):
        self._b = []
        self._a = []
        for i, (f, Q, _) in enumerate(EQ_BANDS):
            b, a = _peak_coeffs(f, self._gains[i], Q, self._sr)
            self._b.append(b)
            self._a.append(a)
        # Resetear estados al cambiar coeficientes
        self._z[:] = 0.0

    def _refresh_band(self, band: int):
        f, Q, _ = EQ_BANDS[band]
        b, a = _peak_coeffs(f, self._gains[band], Q, self._sr)
        self._b[band] = b
        self._a[band] = a
        self._z[band] = 0.0   # resetear estado de esta banda


# ── biquad vectorizado en numpy ───────────────────────────────────────────────

def _biquad(b: np.ndarray, a: np.ndarray,
            x: np.ndarray, z: np.ndarray):
    """
    Filtro biquad IIR (Direct Form II Transposed).
    x: (N,) float64  — señal mono de entrada
    z: (2,) float64  — estado interno
    Devuelve (y, z_new)
    """
    b0, b1, b2 = b[0], b[1], b[2]
    a1, a2 = a[1], a[2]
    y = np.empty_like(x)
    z0, z1 = z[0], z[1]
    for n in range(len(x)):
        yn  = b0 * x[n] + z0
        z0  = b1 * x[n] - a1 * yn + z1
        z1  = b2 * x[n] - a2 * yn
        y[n] = yn
    return y, np.array([z0, z1])
