"""
Mezcla automática "como un DJ".

1. analyze(): por cada canción, posición de cada beat, BPM, fase de compás
   (dónde cae el "1"), tonalidad, energía por beat, dónde empieza el outro.
   Se guarda en caché (~/.josinodj/beatcache) para no repetirlo.

2. plan(): decide cómo y cuándo pasar de la canción A a la B.
   - BPM compatibles (±7 %, también mitad/doble): BLEND con beatmatching.
     La B se acelera/frena para ir clavada a los golpes de A, entra en un
     compás de frase, se hace el cambio de graves (bass swap) a mitad de la
     mezcla y, cuando A ya ha salido, B vuelve poco a poco a su tempo real.
   - BPM incompatibles (reggaetón ↔ house…): ECHO OUT. A suelta un eco a
     tempo en el último compás mientras se le van los graves, y B entra
     limpia justo en el "1" siguiente.
   - Canciones sin ritmo claro (baladas…): FADE largo con cambio de graves.

3. render(): fabrica offline el trozo mezclado (numpy). El motor solo tiene
   que reproducirlo cuando A llega al punto de inicio y después seguir con B
   desde `resume`.
"""
from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 44100
_HOP = 256          # hop a 22050 Hz → 512 muestras a 44100
_HOP44 = _HOP * 2
_CACHE_DIR = Path.home() / '.josinodj' / 'beatcache'
_CACHE_VER = 5
_lock = threading.Lock()   # librosa/numba no se lleva bien con varios hilos a la vez

# Camelot: tonalidad → (número, letra)
_CAMELOT = {
    'G#min': (1, 'A'), 'Bmaj': (1, 'B'), 'D#min': (2, 'A'), 'F#maj': (2, 'B'),
    'A#min': (3, 'A'), 'C#maj': (3, 'B'), 'Fmin': (4, 'A'), 'G#maj': (4, 'B'),
    'Cmin': (5, 'A'), 'D#maj': (5, 'B'), 'Gmin': (6, 'A'), 'A#maj': (6, 'B'),
    'Dmin': (7, 'A'), 'Fmaj': (7, 'B'), 'Amin': (8, 'A'), 'Cmaj': (8, 'B'),
    'Emin': (9, 'A'), 'Gmaj': (9, 'B'), 'Bmin': (10, 'A'), 'Dmaj': (10, 'B'),
    'F#min': (11, 'A'), 'Amaj': (11, 'B'), 'C#min': (12, 'A'), 'Emaj': (12, 'B'),
}


# ══════════════════════════════════════════════════════════════════════════
#  ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class TrackInfo:
    beats: np.ndarray        # posiciones de beat en muestras (44100)
    low_env: np.ndarray      # envolvente de ataques en graves (bombo), 1 valor cada _HOP44
    energy: np.ndarray       # RMS por beat
    phase: int               # índice de beat (mod 4) que es el "1" del compás
    key: str
    bpm: float
    salience: float          # 0..1 — lo claro que es el ritmo
    outro_beat: int          # beat donde empieza el outro (bajada final de energía)
    entry_beat: int          # primer "1" con música (para entrar)
    last_beat: int           # último beat utilizable antes del final real
    phrase: int = 0          # índice de beat (mod 16) donde empiezan las frases


def _cache_path(path: str) -> Path | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    h = hashlib.sha1(f'{path}|{st.st_size}|{int(st.st_mtime)}|{_CACHE_VER}'.encode('utf-8')).hexdigest()
    return _CACHE_DIR / f'{h}.npz'


def analyze(data: np.ndarray, path: str | None = None) -> TrackInfo | None:
    cp = _cache_path(path) if path else None
    if cp and cp.exists():
        try:
            z = np.load(cp, allow_pickle=False)
            return TrackInfo(
                beats=z['beats'], low_env=z['low_env'], energy=z['energy'],
                phase=int(z['phase']), key=str(z['key']), bpm=float(z['bpm']),
                salience=float(z['salience']), outro_beat=int(z['outro_beat']),
                entry_beat=int(z['entry_beat']), last_beat=int(z['last_beat']),
                phrase=int(z['phrase']))
        except Exception:
            pass
    try:
        info = _analyze(data)
    except Exception as e:
        print(f'[dj] análisis falló: {e}')
        return None
    if info and cp:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            np.savez(cp, beats=info.beats, low_env=info.low_env, energy=info.energy,
                     phase=info.phase, key=info.key, bpm=info.bpm, salience=info.salience,
                     outro_beat=info.outro_beat, entry_beat=info.entry_beat,
                     last_beat=info.last_beat, phrase=info.phrase)
        except Exception:
            pass
    return info


