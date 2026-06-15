import json
from pathlib import Path


DEFAULT_SETTINGS = {
    'crossfade_duration': 20.0,
    'master_volume': 1.0,
    'cue_volume': 0.8,
    'master_device': None,
    'cue_device': None,
    'music_folders': [],
    'visible_columns': ['title', 'artist', 'bpm', 'key', 'duration', 'genre'],
    'auto_play': True,
    'last_playlist_path': '',
    'window_width': 1280,
    'window_height': 760,
    'splitter_sizes': [300, 980],
}


class SettingsManager:
    def __init__(self):
        self._config_dir = Path.home() / '.josinodj'
        self._config_dir.mkdir(exist_ok=True)
        self._config_file = self._config_dir / 'settings.json'
        self._data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self._data.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return self._data.get(name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._data[name] = value
            self.save()
