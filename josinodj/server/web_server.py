"""
Mini servidor web para control remoto desde móvil.
Flask corre en un hilo de fondo. Las acciones del móvil se encolan
y un QTimer del hilo principal las ejecuta de forma segura.
"""
import threading
import queue
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
app.config['SECRET_KEY'] = 'josinodj'

# ── Estado compartido (leído por Flask, escrito por el hilo principal) ────────
_state: dict = {
    'title':         '',
    'artist':        '',
    'bpm':           '',
    'position':      0.0,
    'duration':      0.0,
    'playing':       False,
    'volume':        0.8,
    'playlist':      [],   # [{title, artist, i}]
    'current_index': -1,
    'played':        [],   # list of ints
    'next_title':    '',
    'next_artist':   '',
}

# ── Cola de acciones: Flask pone, Qt consume ──────────────────────────────────
_action_queue: queue.Queue = queue.Queue()

# ── Página HTML del mando ─────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>JOSINODJ</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%;overflow:hidden}
  body{background:#0a0a14;color:#fff;font-family:'Segoe UI',sans-serif;
       display:flex;flex-direction:column;user-select:none}
  .header{flex-shrink:0;background:#0a0a14;padding:14px 16px 10px;
          border-bottom:1px solid #0e0e20;
          display:flex;flex-direction:column;align-items:center}
  .sub{font-size:10px;color:#2a2a4a;margin-bottom:10px}
  .track-title{font-size:18px;font-weight:700;text-align:center;color:#fff;
               margin-bottom:3px;min-height:24px;width:100%;max-width:340px;
               white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .track-artist{font-size:13px;color:#555577;margin-bottom:2px}
  .bpm-key{font-size:11px;color:#4a40aa;margin-bottom:8px}
  .progress-wrap{width:100%;max-width:340px;margin-bottom:4px}
  .progress-bg{width:100%;height:5px;background:#1a1a2a;border-radius:3px;cursor:pointer}
  .progress-fill{height:5px;background:linear-gradient(90deg,#5a50e0,#00ccff);
                 border-radius:3px;width:0%;transition:width .5s linear}
  .time{font-size:11px;color:#444466;margin-bottom:10px;font-family:Consolas,monospace}
  .controls{display:flex;gap:16px;align-items:center;margin-bottom:10px}
  .btn{background:#1a1a2a;border:1px solid #2a2a50;border-radius:50%;
       width:52px;height:52px;font-size:20px;color:#aaaacc;cursor:pointer;
       display:flex;align-items:center;justify-content:center;
       -webkit-tap-highlight-color:transparent;transition:background .15s}
  .btn:active{background:#252545}
  .btn.play{background:linear-gradient(135deg,#5a50e0,#8040cc);
            border:none;width:66px;height:66px;font-size:24px;color:#fff}
  .btn.play:active{background:#3a30b0}
  .logo-row{display:flex;align-items:center;justify-content:space-between;
            width:100%;max-width:340px;margin-bottom:2px}
  .logo{font-size:22px;font-weight:900;letter-spacing:3px;color:#fff}
  .logo span{color:#00d4ff}
  .conn-area{display:flex;flex-direction:column;align-items:flex-end;gap:3px}
  .status{font-size:11px;font-weight:600;color:#2a7a3a;text-align:right}
  .status.error{color:#884444}
  .btn-refresh{display:none;background:none;border:1px solid #883333;
               border-radius:6px;color:#cc4444;font-size:16px;
               width:30px;height:30px;cursor:pointer;line-height:1;
               -webkit-tap-highlight-color:transparent}
  .btn-refresh:active{background:#1a0808}
  @keyframes spin{to{transform:rotate(360deg)}}
  .btn-refresh.spinning{animation:spin .7s linear infinite;border-color:#aaaaff;color:#aaaaff}
  .next-wrap{display:flex;align-items:baseline;gap:6px;margin-top:6px;max-width:340px;width:100%}
  .next-lbl{font-size:10px;color:#333355;text-transform:uppercase;letter-spacing:1px;flex-shrink:0}
  .next-title{font-size:12px;color:#444466;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .pl-wrap{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:8px 16px 24px}
  .pl-title{font-size:10px;color:#2a2a4a;letter-spacing:2px;
            text-transform:uppercase;font-weight:700;margin-bottom:6px;padding:0 4px}
  .pl-item{display:flex;align-items:center;gap:10px;padding:14px 10px;
           border-bottom:1px solid #0e0e20;border-radius:4px;
           transition:background .1s,opacity .1s;
           -webkit-tap-highlight-color:transparent;user-select:none}
  .pl-item.current{background:#0d1f10;border-left:3px solid #44ee88}
  .pl-item.played{opacity:0.35}
  .pl-item.dragging{opacity:0.25;background:#0a0a18}
  .pl-item.drag-over{border-top:2px solid #5a50e0}
  .pl-num{font-size:13px;color:#2a2a4a;min-width:26px;text-align:right;
          font-family:Consolas,monospace}
  .pl-item.current .pl-num{color:#44ee88}
  .pl-info{flex:1;overflow:hidden;cursor:pointer}
  .pl-name{font-size:16px;color:#cccccc;white-space:nowrap;
           overflow:hidden;text-overflow:ellipsis}
  .pl-item.current .pl-name{color:#44ee88;font-weight:700}
  .pl-artist{font-size:12px;color:#333355;white-space:nowrap;
             overflow:hidden;text-overflow:ellipsis;margin-top:2px}
  .drag-handle{color:#333366;font-size:22px;padding:0 6px;cursor:grab;
               touch-action:none;line-height:1}
  .drag-ghost{position:fixed;pointer-events:none;z-index:999;
              background:#252545;border-radius:8px;opacity:0.9;
              box-shadow:0 4px 20px rgba(0,0,0,0.6);padding:10px 8px;
              display:flex;align-items:center;gap:8px;font-size:13px;color:#ccc}
  .ctx-overlay{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,0.4)}
  .ctx-menu{display:none;position:fixed;z-index:1001;min-width:220px;
            background:#12121e;border:1px solid #2a2a50;border-radius:10px;
            box-shadow:0 8px 32px rgba(0,0,0,0.7);overflow:hidden}
  .ctx-title{font-size:12px;color:#444466;padding:10px 14px 6px;
             border-bottom:1px solid #1a1a30;white-space:nowrap;
             overflow:hidden;text-overflow:ellipsis}
  .ctx-item{display:block;width:100%;background:none;border:none;
            text-align:left;color:#cccccc;font-size:14px;padding:12px 14px;
            cursor:pointer;-webkit-tap-highlight-color:transparent}
  .ctx-item:active{background:#1e1e38}
  .ctx-sep{height:1px;background:#1a1a30;margin:2px 0}
  .ctx-danger{color:#cc4444}
  .pl-search-wrap{flex-shrink:0;padding:8px 16px 4px}
  #pl-search{width:100%;background:#111122;border:1px solid #2a2a50;
             border-radius:20px;padding:8px 14px;color:#ccc;font-size:14px;
             outline:none;-webkit-appearance:none}
  #pl-search::placeholder{color:#333355}
  #pl-search:focus{border-color:#5a50e0}
  #pl-noresult{display:none;color:#333355;font-size:12px;
               padding:20px 4px;text-align:center}
</style>
</head>
<body>
  <div class="header">
    <div class="logo-row">
      <div class="logo">JOSINO<span>DJ</span></div>
      <div class="conn-area">
        <span class="status" id="status">Conectado ✓</span>
        <button class="btn-refresh" id="btn-refresh" onclick="reconectar()">↺</button>
      </div>
    </div>
    <div class="sub">Control remoto</div>
    <div class="track-title" id="title">Esperando música…</div>
    <div class="track-artist" id="artist"></div>
    <div class="bpm-key" id="bpmkey"></div>
    <div class="progress-wrap">
      <div class="progress-bg" id="prog-bg">
        <div class="progress-fill" id="prog"></div>
      </div>
    </div>
    <div class="time" id="time">0:00 / 0:00</div>
    <div class="controls">
      <button class="btn" ontouchstart="" onclick="api('prev')">⏮</button>
      <button class="btn play" id="playbtn" ontouchstart="" onclick="api('toggle')">▶</button>
      <button class="btn" ontouchstart="" onclick="api('next')">⏭</button>
    </div>
    <div class="next-wrap">
      <span class="next-lbl">Siguiente</span>
      <span class="next-title" id="next-title">—</span>
    </div>
  </div>

  <div class="pl-search-wrap">
    <input type="search" id="pl-search" placeholder="🔍 Buscar canción..." oninput="onSearch(this.value)" autocomplete="off" autocorrect="off" spellcheck="false">
  </div>
  <div class="pl-wrap">
    <div class="pl-title">Lista de reproducción</div>
    <div id="playlist"></div>
    <div id="pl-noresult">Sin resultados</div>
  </div>

  <div class="ctx-overlay" id="ctx-overlay" onclick="closeCtx()"></div>
  <div class="ctx-menu" id="ctx-menu">
    <div class="ctx-title" id="ctx-title"></div>
    <button class="ctx-item" onclick="ctxDo('play')">▶ Reproducir</button>
    <button class="ctx-item" onclick="ctxDo('play_next')">⏭ Reproducir a continuación</button>
    <div class="ctx-sep"></div>
    <button class="ctx-item" onclick="ctxDo('move_top')">⬆ Mover al inicio</button>
    <button class="ctx-item" onclick="ctxDo('move_bottom')">⬇ Mover al final</button>
    <div class="ctx-sep"></div>
    <button class="ctx-item" onclick="ctxDo('unplay')">↩ Quitar reproducida</button>
    <button class="ctx-item ctx-danger" onclick="ctxDo('remove')">🗑 Eliminar de lista</button>
  </div>

<script>
  var _plData=[], _lastCur=-1, _searchQ='';
  var _dg={el:null,ghost:null,fromIdx:-1,toIdx:-1,itemH:0};
  var _scrollTimer=null;

  function onSearch(q){
    _searchQ=q.trim().toLowerCase();
    applySearch();
  }

  function applySearch(){
    var items=document.querySelectorAll('.pl-item');
    var q=_searchQ, found=0;
    items.forEach(function(item,i){
      var t=_plData[i];
      if(!t){item.style.display='none';return;}
      var match=!q
        ||(t.title||'').toLowerCase().indexOf(q)>=0
        ||(t.artist||'').toLowerCase().indexOf(q)>=0;
      item.style.display=match?'':'none';
      if(match) found++;
    });
    var nr=document.getElementById('pl-noresult');
    if(nr) nr.style.display=(found===0&&q)?'':'none';
  }

  function fmt(s){
    s=Math.floor(s||0);
    var m=Math.floor(s/60),ss=s%60;
    return m+':'+(ss<10?'0':'')+ss;
  }

  function setConnected(ok){
    var s=document.getElementById('status');
    var b=document.getElementById('btn-refresh');
    b.classList.remove('spinning');
    if(ok){ s.textContent='Conectado ✓'; s.className='status'; b.style.display='none'; }
    else  { s.textContent='Reconectando…'; s.className='status error'; b.style.display='flex'; b.style.alignItems='center'; b.style.justifyContent='center'; }
  }

  function update(){
    fetch('/api/status').then(r=>r.json()).then(d=>{
      document.getElementById('title').textContent   = d.title  || 'Esperando música…';
      document.getElementById('artist').textContent  = d.artist || '';
      document.getElementById('bpmkey').textContent  = d.bpm    || '';
      document.getElementById('playbtn').textContent = d.playing ? '⏸' : '▶';
      var pct=d.duration>0?(d.position/d.duration*100):0;
      document.getElementById('prog').style.width=pct+'%';
      document.getElementById('time').textContent=fmt(d.position)+' / '+fmt(d.duration);
      document.getElementById('next-title').textContent = d.next_title || '—';
      setConnected(true);
      renderPlaylist(d.playlist||[], d.current_index, d.played||[]);
    }).catch(function(){ setConnected(false); });
  }

  function reconectar(){
    var b=document.getElementById('btn-refresh');
    var s=document.getElementById('status');
    b.classList.add('spinning');
    s.textContent='Intentando reconectar…';
    update();
  }

  function renderPlaylist(tracks, cur, played){
    if(_dg.el) return;  // no reconstruir DOM durante arrastre activo
    _plData=tracks;
    var pl=document.getElementById('playlist');
    if(!tracks.length){
      pl.innerHTML='<div style="color:#222240;font-size:12px;padding:8px">Lista vacía</div>';
      return;
    }
    var html='';
    for(var i=0;i<tracks.length;i++){
      var t=tracks[i];
      var isCur=(t.i===cur), isPlayed=played.indexOf(t.i)>=0&&!isCur;
      var cls='pl-item'+(isCur?' current':'')+(isPlayed?' played':'');
      var icon=isCur?'▶':(isPlayed?'✓':(t.i+1));
      html+='<div class="'+cls+'" data-idx="'+i+'">'
        +'<span class="drag-handle" data-drag="'+i+'">≡</span>'
        +'<span class="pl-num">'+icon+'</span>'
        +'<div class="pl-info" onclick="playIdx('+t.i+')">'
        +  '<div class="pl-name">'+esc(t.title)+'</div>'
        +  '<div class="pl-artist">'+esc(t.artist||'')+'</div>'
        +'</div>'
        +'</div>';
    }
    pl.innerHTML=html;
    applySearch();
    initDrag();
    if(cur>=0 && cur!==_lastCur){
      _lastCur=cur;
      var items=pl.querySelectorAll('.pl-item');
      for(var j=0;j<items.length;j++){
        if(parseInt(items[j].dataset.idx)===cur){
          items[j].scrollIntoView({block:'nearest',behavior:'smooth'});
          break;
        }
      }
    }
  }

  /* ── Context menu ── */
  var _ctxIdx=-1, _lpTimer=null;

  function showCtx(idx, x, y){
    _ctxIdx=idx;
    var t=_plData[idx];
    if(!t) return;
    document.getElementById('ctx-title').textContent=t.title;
    var menu=document.getElementById('ctx-menu');
    var ov=document.getElementById('ctx-overlay');
    menu.style.display='block'; ov.style.display='block';
    // Posicionar sin salirse de pantalla
    var mw=menu.offsetWidth||220, mh=menu.offsetHeight||260;
    var lx=Math.min(x, window.innerWidth-mw-8);
    var ly=Math.min(y, window.innerHeight-mh-8);
    menu.style.left=Math.max(8,lx)+'px';
    menu.style.top=Math.max(8,ly)+'px';
  }

  function closeCtx(){
    document.getElementById('ctx-menu').style.display='none';
    document.getElementById('ctx-overlay').style.display='none';
    _ctxIdx=-1;
  }

  function ctxDo(action){
    var idx=_ctxIdx;
    closeCtx();
    if(idx<0) return;
    var t=_plData[idx];
    if(!t) return;
    if(action==='play'){ playIdx(t.i); return; }
    var ep = action==='remove'?'remove'
           : action==='unplay'?'unplay'
           : action==='play_next'?'play_next'
           : action==='move_top'?'move_top'
           : 'move_bottom';
    fetch('/api/'+ep,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({i:idx})
    }).then(update);
  }

  function initDrag(){
    var pl=document.getElementById('playlist');
    if(pl._dragReady) return;
    pl._dragReady=true;
    pl.addEventListener('touchstart',function(e){
      // Long press en zona de info (no handle)
      if(!e.target.closest('[data-drag]') && !_dg.el){
        var item=e.target.closest('.pl-item');
        if(item){
          var lpIdx=parseInt(item.dataset.idx);
          var lpX=e.touches[0].clientX, lpY=e.touches[0].clientY;
          _lpTimer=setTimeout(function(){
            _lpTimer=null;
            showCtx(lpIdx, lpX, lpY);
          },550);
          var cancelLp=function(){ clearTimeout(_lpTimer); _lpTimer=null; pl.removeEventListener('touchend',cancelLp); pl.removeEventListener('touchmove',cancelLp); };
          pl.addEventListener('touchend',cancelLp,{once:true});
          pl.addEventListener('touchmove',cancelLp,{once:true});
        }
      }
      var handle=e.target.closest('[data-drag]');
      if(!handle||_dg.el) return;
      e.preventDefault();
      var idx=parseInt(handle.dataset.drag);
      var items=document.querySelectorAll('.pl-item');
      var el=items[idx];
      if(!el) return;
      var rect=el.getBoundingClientRect();
      _dg.fromIdx=idx; _dg.toIdx=idx; _dg.el=el; _dg.itemH=rect.height;
      el.classList.add('dragging');
      document.querySelectorAll('.drag-ghost').forEach(function(g){g.remove();});
      var ghost=document.createElement('div');
      ghost.className='drag-ghost';
      ghost.style.top=(e.touches[0].clientY-rect.height/2)+'px';
      ghost.style.left=rect.left+'px';
      ghost.style.width=rect.width+'px';
      ghost.innerHTML='≡ &nbsp;'+esc(_plData[idx]?_plData[idx].title:'');
      document.body.appendChild(ghost);
      _dg.ghost=ghost;
      document.addEventListener('touchmove',onDragMove,{passive:false});
      document.addEventListener('touchend',onDragEnd);
      document.addEventListener('touchcancel',onDragEnd);
    },{passive:false});
  }

  function onDragMove(e){
    e.preventDefault();
    var y=e.touches[0].clientY;
    _dg.ghost.style.top=(y-_dg.itemH/2)+'px';
    // Auto-scroll al acercar el dedo al borde de la lista
    var plWrap=document.querySelector('.pl-wrap');
    var pr=plWrap.getBoundingClientRect();
    clearTimeout(_scrollTimer);
    if(y<pr.top+60)      _scrollTimer=setTimeout(function(){plWrap.scrollTop-=30;},16);
    else if(y>pr.bottom-60) _scrollTimer=setTimeout(function(){plWrap.scrollTop+=30;},16);
    // Indicador de destino
    var items=document.querySelectorAll('.pl-item');
    var newIdx=_dg.fromIdx;
    items.forEach(function(item,i){
      if(item===_dg.el) return;
      var r=item.getBoundingClientRect();
      if(y>r.top&&y<r.bottom) newIdx=i;
    });
    if(newIdx!==_dg.toIdx){
      items.forEach(function(it){it.classList.remove('drag-over');});
      _dg.toIdx=newIdx;
      if(items[newIdx]&&items[newIdx]!==_dg.el) items[newIdx].classList.add('drag-over');
    }
  }

  function onDragEnd(e){
    clearTimeout(_scrollTimer);
    document.removeEventListener('touchmove',onDragMove);
    document.removeEventListener('touchend',onDragEnd);
    document.removeEventListener('touchcancel',onDragEnd);
    document.querySelectorAll('.drag-ghost').forEach(function(g){g.remove();});
    document.querySelectorAll('.pl-item').forEach(function(it){
      it.classList.remove('dragging','drag-over');
    });
    var from=_dg.fromIdx, to=_dg.toIdx;
    _dg.el=null; _dg.ghost=null; _dg.fromIdx=-1; _dg.toIdx=-1;
    if(from!==to && from>=0 && to>=0){
      fetch('/api/reorder',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({from:from,to:to})
      }).then(update);
    }
  }

  function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');}
  function playIdx(i){
    fetch('/api/play_index',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({i:i})}).then(update);
  }
  function api(action){
    fetch('/api/'+action,{method:'POST'}).then(function(){update();});
  }

  setInterval(update,2000);
  update();
</script>
</body>
</html>"""


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    r = Response(_HTML, mimetype='text/html')
    r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    r.headers['Pragma'] = 'no-cache'
    return r

@app.route('/api/status')
def status():
    return jsonify(_state)

@app.route('/api/toggle', methods=['POST'])
def toggle():
    _action_queue.put('toggle')
    return jsonify({'ok': True})

@app.route('/api/next', methods=['POST'])
def next_track():
    _action_queue.put('next')
    return jsonify({'ok': True})

@app.route('/api/prev', methods=['POST'])
def prev_track():
    _action_queue.put('prev')
    return jsonify({'ok': True})

@app.route('/api/play_index', methods=['POST'])
def play_index():
    i = request.json.get('i', 0) if request.is_json else 0
    _action_queue.put(('play_index', int(i)))
    return jsonify({'ok': True})

@app.route('/api/reorder', methods=['POST'])
def reorder():
    data = request.json if request.is_json else {}
    _action_queue.put(('reorder', int(data.get('from', 0)), int(data.get('to', 0))))
    return jsonify({'ok': True})

@app.route('/api/volume', methods=['POST'])
def set_volume():
    v = request.json.get('v', 0.8) if request.is_json else 0.8
    _action_queue.put(('volume', float(v)))
    return jsonify({'ok': True})

@app.route('/api/remove', methods=['POST'])
def remove_track():
    i = request.json.get('i', -1) if request.is_json else -1
    _action_queue.put(('remove', int(i)))
    return jsonify({'ok': True})

@app.route('/api/unplay', methods=['POST'])
def unplay_track():
    i = request.json.get('i', -1) if request.is_json else -1
    _action_queue.put(('unplay', int(i)))
    return jsonify({'ok': True})

@app.route('/api/play_next', methods=['POST'])
def play_next_track():
    i = request.json.get('i', -1) if request.is_json else -1
    _action_queue.put(('play_next', int(i)))
    return jsonify({'ok': True})

@app.route('/api/move_top', methods=['POST'])
def move_track_top():
    i = request.json.get('i', -1) if request.is_json else -1
    _action_queue.put(('move_top', int(i)))
    return jsonify({'ok': True})

@app.route('/api/move_bottom', methods=['POST'])
def move_track_bottom():
    i = request.json.get('i', -1) if request.is_json else -1
    _action_queue.put(('move_bottom', int(i)))
    return jsonify({'ok': True})


# ── Server lifecycle ──────────────────────────────────────────────────────────

_server_thread: threading.Thread | None = None
_running = False

def start(port: int = 8080):
    global _server_thread, _running
    if _running:
        return
    _running = True
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    def _run():
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    _server_thread = threading.Thread(target=_run, daemon=True)
    _server_thread.start()

def stop():
    global _running
    _running = False
    # Flask daemon thread dies with the process

def update_state(**kwargs):
    _state.update(kwargs)

def pop_action():
    """Devuelve la siguiente acción pendiente o None."""
    try:
        return _action_queue.get_nowait()
    except queue.Empty:
        return None
