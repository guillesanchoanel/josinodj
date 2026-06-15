"""
Auto-updater: comprueba si hay una release más nueva en GitHub y,
si la hay, descarga el zip, lo extrae encima y relanza el instalador.
"""
import os
import sys
import zipfile
import tempfile
import subprocess
import urllib.request
import urllib.error
import json

GITHUB_REPO   = 'guillesanchoanel/josinodj'
VERSION_FILE  = os.path.join(os.path.dirname(__file__), '..', '..', 'version.txt')
API_URL       = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
TIMEOUT       = 6   # segundos


def _local_version() -> str:
    try:
        if getattr(sys, 'frozen', False):
            path = os.path.join(os.path.dirname(sys.executable), 'version.txt')
        else:
            path = VERSION_FILE
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return '0.0.0'


def _parse(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip('v').split('.'))
    except Exception:
        return (0, 0, 0)


def check_and_update(parent_widget=None) -> bool:
    """
    Devuelve True si se aplicó una actualización (la app debe reiniciarse).
    Devuelve False si no hay nada nuevo o no hay conexión.
    """
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'JOSINODJ-updater'})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return False

    remote_tag = data.get('tag_name', '')
    remote_ver = remote_tag.lstrip('v')

    if _parse(remote_ver) <= _parse(_local_version()):
        return False

    # Buscar asset .zip
    asset_url = None
    for asset in data.get('assets', []):
        if asset['name'].endswith('.zip'):
            asset_url = asset['browser_download_url']
            break

    if not asset_url:
        return False

    # Confirmar con el usuario
    from PySide6.QtWidgets import QMessageBox
    msg = QMessageBox(parent_widget)
    msg.setWindowTitle('Actualización disponible')
    msg.setText(
        f'Hay una nueva versión de JOSINODJ: <b>v{remote_ver}</b><br>'
        f'(tienes la <b>v{_local_version()}</b>)<br><br>'
        '¿Descargar e instalar ahora?'
    )
    btn_si = msg.addButton('Sí', QMessageBox.AcceptRole)
    msg.addButton('No', QMessageBox.RejectRole)
    msg.setDefaultButton(btn_si)
    msg.exec()
    if msg.clickedButton() != btn_si:
        return False

    # Descargar
    try:
        tmp_zip = os.path.join(tempfile.gettempdir(), 'josinodj_update.zip')
        urllib.request.urlretrieve(asset_url, tmp_zip)
    except Exception as e:
        QMessageBox.critical(parent_widget, 'Error',
                             f'No se pudo descargar la actualización:\n{e}')
        return False

    # Extraer al directorio de instalación
    install_dir = _install_dir()
    try:
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            z.extractall(install_dir)
    except Exception as e:
        QMessageBox.critical(parent_widget, 'Error',
                             f'No se pudo extraer la actualización:\n{e}')
        return False

    # Lanzar instalador si existe
    installer = os.path.join(install_dir, 'INSTALAR.bat')
    if os.path.exists(installer):
        subprocess.Popen(['cmd', '/c', installer], cwd=install_dir,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)

    QMessageBox.information(parent_widget, 'Actualización instalada',
                            'La actualización se instaló correctamente.\n'
                            'La aplicación se cerrará ahora.')
    return True


def _install_dir() -> str:
    # Si corremos como exe compilado: carpeta del exe
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # En desarrollo: raíz del proyecto
    return os.path.dirname(os.path.abspath(VERSION_FILE))
