import json
from pathlib import Path
from datetime import datetime


class SessionManager:
    def __init__(self):
        self._path = Path.home() / '.josinodj' / 'session.json'
        self._path.parent.mkdir(exist_ok=True)

    def save(self, tracks: list, playing_index: int, position: float,
             playlist_name: str = ''):
        data = {
            'tracks': [t.to_dict() for t in tracks],
            'playing_index': playing_index,
            'position': position,
            'playlist_name': playlist_name,
            'saved_at': datetime.now().isoformat(timespec='seconds'),
        }
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self) -> dict | None:
        if not self._path.exists():
            return None
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def clear(self):
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass

    @property
    def exists(self) -> bool:
        return self._path.exists()
