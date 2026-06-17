from dataclasses import dataclass, field
from datetime import datetime
import os


AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.opus',
    '.aiff', '.aif', '.aifc',   # Apple/Mac común en DJs
    '.mp2',                      # MPEG Layer 2
    '.ape',                      # Monkey's Audio lossless
    '.wv',                       # WavPack lossless
    '.mpc', '.mp+',              # Musepack
    '.m4p',                      # AAC protegido (sin DRM activo)
    '.dsf', '.dff',              # DSD / SACD
    '.spx',                      # Speex
    '.amr',                      # AMR
    '.ra', '.ram',               # RealAudio
    '.ac3',                      # Dolby AC3
    '.dts',                      # DTS audio
    '.mid', '.midi',             # MIDI
}

COLUMN_KEYS = ['title', 'artist', 'album', 'genre', 'year', 'bpm', 'key', 'duration', 'bitrate', 'date_added']
COLUMN_LABELS = {
    'title': 'Título',
    'artist': 'Artista',
    'album': 'Álbum',
    'genre': 'Género',
    'year': 'Año',
    'bpm': 'BPM',
    'key': 'Tono',
    'duration': 'Duración',
    'bitrate': 'Bitrate',
    'date_added': 'Añadido',
}
COLUMN_WIDTHS = {
    'title': 240,
    'artist': 160,
    'album': 140,
    'genre': 90,
    'year': 55,
    'bpm': 60,
    'key': 55,
    'duration': 70,
    'bitrate': 75,
    'date_added': 90,
}


@dataclass
class Track:
    path: str
    title: str = ''
    artist: str = ''
    album: str = ''
    genre: str = ''
    year: str = ''
    duration: float = 0.0
    bpm: float = 0.0
    key: str = ''
    bitrate: int = 0
    sample_rate: int = 44100
    date_added: str = ''

    def __post_init__(self):
        # Normalizar path para que las comparaciones de duplicados funcionen
        # independientemente de barras / vs \ o capitalización en Windows
        self.path = os.path.normcase(os.path.normpath(self.path))
        if not self.title:
            self.title = os.path.splitext(os.path.basename(self.path))[0]
        if not self.date_added:
            self.date_added = datetime.now().strftime('%Y-%m-%d')

    @property
    def duration_str(self) -> str:
        t = int(self.duration)
        m, s = divmod(t, 60)
        h, m = divmod(m, 60)
        if h:
            return f'{h}:{m:02d}:{s:02d}'
        return f'{m}:{s:02d}'

    @property
    def bpm_str(self) -> str:
        if self.bpm < 0:
            return '⟳'
        return f'{self.bpm:.0f}' if self.bpm else ''

    @property
    def bitrate_str(self) -> str:
        return f'{self.bitrate // 1000}k' if self.bitrate else ''

    @property
    def extension(self) -> str:
        return os.path.splitext(self.path)[1].lower()

    def get_column(self, key: str) -> str:
        if key == 'duration':
            return self.duration_str
        if key == 'bpm':
            return self.bpm_str
        if key == 'bitrate':
            return self.bitrate_str
        return str(getattr(self, key, ''))

    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'genre': self.genre,
            'year': self.year,
            'duration': self.duration,
            'bpm': max(0.0, self.bpm),
            'key': self.key,
            'bitrate': self.bitrate,
            'sample_rate': self.sample_rate,
            'date_added': self.date_added,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Track':
        valid_keys = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid_keys})


def is_audio_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS
