import os


def read_metadata(path: str) -> dict:
    result = {
        'title': '',
        'artist': '',
        'album': '',
        'genre': '',
        'year': '',
        'duration': 0.0,
        'bpm': 0.0,
        'key': '',
        'bitrate': 0,
        'sample_rate': 44100,
    }
    try:
        from mutagen import File
        audio = File(path)
        if audio is None:
            return result
        if hasattr(audio, 'info'):
            info = audio.info
            result['duration'] = getattr(info, 'length', 0.0)
            result['bitrate'] = getattr(info, 'bitrate', 0)
            result['sample_rate'] = getattr(info, 'sample_rate', 44100)

        ext = os.path.splitext(path)[1].lower()

        if ext == '.mp3':
            _read_mp3(path, result)
        elif ext in ('.flac', '.ogg', '.oga', '.opus'):
            _read_vorbis(audio, result)
        elif ext in ('.m4a', '.aac', '.mp4'):
            _read_mp4(audio, result)
        elif ext == '.wav':
            _read_wav(audio, result)

    except Exception:
        pass

    if not result['title']:
        result['title'] = os.path.splitext(os.path.basename(path))[0]

    return result


def _read_mp3(path: str, result: dict):
    try:
        from mutagen.easyid3 import EasyID3
        tags = EasyID3(path)
        result['title'] = tags.get('title', [''])[0]
        result['artist'] = tags.get('artist', [''])[0]
        result['album'] = tags.get('album', [''])[0]
        result['genre'] = tags.get('genre', [''])[0]
        result['year'] = (tags.get('date', [''])[0] or '')[:4]
        bpm = tags.get('bpm', [''])[0]
        result['bpm'] = _parse_float(bpm)
        result['key'] = tags.get('initialkey', [''])[0]
        return
    except Exception:
        pass
    try:
        from mutagen.id3 import ID3
        tags = ID3(path)
        result['title'] = _id3_str(tags, 'TIT2')
        result['artist'] = _id3_str(tags, 'TPE1')
        result['album'] = _id3_str(tags, 'TALB')
        result['genre'] = _id3_str(tags, 'TCON')
        tdrc = tags.get('TDRC')
        result['year'] = str(tdrc)[:4] if tdrc else ''
        tbpm = tags.get('TBPM')
        result['bpm'] = _parse_float(str(tbpm)) if tbpm else 0.0
        tkey = tags.get('TKEY')
        result['key'] = str(tkey) if tkey else ''
    except Exception:
        pass


def _read_vorbis(audio, result: dict):
    tags = audio.tags
    if not tags:
        return
    result['title'] = _vc(tags, 'title')
    result['artist'] = _vc(tags, 'artist')
    result['album'] = _vc(tags, 'album')
    result['genre'] = _vc(tags, 'genre')
    result['year'] = _vc(tags, 'date')[:4]
    result['bpm'] = _parse_float(_vc(tags, 'bpm'))
    result['key'] = _vc(tags, 'initialkey') or _vc(tags, 'key')


def _read_mp4(audio, result: dict):
    from mutagen.mp4 import MP4
    if not isinstance(audio, MP4):
        return
    tags = audio.tags or {}
    result['title'] = _mp4_str(tags, '\xa9nam')
    result['artist'] = _mp4_str(tags, '\xa9ART')
    result['album'] = _mp4_str(tags, '\xa9alb')
    result['genre'] = _mp4_str(tags, '\xa9gen')
    result['year'] = _mp4_str(tags, '\xa9day')[:4]


def _read_wav(audio, result: dict):
    if hasattr(audio, 'tags') and audio.tags:
        tags = audio.tags
        result['title'] = _vc(tags, 'title')
        result['artist'] = _vc(tags, 'artist')


def _id3_str(tags, key: str) -> str:
    val = tags.get(key)
    return str(val) if val else ''


def _vc(tags, key: str) -> str:
    val = tags.get(key)
    if isinstance(val, list) and val:
        return str(val[0])
    return str(val) if val else ''


def _mp4_str(tags: dict, key: str) -> str:
    val = tags.get(key)
    if isinstance(val, list) and val:
        return str(val[0])
    return ''


def _parse_float(s: str) -> float:
    try:
        return float(s.strip()) if s and s.strip() else 0.0
    except (ValueError, AttributeError):
        return 0.0
