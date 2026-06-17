# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para JOSINODJ.
Genera dist/JOSINODJ/ con JOSINODJ.exe y todas las dependencias.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('assets/ffmpeg.exe', '.'),   # ffmpeg junto al exe para conversión a MP3
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'sounddevice',
        'sounddevice._sounddevice',
        'miniaudio',
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.mp4',
        'mutagen.easyid3',
        'mutagen.id3',
        'mutagen.id3._tags',
        'mutagen.id3._frames',
        'numpy',
        'numpy.core._multiarray_umath',
        'soundfile',
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.postprocessor',
        'yt_dlp.utils',
        'yt_dlp.networking',
        'flask',
        'flask.json',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'jinja2',
        'qrcode',
        'qrcode.image.pil',
        'librosa',
        'librosa.core',
        'librosa.beat',
        'librosa.feature',
        'librosa.effects',
        'librosa.util',
        'scipy',
        'scipy.signal',
        'scipy.ndimage',
        'numba',
        'llvmlite',
        'audioread',
        'soxr',
        'joblib',
        'pooch',
        'scikit-learn',
        'sklearn',
        'sklearn.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'pandas',
        'IPython', 'jupyter', 'notebook', 'PIL._imagingtk',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JOSINODJ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX desactivado — algunos antivirus lo marcan como falso positivo
    console=False,      # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='JOSINODJ',
)
