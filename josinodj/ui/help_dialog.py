from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QUrl

_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {
    background: #0a0a14;
    color: #ccccdd;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    margin: 0;
    padding: 20px 28px 40px;
    line-height: 1.6;
  }
  h1 {
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 3px;
    color: #fff;
    margin-bottom: 4px;
  }
  h1 span { color: #00d4ff; }
  .subtitle {
    font-size: 12px;
    color: #333355;
    margin-bottom: 28px;
    letter-spacing: 1px;
  }
  h2 {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #5a50e0;
    border-bottom: 1px solid #1a1a2a;
    padding-bottom: 6px;
    margin: 28px 0 14px;
  }
  .row {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 12px;
    padding: 10px 12px;
    background: #0e0e1c;
    border-radius: 8px;
    border-left: 3px solid #1a1a3a;
  }
  .row.highlight { border-left-color: #5a50e0; }
  .icon {
    font-size: 22px;
    min-width: 32px;
    text-align: center;
    margin-top: 1px;
  }
  .txt b { color: #ffffff; }
  .txt { color: #aaaacc; font-size: 13px; }
  .badge {
    display: inline-block;
    background: #1a1a2a;
    border: 1px solid #2a2a50;
    border-radius: 5px;
    padding: 1px 7px;
    font-size: 12px;
    color: #8888bb;
    font-family: Consolas, monospace;
    margin: 0 2px;
  }
  .tip {
    background: #0d1a10;
    border-left: 3px solid #44ee88;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 14px 0;
    font-size: 13px;
    color: #88cc99;
  }
  .warn {
    background: #1a0e0e;
    border-left: 3px solid #ee4444;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 14px 0;
    font-size: 13px;
    color: #cc8888;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 13px;
  }
  td { padding: 8px 10px; border-bottom: 1px solid #111122; }
  td:first-child { color: #5a50e0; font-family: Consolas, monospace; font-weight: bold; min-width: 130px; }
  td:last-child { color: #aaaacc; }
  .section-intro { color: #555577; font-size: 13px; margin-bottom: 14px; }
</style>
</head>
<body>

<h1>JOSINO<span>DJ</span></h1>
<div class="subtitle">GUÍA DE USO COMPLETA</div>

<!-- ══════════════════════════════ BARRA SUPERIOR ══════════════════════════════ -->
<h2>🔝 Barra superior</h2>
<p class="section-intro">Controles globales del programa, siempre visibles en la parte de arriba.</p>

<div class="row highlight">
  <div class="icon">🔓</div>
  <div class="txt"><b>Candado — Modo bloqueo</b><br>
    Bloquea toda la interfaz. La música sigue sonando pero nadie puede tocar nada.<br>
    Para desbloquear: toca la pantalla e introduce el PIN (por defecto <span class="badge">0000</span>).</div>
</div>

<div class="row">
  <div class="icon">⛶</div>
  <div class="txt"><b>Pantalla completa</b><br>
    Alterna entre ventana y pantalla completa. También con <span class="badge">F11</span>.</div>
</div>

<div class="row">
  <div class="icon">🎚</div>
  <div class="txt"><b>EQ — Ecualizador</b><br>
    Abre el panel de ecualización para ajustar graves, medios y agudos en tiempo real.</div>
</div>

<div class="row">
  <div class="icon">📱</div>
  <div class="txt"><b>Móvil — Control remoto</b><br>
    Genera un QR para controlar JOSINODJ desde el móvil por WiFi.<br>
    <b>Mismo WiFi:</b> móvil y PC en la misma red.<br>
    <b>Hotspot:</b> el PC crea su propia red, útil en eventos sin WiFi.</div>
</div>

<div class="row">
  <div class="icon">⬇</div>
  <div class="txt"><b>YouTube — Descargar</b><br>
    Descarga canciones directamente desde YouTube. Pega la URL o busca por nombre.</div>
</div>

<div class="row">
  <div class="icon">⚙</div>
  <div class="txt"><b>Ajustes</b><br>
    <b>Audio:</b> dispositivo de salida y normalización de volumen.<br>
    <b>Versión:</b> versión instalada, historial de cambios y botón para buscar actualizaciones.</div>
</div>

<!-- ══════════════════════════════ PANEL IZQUIERDO ══════════════════════════════ -->
<h2>📁 Panel izquierdo — Explorador de música</h2>
<p class="section-intro">Aquí gestionas tus carpetas de música y encuentras las canciones.</p>

<div class="row">
  <div class="icon">📂</div>
  <div class="txt"><b>+ Carpeta</b><br>
    Añade una carpeta de tu PC. Las canciones que contiene aparecen en la lista de abajo.</div>
</div>

<div class="row">
  <div class="icon">🔍</div>
  <div class="txt"><b>Buscador de carpeta</b><br>
    Filtra las pistas de la carpeta seleccionada. Busca por título o artista.</div>
</div>

<div class="row">
  <div class="icon">➕</div>
  <div class="txt"><b>Doble clic en una canción</b><br>
    La añade al final de tu lista de reproducción.</div>
</div>

<div class="row">
  <div class="icon">📂</div>
  <div class="txt"><b>Añadir todo</b><br>
    Carga toda la carpeta activa de golpe en la lista.</div>
</div>

<div class="tip">💡 También puedes arrastrar canciones o carpetas desde el explorador de Windows directamente a la lista.</div>

<!-- ══════════════════════════════ REPRODUCTOR ══════════════════════════════ -->
<h2>▶ Reproductor</h2>
<p class="section-intro">Controla la reproducción y los efectos de mezcla.</p>

<div class="row highlight">
  <div class="icon">▶⏸</div>
  <div class="txt"><b>Play / Pausa</b><br>
    Inicia o pausa la reproducción. Atajo: <span class="badge">Espacio</span></div>
</div>

<div class="row">
  <div class="icon">⏮⏭</div>
  <div class="txt"><b>Anterior / Siguiente</b><br>
    Salta a la canción anterior o siguiente de la lista.<br>
    Atajos: <span class="badge">←</span> <span class="badge">→</span></div>
</div>

<div class="row">
  <div class="icon">∞</div>
  <div class="txt"><b>AUTO — Reproducción automática</b><br>
    Las canciones pasan una tras otra sin que toques nada. Ideal para dejar la música sonando sola.</div>
</div>

<div class="row">
  <div class="icon">⇄</div>
  <div class="txt"><b>Shuffle — Modo aleatorio</b><br>
    Reproduce en orden aleatorio sin repetir canciones ya escuchadas.</div>
</div>

<div class="row">
  <div class="icon">↔</div>
  <div class="txt"><b>Crossfade</b><br>
    Mezcla suave entre canciones. Ajusta los segundos con el deslizador (0 a 30 seg).<br>
    La zona roja en la onda muestra dónde empieza el cruce con la siguiente canción.</div>
</div>

<div class="row">
  <div class="icon">🌊</div>
  <div class="txt"><b>Forma de onda</b><br>
    Muestra la onda de la canción. Haz clic en cualquier punto para saltar a esa posición.</div>
</div>

<!-- ══════════════════════════════ LISTA ══════════════════════════════ -->
<h2>🎵 Lista de reproducción</h2>
<p class="section-intro">La lista central es donde organizas el orden de las canciones para tu sesión.</p>

<div class="row">
  <div class="icon">🖱</div>
  <div class="txt"><b>Doble clic</b><br>Reproduce esa canción inmediatamente.</div>
</div>

<div class="row">
  <div class="icon">↑↓</div>
  <div class="txt"><b>Ordenar por columna</b><br>
    Haz clic en la cabecera (Título, BPM, Duración…) para ordenar. Otro clic invierte el orden.</div>
</div>

<div class="row">
  <div class="icon">🔍</div>
  <div class="txt"><b>Buscador de lista</b><br>
    Filtra las canciones de tu lista actual. No afecta al orden de reproducción.</div>
</div>

<div class="row">
  <div class="icon">A+ A−</div>
  <div class="txt"><b>Tamaño de texto</b><br>
    Aumenta o reduce el tamaño del texto de la lista.</div>
</div>

<div class="row">
  <div class="icon">💾</div>
  <div class="txt"><b>Guardar lista</b><br>
    Guarda tu lista actual como archivo <span class="badge">.jdj</span> para cargarla en otra sesión.</div>
</div>

<div class="row">
  <div class="icon">📂</div>
  <div class="txt"><b>Abrir lista</b><br>
    Carga una lista guardada previamente.</div>
</div>

<!-- ══════════════════════════════ MÓVIL ══════════════════════════════ -->
<h2>📱 Control desde el móvil</h2>
<p class="section-intro">Controla JOSINODJ desde cualquier móvil o tablet sin instalar nada.</p>

<div class="row highlight">
  <div class="icon">📶</div>
  <div class="txt"><b>Cómo conectarse</b><br>
    1. Pulsa <b>📱 Móvil</b> en la barra superior<br>
    2. Elige <b>Mismo WiFi</b> (PC y móvil en la misma red) o <b>Hotspot</b> (el PC crea su propia red)<br>
    3. Escanea el QR con la cámara del móvil<br>
    4. Se abre la página de control en el navegador — sin apps, sin instalación</div>
</div>

<div class="row">
  <div class="icon">▶⏸</div>
  <div class="txt"><b>Play / Pausa / Anterior / Siguiente</b><br>
    Controles básicos de reproducción directamente desde el móvil.</div>
</div>

<div class="row">
  <div class="icon">👆</div>
  <div class="txt"><b>Toca una canción</b><br>
    Reproduce esa canción inmediatamente.</div>
</div>

<div class="row">
  <div class="icon">👆👆</div>
  <div class="txt"><b>Mantén pulsada una canción</b><br>
    Abre un menú con opciones: Reproducir a continuación, Mover al inicio/final, Eliminar de lista.</div>
</div>

<div class="row">
  <div class="icon">≡</div>
  <div class="txt"><b>Reordenar arrastrando</b><br>
    Arrastra el icono <b>≡</b> de cualquier canción para cambiar su posición en la lista.</div>
</div>

<div class="row">
  <div class="icon">🔍</div>
  <div class="txt"><b>Buscador en el móvil</b><br>
    Escribe en el campo de búsqueda para filtrar canciones rápidamente por título o artista.</div>
</div>

<!-- ══════════════════════════════ NORMALIZACIÓN ══════════════════════════════ -->
<h2>🔊 Normalización de volumen</h2>

<div class="row">
  <div class="icon">🔊</div>
  <div class="txt"><b>Igualar volumen automáticamente</b><br>
    Analiza cada canción y ajusta su nivel para que todas suenen igual de fuerte.<br>
    Target: <span class="badge">−16 dBFS</span>. Se activa por defecto. Configurable en <b>⚙ Ajustes → Audio</b>.</div>
</div>

<div class="tip">💡 Si una canción suena demasiado alta o baja respecto a las demás, comprueba que la normalización está activada.</div>

<!-- ══════════════════════════════ RECUPERACIÓN ══════════════════════════════ -->
<h2>💾 Guardado y recuperación de sesión</h2>

<div class="row">
  <div class="icon">⏱</div>
  <div class="txt"><b>Guardado automático cada 30 segundos</b><br>
    JOSINODJ guarda tu lista y posición constantemente.<br>
    Si el programa se cierra de golpe, al volver a abrirlo te preguntará si restaurar la última sesión.</div>
</div>

<!-- ══════════════════════════════ ACTUALIZACIONES ══════════════════════════════ -->
<h2>🔄 Actualizaciones automáticas</h2>

<div class="row">
  <div class="icon">🔄</div>
  <div class="txt"><b>Actualización automática al abrir</b><br>
    Al arrancar, JOSINODJ comprueba si hay una versión nueva. Si la hay, te lo pregunta y se instala sola.<br>
    También puedes buscar manualmente en <b>⚙ Ajustes → Versión → Buscar actualizaciones</b>.</div>
</div>

<!-- ══════════════════════════════ ATAJOS ══════════════════════════════ -->
<h2>⌨ Atajos de teclado</h2>

<table>
  <tr><td>Espacio</td><td>Play / Pausa</td></tr>
  <tr><td>→</td><td>Siguiente canción</td></tr>
  <tr><td>←</td><td>Canción anterior</td></tr>
  <tr><td>F11</td><td>Pantalla completa / Ventana</td></tr>
</table>

<!-- ══════════════════════════════ FORMATOS ══════════════════════════════ -->
<h2>🎵 Formatos de audio compatibles</h2>
<p class="section-intro">MP3 · FLAC · WAV · OGG · M4A · AAC · WMA · OPUS y muchos más.<br>
FFmpeg viene incluido — no necesitas instalar nada extra.</p>

<div class="warn">⚠ Si una canción no suena, puede que el archivo esté corrupto o en un formato muy inusual.</div>

</body>
</html>"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ayuda — JOSINODJ')
        self.setMinimumSize(700, 600)
        self.resize(740, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_HTML)
        browser.setStyleSheet('background:#0a0a14;border:none;')
        layout.addWidget(browser)

        btns = QHBoxLayout()
        btns.addStretch()
        close = QPushButton('Cerrar')
        close.setFixedWidth(100)
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        btns.addSpacing(8)
        layout.addLayout(btns)
