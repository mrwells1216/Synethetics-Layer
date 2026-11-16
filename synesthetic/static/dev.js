/* Developer mode and the change log, for Settings.
 *
 * Developer mode is a layer over the app for fixing it. Highlight text and press Fix/idea; triple-click (or
 * triple-tap) for a screenshot window; the Dev button opens live requests, errors and state. Each note goes to the
 * fixes store (python fixes.py list) for the next Claude session. Off by default; nothing here runs on the page
 * until it is switched on, except a small record of recent requests and errors so the panel has history.
 *
 * Builds everything with DOM calls and textContent: no innerHTML, so nothing typed or read can become markup.
 */
(function(){
  'use strict';
  var ON_KEY = 'synapp.dev', DEV_KEY = 'synapp.devkey', PNG_LIMIT = 3900000;
  function lsGet(k){ try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v){ try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }

  // the dev link (#dev=KEY) links this device, before the app reads the address for its tab
  var paired = false, pm = /^#dev=([A-Za-z0-9_-]{16,128})$/.exec(location.hash);
  if (pm){
    lsSet(DEV_KEY, pm[1]); lsSet(ON_KEY, '1'); paired = true;
    try { history.replaceState(null, '', location.pathname + location.search + '#settings'); } catch (e) { location.hash = 'settings'; }
  }

  // ================= live record: requests, errors, warnings =================
  var LOG = [], subs = [], unseen = 0;
  function push(x){
    x.t = Date.now(); LOG.push(x); if (LOG.length > 200) LOG.shift();
    if (x.type === 'error') unseen++;
    subs.forEach(function(f){ try { f(x); } catch (e) {} });
  }
  function shortUrl(u){
    u = String(u || '');
    if (/^blob:/.test(u)) return 'blob:...';
    if (/^data:/.test(u)) return u.slice(0, 22) + '...';
    try { var x = new URL(u, location.href); return (x.origin === location.origin ? '' : x.origin) + x.pathname + (x.search ? x.search.slice(0, 60) : ''); }
    catch (e) { return u.slice(0, 120); }
  }
  var realFetch = window.fetch ? window.fetch.bind(window) : null;
  if (realFetch) window.fetch = function(input, init){
    var url = typeof input === 'string' ? input : (input && input.url) || String(input);
    var method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    var body = init && init.body, sent = body ? (body.size || body.byteLength || body.length || 0) : 0;
    var t0 = performance.now(), rec = {type: 'net', method: method, url: shortUrl(url), sent: sent};
    return realFetch(input, init).then(function(r){
      rec.status = r.status; rec.ok = r.ok; rec.ms = Math.round(performance.now() - t0);
      var len = r.headers.get('Content-Length'); rec.got = len ? +len : null;
      if (!r.ok) r.clone().text().then(function(t){ rec.note = t.slice(0, 300); push(rec); }, function(){ push(rec); });
      else push(rec);
      return r;
    }, function(e){
      rec.status = 0; rec.ok = false; rec.ms = Math.round(performance.now() - t0); rec.note = String(e && e.message || e); push(rec);
      throw e;
    });
  };
  window.addEventListener('error', function(e){
    var t = e.target;
    if (t && t !== window && t.tagName){ push({type: 'error', msg: 'Could not load ' + t.tagName.toLowerCase() + ' ' + shortUrl(t.currentSrc || t.src || t.href)}); return; }
    push({type: 'error', msg: String(e.message || 'Error'), where: (e.filename ? shortUrl(e.filename) : '') + (e.lineno ? ':' + e.lineno + ':' + e.colno : ''),
      stack: e.error && e.error.stack ? String(e.error.stack).slice(0, 1200) : ''});
  }, true);
  window.addEventListener('unhandledrejection', function(e){
    var r = e.reason; push({type: 'error', msg: 'Not handled: ' + String(r && r.message || r), stack: r && r.stack ? String(r.stack).slice(0, 1200) : ''});
  });
  function fmt(a){ if (a instanceof Error) return a.message; if (typeof a === 'object'){ try { return JSON.stringify(a).slice(0, 300); } catch (e) { return String(a); } } return String(a); }
  ['error', 'warn'].forEach(function(level){
    var orig = console[level]; if (!orig) return;
    console[level] = function(){
      try { push({type: level, msg: Array.prototype.map.call(arguments, fmt).join(' ').slice(0, 600), where: 'console'}); } catch (e) {}
      return orig.apply(console, arguments);
    };
  });

  // ================= helpers =================
  var root = document.documentElement, cfg = {}, app = {};
  function h(tag, props, kids){
    var e = document.createElement(tag);
    if (props) Object.keys(props).forEach(function(k){
      var v = props[k]; if (v == null || v === false) return;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k === 'style') e.style.cssText = v;
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    });
    (kids || []).forEach(function(c){ if (c != null && c !== false) e.append(c); });
    return e;
  }
  function ui(e){ e.setAttribute('data-devui', ''); return e; }
  function $(id){ return document.getElementById(id); }
  function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }
  function wait(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function toast(t){ if (app.toast) app.toast(t); }
  function isOn(){ return lsGet(ON_KEY) === '1'; }
  function devKey(){ return lsGet(DEV_KEY); }
  function tabNow(){ return app.tab ? app.tab() : location.hash.slice(1); }
  function when(iso){
    var d = new Date(iso); if (isNaN(d)) return iso || '';
    return d.toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric'}) + ', ' + d.toLocaleTimeString(undefined, {hour: 'numeric', minute: '2-digit'});
  }
  function clock(t){ var d = new Date(t); return [d.getHours(), d.getMinutes(), d.getSeconds()].map(function(n){ return (n < 10 ? '0' : '') + n; }).join(':'); }
  function size(n){ return n == null ? '' : n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB'; }

  function api(route, payload, asBlob){
    var hd = {'Content-Type': 'application/json', 'X-App': '1'}, k = devKey();
    if (k) hd['X-Dev-Key'] = k;
    return fetch('/api/' + route, {method: 'POST', headers: hd, body: JSON.stringify(payload || {})}).then(function(r){
      if (!r.ok) return r.text().then(function(t){ var e = new Error(t || ('Error ' + r.status)); e.status = r.status; throw e; });
      return asBlob ? r.blob() : r.json();
    });
  }
  function sectionOf(node){
    var e = node && (node.nodeType === 1 ? node : node.parentElement);
    if (!e) return tabNow();
    var ov = e.closest('#result,#roller,dialog');
    if (ov) return ov.id || 'dialog';
    var v = e.closest('section.view');
    return v ? v.id.replace(/^v-/, '') : tabNow();
  }
  function context(extra){
    var c = {viewport: [innerWidth, innerHeight], scroll: [Math.round(scrollX), Math.round(scrollY)], dpr: window.devicePixelRatio || 1,
      theme: root.getAttribute('data-theme'), tab: tabNow(), build: cfg.build || '', ua: navigator.userAgent.slice(0, 200),
      installed: !!((window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone)};
    Object.keys(extra || {}).forEach(function(k){ c[k] = extra[k]; });
    return c;
  }
  function send(entry){
    entry.page = location.pathname + (location.hash && !/^#dev=/.test(location.hash) ? location.hash : '');
    return api('fix-add', entry).then(function(r){ refreshFixes(); return r; });
  }

  // ================= styles =================
  var CSS = [
    '.dv-dock{position:fixed;left:calc(12px + env(safe-area-inset-left));bottom:calc(12px + env(safe-area-inset-bottom));z-index:2147482000;display:inline-flex;gap:7px;align-items:center;padding:8px 13px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--fg);font:750 13px/1 var(--font-body);letter-spacing:.08em;box-shadow:0 4px 14px rgba(0,0,0,.28);cursor:pointer}',
    '.dv-dock i{width:9px;height:9px;border-radius:50%;background:var(--spec)}',
    '.dv-badge{min-width:18px;padding:3px 5px;border-radius:9px;background:var(--c-warning);color:var(--on-warning);font-size:11px;text-align:center;letter-spacing:0}',
    '.dv-panel{position:fixed;z-index:2147482500;left:0;right:0;bottom:0;max-height:64vh;display:flex;flex-direction:column;background:var(--surface);color:var(--fg);border-top:1px solid var(--line);border-radius:18px 18px 0 0;box-shadow:0 -10px 30px rgba(0,0,0,.35);font:15px/1.45 var(--font-body);padding-bottom:env(safe-area-inset-bottom)}',
    '@media (min-width:900px){.dv-panel{left:auto;top:0;width:410px;max-height:none;border-radius:0;border-top:0;border-left:1px solid var(--line)}}',
    '.dv-head{display:flex;align-items:center;gap:8px;padding:12px 14px 8px}',
    '.dv-head h2{margin:0;font:650 1.15rem var(--font-head);flex:1}',
    '.dv-head small{color:var(--muted);font-size:12px}',
    '.dv-line{display:flex;gap:6px;flex-wrap:wrap;padding:0 14px 8px}',
    '.dv-body{overflow:auto;padding:4px 14px 16px;flex:1;min-height:0;overscroll-behavior:contain}',
    '.dv-btn{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;border:1px solid var(--line);background:var(--raised);color:var(--fg);font:650 14px/1.1 var(--font-body);white-space:nowrap}',
    '.dv-btn[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}',
    '.dv-btn:focus-visible,.dv-bar button:focus-visible{outline:2px solid var(--fg);outline-offset:2px}',
    '.dv-x{margin-left:auto}',
    '.dv-row{padding:7px 0;border-bottom:1px solid var(--line);font-size:13px;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:start}',
    '.dv-row time{color:var(--muted);font-variant-numeric:tabular-nums}',
    '.dv-row .t{word-break:break-word}',
    '.dv-row.error .t{color:var(--c-warning)}',
    '.dv-row.warn .t{color:var(--c-date)}',
    '.dv-row pre{margin:4px 0 0;white-space:pre-wrap;font:12px/1.4 ui-monospace,Consolas,monospace;color:var(--muted)}',
    '.dv-row .dv-btn{padding:4px 9px;font-size:12px}',
    '.dv-kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 12px;font-size:13px;margin:6px 0 12px}',
    '.dv-kv dt{color:var(--muted)} .dv-kv dd{margin:0;word-break:break-word}',
    '.dv-empty{color:var(--muted);font-size:14px}',
    '.dv-bar{position:fixed;z-index:2147482600;display:flex;gap:2px;padding:4px;border-radius:999px;background:var(--fg);color:var(--bg);box-shadow:0 6px 18px rgba(0,0,0,.3)}',
    '.dv-bar button{all:unset;cursor:pointer;padding:7px 12px;border-radius:999px;font:750 14px/1 var(--font-body)}',
    '.dv-bar button:hover{background:color-mix(in srgb,var(--bg) 18%,transparent)}',
    '.dv-dim{position:fixed;inset:0;z-index:2147482700;pointer-events:none;background:rgba(0,0,0,.5)}',
    '.dv-frame{position:fixed;z-index:2147482800;border:2px dashed #fff;outline:1px solid rgba(0,0,0,.75);box-shadow:inset 0 0 0 1px rgba(0,0,0,.45);touch-action:none;cursor:move;box-sizing:border-box}',
    '.dv-h{position:absolute;width:30px;height:30px;touch-action:none}',
    '.dv-h::after{content:"";position:absolute;left:9px;top:9px;width:12px;height:12px;background:#fff;border:1px solid #000;border-radius:3px}',
    '.dv-h[data-c=nw]{left:-16px;top:-16px;cursor:nwse-resize}.dv-h[data-c=ne]{right:-16px;top:-16px;cursor:nesw-resize}',
    '.dv-h[data-c=sw]{left:-16px;bottom:-16px;cursor:nesw-resize}.dv-h[data-c=se]{right:-16px;bottom:-16px;cursor:nwse-resize}',
    '.dv-shot{position:fixed;z-index:2147482900;width:min(300px,calc(100vw - 16px));box-sizing:border-box;background:var(--surface);color:var(--fg);border:1px solid var(--line);border-radius:16px;padding:12px;box-shadow:0 12px 30px rgba(0,0,0,.4);font:15px/1.45 var(--font-body)}',
    '.dv-shot h3,.dv-note h3{margin:0;font:650 1.1rem var(--font-head);flex:1}',
    '.dv-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}',
    '.dv-shot p.hint,.dv-note p.hint{margin:0 0 8px;font-size:13px;color:var(--muted)}',
    '.dv-shot textarea,.dv-note textarea{display:block;box-sizing:border-box;width:100%;min-height:72px;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--fg);font:inherit;resize:vertical}',
    '.dv-marks{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}',
    '.dv-st{min-height:1.3em;font-size:13px;color:var(--muted);margin:8px 0 0}',
    '.dv-note{border:1px solid var(--line);border-radius:18px;background:var(--surface);color:var(--fg);padding:16px;width:min(460px,calc(100vw - 24px));box-sizing:border-box;font:15px/1.45 var(--font-body)}',
    '.dv-note::backdrop{background:rgba(0,0,0,.5)}',
    '.dv-note blockquote,.dv-fix blockquote{margin:8px 0;padding:6px 10px;border-left:3px solid var(--c-quote);background:var(--bg);border-radius:6px;font-size:14px;max-height:9em;overflow:auto;white-space:pre-wrap}',
    '.dv-fix{padding:10px 0;border-bottom:1px solid var(--line)} .dv-fix:last-child{border-bottom:0} .dv-fix p{margin:5px 0}',
    '.dv-chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:var(--muted)}',
    '.dv-chip{padding:2px 8px;border-radius:999px;border:1px solid var(--line);font-weight:750;color:var(--fg)}',
    '.dv-chip.open{border-color:var(--c-date)} .dv-chip.done{border-color:var(--c-link)} .dv-chip.skipped{border-color:var(--muted);color:var(--muted)}',
    '.dv-review{font-size:14px} .dv-review b{color:var(--c-link)}',
    '.dv-fix img{display:block;max-width:100%;border-radius:8px;border:1px solid var(--line);margin-top:6px}',
    '.dv-link{all:unset;cursor:pointer;color:var(--muted);font-weight:650;text-decoration:underline;text-underline-offset:3px}',
    '.lg-item{padding:11px 0;border-bottom:1px solid var(--line)} .lg-item:last-child{border-bottom:0}',
    '.lg-top{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;font-size:12px;color:var(--muted)}',
    '.lg-tag{display:inline-flex;align-items:center;gap:5px;font-weight:750;letter-spacing:.08em;text-transform:uppercase;color:var(--fg)}',
    '.lg-tag i{width:9px;height:9px;border-radius:50%;background:var(--k)}',
    '.lg-top a{color:var(--muted);font-family:ui-monospace,Consolas,monospace}',
    '.lg-title{display:block;margin:4px 0 0;font-size:15.5px;font-weight:700}',
    '.lg-item details{margin-top:4px;font-size:14px;color:var(--muted)} .lg-item summary{cursor:pointer;font-weight:650;width:max-content}',
    '.lg-item details p{margin:6px 0}',
    '#log-tags{margin:8px 0 4px}'
  ].join('\n');

  // ================= start =================
  document.addEventListener('DOMContentLoaded', function(){
    try { cfg = JSON.parse($('cfg').textContent); } catch (e) { cfg = {}; }
    app = window.synApp || {};
    document.head.appendChild(h('style', {id: 'dev-css', text: CSS}));
    settingsCard();
    changelogCard();
    setOn(isOn(), true);
    if (paired) setTimeout(function(){ toast('This device is linked. Developer mode is on.'); }, 400);
  });

  var dock = null, panel = null;
  function setOn(on, quiet){
    lsSet(ON_KEY, on ? '1' : '0');
    root.classList.toggle('dev-on', on);
    var sw = $('set-dev'); if (sw) sw.checked = on;
    var more = $('dev-more'); if (more) more.hidden = !on;
    if (on){ makeDock(); dock.hidden = false; devStatus(); refreshFixes(); }
    else { if (dock) dock.hidden = true; closePanel(); hideBar(); closeShot(); }
    if (!quiet) toast(on ? 'Developer mode on' : 'Developer mode off');
  }

  // ================= Settings: the developer card =================
  function settingsCard(){
    var sw = $('set-dev'); if (!sw) return;
    sw.addEventListener('change', function(){ setOn(this.checked); });
    $('dev-shot').addEventListener('click', function(){ openShot(innerWidth / 2, innerHeight / 2); });
    $('dev-panel').addEventListener('click', function(){ openPanel('live'); });
    $('dev-refresh').addEventListener('click', refreshFixes);
    $('dev-unlink').addEventListener('click', function(){
      lsSet(DEV_KEY, null); devStatus(); toast('This device is no longer linked');
    });
  }
  function devStatus(){
    var s = $('dev-status'); if (!s) return;
    var d = cfg.dev || {}, linked = !!devKey();
    $('dev-unlink').hidden = !linked;
    function say(t){ s.textContent = t; }
    if (d.store === 'local') return say('Fixes save on this computer, in the local data folder. Claude reads them with python fixes.py list.');
    if (d.store !== 'blob') return say('Fix storage isn’t connected to this site yet, so fixes can’t be saved here.');
    if (!d.keyed) return say('Developer mode isn’t set up on this site yet (no dev key on the server).');
    if (!linked) return say('This device isn’t linked. Open your dev link on it once, and fixes will save for Claude.');
    say('Checking the link...');
    api('fix-check').then(function(){ say('Linked. Fixes save to the private store, and Claude reads them with python fixes.py list.'); },
      function(e){ say(e.message); });
  }

  // ================= fixes list (Settings card and the panel) =================
  var MARK = {good: '✓ Good', bad: '✕ Not good', fix: 'Fix/idea'};
  var STATUS = {open: 'Waiting for Claude', done: 'Done', skipped: 'Not done'};
  function refreshFixes(){
    var boxes = [$('dev-fixes'), panel && panel.querySelector('[data-fixes]')].filter(Boolean);
    if (!boxes.length || !isOn()) return;
    var d = cfg.dev || {};
    if (d.store === 'none' || (d.store === 'blob' && (!d.keyed || !devKey()))){
      boxes.forEach(function(b){ b.textContent = ''; });
      return;
    }
    boxes.forEach(function(b){ b.textContent = ''; b.append(h('p', {class: 'dv-empty', text: 'Loading your fixes...'})); });
    api('fix-list').then(function(res){
      boxes.forEach(function(b){ fillFixes(b, res.entries || []); });
    }, function(e){
      boxes.forEach(function(b){ b.textContent = ''; b.append(h('p', {class: 'dv-empty', text: 'Could not load fixes: ' + e.message})); });
    });
  }
  function fillFixes(box, list){
    box.textContent = '';
    if (!list.length){ box.append(h('p', {class: 'dv-empty', text: 'Nothing yet. Highlight text and press Fix/idea, or triple-click for a screenshot.'})); return; }
    var open = list.filter(function(e){ return e.status === 'open'; }).length;
    box.append(h('p', {class: 'dv-empty', text: list.length + (list.length === 1 ? ' entry' : ' entries') + ', ' + open + ' waiting for Claude.'}));
    list.forEach(function(e){
      var row = h('div', {class: 'dv-fix', 'data-plain': ''});
      var picBtn = e.picture ? h('button', {class: 'dv-link', text: 'Picture', type: 'button'}) : null;
      row.append(h('div', {class: 'dv-chips'}, [
        h('span', {class: 'dv-chip', text: MARK[e.mark] || e.mark}),
        h('span', {class: 'dv-chip ' + e.status, text: STATUS[e.status] || e.status}),
        picBtn, h('span', {text: when(e.made) + (e.section ? ' · ' + e.section : '')})
      ]));
      if (e.note) row.append(h('p', {text: e.note}));
      if (e.text) row.append(h('blockquote', {text: e.text.length > 400 ? e.text.slice(0, 400) + '...' : e.text}));
      if (e.review) row.append(h('p', {class: 'dv-review'}, [h('b', {text: 'Claude: '}), e.review]));
      if (picBtn) picBtn.addEventListener('click', function(){
        var shown = row.querySelector('img');
        if (shown){ shown.remove(); return; }
        picBtn.textContent = 'Loading...';
        api('fix-image', {ref: e.ref}, true).then(function(b){
          row.append(h('img', {src: URL.createObjectURL(b), alt: 'Screenshot from ' + when(e.made)})); picBtn.textContent = 'Picture';
        }, function(err){ picBtn.textContent = 'Picture'; toast(err.message); });
      });
      box.append(row);
    });
  }

  // ================= the Dev button and live panel =================
  function makeDock(){
    if (dock) return;
    dock = ui(h('button', {class: 'dv-dock', type: 'button', 'aria-label': 'Developer panel'}, [h('i'), 'DEV', h('span', {class: 'dv-badge', hidden: true})]));
    dock.addEventListener('click', function(){ if (panel) closePanel(); else openPanel('live'); });
    document.body.appendChild(dock);
    subs.push(function(){ badge(); });
    badge();
  }
  function badge(){
    if (!dock) return;
    var b = dock.querySelector('.dv-badge');
    b.hidden = !unseen; b.textContent = unseen > 99 ? '99+' : String(unseen);
  }
  var panelTab = 'live', liveT = null;
  function openPanel(tab){
    panelTab = tab || panelTab;
    if (!panel){
      var body = h('div', {class: 'dv-body'});
      var tabs = h('div', {class: 'dv-line', role: 'tablist'});
      [['live', 'Live'], ['fixes', 'Fixes'], ['state', 'State']].forEach(function(t){
        var b = h('button', {class: 'dv-btn', type: 'button', 'data-v': t[0], text: t[1]});
        b.addEventListener('click', function(){ panelTab = t[0]; drawPanel(); });
        tabs.append(b);
      });
      var shotB = h('button', {class: 'dv-btn', type: 'button', text: 'Screenshot'});
      shotB.addEventListener('click', function(){ closePanel(); openShot(innerWidth / 2, innerHeight / 2); });
      var ideaB = h('button', {class: 'dv-btn', type: 'button', text: 'Note an idea'});
      ideaB.addEventListener('click', function(){ openNote({kind: 'shot', title: 'An idea', section: tabNow(), context: {picture: 'not drawn: idea only'}}); });
      var x = h('button', {class: 'dv-btn dv-x', type: 'button', 'aria-label': 'Close', text: '✕ Close'});
      x.addEventListener('click', closePanel);
      panel = ui(h('div', {class: 'dv-panel', role: 'dialog', 'aria-label': 'Developer'}, [
        h('div', {class: 'dv-head'}, [h('h2', {text: 'Developer'}), h('small', {text: cfg.build ? 'build ' + cfg.build : ''}), x]),
        tabs, h('div', {class: 'dv-line'}, [shotB, ideaB]), body]));
      panel._body = body; panel._tabs = tabs;
      document.body.appendChild(panel);
      subs.push(function(){ if (panel && panelTab === 'live'){ clearTimeout(liveT); liveT = setTimeout(drawPanel, 250); } });
    }
    drawPanel();
  }
  function closePanel(){ if (panel){ panel.remove(); panel = null; } }
  function drawPanel(){
    if (!panel) return;
    panel._tabs.querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-v') === panelTab ? 'true' : 'false'); });
    var body = panel._body; body.textContent = '';
    if (panelTab === 'live'){
      unseen = 0; badge();
      var clearB = h('button', {class: 'dv-btn', type: 'button', text: 'Clear'});
      clearB.addEventListener('click', function(){ LOG.length = 0; drawPanel(); });
      body.append(h('div', {class: 'dv-line', style: 'padding:0 0 6px'}, [h('span', {class: 'dv-empty', style: 'flex:1', text: 'Requests, errors and warnings as they happen, newest first.'}), clearB]));
      if (!LOG.length){ body.append(h('p', {class: 'dv-empty', text: 'Nothing yet. Use the app and it shows up here.'})); return; }
      LOG.slice().reverse().slice(0, 120).forEach(function(x){ body.append(liveRow(x)); });
    } else if (panelTab === 'fixes'){
      var refreshB = h('button', {class: 'dv-btn', type: 'button', text: 'Refresh'});
      refreshB.addEventListener('click', refreshFixes);
      body.append(h('div', {class: 'dv-line', style: 'padding:0 0 6px'}, [h('span', {class: 'dv-empty', style: 'flex:1', text: 'What you sent, and what Claude did with it.'}), refreshB]));
      body.append(h('div', {'data-fixes': ''}));
      refreshFixes();
    } else {
      var st = stateNow(), dl = h('dl', {class: 'dv-kv'});
      Object.keys(st).forEach(function(k){ dl.append(h('dt', {text: k}), h('dd', {text: typeof st[k] === 'object' ? JSON.stringify(st[k]) : String(st[k])})); });
      var copyB = h('button', {class: 'dv-btn', type: 'button', text: 'Copy'});
      copyB.addEventListener('click', function(){
        var txt = JSON.stringify(stateNow(), null, 2);
        (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function(){ toast('Copied'); }, function(){ toast('Could not copy here'); });
      });
      var noteB = h('button', {class: 'dv-btn', type: 'button', text: 'Send to Claude'});
      noteB.addEventListener('click', function(){ openNote({kind: 'text', title: 'Send the state', text: JSON.stringify(stateNow(), null, 1), section: tabNow(), context: {picture: 'not drawn: state'}}); });
      body.append(dl, h('div', {class: 'dv-line', style: 'padding:0'}, [copyB, noteB]));
    }
  }
  function liveRow(x){
    var text, cls = x.type;
    if (x.type === 'net'){
      text = x.method + ' ' + x.url + '  ' + (x.status || 'failed') + ' · ' + x.ms + ' ms' + (x.sent ? ' · sent ' + size(x.sent) : '') + (x.got ? ' · got ' + size(x.got) : '');
      if (!x.ok) cls = 'error';
    } else text = x.msg + (x.where ? '  (' + x.where + ')' : '');
    var mid = h('div', {class: 't'}, [text]);
    if (x.note) mid.append(h('pre', {text: x.note}));
    if (x.stack) mid.append(h('pre', {text: x.stack}));
    var fixB = null;
    if (cls === 'error' || cls === 'warn'){
      fixB = h('button', {class: 'dv-btn', type: 'button', text: 'Fix/idea'});
      fixB.addEventListener('click', function(){ openNote({kind: 'text', title: 'About this error', text: text + (x.note ? '\n' + x.note : '') + (x.stack ? '\n' + x.stack : ''), section: tabNow(), context: {picture: 'not drawn: from the live panel', at: new Date(x.t).toISOString()}}); });
    }
    return h('div', {class: 'dv-row ' + cls}, [h('time', {text: clock(x.t)}), mid, fixB]);
  }
  function stateNow(){
    var s = {};
    s.tab = tabNow(); s.build = cfg.build || '(unknown)';
    s.viewport = innerWidth + ' × ' + innerHeight + ' at ' + (window.devicePixelRatio || 1) + 'x';
    s.scroll = Math.round(scrollX) + ', ' + Math.round(scrollY);
    s.theme = root.getAttribute('data-theme'); s.online = navigator.onLine;
    s.installed = context().installed;
    s.storage = (cfg.dev || {}).store + (devKey() ? ', linked' : ', not linked');
    s.hosted = !!cfg.hosted; s.grammar = !!cfg.grammar;
    s['max file'] = size(cfg.maxBytes);
    s.errors = LOG.filter(function(x){ return x.type === 'error'; }).length;
    s.requests = LOG.filter(function(x){ return x.type === 'net'; }).length;
    try { var style = JSON.parse(lsGet('synapp.style') || 'null'); if (style) s.style = {mode: style.mode, palette: style.palette, theme: style.theme, body: style.body, heading: style.heading, size: style.size, hl: style.hl, wordbank: style.wordbank ? (style.wordbank.on ? 'on' : 'off') + ', ' + (style.wordbank.words || []).length + ' words' : 'none'}; } catch (e) {}
    s.browser = navigator.userAgent;
    return s;
  }

  // ================= note dialog =================
  var noteD = null, noteOpts = null;
  function openNote(opts){
    noteOpts = opts;
    if (!noteD){
      var ta = h('textarea', {placeholder: 'What should change, or your idea', 'aria-label': 'Your note', rows: '4'});
      var st = h('p', {class: 'dv-st', role: 'status'});
      var save = h('button', {class: 'dv-btn', type: 'button', text: 'Save'});
      var cancel = h('button', {class: 'dv-btn', type: 'button', text: 'Cancel'});
      var x = h('button', {class: 'dv-btn', type: 'button', 'aria-label': 'Close', text: '✕'});
      noteD = ui(h('dialog', {class: 'dv-note', 'aria-label': 'Fix or idea'}, [
        h('div', {class: 'dv-top'}, [h('h3'), x]),
        h('p', {class: 'hint', text: 'Saved for the next Claude session, which makes the change and reports back here. ' + (/Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl') + '+Enter saves.'}),
        h('blockquote'), ta, h('div', {class: 'dv-marks'}, [save, cancel]), st]));
      document.body.appendChild(noteD);
      noteD._ta = ta; noteD._st = st;
      function close(){ noteD.close(); }
      x.addEventListener('click', close); cancel.addEventListener('click', close);
      save.addEventListener('click', saveNote);
      noteD.addEventListener('keydown', function(e){
        if (e.key === 'Escape'){ e.stopPropagation(); }
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); saveNote(); }
      });
    }
    noteD.querySelector('h3').textContent = opts.title || 'Fix or idea';
    var q = noteD.querySelector('blockquote');
    q.hidden = !opts.text; q.textContent = opts.text ? (opts.text.length > 900 ? opts.text.slice(0, 900) + '...' : opts.text) : '';
    noteD._ta.value = ''; noteD._st.textContent = '';
    if (!noteD.open) noteD.showModal();
    noteD._ta.focus();
  }
  function saveNote(){
    var o = noteOpts, note = noteD._ta.value.trim(), st = noteD._st;
    if (!note){ st.textContent = 'Write what should change, or your idea.'; noteD._ta.focus(); return; }
    st.textContent = 'Saving...';
    send({kind: o.kind, mark: o.mark || 'fix', note: note, text: (o.text || '').slice(0, 4000), section: o.section || tabNow(), context: context(o.context)})
      .then(function(){ noteD.close(); toast('Saved for Claude'); }, function(e){ st.textContent = e.message; });
  }

  // ================= highlight -> Fix/idea =================
  var bar = null, barSel = null, dismissed = '';
  function hideBar(){ if (bar) bar.hidden = true; barSel = null; }
  function checkSel(){
    if (!isOn() || shot || (noteD && noteD.open)) return hideBar();
    var s = window.getSelection();
    if (!s || s.isCollapsed || !s.rangeCount) return hideBar();
    var txt = s.toString().trim();
    if (txt.length < 2 || txt === dismissed) return hideBar();
    var r = s.getRangeAt(0), n = r.commonAncestorContainer, e = n.nodeType === 1 ? n : n.parentElement;
    if (!e || e.closest('[data-devui],input,textarea,select,[contenteditable]:not([contenteditable=false]),#ro-stage')) return hideBar();
    var rect = r.getBoundingClientRect();
    if (!rect.width && !rect.height) return hideBar();
    if (!bar){
      var fixB = h('button', {type: 'button', text: 'Fix/idea'}), closeB = h('button', {type: 'button', 'aria-label': 'Close', text: '✕'});
      bar = ui(h('div', {class: 'dv-bar', role: 'toolbar', 'aria-label': 'Fix or idea'}, [fixB, closeB]));
      // keep the selection when the bar is pressed
      bar.addEventListener('mousedown', function(ev){ ev.preventDefault(); });
      fixB.addEventListener('click', function(){
        var sel = barSel; hideBar(); if (!sel) return;
        openNote({kind: 'text', title: 'Fix or idea', text: sel.text, section: sel.section, context: {picture: 'not drawn: highlight'}});
      });
      closeB.addEventListener('click', function(){ dismissed = barSel ? barSel.text : ''; hideBar(); });
      document.body.appendChild(bar);
    }
    barSel = {text: txt.slice(0, 4000), section: sectionOf(e)};
    bar.hidden = false;
    var bw = bar.offsetWidth || 150, bh = bar.offsetHeight || 40;
    // phones show their own Copy menu above a selection, so there the bar goes below it
    var coarse = window.matchMedia && matchMedia('(pointer: coarse)').matches;
    var top = coarse ? rect.bottom + 14 : rect.top - bh - 10;
    if (coarse ? top + bh > innerHeight - 8 : top < 8) top = coarse ? rect.top - bh - 14 : rect.bottom + 10;
    bar.style.top = clamp(top, 8, innerHeight - bh - 8) + 'px';
    bar.style.left = clamp(rect.left + rect.width / 2 - bw / 2, 8, innerWidth - bw - 8) + 'px';
  }
  var selT = null;
  document.addEventListener('selectionchange', function(){ if (!isOn()) return; clearTimeout(selT); selT = setTimeout(checkSel, 220); });
  window.addEventListener('scroll', function(){ if (bar && !bar.hidden){ clearTimeout(selT); selT = setTimeout(checkSel, 60); } }, {passive: true, capture: true});

  // ================= triple-click / triple-tap -> screenshot =================
  var SKIP = 'input,textarea,select,button,a,label,dialog,summary,[contenteditable]:not([contenteditable=false]),[data-devui]';
  document.addEventListener('mousedown', function(e){
    if (!isOn() || shot || e.button !== 0 || e.detail !== 3) return;
    if (e.target.closest && e.target.closest(SKIP)) return;
    e.preventDefault();  // no paragraph selection
    var s = window.getSelection(); if (s) s.removeAllRanges();
    openShot(e.clientX, e.clientY);
  }, true);
  var taps = [];
  document.addEventListener('pointerup', function(e){
    if (!isOn() || shot || e.pointerType !== 'touch') return;
    if (e.target.closest && e.target.closest(SKIP)){ taps = []; return; }
    var now = Date.now();
    taps = taps.filter(function(t){ return now - t.t < 900 && Math.abs(t.x - e.clientX) < 30 && Math.abs(t.y - e.clientY) < 30; });
    taps.push({t: now, x: e.clientX, y: e.clientY});
    if (taps.length >= 3){ taps = []; var s = window.getSelection(); if (s) s.removeAllRanges(); openShot(e.clientX, e.clientY); }
  }, true);

  var shot = null;
  function vw(){ return document.documentElement.clientWidth || innerWidth; }
  function vh(){ return innerHeight; }
  function openShot(cx, cy){
    if (shot || !isOn()) return;
    hideBar();
    var w = Math.min(420, vw() - 32), hh = Math.min(260, Math.round(vh() * 0.4));
    shot = {x: clamp(cx - w / 2, 8, vw() - w - 8), y: clamp(cy - hh / 2, 8, vh() - hh - 8), w: w, h: hh};
    shot.dim = ui(h('div', {class: 'dv-dim', 'aria-hidden': 'true'}));
    shot.frame = ui(h('div', {class: 'dv-frame', 'aria-label': 'Screenshot frame. Drag to move, corners to resize.'},
      ['nw', 'ne', 'sw', 'se'].map(function(c){ return h('div', {class: 'dv-h', 'data-c': c}); })));
    var ta = h('textarea', {placeholder: 'Comment (optional)', 'aria-label': 'Comment', rows: '3'});
    var st = h('p', {class: 'dv-st', role: 'status'});
    var x = h('button', {class: 'dv-btn', type: 'button', 'aria-label': 'Close without saving', text: '✕'});
    x.addEventListener('click', closeShot);
    var marks = h('div', {class: 'dv-marks'}, [['good', '✓ Good'], ['bad', '✕ Not good'], ['fix', 'Fix/idea']].map(function(m){
      var b = h('button', {class: 'dv-btn', type: 'button', text: m[1], title: {good: 'Keep it like this', bad: 'Not good', fix: 'Something to change, or an idea'}[m[0]]});
      b.addEventListener('click', function(){ saveShot(m[0]); });
      return b;
    }));
    shot.panel = ui(h('div', {class: 'dv-shot', role: 'dialog', 'aria-label': 'Screenshot'}, [
      h('div', {class: 'dv-top'}, [h('h3', {text: 'Screenshot'}), x]),
      h('p', {class: 'hint', text: 'Drag the frame, or a corner to resize it. The page still scrolls. Pressing a mark saves.'}),
      ta, marks, st]));
    shot.ta = ta; shot.st = st;
    [shot.dim, shot.frame, shot.panel].forEach(function(e){ document.body.appendChild(e); });
    dragging(shot.frame);
    layout();
  }
  function closeShot(){
    if (!shot) return;
    [shot.dim, shot.frame, shot.panel].forEach(function(e){ e.remove(); });
    shot = null;
  }
  var DIM_PATH = null;
  function layout(){
    if (!shot) return;
    if (DIM_PATH === null) DIM_PATH = !!(window.CSS && CSS.supports && CSS.supports('clip-path', 'path(evenodd, "M0 0H10V10H0Z")'));
    var W = vw(), H = vh();
    shot.w = Math.min(shot.w, W - 16); shot.h = Math.min(shot.h, H - 16);
    shot.x = clamp(shot.x, 0, W - shot.w); shot.y = clamp(shot.y, 0, H - shot.h);
    var f = shot.frame.style;
    f.left = shot.x + 'px'; f.top = shot.y + 'px'; f.width = shot.w + 'px'; f.height = shot.h + 'px';
    if (DIM_PATH) shot.dim.style.clipPath = 'path(evenodd, "M0 0H' + W + 'V' + H + 'H0Z M' + shot.x + ' ' + shot.y + 'h' + shot.w + 'v' + shot.h + 'h' + (-shot.w) + 'Z")';
    else shot.dim.style.background = 'rgba(0,0,0,.18)';
    // the panel sits beside the frame: right, left, below, above, else over the bottom
    var p = shot.panel, pw = p.offsetWidth, ph = p.offsetHeight, px, py;
    if (shot.x + shot.w + 12 + pw <= W - 8){ px = shot.x + shot.w + 12; py = clamp(shot.y, 8, H - ph - 8); }
    else if (shot.x - 12 - pw >= 8){ px = shot.x - 12 - pw; py = clamp(shot.y, 8, H - ph - 8); }
    else if (shot.y + shot.h + 12 + ph <= H - 8){ py = shot.y + shot.h + 12; px = clamp(shot.x, 8, W - pw - 8); }
    else if (shot.y - 12 - ph >= 8){ py = shot.y - 12 - ph; px = clamp(shot.x, 8, W - pw - 8); }
    else { px = clamp((W - pw) / 2, 8, W - pw - 8); py = H - ph - 8; }
    p.style.left = px + 'px'; p.style.top = py + 'px';
  }
  window.addEventListener('resize', function(){ if (shot) layout(); });
  function dragging(frame){
    var drag = null;
    frame.addEventListener('pointerdown', function(e){
      if (e.button !== 0) return;
      e.preventDefault();
      var c = e.target.getAttribute && e.target.getAttribute('data-c');
      drag = {c: c, sx: e.clientX, sy: e.clientY, x: shot.x, y: shot.y, w: shot.w, h: shot.h, id: e.pointerId};
      try { frame.setPointerCapture(e.pointerId); } catch (err) {}
    });
    frame.addEventListener('pointermove', function(e){
      if (!drag || e.pointerId !== drag.id || !shot) return;
      var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy, W = vw(), H = vh(), MINW = 60, MINH = 40;
      if (!drag.c){ shot.x = clamp(drag.x + dx, 0, W - shot.w); shot.y = clamp(drag.y + dy, 0, H - shot.h); }
      else {
        var x1 = drag.x, y1 = drag.y, x2 = drag.x + drag.w, y2 = drag.y + drag.h;
        if (drag.c.indexOf('w') >= 0) x1 = clamp(drag.x + dx, 0, x2 - MINW); else x2 = clamp(x2 + dx, x1 + MINW, W);
        if (drag.c.indexOf('n') >= 0) y1 = clamp(drag.y + dy, 0, y2 - MINH); else y2 = clamp(y2 + dy, y1 + MINH, H);
        shot.x = x1; shot.y = y1; shot.w = x2 - x1; shot.h = y2 - y1;
      }
      layout();
    });
    function end(e){ if (drag && e.pointerId === drag.id) drag = null; }
    frame.addEventListener('pointerup', end); frame.addEventListener('pointercancel', end);
  }
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && shot){ e.preventDefault(); e.stopImmediatePropagation(); closeShot(); }
  }, true);

  function uiQuiet(on){
    if (!shot) return;
    [shot.frame, shot.panel].forEach(function(e){ e.style.pointerEvents = on ? 'none' : ''; });
  }
  function saveShot(mark){
    if (!shot || shot.busy) return;
    var s = shot, note = s.ta.value.trim();
    var region = {x: Math.round(s.x), y: Math.round(s.y), w: Math.round(s.w), h: Math.round(s.h)};
    s.busy = true; s.st.textContent = 'Reading the text...';
    uiQuiet(true);
    var text = '', section = tabNow();
    try {
      text = textUnder(document, region);
      section = sectionOf(document.elementFromPoint(region.x + region.w / 2, region.y + region.h / 2));
    } catch (e) {}
    uiQuiet(false);
    s.st.textContent = 'Drawing the picture...';
    snapshot(region).then(function(png){ return {png: png, why: ''}; }, function(e){ return {png: null, why: String(e && (e.message || e.name) || e)}; })
      .then(function(r){
        if (!r.png && !text && !note){ throw new Error('Nothing to save: add a comment.'); }
        var payload = {kind: 'shot', mark: mark, note: note, text: text, section: section, image: r.png,
          context: context({region: [region.x, region.y, region.w, region.h], picture: r.png ? 'drawn' : 'not drawn: ' + r.why})};
        s.st.textContent = 'Saving...';
        return send(payload).then(function(res){ return {res: res, pic: !!r.png}; }, function(err){
          if (!r.png) throw err;
          payload.image = null; payload.context.picture = 'not drawn: ' + (err.message || 'refused').slice(0, 120);
          return send(payload).then(function(res){ return {res: res, pic: false}; });
        });
      })
      .then(function(o){
        if (shot !== s) return;
        s.st.textContent = o.pic ? 'Saved.' : 'Saved without a picture (this browser could not draw it).';
        toast(o.pic ? 'Saved for Claude' : 'Saved for Claude, without a picture');
        setTimeout(function(){ if (shot === s) closeShot(); }, o.pic ? 600 : 1800);
      }, function(e){ if (shot === s){ s.busy = false; s.st.textContent = e.message; } });
  }

  // the visible text under the frame: only text whose own element is what's actually showing there
  function textUnder(doc, region){
    var out = [], walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, {acceptNode: function(n){
      if (!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      var p = n.parentElement;
      if (!p || p.closest('script,style,noscript,[data-devui]')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    var range = doc.createRange(), n, total = 0, W = vw(), H = vh();
    while ((n = walker.nextNode()) && total < 4000){
      range.selectNodeContents(n);
      var rects = range.getClientRects();
      for (var i = 0; i < rects.length; i++){
        var r = rects[i];
        var x1 = Math.max(r.left, region.x, 0), y1 = Math.max(r.top, region.y, 0), x2 = Math.min(r.right, region.x + region.w, W), y2 = Math.min(r.bottom, region.y + region.h, H);
        if (x2 - x1 < 2 || y2 - y1 < 2) continue;
        var hit = doc.elementFromPoint((x1 + x2) / 2, (y1 + y2) / 2);
        if (hit && (hit === n.parentElement || n.parentElement.contains(hit))){
          var t = n.nodeValue.replace(/\s+/g, ' ').trim(); out.push(t); total += t.length + 1;
          break;
        }
      }
    }
    return out.join(' ').slice(0, 4000);
  }

  // ================= drawing the page into a PNG =================
  // A page can't photograph itself without a screen-share prompt, so it draws a copy of itself: the body is
  // cloned, its CSS settled against the live page, and the lot drawn through an SVG <foreignObject>.
  function snapshot(region){
    return snapDoc(window, region, 0, true);
  }
  function setImp(el, props){ Object.keys(props).forEach(function(k){ el.style.setProperty(k, props[k], 'important'); }); }
  function snapDoc(win, region, depth, top){
    var doc = win.document, body = doc.body, html = doc.documentElement;
    var sx = win.scrollX || 0, sy = win.scrollY || 0;
    var W = Math.max(html.clientWidth, 1), H = Math.ceil(region.y + sy + region.h);
    var orig = [body].concat(Array.prototype.slice.call(body.querySelectorAll('*')));
    var copy = body.cloneNode(true);
    var cl = [copy].concat(Array.prototype.slice.call(copy.querySelectorAll('*')));
    var drop = [], swaps = [], waits = [], fixed = new Map();
    for (var i = 0; i < orig.length && i < cl.length; i++){
      (function(o, c){
        var tag = o.tagName;
        if (tag === 'SCRIPT' || tag === 'NOSCRIPT' || tag === 'STYLE' || tag === 'LINK' || tag === 'TEMPLATE' || o.hasAttribute('data-devui')){ drop.push(c); return; }
        if (tag === 'DIALOG' && !o.open){ drop.push(c); return; }
        var cs = win.getComputedStyle(o);
        if (cs.display === 'none') return;
        var pos = cs.position;
        if (pos === 'fixed'){
          var r = o.getBoundingClientRect(), anc = null, p = o.parentElement;
          while (p){ if (fixed.has(p)){ anc = fixed.get(p); break; } p = p.parentElement; }
          var left = anc ? r.left - anc.left - anc.cl : r.left + sx, topY = anc ? r.top - anc.top - anc.ct : r.top + sy;
          fixed.set(o, {left: r.left, top: r.top, cl: o.clientLeft, ct: o.clientTop});
          setImp(c, {position: 'absolute', inset: 'auto', left: left + 'px', top: topY + 'px', width: r.width + 'px', height: r.height + 'px', margin: '0', transform: 'none', translate: 'none'});
        } else if (pos === 'sticky'){
          var r1 = o.getBoundingClientRect(), prev = o.style.getPropertyValue('position'), prevP = o.style.getPropertyPriority('position');
          o.style.setProperty('position', 'static', 'important');
          var r2 = o.getBoundingClientRect();
          if (prev) o.style.setProperty('position', prev, prevP); else o.style.removeProperty('position');
          setImp(c, {position: 'relative', top: (r1.top - r2.top) + 'px', left: (r1.left - r2.left) + 'px', bottom: 'auto', right: 'auto'});
        }
        if ((o.scrollTop || o.scrollLeft) && o !== body && o !== html){
          c.style.setProperty('overflow', 'hidden', 'important');
          for (var k = 0; k < c.children.length; k++) c.children[k].style.setProperty('translate', (-o.scrollLeft) + 'px ' + (-o.scrollTop) + 'px');
        }
        if (tag === 'INPUT'){
          if (o.type === 'checkbox' || o.type === 'radio'){ if (o.checked) c.setAttribute('checked', ''); else c.removeAttribute('checked'); }
          else if (o.type !== 'file' && o.type !== 'password') c.setAttribute('value', o.value);
        } else if (tag === 'TEXTAREA') c.textContent = o.value;
        else if (tag === 'SELECT'){
          for (var j = 0; j < o.options.length && j < c.options.length; j++){ if (o.options[j].selected) c.options[j].setAttribute('selected', ''); else c.options[j].removeAttribute('selected'); }
        } else if (tag === 'CANVAS'){
          try {
            if (o.width && o.height){
              var im = doc.createElement('img'); im.src = o.toDataURL(); copyBox(o, c, im, cs); swaps.push([c, im]);
            }
          } catch (e) {}
        } else if (tag === 'IMG'){
          var src = o.currentSrc || o.src;
          if (src && !/^data:/.test(src)) waits.push(inline(win, src).then(function(d){ c.setAttribute('src', d); c.removeAttribute('srcset'); c.removeAttribute('loading'); }, function(){}));
        } else if (tag === 'IFRAME'){
          var fw = null;
          try { fw = o.contentWindow; if (!fw || !fw.document || !fw.document.body) fw = null; } catch (e) { fw = null; }
          var ph = doc.createElement('div'); copyBox(o, c, ph, cs); ph.style.background = 'var(--doc-bg, #fff)'; swaps.push([c, ph]);
          if (fw && depth < 1 && o.clientWidth > 0 && o.clientHeight > 0){
            waits.push(snapDoc(fw, {x: 0, y: 0, w: o.clientWidth, h: o.clientHeight}, depth + 1, false).then(function(d){
              var im2 = doc.createElement('img'); im2.src = d; copyBox(o, c, im2, cs); ph.replaceWith(im2);
            }, function(){}));
          }
        }
      })(orig[i], cl[i]);
    }
    drop.forEach(function(c){ c.remove(); });
    swaps.forEach(function(s){ if (s[0].parentNode) s[0].replaceWith(s[1]); });
    return Promise.all(waits).then(function(){ return collectCss(win); }).then(function(css){
      var wrap = doc.createElement('div');
      Array.prototype.forEach.call(body.attributes, function(a){ if (a.name !== 'class' && a.name !== 'style' && a.name !== 'id') wrap.setAttribute(a.name, a.value); });
      wrap.className = ('x-body ' + body.className).trim();
      wrap.setAttribute('style', (body.getAttribute('style') || '') + ';position:relative;');
      while (copy.firstChild) wrap.appendChild(copy.firstChild);
      var xhtml = new XMLSerializer().serializeToString(wrap);
      var hs = win.getComputedStyle(html);
      var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '"' +
        attr('class', html.getAttribute('class')) + attr('data-theme', html.getAttribute('data-theme')) + attr('lang', html.getAttribute('lang')) +
        attr('style', (html.getAttribute('style') || '') + ';font-size:' + hs.fontSize + ';color-scheme:' + (hs.colorScheme || 'normal')) + '>' +
        '<style><![CDATA[' + css.replace(/\]\]>/g, ']]]]><![CDATA[>') + ']]></style>' +
        '<foreignObject x="0" y="0" width="' + W + '" height="' + H + '">' + xhtml + '</foreignObject></svg>';
      var bg = win.getComputedStyle(body).backgroundColor;
      if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') bg = hs.backgroundColor;
      if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') bg = '#ffffff';
      return draw(svg, W, H, {x: region.x + sx, y: region.y + sy, w: region.w, h: region.h}, bg, top);
    });
  }
  function attr(n, v){ return v == null || v === '' ? '' : ' ' + n + '="' + String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"'; }
  function copyBox(o, c, el, cs){
    if (c.id) el.id = c.id;
    if (c.getAttribute('class')) el.setAttribute('class', c.getAttribute('class'));
    if (c.getAttribute('style')) el.setAttribute('style', c.getAttribute('style'));
    el.style.width = o.offsetWidth + 'px'; el.style.height = o.offsetHeight + 'px';
    if (cs.display === 'inline') el.style.display = 'inline-block';
  }
  var inlined = new Map();
  function inline(win, src){
    if (!inlined.has(src)) inlined.set(src, (realFetch || win.fetch)(src).then(function(r){ if (!r.ok) throw new Error(r.status); return r.blob(); }).then(dataUrl));
    return inlined.get(src);
  }
  function dataUrl(blob){
    return new Promise(function(res, rej){ var fr = new FileReader(); fr.onload = function(){ res(fr.result); }; fr.onerror = function(){ rej(fr.error); }; fr.readAsDataURL(blob); });
  }
  function rewriteSel(sel){
    return sel.replace(/(^|[\s,>+~(])html(?![\w-])/g, '$1:root').replace(/(^|[\s,>+~(])body(?![\w-])/g, '$1.x-body');
  }
  // settle @media and @supports against the live page: inside an image they read differently
  function walkRules(rules, out, win){
    for (var i = 0; i < rules.length; i++){
      var r = rules[i];
      try {
        if (r.type === 1) out.push(rewriteSel(r.selectorText) + '{' + r.style.cssText + '}');
        else if (r.type === 4){ if (win.matchMedia(r.media.mediaText).matches) walkRules(r.cssRules, out, win); }
        else if (r.type === 12){ if (win.CSS && win.CSS.supports(r.conditionText)) walkRules(r.cssRules, out, win); }
        else if (r.type === 3){ if (r.styleSheet) walkRules(r.styleSheet.cssRules, out, win); }
        else if (r.cssRules && /Layer/.test(r.constructor && r.constructor.name)) walkRules(r.cssRules, out, win);
        else out.push(r.cssText);
      } catch (e) {}
    }
  }
  function collectCss(win){
    var doc = win.document, out = [], jobs = [];
    Array.prototype.forEach.call(doc.styleSheets, function(sh){
      var rules = null;
      try { rules = sh.cssRules; } catch (e) { rules = null; }
      if (rules) walkRules(rules, out, win);
      else if (sh.href && /^https:\/\/fonts\.googleapis\.com\//.test(sh.href)) jobs.push(googleFonts(sh.href));
    });
    return Promise.all(jobs).then(function(fonts){
      return fonts.join('\n') + '\n' + out.join('\n') + '\n*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}';
    });
  }
  // web fonts can't load inside an image, so the Latin ones are embedded
  var fontCss = new Map();
  function googleFonts(href){
    if (!fontCss.has(href)) fontCss.set(href, (realFetch || fetch)(href).then(function(r){ if (!r.ok) throw new Error(r.status); return r.text(); }).then(function(css){
      var blocks = [], re = /(?:\/\*\s*([\w-]+)\s*\*\/\s*)?@font-face\s*\{[^}]*\}/g, m;
      while ((m = re.exec(css))){ if (!m[1] || m[1] === 'latin') blocks.push(m[0].replace(/^\/\*[^*]*\*\/\s*/, '')); }
      return Promise.all(blocks.map(function(b){
        var u = /url\((https:[^)]+)\)/.exec(b);
        if (!u) return b;
        return inline(window, u[1]).then(function(d){ return b.replace(u[1], d); }, function(){ return ''; });
      })).then(function(list){ return list.join('\n'); });
    }).catch(function(){ return ''; }));
    return fontCss.get(href);
  }
  function draw(svg, W, H, area, bg, top){
    return new Promise(function(res, rej){
      var img = new Image();
      img.onload = function(){ res(img); };
      img.onerror = function(){ rej(new Error('the page copy could not be drawn')); };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    }).then(function(img){ return wait(80).then(function(){ return img; }); }).then(function(img){
      var scale = Math.min(2, window.devicePixelRatio || 1, Math.sqrt(4e6 / Math.max(1, area.w * area.h)));
      function render(sc){
        var cv = document.createElement('canvas');
        cv.width = Math.max(1, Math.round(area.w * sc)); cv.height = Math.max(1, Math.round(area.h * sc));
        var cx = cv.getContext('2d');
        cx.fillStyle = bg; cx.fillRect(0, 0, cv.width, cv.height);
        cx.setTransform(sc, 0, 0, sc, 0, 0);
        cx.drawImage(img, -area.x, -area.y, W, H);
        cx.drawImage(img, -area.x, -area.y, W, H);  // Safari can miss inlined images on the first pass
        return cv.toDataURL('image/png');
      }
      var url = render(scale), tries = 0;
      while (top && url.length > PNG_LIMIT && tries < 5){ scale *= 0.7; url = render(scale); tries++; }
      if (top && url.length > PNG_LIMIT) throw new Error('the picture is too large');
      return url;
    });
  }

  // ================= the change log (Settings, What's new) =================
  var LOG_COLORS = {Added: 'var(--c-link)', Changed: 'var(--c-date)', Fixed: 'var(--c-number)', Removed: 'var(--c-warning)'};
  var changes = null, logTag = 'all', logShown = 8;
  function changelogCard(){
    var card = $('log-card'); if (!card) return;
    $('log-tags').addEventListener('click', function(e){
      var b = e.target.closest('button'); if (!b) return;
      logTag = b.getAttribute('data-v'); logShown = 8; drawLog();
    });
    $('log-more').addEventListener('click', function(){ logShown += 10; drawLog(); });
    var load = function(){
      if (changes) return;
      changes = [];
      $('log-list').textContent = 'Loading...';
      (realFetch || fetch)('/changelog.json?v=' + encodeURIComponent(cfg.build || '')).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function(d){ changes = Array.isArray(d) ? d : []; drawLog(); }, function(){ changes = null; $('log-list').textContent = 'Could not load the change log.'; });
    };
    if (window.IntersectionObserver){
      var io = new IntersectionObserver(function(es){ if (es.some(function(e){ return e.isIntersecting; })){ io.disconnect(); load(); } });
      io.observe(card);
    } else load();
  }
  function logDate(s){
    if (!s) return 'Latest';
    var d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'});
  }
  function drawLog(){
    $('log-tags').querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-v') === logTag ? 'true' : 'false'); });
    var list = (changes || []).filter(function(c){ return logTag === 'all' || (c.tags || []).indexOf(logTag) >= 0; });
    var box = $('log-list'); box.textContent = '';
    if (!list.length){ box.append(h('p', {class: 'hint', text: 'Nothing here.'})); }
    list.slice(0, logShown).forEach(function(c){
      var top = h('div', {class: 'lg-top'});
      (c.tags || []).forEach(function(t){
        var tag = h('span', {class: 'lg-tag'}, [h('i'), t]); tag.style.setProperty('--k', LOG_COLORS[t] || 'var(--muted)'); top.append(tag);
      });
      top.append(h('span', {text: logDate(c.date)}));
      if (c.url && c.short) top.append(h('a', {href: c.url, target: '_blank', rel: 'noopener', text: c.short, 'data-plain': ''}));
      var item = h('div', {class: 'lg-item'}, [top, h('span', {class: 'lg-title', text: c.title})]);
      if (c.body){
        var det = h('details', null, [h('summary', {text: 'What changed'})]);
        c.body.split(/\n\n+/).forEach(function(p){ det.append(h('p', {text: p})); });
        item.append(det);
      }
      box.append(item);
    });
    $('log-more').hidden = list.length <= logShown;
  }
})();
