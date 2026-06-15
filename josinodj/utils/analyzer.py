"""
Análisis de BPM y tonalidad musical.
Solo usa numpy — sin librosa ni dependencias extra.
"""
import numpy as np

# ── Krumhansl-Schmuckler key profiles ────────────────────────────────────────
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_KEYS  = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim > 1:
        return np.mean(audio, axis=1).astype(np.float32)
    return audio.astype(np.float32)


def detect_bpm(audio: np.ndarray, sr: int) -> float:
    """Devuelve BPM estimado (0 si no se puede calcular)."""
    mono = _to_mono(audio)
    hop  = 512

    n_frames = len(mono) // hop
    if n_frames < 128:
        return 0.0

    # RMS per frame → onset strength (positive flux)
    frames = mono[:n_frames * hop].reshape(n_frames, hop)
    rms    = np.sqrt(np.mean(frames ** 2, axis=1))
    onset  = np.maximum(0.0, np.diff(rms))

    fps     = sr / hop
    min_lag = max(1, int(fps * 60 / 190))   # 190 BPM tope superior
    max_lag = min(len(onset) - 1, int(fps * 60 / 55))  # 55 BPM tope inferior

    if min_lag >= max_lag:
        return 0.0

    # Autocorrelación por FFT (mucho más rápido que np.correlate)
    n_fft = 1
    while n_fft < 2 * len(onset):
        n_fft <<= 1
    f     = np.fft.rfft(onset, n=n_fft)
    acorr = np.fft.irfft(f * np.conj(f))[:len(onset)]
    if acorr[0] > 0:
        acorr /= acorr[0]

    # Mejor pico en rango de BPM válido
    peak  = np.argmax(acorr[min_lag:max_lag]) + min_lag
    bpm   = fps * 60.0 / peak

    # Redondear a 0.5 más cercano
    return round(bpm * 2) / 2


def detect_key(audio: np.ndarray, sr: int) -> str:
    """Devuelve tonalidad musical ('Cmaj', 'Amin', 'F#maj', …)."""
    mono = _to_mono(audio)

    # Segmento central de máx. 25 s (evita intros/outros)
    n    = len(mono)
    dur  = min(sr * 25, n)
    seg  = mono[max(0, n // 2 - dur // 2): max(0, n // 2 - dur // 2) + dur]

    frame_size = 4096
    hop        = 2048
    window     = np.hanning(frame_size).astype(np.float32)

    # Precalcular: frecuencia → pitch class
    freqs = np.fft.rfftfreq(frame_size, 1.0 / sr)
    valid = (freqs >= 65.4) & (freqs <= 4186.0)
    vf    = freqs[valid]
    with np.errstate(divide='ignore', invalid='ignore'):
        midi_f = 69.0 + 12.0 * np.log2(np.where(vf > 0, vf / 440.0, 1e-8))
    pc = np.round(midi_f).astype(int) % 12

    chroma   = np.zeros(12, dtype=np.float64)
    n_frames = 0
    for i in range(0, len(seg) - frame_size, hop):
        spec    = np.abs(np.fft.rfft(seg[i: i + frame_size] * window))
        chroma += np.bincount(pc, weights=spec[valid], minlength=12)
        n_frames += 1

    if n_frames == 0 or chroma.sum() < 1e-8:
        return ''

    chroma /= chroma.sum()

    # Correlación de Pearson con los 24 perfiles (12 mayor + 12 menor)
    best_r, best_key = -np.inf, ''
    for root in range(12):
        for profile, suffix in [(_MAJOR, 'maj'), (_MINOR, 'min')]:
            p = np.roll(profile, root)
            r = float(np.corrcoef(chroma, p)[0, 1])
            if r > best_r:
                best_r, best_key = r, f'{_KEYS[root]}{suffix}'

    return best_key


def analyze_file(path: str) -> tuple[float, str]:
    """
    Decodifica el archivo a 22050 Hz mono y devuelve (bpm, key).
    Usa 22050 Hz para ser más rápido que a 44100 Hz.
    """
    try:
        import miniaudio
        d    = miniaudio.decode_file(
            path,
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=1,
            sample_rate=22050,
        )
        mono = np.frombuffer(d.samples, dtype=np.float32)
        bpm  = detect_bpm(mono, 22050)
        key  = detect_key(mono.reshape(-1, 1), 22050)
        return bpm, key
    except Exception as e:
        print(f'[analyzer] {path}: {e}')
        return 0.0, ''