def _analyze(data: np.ndarray) -> TrackInfo | None:
    import librosa
    mono = data.mean(axis=1) if data.ndim > 1 else data
    n2 = len(mono) // 2 * 2
    y = mono[:n2].reshape(-1, 2).mean(axis=1).astype(np.float32)   # 22050 Hz
    if len(y) < 22050 * 10:
        return None
    with _lock:
        env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=_HOP)
        low_env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=_HOP,
                                               fmax=180, n_mels=24)
        hi_env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=_HOP,
                                              fmin=1500, n_mels=32)
        # Candidatos de tempo (evita errores de doble/mitad/"casi"): nos quedamos
        # con la rejilla donde el bombo cae más claramente en el beat.
        tg = librosa.feature.tempo(onset_envelope=env, sr=22050, hop_length=_HOP,
                                   aggregate=None, max_tempo=200)
        base = float(np.median(tg)) if len(tg) else 120.0
        cands = sorted({round(c, 1) for c in (base, base * 2, base / 2)
                        if 70 <= c <= 180})
        le = low_env.astype(np.float32)
        best = None
        for c in cands or [120.0]:
            _, bf = librosa.beat.beat_track(onset_envelope=env, sr=22050, hop_length=_HOP,
                                            start_bpm=c, tightness=400, trim=False)
            bf = np.asarray(bf)
            if len(bf) < 32:
                continue
            ibi = np.diff(bf)
            half = np.clip(bf[:-1] + ibi // 2, 0, len(le) - 1)
            score = (le[np.clip(bf[:-1], 0, len(le) - 1)].mean() + env[np.clip(bf[:-1], 0, len(env) - 1)].mean())                 / (le[half].mean() + env[half].mean() + 1e-6)
            # A igualdad, preferir el rango típico de baile (85–150)
            bpm_c = 60.0 * 22050 / _HOP / float(np.median(ibi))
            score *= 1.0 if 88 <= bpm_c <= 160 else 0.8
            if best is None or score > best[0]:
                best = (score, bf)
    if best is None:
        return None
    ratio, fr = best
    fr = fr.copy()

    # Refinar cada beat al pico de graves cercano (±2 frames) → menos jitter
    for i, f in enumerate(fr):
        a, b = max(0, f - 2), min(len(le), f + 3)
        if b > a:
            fr[i] = a + int(np.argmax(le[a:b]))
    beats = fr.astype(np.int64) * _HOP44

    ibi = np.diff(beats)
    med = float(np.median(ibi))
    bpm = 60.0 * SR / med

    # Energía por beat
    m = mono.astype(np.float32)
    energy = np.array([float(np.sqrt(np.mean(m[beats[i]:beats[i + 1]] ** 2) + 1e-12))
                       for i in range(len(beats) - 1)] + [0.0], dtype=np.float32)

    # Saliencia global
    sal = float(np.clip((ratio - 1.0) / 1.2, 0, 1))
    if float(np.std(ibi) / med) > 0.12:
        sal *= 0.4

    # Fase de compás.
    #  · Caja/palmas en 2 y 4 → decide la pareja (1,3) frente a (2,4).
    #  · Cambios de sección caen en el "1" → decide 1 frente a 3.
    he = hi_env.astype(np.float32)
    hb = he[np.clip(fr, 0, len(he) - 1)]
    lb = le[np.clip(fr, 0, len(le) - 1)]
    e = energy
    nov = np.zeros(len(e))
    for i in range(4, len(e) - 4):
        nov[i] = abs(e[i:i + 4].mean() - e[i - 4:i].mean())
    n = len(e) // 4 * 4
    sc = []
    for p in range(4):
        idx = np.arange(p, n - 3, 4)
        back = (hb[idx + 1].mean() + hb[idx + 3].mean()) - (hb[idx].mean() + hb[idx + 2].mean())
        kick = lb[idx].mean() - lb[idx + 1].mean()
        sc.append((back / (hb.mean() + 1e-6), kick / (lb.mean() + 1e-6), nov[idx].sum() / (nov.sum() + 1e-9)))
    sc = np.array(sc)
    pair_score = sc[:, 0] + 0.5 * sc[:, 1]
    pair = 0 if pair_score[[0, 2]].sum() >= pair_score[[1, 3]].sum() else 1
    phase = pair if sc[pair, 2] + 0.3 * sc[pair, 1] >= sc[pair + 2, 2] + 0.3 * sc[pair + 2, 1] else pair + 2

    # Frase (16 beats): el desfase (0/4/8/12) con más cambios de sección
    ph = []
    for q in (0, 4, 8, 12):
        idx = np.arange(phase + q, len(nov), 16)
        ph.append(nov[idx].sum())
    phrase = (phase + 4 * int(np.argmax(ph))) % 16

    # Energía suavizada (8 beats) para intro/outro
    k = 8
    sm = np.convolve(e, np.ones(k) / k, mode='same')
    med_e = float(np.median(sm[sm > 0])) if np.any(sm > 0) else 0.0
    last = len(beats) - 1
    while last > 0 and e[last - 1] < 0.08 * med_e:
        last -= 1
    last = max(16, last - 1)
    i = last
    while i > len(e) * 0.5 and sm[i] < 0.62 * med_e:
        i -= 1
    outro = i if i < last - 8 else last
    # Entrada: primer "1" con música; si la frase empieza poco después, mejor ahí
    entry = 0
    for j in range(len(e)):
        if e[j] > 0.15 * med_e:
            entry = j
            break
    while (entry - phase) % 4 != 0 and entry > 0:
        entry -= 1
    while (entry - phase) % 4 != 0:
        entry += 1

    from ..utils.analyzer import detect_key
    try:
        key = detect_key(data, SR)
    except Exception:
        key = ''

    return TrackInfo(beats=beats, low_env=le, energy=energy, phase=phase, key=key,
                     bpm=bpm, salience=sal, outro_beat=int(outro), entry_beat=int(entry),
                     last_beat=int(last), phrase=int(phrase))


def key_distance(a: str, b: str) -> int:
    """Distancia en la rueda Camelot (0 = misma, 1 = compatible, >1 choca)."""
    ca, cb = _CAMELOT.get(a), _CAMELOT.get(b)
    if not ca or not cb:
        return 1
    d = abs(ca[0] - cb[0])
    d = min(d, 12 - d)
    if ca[1] != cb[1]:
        d += 1 if d == 0 else 2
    return d


# ══════════════════════════════════════════════════════════════════════════
#  PLAN
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class Plan:
    kind: str           # 'blend' | 'echo' | 'fade'
    start: int          # muestra en A donde empieza la mezcla
    a_period: float     # muestras por beat de A en la zona de mezcla
    b_start: float      # posición en B que suena en `start` (o donde entra B)
    b_period: float     # muestras por beat de B
    beats: int          # duración de la mezcla en beats de A
    rate: float         # velocidad de B durante el blend (1 = natural)
    b_delay: int = 0    # (echo/fade) muestras desde `start` hasta que entra B


def _grid(info: TrackInfo, b0: int, n: int) -> tuple[float, float]:
    """Ajuste lineal de la rejilla de beats [b0, b0+n] → (pos beat b0, periodo)."""
    b1 = min(len(info.beats) - 1, b0 + n)
    b0 = max(0, min(b0, b1 - 2))
    idx = np.arange(b0, b1 + 1)
    pos = info.beats[idx].astype(np.float64)
    slope, icpt = np.polyfit(idx - b0, pos, 1)
    return float(icpt), float(slope)


def _local_salience(info: TrackInfo, start: float, period: float, n: int) -> float:
    le = info.low_env
    on = [le[int((start + k * period) // _HOP44)] for k in range(n)
          if 0 <= int((start + k * period) // _HOP44) < len(le)]
    off = [le[int((start + (k + .5) * period) // _HOP44)] for k in range(n)
           if 0 <= int((start + (k + .5) * period) // _HOP44) < len(le)]
    if not on or not off:
        return 0.0
    return float(np.mean(on) / (np.mean(off) + 1e-6))


def _refine(info: TrackInfo, start: float, period: float, n: int) -> tuple[float, float]:
    """Como un DJ con los cascos: busca el desfase (±½ beat) que hace caer los
    bombos justo en la rejilla. Devuelve (inicio_corregido, claridad)."""
    le = info.low_env
    x = np.arange(len(le)) * _HOP44 + _HOP44 / 2
    ks = np.arange(n)
    best = (start, 0.0)
    for d in np.arange(-period / 2, period / 2, _HOP44 / 4):
        on = np.interp(start + d + ks * period, x, le).mean()
        off = np.interp(start + d + (ks + .5) * period, x, le).mean()
        r = on / (off + 1e-6)
        if r > best[1]:
            best = (start + d, r)
    return best


def plan(a: TrackInfo, b: TrackInfo, a_len: int, b_len: int,
         earliest: int, max_blend_s: float, quick: bool = False,
         allow_blend: bool = True) -> Plan | None:
    """earliest: primera muestra de A donde se puede empezar (posición actual + margen)."""
    if a is None or b is None:
        return None
    nb = len(a.beats)
    first_ok = int(np.searchsorted(a.beats, earliest))
    if first_ok >= nb - 4:
        return None

    # ── ¿BPM compatibles? (también mitad/doble) ─────────────────────────
    best = None
    for mult in (1.0, 2.0, 0.5):
        r = (b.bpm * mult) / a.bpm          # >1: B más rápida
        if best is None or abs(r - 1) < abs(best[1] - 1):
            best = (mult, r)
    mult, r = best
    tol = 0.10 if _HAVE_RB else 0.07          # con key-lock se puede estirar más sin que se note
    beatable = allow_blend and abs(r - 1) <= tol and a.salience > 0.1 and b.salience > 0.1
    kd = key_distance(a.key, b.key)

    def aligned(k, step):
        ref = a.phrase if step == 16 else a.phase
        return (k - ref) % step == 0

    def pick_start(n_beats: int) -> int | None:
        hi = a.last_beat - n_beats
        if hi < first_ok:
            return None
        if quick:
            for k in range(first_ok, hi + 1):
                if aligned(k, 4):
                    return k
            return None
        target = min(max(a.outro_beat, first_ok), hi)
        cands = [k for k in range(first_ok, hi + 1) if aligned(k, 16)]
        cands = [k for k in cands if abs(k - target) <= 16] or \
                [k for k in range(first_ok, hi + 1) if aligned(k, 4)]
        if not cands:
            return None
        return min(cands, key=lambda k: (abs(k - target), -k))

    if beatable:
        a_per_s = 60.0 / a.bpm
        if quick:
            options = (8,)
        else:
            # Mezclas cortas: 16 tiempos (~7-8 s) como mucho, 8 si va rápido
            options = [n for n in (16, 8) if n * a_per_s <= min(max(max_blend_s, 6.0), 9.0)] or [8]
        if kd > 1:
            options = [max(8, n // 2) for n in options]
        for n in options:
            k0 = pick_start(n)
            if k0 is None:
                continue
            a0, ap = _grid(a, k0, n)
            # Entrada de B: su primer "1"; rejilla de B ajustada en una ventana amplia
            j0 = b.entry_beat
            nb_beats = int(np.ceil(n / mult)) + 16
            b0, bp = _grid(b, j0, nb_beats)
            bp_eff = bp / mult                       # muestras de B por beat de A
            rate = bp_eff / ap
            if abs(rate - 1) > tol + 0.01:
                continue
            # Afinar la fase de A y de B sobre el bombo real
            a0r, sa = _refine(a, a0, ap, n)
            b0, sb = _refine(b, b0, bp_eff, n + 16)
            while b0 < 0:
                b0 += bp_eff * 4          # un compás más tarde, misma fase
            if sa < 1.15 or sb < 1.15:
                beatable = False
                break
            a0 = max(float(earliest), a0r)
            if b0 + (n + 16) * bp_eff >= b_len:
                continue
            return Plan('blend', int(round(a0)), ap, b0, bp_eff, n, rate)

    # ── Echo out (ritmo claro en A) o fade ──────────────────────────────
    if a.salience > 0.1:
        k0 = pick_start(4)
        if k0 is not None:
            a0, ap = _grid(a, k0, 4)
            b0, bp = _grid(b, b.entry_beat, 4)
            return Plan('echo', int(round(a0)), ap, b0, bp, 4, 1.0, b_delay=int(round(4 * ap)))

    fade_s = 3.0 if quick else 5.0
    fade = int(fade_s * SR)
    if quick:
        start = max(earliest, 0)
    else:
        start = int(a.beats[min(a.outro_beat, nb - 1)])
        end = int(a.beats[min(a.last_beat, nb - 1)])
        start = min(start, end - fade)
        start = max(start, earliest)
    if start + fade >= a_len:
        start = a_len - fade - 1
    if start < earliest:
        return None
    b0 = float(b.beats[b.entry_beat]) if len(b.beats) else 0.0
    return Plan('fade', start, fade / 16, b0, fade / 16, 16, 1.0)


# ══════════════════════════════════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════════════════════════════════

def _split(x: np.ndarray, fc: float = 180.0):
    """Divide en graves / resto (fase cero; graves + resto = original)."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, fc, btype='low', fs=SR, output='sos')
    low = sosfiltfilt(sos, x, axis=0).astype(np.float32)
    return low, (x - low).astype(np.float32)


def _ramp(t: np.ndarray, t0: float, t1: float) -> np.ndarray:
    """0 antes de t0, 1 después de t1, curva suave en medio."""
    if t1 <= t0:
        return (t >= t0).astype(np.float32)
    x = np.clip((t - t0) / (t1 - t0), 0, 1)
    return (x * x * (3 - 2 * x)).astype(np.float32)


def _soft_limit(x: np.ndarray, thr: float = 0.92) -> np.ndarray:
    ax = np.abs(x)
    over = ax > thr
    if np.any(over):
        x = x.copy()
        x[over] = np.sign(x[over]) * (thr + (1 - thr) * np.tanh((ax[over] - thr) / (1 - thr)))
    return x


def _resample_path(b: np.ndarray, pos: np.ndarray) -> np.ndarray:
    pos = np.clip(pos, 0, len(b) - 2)
    i = pos.astype(np.int64)
    f = (pos - i).astype(np.float32)[:, None]
    return b[i] * (1 - f) + b[i + 1] * f


def render(a: np.ndarray, b: np.ndarray, ga: float, gb: float, p: Plan):
    """Devuelve (buffer_mezclado, posición_en_B_para_seguir)."""
    if p.kind == 'blend':
        return _render_blend(a, b, ga, gb, p)
    if p.kind == 'echo':
        return _render_echo(a, b, ga, gb, p)
    return _render_fade(a, b, ga, gb, p)


def _render_blend(a, b, ga, gb, p: Plan):
    N = p.beats
    R = 16 if abs(p.rate - 1) > 0.003 else 0         # beats para volver al tempo real de B
    # Duración en salida de cada beat de B: primero clavado a A, luego vuelve a su tempo
    per = [p.a_period] * N
    for k in range(R):
        x = (k + 1) / R
        rk = p.rate + (1 - p.rate) * (x * x * (3 - 2 * x))
        per.append(p.b_period / rk)
    out_m = np.concatenate([[0.0], np.cumsum(per)])
    in_m = p.b_start + np.arange(N + R + 1) * p.b_period
    total = int(round(out_m[-1]))

    if R == 0:
        s0 = int(round(p.b_start))
        bseg = np.zeros((total, 2), dtype=np.float32)
        bn = max(0, min(total, len(b) - s0))
        bseg[:bn] = b[s0:s0 + bn]
    else:
        bseg = _stretch_marks(b, in_m, out_m)
    bseg = bseg * gb
    resume = int(round(in_m[-1]))

    aseg = np.zeros((total, 2), dtype=np.float32)
    an = max(0, min(total, len(a) - p.start))
    aseg[:an] = a[p.start:p.start + an] * ga

    a_lo, a_hi = _split(aseg)
    b_lo, b_hi = _split(bseg)

    t = np.arange(total, dtype=np.float64)
    beat = t / p.a_period
    half = N / 2
    sw = 0.125                                    # bass swap en 1/8 de beat, en el "1"
    in_hi = np.sin(np.pi / 2 * _ramp(beat, 0, half)) ** 2
    in_lo = _ramp(beat, half, half + sw)
    out_lo = 1 - in_lo
    out_hi = np.cos(np.pi / 2 * _ramp(beat, half, N)) ** 2
    # La entrante algo más baja de medios/agudos al principio (hueco para la saliente)
    in_hi = in_hi * (0.8 + 0.2 * _ramp(beat, half - 2, half))

    mix = (a_lo * out_lo[:, None] + a_hi * out_hi[:, None]
           + b_lo * in_lo[:, None] + b_hi * in_hi[:, None])
    _render_blend.last_align = _grid_align(b_lo, p.a_period, N)
    return _soft_limit(mix.astype(np.float32)), resume


def _grid_align(x: np.ndarray, period: float, n: int) -> float:
    """Bombos de x en la rejilla (period, 2·period…) frente a medio beat.
    Si en el tramo apenas hay graves (intro sin batería) no se puede juzgar → 9."""
    import librosa
    y = x.mean(axis=1)
    y = y[:len(y) // 2 * 2].reshape(-1, 2).mean(axis=1).astype(np.float32)
    if float(np.sqrt(np.mean(y ** 2))) < 0.01:
        return 9.0
    with _lock:
        le = librosa.onset.onset_strength(y=y, sr=22050, hop_length=_HOP, fmax=180, n_mels=24)
    xs = np.arange(len(le)) * _HOP44
    ks = np.arange(1, n)
    on = np.interp(ks * period, xs, le).mean()
    off = np.interp((ks + .5) * period, xs, le).mean()
    return float(on / (off + 1e-6))


def build(a_data, b_data, ga, gb, ia: TrackInfo, ib: TrackInfo, earliest: int,
          max_blend_s: float, quick: bool = False):
    """Planifica + renderiza + comprueba. Devuelve (plan, buffer, resume) o None."""
    p = plan(ia, ib, len(a_data), len(b_data), earliest, max_blend_s, quick)
    if p is None:
        return None
    buf, res = render(a_data, b_data, ga, gb, p)
    if p.kind == 'blend' and getattr(_render_blend, 'last_align', 0) < 1.3:
        print(f'[dj] beatmatch dudoso ({_render_blend.last_align:.2f}) → eco')
        p2 = plan(ia, ib, len(a_data), len(b_data), earliest, max_blend_s, quick, allow_blend=False)
        if p2 is None:
            return None
        p = p2
        buf, res = render(a_data, b_data, ga, gb, p)
    return p, buf, res


# ── Time-stretch con key-lock (Rubber Band R3, el mismo motor que usan los
#    programas profesionales). Sin la librería: resampleo tipo vinilo. ──────

try:
    import pylibrb as _rb
    _HAVE_RB = True
except Exception:
    _rb = None
    _HAVE_RB = False

_RB_CHUNK = 65536


def _stretch_fixed(x: np.ndarray, ratio: float) -> np.ndarray:
    n = len(x)
    if abs(ratio - 1) < 1e-5 or n == 0:
        return x.astype(np.float32, copy=True)
    s = _rb.RubberBandStretcher(SR, 2, _rb.Option.PROCESS_OFFLINE | _rb.Option.ENGINE_FINER,
                                initial_time_ratio=ratio)
    s.set_expected_input_duration(n)
    s.set_max_process_size(_RB_CHUNK)
    arr = np.ascontiguousarray(x.T.astype(np.float32))
    for i in range(0, n, _RB_CHUNK):
        s.study(arr[:, i:i + _RB_CHUNK], final=i + _RB_CHUNK >= n)
    outs = []
    for i in range(0, n, _RB_CHUNK):
        s.process(arr[:, i:i + _RB_CHUNK], final=i + _RB_CHUNK >= n)
        while (av := s.available()) > 0:
            outs.append(s.retrieve(av))
    while (av := s.available()) > 0:
        outs.append(s.retrieve(av))
    return np.concatenate(outs, axis=1).T if outs else np.zeros((0, 2), np.float32)


def _stretch_marks(b: np.ndarray, in_m: np.ndarray, out_m: np.ndarray) -> np.ndarray:
    """Estira b para que la muestra in_m[k] caiga exactamente en out_m[k].
    Se procesa beat a beat (con contexto) y se une con fundidos de 4 ms
    puestos un pelín antes de cada golpe → error < 1 ms en todo el tramo."""
    total = int(round(out_m[-1]))
    if not _HAVE_RB:
        t = np.arange(total, dtype=np.float64)
        return _resample_path(b, np.interp(t, out_m, in_m))
    pad = int(0.3 * SR)
    xf = int(0.004 * SR)
    # Cortes 1/16 de beat antes de cada golpe
    lead_in = np.diff(in_m) / 16
    lead_out = np.diff(out_m) / 16
    cin = in_m.copy()
    cout = out_m.copy()
    cin[1:-1] -= lead_in[1:]
    cout[1:-1] -= lead_out[1:]
    res = np.zeros((total + xf, 2), dtype=np.float32)
    for k in range(len(cin) - 1):
        i0, i1 = cin[k], cin[k + 1]
        r = (cout[k + 1] - cout[k]) / (i1 - i0)
        a0 = max(0, int(i0) - pad)
        a1 = min(len(b), int(i1) + pad)
        if a1 - a0 < 64:
            break
        y = _stretch_fixed(b[a0:a1], r)
        o0, o1 = int(round(cout[k])), int(round(cout[k + 1]))
        src0 = int(round((i0 - a0) * r))
        pre = xf if k > 0 else 0
        s0 = src0 - pre
        nseg = (o1 - o0) + pre
        seg = y[max(0, s0):max(0, s0) + nseg]
        if len(seg) < nseg:
            seg = np.vstack([seg, np.zeros((nseg - len(seg), 2), np.float32)])
        if pre:
            f = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
            res[o0 - xf:o0] = res[o0 - xf:o0] * (1 - f) + seg[:xf] * f
            res[o0:o1] = seg[xf:]
        else:
            res[o0:o1] = seg
    return res[:total]


def _render_echo(a, b, ga, gb, p: Plan):
    bar = int(round(4 * p.a_period))
    beat = p.a_period
    tail_beats = 8
    T = int(round(tail_beats * beat))
    L = bar + T
    t = np.arange(L, dtype=np.float64)
    bt = t / beat

    aseg = np.zeros((L, 2), dtype=np.float32)
    an = max(0, min(bar, len(a) - p.start))
    aseg[:an] = a[p.start:p.start + an] * ga
    a_lo, a_hi = _split(aseg)
    # Durante el compás de salida se le van los graves
    lo_env = 1 - _ramp(bt, 1.0, 3.5)
    dry = a_lo * lo_env[:, None] + a_hi
    dry[bar:] = 0
    # Eco a tempo (medio beat) sobre el último beat, sin graves
    src = np.zeros_like(aseg)
    s0 = int(round(3 * beat))
    src[s0:bar] = a_hi[s0:bar]
    d = int(round(beat / 2))
    echo = np.zeros_like(aseg)
    g = 0.6
    k = 1
    while g > 0.03 and k * d < L:
        sh = k * d
        echo[sh:] += src[:L - sh] * g
        g *= 0.6
        k += 1
    echo[:bar] *= 0.5

    # B entra limpia en el "1" siguiente, a su tempo
    bstart = max(0, int(round(p.b_start)))
    bseg = np.zeros((L, 2), dtype=np.float32)
    bn = max(0, min(T, len(b) - bstart))
    bseg[bar:bar + bn] = b[bstart:bstart + bn] * gb
    fade_in = _ramp(t, bar, bar + 0.02 * SR)
    mix = dry + echo + bseg * fade_in[:, None]
    return _soft_limit(mix.astype(np.float32)), bstart + T


def _render_fade(a, b, ga, gb, p: Plan):
    F = int(round(p.beats * p.a_period))
    t = np.arange(F, dtype=np.float64)
    aseg = np.zeros((F, 2), dtype=np.float32)
    an = max(0, min(F, len(a) - p.start))
    aseg[:an] = a[p.start:p.start + an] * ga
    bstart = max(0, int(round(p.b_start)))
    bseg = np.zeros((F, 2), dtype=np.float32)
    bn = max(0, min(F, len(b) - bstart))
    bseg[:bn] = b[bstart:bstart + bn] * gb
    a_lo, a_hi = _split(aseg)
    b_lo, b_hi = _split(bseg)
    x = t / F
    out_hi = np.cos(np.pi / 2 * _ramp(x, 0.0, 1.0)) ** 2
    in_hi = np.sin(np.pi / 2 * _ramp(x, 0.0, 0.8)) ** 2
    in_lo = _ramp(x, 0.45, 0.6)
    out_lo = 1 - in_lo
    mix = (a_lo * out_lo[:, None] + a_hi * out_hi[:, None]
           + b_lo * in_lo[:, None] + b_hi * in_hi[:, None])
    return _soft_limit(mix.astype(np.float32)), bstart + F
