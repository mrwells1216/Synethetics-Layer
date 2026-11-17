/* Developer tools and the change log.
 *
 * The DEV button under the green bar turns the tools on: highlight text, or triple-click (triple-tap) for a
 * screenshot frame. Either way the marks come up first (Good, Not good, Fix/idea); picking one opens the
 * comment window, with Submit and Skip. Off, none of it runs. A note goes to the fixes store
 * (python fixes.py list) when the app runs on the owner's computer or the site has a store and this device is
 * linked; anywhere else it is kept on this device, to copy into a Claude chat.
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

  var realFetch = window.fetch ? window.fetch.bind(window) : null;

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
  // ================= where notes are kept =================
  function toStore(){ var d = cfg.dev || {}; return d.store === 'local' || (d.store === 'blob' && d.keyed && !!devKey()); }
  var idbP = null;
  function idb(){
    if (!idbP) idbP = new Promise(function(res, rej){
      var rq;
      try { rq = indexedDB.open('synapp-notes', 1); } catch (e) { rej(e); return; }
      rq.onupgradeneeded = function(){ rq.result.createObjectStore('notes', {keyPath: 'id', autoIncrement: true}); };
      rq.onsuccess = function(){ res(rq.result); };
      rq.onerror = function(){ rej(rq.error); };
    }).catch(function(){ idbP = null; throw new Error('This browser can’t keep notes here.'); });
    return idbP;
  }
  function tx(mode, fn){
    return idb().then(function(db){ return new Promise(function(res, rej){
      var t = db.transaction('notes', mode), rq = fn(t.objectStore('notes'));
      t.oncomplete = function(){ res(rq && rq.result); };
      t.onerror = t.onabort = function(){ rej(new Error('Could not save on this device.')); };
    }); });
  }
  function keepAdd(entry){ return tx('readwrite', function(st){ return st.add(entry); }); }
  function keepAll(){ return tx('readonly', function(st){ return st.getAll(); }).then(function(l){ return (l || []).reverse(); }); }
  function keepClear(){ return tx('readwrite', function(st){ return st.clear(); }); }

  // resolves to where the note went: 'claude' (the fixes store) or 'kept' (this device)
  function send(entry){
    entry.page = location.pathname + (location.hash && !/^#dev=/.test(location.hash) ? location.hash : '');
    if (toStore()) return api('fix-add', entry).then(function(){ refreshFixes(); return 'claude'; });
    entry.made = new Date().toISOString(); entry.status = 'kept';
    return keepAdd(entry).then(function(){ refreshFixes(); return 'kept'; });
  }
  function saved(where, pic){
    if (where === 'claude') toast(pic === false ? 'Saved for Claude, without a picture' : 'Saved for Claude');
    else if (app.toast) app.toast(pic === false ? 'Saved on this device, without a picture' : 'Saved on this device', 'Copy all', copyNotes);
  }

  // ================= styles =================
  var CSS = [
    '.dv-btn{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;border:1px solid var(--line);background:var(--raised);color:var(--fg);font:650 14px/1.1 var(--font-body);white-space:nowrap}',
    '.dv-btn[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}',
    '.dv-btn:focus-visible,.dv-bar button:focus-visible{outline:2px solid var(--fg);outline-offset:2px}',
    '.dv-empty{color:var(--muted);font-size:14px}',
    '.dv-bar{position:fixed;z-index:2147482600;display:flex;gap:2px;padding:4px;border-radius:999px;background:var(--fg);color:var(--bg);box-shadow:0 6px 18px rgba(0,0,0,.3)}',
    '.dv-bar button{all:unset;cursor:pointer;padding:7px 12px;border-radius:999px;font:750 14px/1 var(--font-body)}',
    '.dv-bar button:hover{background:color-mix(in srgb,var(--bg) 18%,transparent)}',
    '.dv-bar .dv-barx{margin-left:2px;padding:7px 10px;border-left:1px solid color-mix(in srgb,var(--bg) 30%,transparent);border-radius:0 999px 999px 0;opacity:.75}',
    '.dv-shot.pick{width:auto;padding:6px;border-radius:999px}',
    '.dv-shot.pick .dv-marks{margin:0;flex-wrap:nowrap}',
    '.dv-dim{position:fixed;inset:0;z-index:2147482700;pointer-events:none;background:rgba(0,0,0,.5)}',
    '.dv-frame{position:fixed;z-index:2147482800;border:2px solid;border-image:linear-gradient(100deg,#ff9d9d,#ffc091,#f6d68a,#96e2b3,#84e4e0,#9dcdff,#cdb9ff) 1;outline:1px solid rgba(0,0,0,.6);box-shadow:inset 0 0 0 1px rgba(0,0,0,.35);touch-action:none;cursor:move;box-sizing:border-box}',
    '.dv-h{position:absolute;width:30px;height:30px;touch-action:none}',
    '.dv-h::after{content:"";position:absolute;left:9px;top:9px;width:12px;height:12px;background:var(--hc,#fff);border:1px solid rgba(0,0,0,.7);border-radius:3px}',
    '.dv-h[data-c=nw]{left:-16px;top:-16px;cursor:nwse-resize;--hc:#ff9d9d}.dv-h[data-c=ne]{right:-16px;top:-16px;cursor:nesw-resize;--hc:#cdb9ff}',
    '.dv-h[data-c=sw]{left:-16px;bottom:-16px;cursor:nesw-resize;--hc:#f6d68a}.dv-h[data-c=se]{right:-16px;bottom:-16px;cursor:nwse-resize;--hc:#84e4e0}',
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
    '.dv-chip.open{border-color:var(--c-date)} .dv-chip.done{border-color:var(--c-link)} .dv-chip.skipped{border-color:var(--muted);color:var(--muted)} .dv-chip.kept{border-color:var(--c-number)}',
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
    if (paired) setTimeout(function(){ toast('This device is linked. The tools are on.'); }, 400);
  });

  function setOn(on, quiet){
    lsSet(ON_KEY, on ? '1' : '0');
    root.classList.toggle('dev-on', on);
    var sw = $('set-dev'); if (sw) sw.checked = on;
    var vd = $('vdev'); if (vd) vd.setAttribute('aria-pressed', on ? 'true' : 'false');
    var more = $('dev-more'); if (more) more.hidden = !on;
    devStatus();
    if (on) refreshFixes(); else { hideBar(); closeShot(); if (noteD && noteD.open) noteD.close(); }
    if (!quiet) toast(on ? 'Tools on: highlight text, or triple-tap for a screenshot' : 'Tools off');
  }

  // ================= the switch, and the notes card in Settings =================
  function settingsCard(){
    var sw = $('set-dev'); if (!sw) return;
    sw.addEventListener('change', function(){ setOn(this.checked); });
    var vd = $('vdev'); if (vd) vd.addEventListener('click', function(){ setOn(!isOn()); });
    Array.prototype.forEach.call(document.querySelectorAll('iframe'), function(f){ if (!f.closest('#roller')) hookFrame(f); });
    $('dev-copy').addEventListener('click', copyNotes);
    $('dev-share').addEventListener('click', shareNotes);
    $('dev-clear').addEventListener('click', function(){
      if (!window.confirm('Remove the notes kept on this device? This can’t be undone.')) return;
      keepClear().then(function(){ refreshFixes(); toast('Notes cleared'); }, function(e){ toast(e.message); });
    });
  }
  function devStatus(){
    var s = $('dev-status'); if (!s) return;
    var how = 'Highlight text, or triple-click (triple-tap on a phone) for a screenshot, then pick Good, Not good or Fix/idea. ';
    if (!isOn()) s.textContent = 'Press DEV under the green bar at the top of the page. ' + how.replace(/^H/, 'Then h');
    else s.textContent = how + (toStore() ? 'Notes go straight to Claude’s list.' : 'Notes are kept on this device: press Copy for Claude, then paste into your Claude chat.');
  }

  // ================= the notes list =================
  var MARK = {good: '✓ Good', bad: '✕ Not good', fix: 'Fix/idea'};
  var STATUS = {open: 'Waiting for Claude', done: 'Done', skipped: 'Not done', kept: 'On this device'};
  function acts(list){
    var any = list.length > 0, pics = list.some(function(e){ return e.image; });
    $('dev-copy').hidden = !any; $('dev-clear').hidden = !any;
    $('dev-share').hidden = !(pics && navigator.share && navigator.canShare);
  }
  function refreshFixes(){
    var box = $('dev-fixes'); if (!box || !isOn()) return;
    function fail(e){ box.textContent = ''; box.append(h('p', {class: 'dv-empty', text: 'Could not load notes: ' + e.message})); }
    if (!toStore()){
      keepAll().then(function(list){ acts(list); fillFixes(box, list); }, function(e){ acts([]); fail(e); });
      return;
    }
    acts([]);
    api('fix-list').then(function(res){ fillFixes(box, res.entries || []); }, fail);
  }
  function fillFixes(box, list){
    box.textContent = '';
    if (!list.length){ box.append(h('p', {class: 'dv-empty', text: 'No notes yet.'})); return; }
    var open = list.filter(function(e){ return e.status === 'open'; }).length, n = list.length + (list.length === 1 ? ' note' : ' notes');
    box.append(h('p', {class: 'dv-empty', text: toStore() ? n + ', ' + open + ' waiting for Claude.' : n + ' kept on this device.'}));
    list.forEach(function(e){
      var row = h('div', {class: 'dv-fix', 'data-plain': ''});
      var picBtn = (e.picture || e.image) ? h('button', {class: 'dv-link', text: 'Picture', type: 'button'}) : null;
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
        function show(src){ row.append(h('img', {src: src, alt: 'Screenshot from ' + when(e.made)})); picBtn.textContent = 'Picture'; }
        if (e.image){ show(e.image); return; }
        picBtn.textContent = 'Loading...';
        api('fix-image', {ref: e.ref}, true).then(function(b){ show(URL.createObjectURL(b)); },
          function(err){ picBtn.textContent = 'Picture'; toast(err.message); });
      });
      box.append(row);
    });
  }

  // ================= notes kept on this device: copy or share them into a Claude chat =================
  function notesText(list){
    var out = ['Notes from Synesthetic Layer' + (cfg.build ? ' (build ' + cfg.build + ')' : '') + ':'];
    list.slice().reverse().forEach(function(e, i){
      out.push('', (i + 1) + '. [' + (MARK[e.mark] || e.mark).replace(/^[✓✕] /, '') + '] ' + (e.section ? 'on ' + e.section + ', ' : '') + when(e.made) + (e.image ? ' (with a picture)' : ''));
      if (e.note) out.push('   Note: ' + e.note);
      if (e.text) out.push('   Text: "' + (e.text.length > 600 ? e.text.slice(0, 600) + '...' : e.text) + '"');
    });
    return out.join('\n');
  }
  function copyNotes(){
    keepAll().then(function(list){
      if (!list.length) throw new Error('No notes to copy');
      if (!navigator.clipboard) throw new Error('Could not copy here');
      return navigator.clipboard.writeText(notesText(list)).then(function(){ toast('Copied. Paste into your Claude chat.'); });
    }).catch(function(e){ toast(e.message || 'Could not copy here'); });
  }
  function pngFile(dataUrl, name){
    var bin = atob(dataUrl.slice(dataUrl.indexOf(',') + 1)), buf = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return new File([buf], name, {type: 'image/png'});
  }
  function shareNotes(){
    keepAll().then(function(list){
      var files = [];
      list.slice().reverse().forEach(function(e, i){ if (e.image) files.push(pngFile(e.image, 'note-' + (i + 1) + '.png')); });
      var data = {title: 'Synesthetic Layer notes', text: notesText(list), files: files};
      if (!navigator.canShare || !navigator.canShare(data)) throw new Error('This browser can’t share pictures.');
      return navigator.share(data);
    }).catch(function(e){ if (!e || e.name !== 'AbortError') toast((e && e.message) || 'Could not share'); });
  }

  // ================= comment window (after a mark is picked on highlighted text) =================
  var NOTE_HINT = {good: 'What works here (optional)', bad: 'What is off (optional)', fix: 'What should change, or your idea (optional)'};
  var noteD = null, noteOpts = null;
  function openNote(opts){
    noteOpts = opts;
    if (!noteD){
      var ta = h('textarea', {'aria-label': 'Your comment', rows: '4'});
      var st = h('p', {class: 'dv-st', role: 'status'});
      var save = h('button', {class: 'dv-btn', type: 'button', 'aria-pressed': 'true', text: 'Submit'});
      var skip = h('button', {class: 'dv-btn', type: 'button', text: 'Skip', title: 'Save the mark without a comment'});
      var x = h('button', {class: 'dv-btn', type: 'button', 'aria-label': 'Close without saving', text: '✕'});
      noteD = ui(h('dialog', {class: 'dv-note', 'aria-label': 'Comment'}, [
        h('div', {class: 'dv-top'}, [h('h3'), x]),
        h('blockquote'), ta, h('div', {class: 'dv-marks'}, [save, skip]), st]));
      document.body.appendChild(noteD);
      noteD._ta = ta; noteD._st = st;
      x.addEventListener('click', function(){ noteD.close(); });
      save.addEventListener('click', function(){ saveNote(false); });
      skip.addEventListener('click', function(){ saveNote(true); });
      noteD.addEventListener('keydown', function(e){
        if (e.key === 'Escape'){ e.stopPropagation(); }
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); saveNote(false); }
      });
    }
    var mark = opts.mark || 'fix';
    noteD.querySelector('h3').textContent = MARK[mark] || mark;
    var q = noteD.querySelector('blockquote');
    q.hidden = !opts.text; q.textContent = opts.text ? (opts.text.length > 900 ? opts.text.slice(0, 900) + '...' : opts.text) : '';
    noteD._ta.value = ''; noteD._st.textContent = '';
    noteD._ta.placeholder = NOTE_HINT[mark] || NOTE_HINT.fix;
    if (!noteD.open) noteD.showModal();
    noteD._ta.focus();
  }
  function saveNote(skip){
    var o = noteOpts, note = skip ? '' : noteD._ta.value.trim(), st = noteD._st;
    if (!note && !o.text){ st.textContent = 'Write a comment first.'; noteD._ta.focus(); return; }
    st.textContent = 'Saving...';
    send({kind: o.kind, mark: o.mark || 'fix', note: note, text: (o.text || '').slice(0, 4000), section: o.section || tabNow(), context: context(o.context)})
      .then(function(w){ noteD.close(); saved(w); }, function(e){ st.textContent = e.message; });
  }

  // ================= highlight -> Fix/idea =================
  var bar = null, barSel = null, dismissed = '';
  function hideBar(){ if (bar) bar.hidden = true; barSel = null; }
  function checkSel(){
    if (!isOn() || shot || (noteD && noteD.open)) return hideBar();
    var cur = selNow();
    if (!cur) return hideBar();
    var s = cur.s, txt = s.toString().trim();
    if (txt.length < 2 || txt === dismissed) return hideBar();
    var r = s.getRangeAt(0), n = r.commonAncestorContainer, e = n.nodeType === 1 ? n : n.parentElement;
    if (!e || e.closest('[data-devui],input,textarea,select,[contenteditable]:not([contenteditable=false]),#ro-stage')) return hideBar();
    var rr = r.getBoundingClientRect();
    if (!rr.width && !rr.height) return hideBar();
    var rect = {left: rr.left + cur.dx, top: rr.top + cur.dy, bottom: rr.bottom + cur.dy, width: rr.width};
    if (!bar){
      var closeB = h('button', {type: 'button', class: 'dv-barx', 'aria-label': 'Close', text: '✕'});
      var markBs = [['good', 'Good'], ['bad', 'Not good'], ['fix', 'Fix/idea']].map(function(m){
        var b = h('button', {type: 'button', text: m[1]});
        b.addEventListener('click', function(){
          var sel = barSel; hideBar(); if (!sel) return;
          openNote({kind: 'text', mark: m[0], text: sel.text, section: sel.section, context: {picture: 'not drawn: highlight'}});
        });
        return b;
      });
      bar = ui(h('div', {class: 'dv-bar', role: 'toolbar', 'aria-label': 'Mark this text'}, markBs.concat([closeB])));
      // keep the selection when the bar is pressed
      bar.addEventListener('mousedown', function(ev){ ev.preventDefault(); });
      closeB.addEventListener('click', function(){ dismissed = barSel ? barSel.text : ''; hideBar(); });
      document.body.appendChild(bar);
    }
    barSel = {text: txt.slice(0, 4000), section: sectionOf(cur.host || e)};
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
  function onSel(){ if (!isOn()) return; clearTimeout(selT); selT = setTimeout(checkSel, 220); }
  document.addEventListener('selectionchange', onSel);

  // A frame of the app's own (the example document) is a page of its own: its selection and its clicks never
  // reach this one. So each is wired the same way, and its positions are moved by where the frame sits.
  var frames = [];
  function frameAt(f){ var r = f.getBoundingClientRect(); return {dx: r.left + f.clientLeft, dy: r.top + f.clientTop}; }
  function selNow(){
    var s = window.getSelection();
    if (s && !s.isCollapsed && s.rangeCount) return {s: s, dx: 0, dy: 0, host: null};
    for (var i = 0; i < frames.length; i++){
      var f = frames[i], d = null;
      try { d = f.isConnected && f.getClientRects().length && f.contentDocument; } catch (e) {}
      var fs = d && d.getSelection && d.getSelection();
      if (fs && !fs.isCollapsed && fs.rangeCount){ var o = frameAt(f); return {s: fs, dx: o.dx, dy: o.dy, host: f}; }
    }
    return null;
  }
  function clearSel(doc){ try { var s = (doc || document).getSelection(); if (s) s.removeAllRanges(); } catch (e) {} }
  function hookFrame(f){
    if (frames.indexOf(f) < 0) frames.push(f);
    function wire(){
      var d = null;
      try { d = f.contentDocument; } catch (e) {}
      if (!d || d._dv) return;
      d._dv = true;
      d.addEventListener('selectionchange', onSel);
      d.addEventListener('mousedown', function(e){
        if (!isOn() || shot || e.button !== 0 || e.detail !== 3) return;
        if (e.target.closest && e.target.closest(SKIP)) return;
        e.preventDefault(); clearSel(d);
        var o = frameAt(f); openShot(e.clientX + o.dx, e.clientY + o.dy);
      }, true);
      var ft = [];
      d.addEventListener('pointerup', function(e){
        if (!isOn() || shot || e.pointerType !== 'touch') return;
        if (e.target.closest && e.target.closest(SKIP)){ ft = []; return; }
        ft = tapped(ft, e);
        if (ft.length >= 3){ ft = []; clearSel(d); var o = frameAt(f); openShot(e.clientX + o.dx, e.clientY + o.dy); }
      }, true);
    }
    f.addEventListener('load', wire);
    wire();
  }
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
    taps = tapped(taps, e);
    if (taps.length >= 3){ taps = []; clearSel(); openShot(e.clientX, e.clientY); }
  }, true);
  function tapped(list, e){   // the taps so far that are close to this one in time and place, plus this one
    var now = Date.now();
    list = list.filter(function(t){ return now - t.t < 900 && Math.abs(t.x - e.clientX) < 30 && Math.abs(t.y - e.clientY) < 30; });
    list.push({t: now, x: e.clientX, y: e.clientY});
    return list;
  }

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
    var x = h('button', {class: 'dv-btn', type: 'button', 'aria-label': 'Close without saving', text: '✕'});
    x.addEventListener('click', closeShot);
    var marks = h('div', {class: 'dv-marks'}, Object.keys(MARK).map(function(m){
      var b = h('button', {class: 'dv-btn', type: 'button', text: MARK[m], title: {good: 'Keep it like this', bad: 'Not good', fix: 'Something to change, or an idea'}[m]});
      b.addEventListener('click', function(){ pickShot(m); });
      return b;
    }).concat([x]));
    shot.panel = ui(h('div', {class: 'dv-shot pick', role: 'dialog', 'aria-label': 'Screenshot: pick a mark. Drag the frame, or a corner to resize it.'}, [marks]));
    [shot.dim, shot.frame, shot.panel].forEach(function(e){ document.body.appendChild(e); });
    dragging(shot.frame);
    layout();
  }
  function pickShot(mark){
    if (!shot || shot.busy) return;
    var s = shot, p = s.panel;
    var ta = h('textarea', {placeholder: NOTE_HINT[mark], 'aria-label': 'Comment', rows: '3'});
    var st = h('p', {class: 'dv-st', role: 'status'});
    var x = h('button', {class: 'dv-btn', type: 'button', 'aria-label': 'Close without saving', text: '✕'});
    var save = h('button', {class: 'dv-btn', type: 'button', 'aria-pressed': 'true', text: 'Submit'});
    var skip = h('button', {class: 'dv-btn', type: 'button', text: 'Skip', title: 'Save the picture and the mark without a comment'});
    x.addEventListener('click', closeShot);
    save.addEventListener('click', function(){ saveShot(mark); });
    skip.addEventListener('click', function(){ ta.value = ''; saveShot(mark); });
    ta.addEventListener('keydown', function(e){ if ((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); saveShot(mark); } });
    p.textContent = ''; p.classList.remove('pick'); p.setAttribute('aria-label', 'Screenshot comment');
    p.append(h('div', {class: 'dv-top'}, [h('h3', {text: MARK[mark]}), x]), ta, h('div', {class: 'dv-marks'}, [save, skip]), st);
    s.ta = ta; s.st = st;
    layout();
    ta.focus();
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
      frames.forEach(function(f){   // and the words of an example document showing under the frame
        var d = null;
        try { d = f.getClientRects().length && f.contentDocument; } catch (e) {}
        if (!d || !d.body) return;
        var o = frameAt(f), t = textUnder(d, {x: region.x - o.dx, y: region.y - o.dy, w: region.w, h: region.h}, f.clientWidth, f.clientHeight);
        if (t) text = (text ? text + ' ' : '') + t;
      });
      text = text.slice(0, 4000);
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
        saved(o.res, o.pic);
        setTimeout(function(){ if (shot === s) closeShot(); }, o.pic ? 600 : 1800);
      }, function(e){ if (shot === s){ s.busy = false; s.st.textContent = e.message; } });
  }

  // the visible text under the frame: only text whose own element is what's actually showing there
  function textUnder(doc, region, fw, fh){
    var out = [], walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT, {acceptNode: function(n){
      if (!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      var p = n.parentElement;
      if (!p || p.closest('script,style,noscript,[data-devui],#toast')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    var range = doc.createRange(), n, total = 0, W = fw || vw(), H = fh || vh();
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
        if (tag === 'SCRIPT' || tag === 'NOSCRIPT' || tag === 'STYLE' || tag === 'LINK' || tag === 'TEMPLATE' || o.hasAttribute('data-devui') || o.id === 'toast'){ drop.push(c); return; }
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
        attr('class', html.getAttribute('class')) + attr('lang', html.getAttribute('lang')) +
        Array.prototype.map.call(html.attributes, function(a){ return /^data-/.test(a.name) ? attr(a.name, a.value) : ''; }).join('') +
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
