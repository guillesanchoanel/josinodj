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
import threading

GITHUB_REPO = 'guillesanchoanel/josinodj'
API_URL     = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
WEB_LATEST  = f'https://github.com/{GITHUB_REPO}/releases/latest'
ZIP_URL     = f'https://github.com/{GITHUB_REPO}/releases/download/v{{v}}/JOSINODJ-v{{v}}.zip'
TIMEOUT     = 10
_UA         = {'User-Agent': 'JOSINODJ-updater'}


def _local_version() -> str:
    try:
        from josinodj.utils._version import VERSION
        return VERSION
    except Exception:
        return '0.0.0'


def _parse(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip('v').split('.'))
    except Exception:
        return (0, 0, 0)


def _ssl_ctx():
    """Certificados propios (certifi): en algunos Windows faltan los de GitHub
    hasta que se visita la web con el navegador, y la comprobación fallaba."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url: str, timeout: float = TIMEOUT, method: str = 'GET'):
    req = urllib.request.Request(url, headers=_UA, method=method)
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx())
    except urllib.error.URLError as e:
        if 'CERTIFICATE' not in str(e).upper():
            raise
        import ssl
        return urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context())


def latest_release() -> tuple[str, str, int]:
    """(versión, url_del_zip, tamaño). Primero la API de GitHub; si falla
    (límite de 60 consultas/hora por IP: con datos del móvil se agota enseguida,
    red lenta...), la página web de releases, que no tiene ese límite."""
    err = None
    try:
        with _open(API_URL) as r:
            data = json.loads(r.read().decode())
        ver = data.get('tag_name', '').lstrip('v')
        for asset in data.get('assets', []):
            if asset['name'].endswith('.zip'):
                return ver, asset['browser_download_url'], asset.get('size', 0)
        return ver, ZIP_URL.format(v=ver), 0
    except Exception as e:
        err = e
    try:
        with _open(WEB_LATEST, method='HEAD') as r:
            final = r.geturl()                      # .../releases/tag/v2.6.5
        ver = final.rstrip('/').rsplit('/', 1)[-1].lstrip('v')
        if _parse(ver) == (0, 0, 0):
            raise ValueError(f'respuesta rara de GitHub: {final}')
        return ver, ZIP_URL.format(v=ver), 0
    except Exception as e2:
        raise RuntimeError(f'No se pudo consultar GitHub ({err}; {e2})')


def check_and_update(parent_widget=None) -> bool:
    """
    Devuelve True si se aplicó una actualización (la app debe reiniciarse).
    Devuelve False si no hay nada nuevo o no hay conexión.
    """
    if not getattr(sys, 'frozen', False):
        return False  # En dev no se actualiza
    try:
        remote_ver, asset_url, asset_size = latest_release()
    except Exception as e:
        print(f'[updater] {e}')
        return False
    if _parse(remote_ver) <= _parse(_local_version()):
        return False
    return download_and_install(parent_widget, remote_ver, asset_url, asset_size)


def download_and_install(parent_widget, remote_ver: str, asset_url: str,
                         asset_size: int = 0, ask: bool = True) -> bool:
    """Descarga el zip de la versión y lanza el instalador. True = cerrar la app."""
    from PySide6.QtWidgets import QMessageBox, QProgressDialog
    from PySide6.QtCore import Qt
    if ask:
        # Confirmar con el usuario
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

    # Diálogo de progreso
    size_mb = asset_size / (1024 * 1024) if asset_size else 0
    label = f'Descargando actualización v{remote_ver}…'
    if size_mb:
        label += f'\n({size_mb:.0f} MB — puede tardar varios minutos)'
    progress = QProgressDialog(label, None, 0, 100, parent_widget)
    progress.setWindowTitle('JOSINODJ — Actualizando')
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setMinimumWidth(400)
    progress.setCancelButton(None)   # sin botón cancelar
    progress.setValue(0)
    progress.show()

    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()

    # Descargar en hilo de fondo — reportar progreso al hilo principal
    tmp_zip = os.path.join(tempfile.gettempdir(), 'josinodj_update.zip')
    download_error = [None]
    download_done  = [False]
    bytes_received = [0]

    def _download():
        try:
            with _open(asset_url, timeout=60) as resp:
                total = int(resp.headers.get('Content-Length', asset_size or 0))
                chunk = 65536   # 64 KB
                received = 0
                with open(tmp_zip, 'wb') as f:
                    while True:
                        data = resp.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        bytes_received[0] = received
                        if total:
                            bytes_received[0] = int(received / total * 90)  # 0-90%
        except Exception as e:
            download_error[0] = str(e)
        finally:
            download_done[0] = True

    t = threading.Thread(target=_download, daemon=True)
    t.start()

    while not download_done[0]:
        progress.setValue(bytes_received[0] if asset_size else (progress.value() + 1) % 90)
        QApplication.processEvents()
        t.join(timeout=0.1)

    if download_error[0]:
        progress.close()
        QMessageBox.critical(parent_widget, 'Error de descarga',
                             f'No se pudo descargar la actualización:\n{download_error[0]}')
        return False

    # Extraer
    progress.setLabelText('Extrayendo archivos…')
    progress.setValue(91)
    QApplication.processEvents()

    tmp_extract = tempfile.mkdtemp(prefix='josinodj_update_')
    try:
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            z.extractall(tmp_extract)
    except Exception as e:
        progress.close()
        QMessageBox.critical(parent_widget, 'Error',
                             f'No se pudo extraer la actualización:\n{e}')
        return False

    installer = os.path.join(tmp_extract, 'INSTALAR.bat')
    if not os.path.exists(installer):
        progress.close()
        QMessageBox.warning(parent_widget, 'Aviso',
                            'Archivos descargados pero no se encontró el instalador.\n'
                            f'Instala manualmente desde:\n{tmp_extract}')
        return False

    progress.setValue(100)
    progress.close()
    QApplication.processEvents()

    # Avisar al usuario ANTES de lanzar el instalador — así el click en OK
    # sucede antes de que INSTALAR.bat empiece, dando tiempo al exe a cerrarse.
    QMessageBox.information(
        parent_widget,
        'Listo para instalar',
        'La actualización se ha descargado correctamente.\n\n'
        'Al pulsar OK:\n'
        '  1. JOSINODJ se cerrará\n'
        '  2. Aparecerá una ventana pidiendo permisos de administrador — acéptala\n'
        '  3. La actualización se instalará y JOSINODJ se abrirá de nuevo'
    )

    # Lanzar INSTALAR.bat justo después del click en OK
    subprocess.Popen(
        ['cmd', '/c', installer],
        cwd=tmp_extract,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    return True


def _install_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
