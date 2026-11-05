"""Mantiene yt-dlp al día sin reinstalar JOSINODJ.

YouTube cambia a menudo y las versiones viejas de yt-dlp acaban dando
"HTTP Error 403: Forbidden". La versión que va dentro del exe se queda
congelada, así que descargamos la última de GitHub (es un zip de Python
puro) a ~/.josinodj/ytdlp/ y la ponemos delante en sys.path.
"""
import os
import re
import sys
import json
import time
import zipfile
import threading
import urllib.request
from pathlib import Path

_DIR = Path.home() / '.josinodj' / 'ytdlp'
_STAMP = _DIR / 'last_check.txt'
_API = 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'
_DL = 'https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp'
_UA = {'User-Agent': 'JOSINODJ-updater'}
_lock = threading.Lock()


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r'\d+', v or '0'))


def _zips() -> list[Path]:
    if not _DIR.exists():
        return []
    return sorted(_DIR.glob('yt-dlp-*.zip'), key=lambda p: _vt(p.stem))


def _bundled_version() -> str:
    """Versión del yt-dlp que viene dentro del programa (sin el zip)."""
    for p in sys.path:
        if 'yt-dlp-' in os.path.basename(p):
            continue
        f = Path(p) / 'yt_dlp' / 'version.py'
        if f.exists():
            m = re.search(r"__version__\s*=\s*'([^']+)'", f.read_text('utf-8', 'ignore'))
            if m:
                return m.group(1)
    try:
        import importlib.metadata as md
        return md.version('yt-dlp')
    except Exception:
        return '0'


def activate():
    """Llamar antes de `import yt_dlp`: usa el zip descargado si es más nuevo."""
    zs = _zips()
    if not zs:
        return
    best = zs[-1]
    if _vt(best.stem) <= _vt(_bundled_version()):
        return
    sp = str(best)
    if sp in sys.path:
        return
    _deactivate()
    sys.path.insert(0, sp)
    try:
        import yt_dlp  # noqa: F401  comprobar que carga dentro del exe
        from yt_dlp import YoutubeDL  # noqa: F401
    except Exception as e:
        print(f'[yt-dlp] {best.name} no carga ({e}); uso el del programa')
        _deactivate()
        try:
            best.unlink()
        except Exception:
            pass


def _deactivate():
    for p in list(sys.path):
        if 'yt-dlp-' in os.path.basename(p):
            sys.path.remove(p)
    sys.path_importer_cache.clear()
    _purge()


def _purge():
    for name in list(sys.modules):
        if name == 'yt_dlp' or name.startswith('yt_dlp.'):
            del sys.modules[name]


def current_version() -> str:
    activate()
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return '0'


def update(force: bool = False) -> bool:
    """Descarga la última versión si es más nueva. True si ha cambiado algo."""
    with _lock:
        try:
            _DIR.mkdir(parents=True, exist_ok=True)
            if not force and _STAMP.exists() and time.time() - _STAMP.stat().st_mtime < 86400:
                return False
            req = urllib.request.Request(_API, headers=_UA)
            with urllib.request.urlopen(req, timeout=10) as r:
                tag = json.loads(r.read().decode('utf-8'))['tag_name']
            _STAMP.write_text(tag, encoding='utf-8')
            if _vt(tag) <= _vt(current_version()):
                return False
            dest = _DIR / f'yt-dlp-{tag}.zip'
            tmp = dest.with_suffix('.part')
            req = urllib.request.Request(_DL.format(tag=tag), headers=_UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            with zipfile.ZipFile(tmp) as z:
                if 'yt_dlp/__init__.py' not in z.namelist():
                    raise ValueError('zip de yt-dlp no válido')
            os.replace(tmp, dest)
            for old in _zips():
                if old != dest:
                    try:
                        old.unlink()
                    except Exception:
                        pass
            activate()
            if str(dest) not in sys.path:
                return False
            print(f'[yt-dlp] actualizado a {tag}')
            return True
        except Exception as e:
            print(f'[yt-dlp] no se pudo actualizar: {e}')
            return False


def update_async():
    threading.Thread(target=update, daemon=True).start()
