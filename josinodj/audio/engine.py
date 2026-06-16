import threading
import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer

_SPEC_SIZE = 4096  # circular buffer for real-time spectrum


class AudioEngine(QObject):
    position_changed   = Signal(float)
    duration_changed   = Signal(float)
    playback_started   = Signal()
    playback_paused    = Signal()
    playback_stopped   = Signal()
    track_switched     = Signal()   # crossfade completed — do NOT call play_file again
    track_ended        = Signal()   # natural end — safe to play next
    waveform_ready      = Signal(object)   # peaks np.ndarray current track (bg computed)
    next_waveform_ready = Signal(object)   # peaks np.ndarray for next track
    decode_error        = Signal(str)           # human-readable error when file can't be decoded

    def __init__(self):
        super().__init__()
        self._sr = 44100
        self._ch = 2

        self._master_volume = 0.8
        self._crossfade_duration = 4.0
        self._cf_samples = int(self._crossfade_duration * self._sr)
        self._cf_samples_actual = self._cf_samples  # actual duration for current CF (never mutates _cf_samples)

        # Normalización de volumen
        self._normalize     = True
        self._current_gain  = 1.0
        self._next_gain     = 1.0

        from .equalizer import Equalizer
        self._eq = Equalizer(self._sr, self._ch)

        self._current: np.ndarray | None = None
        self._current_pos = 0
        self._current_len = 0

        self._current_effective_end = 0  # outro point in samples
        self._next_intro  = 0             # intro offset for next track
        self._next_effective_end = 0      # outro point for next track
        self._switch_peaks = None         # cached peaks from preload → emitted at track switch
        self._preload_gen = 0             # incremented on every play_file/preload to cancel stale workers

        self._next: np.ndarray | None = None
        self._next_pos = 0
        self._next_loaded = False
        self._cf_progress = 0
        self._crossfading = False

        self._playing = False
        self._paused = False

        self._master_stream = None
        self._master_device = None

        self._pending_switch = False
        self._pending_end   = False

        # Spectrum buffer — written by audio callback, read by main thread
        self._spec_buf = np.zeros(_SPEC_SIZE, dtype=np.float32)
        self._spec_idx = 0

        self._ticker = QTimer()
        self._ticker.timeout.connect(self._tick)
        self._ticker.start(50)

    # ── decode ────────────────────────────────────────────────────────────

    def _decode(self, path: str) -> np.ndarray:
        import os
        last_err = None

        # ── Attempt 1: miniaudio, force 44100 Hz stereo ───────────────────
        try:
            import miniaudio
            d = miniaudio.decode_file(
                path,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=self._ch,
                sample_rate=self._sr,
            )
            arr = np.frombuffer(d.samples, dtype=np.float32).copy()
            return np.ascontiguousarray(arr.reshape(-1, self._ch))
        except Exception as e:
            last_err = e

        # ── Attempt 2: miniaudio, native rate then resample ───────────────
        try:
            import miniaudio
            d = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32)
            arr = np.frombuffer(d.samples, dtype=np.float32).copy().reshape(-1, d.nchannels)
            arr = self._to_stereo(arr, d.nchannels)
            arr = self._resample(arr, d.sample_rate)
            return np.ascontiguousarray(arr)
        except Exception as e:
            last_err = e

        # ── Attempt 3: soundfile (libsndfile ≥1.1 includes MP3) ──────────
        try:
            import soundfile as sf
            arr, sr = sf.read(path, dtype='float32', always_2d=True)
            arr = self._to_stereo(arr, arr.shape[1])
            arr = self._resample(arr, sr)
            return np.ascontiguousarray(arr)
        except Exception as e:
            last_err = e

        # ── All failed ────────────────────────────────────────────────────
        raise RuntimeError(
            f'No se pudo decodificar:\n"{os.path.basename(path)}"\n\n'
            f'Causa: {last_err}\n\n'
            f'Solución: instala FFmpeg y añade su carpeta al PATH.\n'
            f'Descarga: https://ffmpeg.org/download.html\n'
            f'Una vez instalado reinicia JOSINODJ.'
        )

    def _to_stereo(self, arr: np.ndarray, ch: int) -> np.ndarray:
        if ch == 1:
            return np.column_stack([arr, arr])
        if ch > 2:
            return arr[:, :2]
        return arr

    def _resample(self, arr: np.ndarray, src_sr: int) -> np.ndarray:
        if src_sr == self._sr:
            return arr.astype(np.float32)
        ratio = self._sr / src_sr
        new_len = int(len(arr) * ratio)
        idx = np.linspace(0, len(arr) - 1, new_len)
        return np.column_stack([
            np.interp(idx, np.arange(len(arr)), arr[:, 0]),
            np.interp(idx, np.arange(len(arr)), arr[:, 1]),
        ]).astype(np.float32)

    @staticmethod
    def _detect_intro(data: np.ndarray, sr: int) -> int:
        """Devuelve el offset en samples donde empieza realmente la música."""
        mono = np.mean(data, axis=1) if data.ndim > 1 else data.flatten()
        win = max(1, sr // 20)  # ventanas de 50ms
        n = len(mono) // win
        if n < 4:
            return 0
        blocks = mono[:n * win].reshape(n, win)
        rms = np.sqrt(np.mean(blocks ** 2, axis=1))
        thr = rms.max() * 0.02
        for i in range(n - 1):
            if rms[i] > thr and rms[i + 1] > thr:
                return max(0, (i - 1) * win)
        return 0

    @staticmethod
    def _detect_outro(data: np.ndarray, sr: int) -> int:
        """Devuelve el offset en samples donde la música termina realmente."""
        mono = np.mean(data, axis=1) if data.ndim > 1 else data.flatten()
        win = max(1, sr // 20)  # ventanas de 50ms
        n = len(mono) // win
        if n < 4:
            return len(data)
        blocks = mono[:n * win].reshape(n, win)
        rms = np.sqrt(np.mean(blocks ** 2, axis=1))
        thr = rms.max() * 0.01
        for i in range(n - 1, -1, -1):
            if rms[i] > thr:
                return min(len(data), (i + 3) * win)
        return len(data)

    @staticmethod
    def _compute_peaks(data: np.ndarray, n: int = 500) -> np.ndarray:
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

    def _compute_gain(self, data: np.ndarray) -> float:
        """
        Calcula la ganancia para normalizar el volumen de un track.
        Target: -16 dBFS RMS. Usa percentil 75 de bloques de 250ms
        (ignora silencios y partes muy quietas).
        """
        if not self._normalize:
            return 1.0
        mono = np.mean(data, axis=1) if data.ndim > 1 else data.flatten()
        chunk = self._sr // 4  # 250 ms
        n = len(mono) // chunk
        if n >= 4:
            blocks = mono[:n * chunk].reshape(n, chunk)
            rms_vals = np.sqrt(np.mean(blocks ** 2, axis=1))
            active = rms_vals[rms_vals > 0.002]   # ignorar silencio
            rms = float(np.percentile(active, 75)) if len(active) > 0 else 1e-8
        else:
            rms = float(np.sqrt(np.mean(mono ** 2)))
        if rms < 1e-8:
            return 1.0
        target = 10 ** (-16.0 / 20.0)   # ≈ 0.158 — similar a Spotify/YouTube
        gain = target / rms
        return float(np.clip(gain, 0.15, 5.0))  # -16dB … +14dB máximo

    # ── audio callback ────────────────────────────────────────────────────

    def _master_cb(self, outdata, frames, time_info, status):
        if not self._playing or self._paused or self._current is None:
            outdata[:] = 0
            self._feed_spec(outdata[:, 0] if outdata.ndim > 1 else outdata.flatten())
            return

        remaining = self._current_len - self._current_pos

        if self._crossfading and self._next is not None:
            next_rem = len(self._next) - self._next_pos
            read = min(frames, remaining, next_rem)

            if read > 0 and self._cf_samples_actual > 0:
                t0 = self._cf_progress / self._cf_samples_actual
                t1 = min(1.0, (self._cf_progress + read) / self._cf_samples_actual)
                t  = np.linspace(t0, t1, read, dtype=np.float32)
                fo = (np.cos(t * (np.pi / 2)) ** 2).reshape(-1, 1)
                fi = (np.sin(t * (np.pi / 2)) ** 2).reshape(-1, 1)
                a  = self._current[self._current_pos: self._current_pos + read] * self._current_gain
                b  = self._next[self._next_pos: self._next_pos + read] * self._next_gain
                outdata[:read] = np.clip((a * fo + b * fi) * self._master_volume, -1.0, 1.0)
                if read < frames:
                    outdata[read:] = 0
                self._current_pos += read
                self._next_pos    += read
                self._cf_progress += read

                done = (self._cf_progress >= self._cf_samples_actual
                        or self._current_pos >= self._current_len)
                if done:
                    self._current      = self._next
                    self._current_pos  = self._next_pos
                    self._current_len  = len(self._current)
                    self._current_effective_end = (
                        self._next_effective_end if self._next_effective_end > 0
                        else len(self._current)
                    )
                    self._next               = None
                    self._next_pos           = 0
                    self._next_intro         = 0
                    self._next_effective_end = 0
                    self._crossfading        = False
                    self._cf_progress        = 0
                    self._next_loaded        = False
                    self._current_gain       = self._next_gain
                    self._next_gain          = 1.0
                    self._pending_switch     = True
            else:
                # Current track ran out (or cf_samples=0) → switch immediately to next
                self._current      = self._next
                self._current_pos  = self._next_pos
                self._current_len  = len(self._current)
                self._current_effective_end = (
                    self._next_effective_end if self._next_effective_end > 0
                    else len(self._current)
                )
                self._next               = None
                self._next_pos           = 0
                self._next_intro         = 0
                self._next_effective_end = 0
                self._crossfading        = False
                self._cf_progress        = 0
                self._next_loaded        = False
                self._current_gain       = self._next_gain
                self._next_gain          = 1.0
                self._pending_switch     = True
                # Fill outdata from the new current track
                rem2 = self._current_len - self._current_pos
                rd2  = min(frames, rem2)
                if rd2 > 0:
                    outdata[:rd2] = np.clip(
                        self._current[self._current_pos: self._current_pos + rd2] * self._master_volume,
                        -1.0, 1.0)
                    outdata[rd2:] = 0
                    self._current_pos += rd2
                else:
                    outdata[:] = 0
        else:
            vol = self._master_volume * self._current_gain
            if remaining >= frames:
                outdata[:] = np.clip(
                    self._current[self._current_pos: self._current_pos + frames] * vol,
                    -1.0, 1.0)
                self._current_pos += frames
            elif remaining > 0:
                outdata[:remaining] = np.clip(
                    self._current[self._current_pos:] * vol, -1.0, 1.0)
                outdata[remaining:] = 0
                self._current_pos += remaining
            else:
                outdata[:] = 0
                if not self._next_loaded:
                    self._playing = False
                    self._pending_end = True

            if self._next is not None and not self._crossfading:
                samples_left = self._current_effective_end - self._current_pos
                if samples_left <= self._cf_samples:
                    # Clamp actual CF duration — never touch _cf_samples (user-set value)
                    self._cf_samples_actual = max(1, samples_left)
                    self._crossfading = True
                    self._cf_progress = 0
                    self._next_pos    = self._next_intro  # skip silent intro of next track

        # Aplicar EQ al bloque completo de salida
        if self._playing and not self._paused and not self._eq.is_flat():
            try:
                outdata[:] = self._eq.process(outdata)
            except Exception:
                pass

        # Feed output samples to spectrum buffer
        mono = outdata[:, 0] if outdata.ndim > 1 else outdata.flatten()
        self._feed_spec(mono)

    def _feed_spec(self, mono: np.ndarray):
        n = len(mono)
        end = self._spec_idx + n
        if end <= _SPEC_SIZE:
            self._spec_buf[self._spec_idx:end] = mono
        else:
            first = _SPEC_SIZE - self._spec_idx
            self._spec_buf[self._spec_idx:] = mono[:first]
            self._spec_buf[:n - first] = mono[first:]
        self._spec_idx = (self._spec_idx + n) % _SPEC_SIZE

    def get_spectrum_snapshot(self) -> np.ndarray:
        """Return the last _SPEC_SIZE audio samples (mono, ordered oldest→newest)."""
        idx = self._spec_idx
        buf = self._spec_buf.copy()
        return np.roll(buf, -idx)

    # ── stream ────────────────────────────────────────────────────────────

    def _open_stream(self, callback, device):
        import sounddevice as sd
        kw = dict(samplerate=self._sr, channels=self._ch, dtype='float32',
                  callback=callback, blocksize=1024)
        if device is not None:
            kw['device'] = device
        s = sd.OutputStream(**kw)
        s.start()
        return s

    def _close_stream(self, stream):
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    # ── public API ────────────────────────────────────────────────────────

    def play_file(self, path: str) -> bool:
        # Stop crossfade immediately — decode blocks main thread for 1-5s;
        # without this the old crossfade keeps playing during the entire decode.
        self._crossfading = False
        self._next = None
        self._next_loaded = False
        self._paused = True          # mute old stream while decoding
        self._preload_gen += 1       # invalidate any running preload workers

        try:
            data = self._decode(path)
        except Exception as e:
            self._paused = False
            self.decode_error.emit(str(e))
            return False
        self._close_stream(self._master_stream)
        self._master_stream = None
        self._current      = data
        self._current_pos  = 0
        self._current_len  = len(data)
        self._current_effective_end = len(data)  # provisional, refined in bg
        self._current_gain = self._compute_gain(data)
        self._switch_peaks = None  # clear cached peaks on manual track change
        self._next         = None
        self._next_pos     = 0
        self._next_intro   = 0
        self._next_effective_end = 0
        self._next_gain    = 1.0
        self._next_loaded  = False
        self._crossfading  = False
        self._cf_progress  = 0
        self._pending_switch = False
        self._pending_end    = False
        self._playing = True
        self._paused  = False
        self._master_stream = self._open_stream(self._master_cb, self._master_device)
        self.playback_started.emit()
        self.duration_changed.emit(self._current_len / self._sr)
        def _emit_peaks(d=data, sr=self._sr):
            peaks = self._compute_peaks(d)
            self.waveform_ready.emit(peaks)
            outro = self._detect_outro(d, sr)
            # Guard: only update if still on same track (avoids race after crossfade switch)
            if self._current is d:
                self._current_effective_end = outro
                self.duration_changed.emit(outro / sr)
        threading.Thread(target=_emit_peaks, daemon=True).start()
        return True

    def preload_next_async(self, path: str):
        self._preload_gen += 1
        threading.Thread(target=self._preload_worker, args=(path, self._preload_gen), daemon=True).start()

    def _preload_worker(self, path: str, gen: int):
        try:
            data = self._decode(path)
            # Abort if play_file was called while we were decoding
            if gen != self._preload_gen:
                return
            self._next               = data
            self._next_pos           = 0
            self._next_intro         = 0
            self._next_effective_end = len(data)
            self._next_loaded        = True
            self._next_gain          = self._compute_gain(data)
            peaks = self._compute_peaks(data)
            self._switch_peaks = peaks   # cache for instant emission at track switch
            self.next_waveform_ready.emit(peaks)
            # Refine intro/outro — only update if crossfade hasn't started yet
            intro = self._detect_intro(data, self._sr)
            outro = self._detect_outro(data, self._sr)
            if self._next is data and gen == self._preload_gen:
                self._next_intro         = intro
                self._next_effective_end = outro
        except Exception as e:
            print(f'[engine] preload error: {e}')

    def pause(self):
        self._paused = True
        self.playback_paused.emit()

    def resume(self):
        self._paused = False
        self.playback_started.emit()

    def toggle_pause(self):
        if self._paused:
            self.resume()
        else:
            self.pause()

    def stop(self):
        self._playing = False
        self._close_stream(self._master_stream)
        self._master_stream = None
        self.playback_stopped.emit()

    def seek(self, seconds: float):
        if self._current is not None:
            self._current_pos = max(0, min(int(seconds * self._sr), self._current_len - 1))

    @property
    def position(self) -> float:
        return self._current_pos / self._sr if self._current is not None else 0.0

    @property
    def duration(self) -> float:
        if self._current is None:
            return 0.0
        end = self._current_effective_end if self._current_effective_end > 0 else self._current_len
        return end / self._sr

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def crossfade_duration(self) -> float:
        return self._crossfade_duration

    @crossfade_duration.setter
    def crossfade_duration(self, v: float):
        self._crossfade_duration = max(0.0, min(v, 30.0))
        self._cf_samples = int(self._crossfade_duration * self._sr)
        if not self._crossfading:
            self._cf_samples_actual = self._cf_samples

    @property
    def normalize(self) -> bool:
        return self._normalize

    @normalize.setter
    def normalize(self, v: bool):
        self._normalize = v
        # Recalculate gain for current track immediately
        if self._current is not None:
            self._current_gain = self._compute_gain(self._current)
        if self._next is not None:
            self._next_gain = self._compute_gain(self._next)

    @property
    def master_volume(self) -> float:
        return self._master_volume

    @master_volume.setter
    def master_volume(self, v: float):
        self._master_volume = max(0.0, min(1.0, v))

    def set_master_device(self, device):
        self._master_device = device
        if self._playing:
            pos = self._current_pos
            self._close_stream(self._master_stream)
            self._master_stream = self._open_stream(self._master_cb, device)
            self._current_pos = pos

    @property
    def eq(self):
        return self._eq

    def get_devices(self) -> list[dict]:
        try:
            import sounddevice as sd
            return [{'index': i, 'name': d['name']}
                    for i, d in enumerate(sd.query_devices())
                    if d['max_output_channels'] > 0]
        except Exception:
            return []

    def _tick(self):
        if self._pending_switch:
            self._pending_switch = False
            if self._current is not None:
                end = self._current_effective_end if self._current_effective_end > 0 else self._current_len
                self.duration_changed.emit(end / self._sr)
                if self._switch_peaks is not None:
                    # Emit from main thread — instant, no CPU spike, no position reset race
                    self.waveform_ready.emit(self._switch_peaks)
                    self._switch_peaks = None
                else:
                    def _emit_sw(d=self._current):
                        self.waveform_ready.emit(self._compute_peaks(d))
                    threading.Thread(target=_emit_sw, daemon=True).start()
            self.track_switched.emit()
        if self._pending_end:
            self._pending_end = False
            self.playback_stopped.emit()
            self.track_ended.emit()
        if self._playing and not self._paused:
            self.position_changed.emit(self.position)
