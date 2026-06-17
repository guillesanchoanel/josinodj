"""
Detección de BPM con librosa y escritura del tag en el archivo.
Soporta MP3, FLAC, OGG, OPUS, OGA, M4A, AAC, WAV.
"""
import os


def detect_bpm(path: str) -> float:
    """Devuelve BPM detectado, 0.0 si falla."""
    try:
        import librosa
        # Carga 60 s desde el segundo 30 (evita intros con ritmo irregular)
        offset = 30.0
        y, sr = librosa.load(path, sr=22050, duration=60.0, offset=offset, mono=True)
        if len(y) < sr * 5:
            # Demasiado corta — intentar desde el principio
            y, sr = librosa.load(path, sr=22050, duration=60.0, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        return round(bpm, 1) if bpm > 0 else 0.0
    except Exception:
        return 0.0


def write_bpm(path: str, bpm: float) -> bool:
    """Escribe el BPM en el tag del archivo. Devuelve True si tuvo éxito."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.mp3':
            return _write_mp3(path, bpm)
        elif ext in ('.flac', '.ogg', '.oga', '.opus'):
            return _write_vorbis(path, bpm)
        elif ext in ('.m4a', '.aac', '.mp4'):
            return _write_mp4(path, bpm)
        elif ext == '.wav':
            return _write_wav(path, bpm)
    except Exception:
        pass
    return False


def _write_mp3(path: str, bpm: float) -> bool:
    try:
        from mutagen.easyid3 import EasyID3
        tags = EasyID3(path)
        tags['bpm'] = [str(int(round(bpm)))]
        tags.save()
        return True
    except Exception:
        pass
    try:
        from mutagen.id3 import ID3, TBPM
        tags = ID3(path)
        tags['TBPM'] = TBPM(encoding=3, text=str(int(round(bpm))))
        tags.save()
        return True
    except Exception:
        return False


def _write_vorbis(path: str, bpm: float) -> bool:
    from mutagen import File
    audio = File(path)
    if audio is None or audio.tags is None:
        return False
    audio.tags['bpm'] = [str(int(round(bpm)))]
    audio.save()
    return True


def _write_mp4(path: str, bpm: float) -> bool:
    from mutagen.mp4 import MP4
    audio = MP4(path)
    audio.tags['tmpo'] = [int(round(bpm))]
    audio.save()
    return True


def _write_wav(path: str, bpm: float) -> bool:
    from mutagen import File
    audio = File(path)
    if audio is None:
        return False
    if audio.tags is None:
        audio.add_tags()
    try:
        audio.tags['bpm'] = [str(int(round(bpm)))]
        audio.save()
        return True
    except Exception:
        return False
