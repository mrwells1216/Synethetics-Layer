/* The Roller tab: a passage to enhance, the floating bar of 8 blocks, and their menus.
   The blocks and menu paths come from /roller-menu.js; this file draws them and puts the enhancers on the text.
   Every enhancer lives on a <span class="rx" data-look="{...}"> around the text it covers (line spacing goes on
   the paragraph). Spans stay flat: a change to part of one splits it, so each span carries its whole look. */
(function(){
  var A = window.synApp, MENU = window.ROLLER_MENU || [];
  if (!A || !document.getElementById('rl-text')) return;
  var $ = function(id){ return document.getElementById(id); };
  var el = A.el, box = $('rl-text'), bar = $('rl-bar'), drop = $('rl-drop');
  var BLOCK_COLORS = ['warning', 'quote', 'date', 'link', 'id', 'number', 'reference'];

  var DEFAULT = [
    'The river trail opens at 7:30 on Saturday, March 14, and closes at dusk. Bring 2 liters of water per person; the last fountain is near mile 4.5, just past the old stone bridge.',
    'Mara Lindqvist has walked it 112 times. "Start slow," she says, "and the hills feel half as steep." Her notebook lists every tree she passes: oak, birch, three tall pines and one crooked maple that leans over the water.',
    'Do not leave the marked path after sunset. Rangers close the north gate at 8:00 pm sharp, and the fine for camping without a permit is $250. Trail maps cost $3 at the visitor center, or see page 12 of the park guide.',
    'On clear evenings the light turns the whole valley gold, and the river sounds louder once the birds go quiet.'
  ].join('\n\n');

  // ---------- the passage ----------
  function setText(text){
    box.textContent = '';
    String(text).replace(/\r\n?/g, '\n').split(/\n\s*\n/).map(function(p){ return p.trim(); }).filter(Boolean).forEach(function(p){
      var para = el('p');
      p.split('\n').forEach(function(line, i){ if (i) para.appendChild(el('br')); para.appendChild(document.createTextNode(line)); });
      box.appendChild(para);
    });
    if (!box.firstChild) box.appendChild(el('p', null, 'Nothing to show: paste or upload some text.'));
  }

  // ---------- undo ----------
  var undo = [], lastSnap = {key: '', at: 0};
  function snapshot(key){   // a slider sends many changes: they count as one while they keep coming
    var now = Date.now();
    if (key && lastSnap.key === key && now - lastSnap.at < 900){ lastSnap.at = now; return; }
    lastSnap = {key: key || '', at: now};
    undo.push(box.innerHTML); if (undo.length > 50) undo.shift();
    $('rl-undo').disabled = false;
  }
  function doUndo(){
    if (!undo.length){ A.toast('Nothing to undo'); return; }
    box.innerHTML = undo.pop(); lastSnap = {key: '', at: 0};
    if (sel) reselect(); refreshDrop();
  }

  // ---------- selections, as character offsets in the passage ----------
  // (most of these take a root: the Roller's passage by default, or Free Rain's page when a preset rolls there)
  function offIn(node, o){ var r = document.createRange(); r.selectNodeContents(box); r.setEnd(node, o); return r.toString().length; }
  function current(){
    var s = getSelection();
    if (!s.rangeCount || s.isCollapsed) return null;
    var r = s.getRangeAt(0);
    if (!box.contains(r.commonAncestorContainer)) return null;
    var a = offIn(r.startContainer, r.startOffset), b = offIn(r.endContainer, r.endOffset);
    return a < b ? [a, b] : null;
  }
  function texts(rt){
    var w = document.createTreeWalker(rt || box, NodeFilter.SHOW_TEXT), list = [], t;
    while ((t = w.nextNode())) list.push(t);
    return list;
  }
  function rangeOf(o, rt){
    var r = document.createRange(), pos = 0, started = false, last = null;
    var list = texts(rt);
    for (var i = 0; i < list.length; i++){
      var t = list[i], n = t.nodeValue.length; last = t;
      if (!started && pos + n > o[0]){ r.setStart(t, o[0] - pos); started = true; }
      if (started && pos + n >= o[1]){ r.setEnd(t, o[1] - pos); return r; }
      pos += n;
    }
    if (started && last){ r.setEnd(last, last.nodeValue.length); return r; }
    return null;
  }
  var ours = false;
  function reselect(){
    var r = rangeOf(sel); if (!r) return;
    ours = true;
    var s = getSelection(); s.removeAllRanges(); s.addRange(r);
    setTimeout(function(){ ours = false; }, 50);
  }
  function selText(){ var r = rangeOf(sel); return r ? r.toString() : ''; }

  // ---------- looks: one object per span ----------
  function lookOf(span){ try { return JSON.parse(span.getAttribute('data-look') || '{}'); } catch (e){ return {}; } }
  function getPath(o, p){ return p.split('.').reduce(function(x, k){ return x == null ? undefined : x[k]; }, o); }
  function setPath(o, p, v){
    var ks = p.split('.'), last = ks.pop(), x = o;
    ks.forEach(function(k){ if (!x[k] || typeof x[k] !== 'object') x[k] = {}; x = x[k]; });
    if (v === null || v === undefined || v === false) delete x[last]; else x[last] = v;
    if (ks.length && !Object.keys(x).length) delete o[ks[0]];
  }
  function styleOf(l){ return A.richCss(l); }   // the app's richCss: the same CSS pages and the Core Pool use
  function writeLook(span, l){
    if (!Object.keys(l).length){ span.removeAttribute('data-look'); span.removeAttribute('style'); return; }
    span.setAttribute('data-look', JSON.stringify(l)); span.setAttribute('style', styleOf(l));
  }

  // the spans that cover the selection, splitting text and spans at its edges
  function targets(o, rt){
    var pos = 0, cut = [];
    texts(rt).forEach(function(t){
      var n = t.nodeValue.length, s = Math.max(o[0], pos) - pos, e = Math.min(o[1], pos + n) - pos;
      if (e > s) cut.push([t, s, e]);
      pos += n;
    });
    return cut.map(function(c){
      var t = c[0];
      if (c[2] < t.nodeValue.length) t.splitText(c[2]);
      if (c[1] > 0) t = t.splitText(c[1]);
      return spanFor(t);
    });
  }
  function spanFor(t){
    var p = t.parentNode;
    if (p.classList && p.classList.contains('rx')){
      if (p.childNodes.length === 1) return p;
      var before = [], after = [], seen = false;
      [].slice.call(p.childNodes).forEach(function(n){ if (n === t) seen = true; else (seen ? after : before).push(n); });
      if (before.length){ var b = p.cloneNode(false); before.forEach(function(n){ b.appendChild(n); }); p.parentNode.insertBefore(b, p); }
      if (after.length){ var a = p.cloneNode(false); after.forEach(function(n){ a.appendChild(n); }); p.parentNode.insertBefore(a, p.nextSibling); }
      return p;
    }
    var s = el('span', 'rx'); p.insertBefore(s, t); s.appendChild(t);
    return s;
  }
  function tidy(rt){   // drop spans with no look left, join neighbors that look the same
    rt = rt || box;
    rt.querySelectorAll('span.rx').forEach(function(s){
      if (!s.getAttribute('data-look')){ var p = s.parentNode; while (s.firstChild) p.insertBefore(s.firstChild, s); p.removeChild(s); }
    });
    rt.querySelectorAll('span.rx').forEach(function(s){
      var n = s.nextSibling;
      while (n && n.nodeType === 1 && n.classList.contains('rx') && n.getAttribute('data-look') === s.getAttribute('data-look')){
        while (n.firstChild) s.appendChild(n.firstChild);
        var gone = n; n = n.nextSibling; gone.parentNode.removeChild(gone);
      }
    });
    rt.normalize();
  }
  var BLOCKS = 'p,li,h1,h2,h3,h4,blockquote,div';
  function paras(o, rt){   // the innermost blocks (paragraphs, list items) the offsets touch
    rt = rt || box;
    var r = rangeOf(o, rt); if (!r) return [];
    return [].filter.call(rt.querySelectorAll(BLOCKS), function(p){ return !p.querySelector(BLOCKS) && r.intersectsNode(p); });
  }
  // the look at the start of the selection, for showing what is set now
  function lookAt(o){
    var r = rangeOf([o[0], Math.min(o[0] + 1, o[1])]); if (!r) return {};
    var n = r.startContainer; n = n.nodeType === 3 ? n.parentNode : n;
    var s = n.closest && n.closest('span.rx');
    var l = s ? lookOf(s) : {};
    var p = paras(o)[0]; if (p && p.getAttribute('data-lh')) l.lh = +p.getAttribute('data-lh');
    return l;
  }
  function sizeNow(span){ return Math.round(parseFloat(getComputedStyle(span).fontSize)) || 17; }

  // The bar can also edit a look that isn't on the page (the Core Pool): `target` holds it while it's open.
  // target = {get(): look, set(look), anchor: the element the bar sits by, done()}
  var target = null;
  function patch(l, c){   // one change to one look object
    if (c.mode === 'toggle') setPath(l, c.path, getPath(l, c.path) ? null : true);
    else if (c.mode === 'clear') setPath(l, c.path, null);
    else if (c.mode === 'bump'){ var now = getPath(l, c.path); if (now == null) now = 17; setPath(l, c.path, Math.max(c.min || 10, Math.min(c.max || 64, now + c.by))); }
    else setPath(l, c.path, c.value);
    return l;
  }
  // one change: {path, mode: set|toggle|bump|clear, value, by, min, max}
  function change(c, o){
    if (target){ target.set(patch(JSON.parse(JSON.stringify(target.get())), c)); return; }
    o = o || sel; if (!o) return;
    if (c.path === 'lh'){
      paras(o).forEach(function(p){
        if (c.mode === 'clear' || c.value == null){ p.style.lineHeight = ''; p.removeAttribute('data-lh'); }
        else { p.style.lineHeight = c.value; p.setAttribute('data-lh', c.value); }
      });
      return;
    }
    var spans = targets(o);
    var allOn = c.mode === 'toggle' && spans.every(function(s){ return !!getPath(lookOf(s), c.path); });
    spans.forEach(function(s){
      var l = lookOf(s);
      if (c.mode === 'toggle') setPath(l, c.path, allOn ? null : true);
      else if (c.mode === 'clear') setPath(l, c.path, null);
      else if (c.mode === 'bump'){
        var now = getPath(l, c.path); if (now == null) now = sizeNow(s);
        setPath(l, c.path, Math.max(c.min || 10, Math.min(c.max || 64, now + c.by)));
      }
      else setPath(l, c.path, c.value);
      writeLook(s, l);
    });
    tidy();
  }
  function applyNow(c, key){
    if (target){ change(c); refreshDrop(); return; }
    if (!sel){ A.toast('Select some text first'); return; }
    snapshot(key);
    change(c); reselect(); refreshDrop();
    if (!changed){ changed = true; drawBar(); }   // the green check appears: done with this section
  }

  // ---------- Multiple: pick several, then apply them together ----------
  var multi = false, staged = [], changed = false;
  function stage(c, label, blockId){
    if (c.mode === 'bump'){
      var same = staged.filter(function(x){ return x.c.mode === 'bump' && x.c.path === c.path; })[0];
      if (same){ same.c.by += c.by; same.label = (same.c.by > 0 ? 'Font up ' : 'Font down ') + Math.abs(same.c.by) + 'px'; same.blocks[blockId] = 1; return drawBar(); }
    }
    staged = staged.filter(function(x){ return x.c.path !== c.path || x.c.mode === 'bump'; });
    var b = {}; b[blockId] = 1;
    staged.push({c: c, label: label, blocks: b});
    drawBar(); refreshDrop();
    A.toast('Picked: ' + label + '. Open Multiple to apply.');
  }
  function applyStaged(){
    if (!staged.length || !(sel || target)) return;
    if (!target) snapshot();
    staged.forEach(function(x){ change(x.c); });
    var n = staged.length; staged = []; changed = true;
    if (!target) reselect();
    closeDrop(); drawBar();
    A.toast(n + (n === 1 ? ' enhancer' : ' enhancers') + ' applied');
  }
  function act(c, label, blockId, key){ if (multi) stage(c, label, blockId); else applyNow(c, key); }

  // ---------- the bar ----------
  var openId = null, path = [], trail = [];
  function drawBar(){
    bar.textContent = '';
    var grip = el('button', 'rl-grip'); grip.type = 'button'; grip.setAttribute('aria-label', 'Move the bar (double-tap to send it back)'); grip.title = 'Drag to move. Double-tap: back to following the text.';
    bar.appendChild(grip); dragging(grip);
    MENU.forEach(function(b, i){
      var x = el('button', 'rl-b'); x.type = 'button'; x.setAttribute('data-id', b.id);
      var k = BLOCK_COLORS[i % BLOCK_COLORS.length];
      x.style.setProperty('--k', b.multi ? 'var(--fg)' : 'var(--c-' + k + ')');
      x.style.setProperty('--on-k', b.multi ? 'var(--bg)' : 'var(--on-' + k + ')');
      x.setAttribute('aria-label', b.label); x.title = b.label;
      var ic = el('i', null, b.icon || b.label.slice(0, 2));
      if (b.id === 'up') ic.textContent = 'A▲';
      if (b.id === 'down') ic.textContent = 'A▼';
      if (b.id === 'amp') ic.style.fontWeight = '900';
      if (b.id === 'hl'){ ic.style.background = 'var(--k)'; ic.style.color = 'var(--on-k)'; ic.style.padding = '0 3px'; ic.style.borderRadius = '4px'; ic.textContent = 'ab'; }
      if (b.id === 'space'){ ic.textContent = 'a b'; ic.style.letterSpacing = '.18em'; }
      if (b.id === 'multi'){ ic.textContent = staged.length ? '✓' + staged.length : '≡'; }
      x.appendChild(ic); x.appendChild(el('small', null, b.short || b.label));
      if (b.multi) x.setAttribute('aria-pressed', multi ? 'true' : 'false');
      if (b.children) x.setAttribute('aria-expanded', openId === b.id ? 'true' : 'false');
      if (staged.some(function(s){ return s.blocks[b.id]; })) x.classList.add('picked');
      x.onclick = function(){ blockTap(b); };
      bar.appendChild(x);
    });
    if (changed || target){
      var done = el('button', 'rl-done'); done.type = 'button';
      var tip = target ? 'Done: keep this look' : 'Done with this section: keep it as a layer';
      done.setAttribute('aria-label', tip); done.title = tip;
      done.append(el('i', null, '✓'), el('small', null, 'Done'));
      done.onclick = target ? endTarget : commitLayer;
      bar.appendChild(done);
    }
  }
  function blockTap(b){
    if (b.multi){
      if (!multi){ multi = true; openId = b.id; path = []; drawBar(); openDrop(); return; }
      if (openId === b.id){ closeDrop(); return; }
      openId = b.id; path = []; drawBar(); openDrop(); return;
    }
    if (b.quick){
      var q = b.quick;
      act({path: q.set, mode: q.type, by: q.by, min: q.min, max: q.max}, b.label, b.id);
      return;
    }
    if (openId === b.id){ closeDrop(); return; }
    openId = b.id; path = []; drawBar(); openDrop();
  }

  // ---------- the menus: columns, like a computer's file menu ----------
  function block(){ for (var i = 0; i < MENU.length; i++) if (MENU[i].id === openId) return MENU[i]; return null; }
  function visible(items){ var one = !target && !/\S\s+\S/.test(selText().trim()); return items.filter(function(it){ return !(it.words && one); }); }
  function openDrop(){ drop.hidden = false; renderDrop(); place(true); }
  function closeDrop(){ openId = null; path = []; drop.hidden = true; drawBar(); }
  function refreshDrop(){ if (!drop.hidden) renderDrop(); }
  function renderDrop(){
    var b = block(); if (!b){ drop.hidden = true; return; }
    drop.textContent = '';
    var head = el('div', 'rd-path');
    if (path.length){ var back = el('button', 'rd-back', '‹ Back'); back.type = 'button'; back.onclick = function(){ path.pop(); renderDrop(); place(true); }; head.appendChild(back); }
    var names = [b.label], items = b.children || [];
    path.forEach(function(i){ var it = visible(items)[i]; if (it){ names.push(it.label); items = it.children || []; } });
    trail = names.slice(1);
    head.appendChild(el('span', null, names.slice(0, -1).join(' › ') + (names.length > 1 ? ' › ' : '')));
    head.lastChild.appendChild(el('b', null, names[names.length - 1]));
    var x = el('button', 'rd-x', '✕'); x.type = 'button'; x.setAttribute('aria-label', 'Close the menu'); x.onclick = closeDrop; head.appendChild(x);
    drop.appendChild(head);
    var cols = el('div', 'rd-cols'); drop.appendChild(cols);
    if (b.multi){ cols.appendChild(multiCol()); return; }
    var level = b.children || [], now = target ? target.get() : sel ? lookAt(sel) : {};
    for (var d = 0; d <= path.length; d++){
      var list = visible(level), col = el('div', 'rd-col');
      list.forEach(function(it, i){ col.appendChild(itemBtn(it, i, d, now, b)); });
      cols.appendChild(col);
      var pick = list[path[d]];
      if (d === path.length || !pick) break;
      if (pick.children) level = pick.children;
      else { cols.appendChild(control(pick, now, b)); break; }
    }
    cols.scrollLeft = cols.scrollWidth;
  }
  function fmt(it, v){
    if (v == null || v === '') return '';
    if (it.type === 'choice'){ var o = it.options.filter(function(p){ return p[1] === v; })[0]; return o ? o[0] : v; }
    if (it.type === 'font') return A.fonts[v] ? A.fonts[v].label : '';
    if (it.type === 'color') return '●';
    if (typeof v === 'number') return (Math.round(v * 100) / 100) + (it.unit || '');
    return '';
  }
  function itemBtn(it, i, depth, now, b){
    var x = el('button', 'rd-it'); x.type = 'button'; x.setAttribute('role', 'menuitem');
    x.appendChild(el('span', null, it.label));
    if (it.children){ x.appendChild(el('span', 'arr', '›')); x.setAttribute('aria-expanded', path[depth] === i ? 'true' : 'false'); }
    else if (it.type === 'toggle'){ x.setAttribute('aria-pressed', getPath(now, it.set) ? 'true' : 'false'); x.appendChild(el('span', 'now', getPath(now, it.set) ? 'On' : 'Off')); }
    else if (it.type !== 'clear'){
      var v = getPath(now, it.set), n = el('span', 'now', fmt(it, v));
      if (it.type === 'color' && v) n.style.color = v;
      x.appendChild(n); x.appendChild(el('span', 'arr', '›'));
      x.setAttribute('aria-expanded', path[depth] === i ? 'true' : 'false');
    }
    x.onclick = function(){
      if (it.type === 'toggle') return act({path: it.set, mode: 'toggle'}, it.label, b.id);
      if (it.type === 'clear') return act({path: it.set, mode: 'clear'}, it.label, b.id);
      path = path.slice(0, depth); path.push(i); renderDrop(); place(true);
    };
    return x;
  }
  function control(it, now, b){
    var col = el('div', 'rd-col ctl'), c = el('div', 'rd-ctl'); col.appendChild(c);
    c.appendChild(el('h4', null, it.label));
    // what a pick is called in Multiple's list: its path, so "Thickness" says which line
    var name = trail.length > 1 ? trail.slice(-2).join(' ') : it.label;
    var v = getPath(now, it.set), label = function(val){ return name + ': ' + (fmt(it, val) || val); };
    if (it.type === 'choice'){
      it.options.forEach(function(o){
        var x = el('button', 'rd-it', o[0]); x.type = 'button'; x.setAttribute('aria-pressed', v === o[1] ? 'true' : 'false');
        if (it.set === 'weight') x.style.fontWeight = o[1];
        if (/\.w$/.test(it.set)) x.style.textDecoration = (it.set.indexOf('over') === 0 ? 'overline ' : 'underline ') + o[1] + 'px';
        x.onclick = function(){ act({path: it.set, mode: 'set', value: o[1]}, label(o[1]), b.id); };
        c.appendChild(x);
      });
    } else if (it.type === 'color'){
      var sw = el('div', 'rd-sw'), cols = A.rainbow().concat(['#ffffff', '#8d95a3', '#1b1d22']);
      cols.forEach(function(h){
        var x = el('button'); x.type = 'button'; x.style.setProperty('--sw', h); x.setAttribute('aria-label', h); x.title = h;
        x.setAttribute('aria-pressed', v === h ? 'true' : 'false');
        x.onclick = function(){ act({path: it.set, mode: 'set', value: h}, name, b.id); };
        sw.appendChild(x);
      });
      var lab = el('label', null, 'Any'), inp = el('input'); inp.type = 'color'; inp.value = /^#[0-9a-f]{6}$/i.test(v || '') ? v : '#ff6b6b';
      inp.setAttribute('aria-label', 'Any color'); inp.oninput = function(){ act({path: it.set, mode: 'set', value: inp.value}, name, b.id, it.set); };
      lab.appendChild(inp); sw.appendChild(lab);
      c.appendChild(sw);
      var none = el('button', 'rd-it', 'No color'); none.type = 'button';
      none.onclick = function(){ act({path: it.set, mode: 'clear'}, name + ': none', b.id); };
      c.appendChild(none);
    } else if (it.type === 'font'){
      var st = A.st(), list = el('div', 'rd-fonts');
      Object.keys(A.fonts).filter(function(k){ return (st.fontsOff || []).indexOf(k) < 0; }).forEach(function(k){
        var f = A.fonts[k], x = el('button', 'rd-it', f.label); x.type = 'button'; A.useFont(k);
        x.style.fontFamily = f.stack; x.setAttribute('aria-pressed', v === k ? 'true' : 'false');
        x.onclick = function(){ act({path: 'font', mode: 'set', value: k}, 'Font: ' + f.label, b.id); };
        list.appendChild(x);
      });
      var same = el('button', 'rd-it', 'Same as the page'); same.type = 'button';
      same.onclick = function(){ act({path: 'font', mode: 'clear'}, 'Font: same as the page', b.id); };
      list.appendChild(same);
      c.appendChild(list);
      c.appendChild(el('p', 'hint', 'Choose which fonts show here in Settings, Fonts.'));
    } else if (it.type === 'size'){
      var row = el('div', 'rd-step'), base = v || (sel ? sizeNow(targetsPeek()) : 17);
      var dn = el('button', null, '−'), up = el('button', null, '+'), field = el('input');
      dn.type = up.type = 'button'; dn.setAttribute('aria-label', 'Smaller'); up.setAttribute('aria-label', 'Larger');
      field.type = 'number'; field.min = it.min; field.max = it.max; field.step = 1; field.value = base; field.setAttribute('aria-label', 'Size in pixels');
      var setSize = function(n){ n = Math.max(it.min, Math.min(it.max, Math.round(n))); field.value = n; act({path: 'size', mode: 'set', value: n}, 'Font size ' + n + 'px', b.id, 'size'); };
      dn.onclick = function(){ setSize((+field.value || base) - it.step); };
      up.onclick = function(){ setSize((+field.value || base) + it.step); };
      field.onchange = function(){ if (+field.value) setSize(+field.value); };
      row.append(dn, field, el('span', 'hint', 'px'), up);
      c.appendChild(row);
      var rs = el('button', 'rd-it', 'Back to the page size'); rs.type = 'button';
      rs.onclick = function(){ act({path: 'size', mode: 'clear'}, 'Font size: page size', b.id); };
      c.appendChild(rs);
    } else if (it.type === 'step' || it.type === 'range'){
      var cur = v != null ? v : defaultOf(it), r2 = el('div', 'rd-step'), out = el('output');
      var minus = el('button', null, '−'), plus = el('button', null, '+');
      minus.type = plus.type = 'button'; minus.setAttribute('aria-label', 'Less'); plus.setAttribute('aria-label', 'More');
      var show = function(n){ out.textContent = (Math.round(n * 100) / 100) + (it.unit || ''); };
      var setN = function(n){
        n = Math.round(Math.max(it.min, Math.min(it.max, n)) / it.step) * it.step;
        n = Math.round(n * 1000) / 1000; cur = n; show(n); if (slider) slider.value = n;
        act({path: it.set, mode: 'set', value: n}, label(n), b.id, it.set);
      };
      minus.onclick = function(){ setN(cur - it.step); };
      plus.onclick = function(){ setN(cur + it.step); };
      show(cur); r2.append(minus, out, plus); c.appendChild(r2);
      var slider = null;
      if (it.type === 'range'){
        slider = el('input'); slider.type = 'range'; slider.min = it.min; slider.max = it.max; slider.step = it.step; slider.value = cur;
        slider.setAttribute('aria-label', it.label);
        slider.oninput = function(){ setN(+slider.value); };
        c.appendChild(slider);
      }
      var back = el('button', 'rd-it', 'Back to normal'); back.type = 'button';
      back.onclick = function(){ act({path: it.set, mode: 'clear'}, it.label + ': normal', b.id); };
      c.appendChild(back);
    }
    return col;
  }
  function defaultOf(it){ return {'hl.h': 100, 'hl.w': .1, ls: 0, ws: 0, lh: 1.75}[it.set] != null ? {'hl.h': 100, 'hl.w': .1, ls: 0, ws: 0, lh: 1.75}[it.set] : it.min; }
  function targetsPeek(){   // the span or paragraph at the start of the selection, without changing anything
    var r = rangeOf([sel[0], sel[0] + 1]); var n = r && r.startContainer; n = n && (n.nodeType === 3 ? n.parentNode : n);
    return n || box;
  }
  function multiCol(){
    var col = el('div', 'rd-col ctl'), c = el('div', 'rd-ctl'); col.appendChild(c);
    c.appendChild(el('h4', null, 'Multiple is on'));
    if (!staged.length) c.appendChild(el('p', 'hint', 'Pick enhancers from the other blocks. Each one waits here, and its block shows a check, until you apply them together.'));
    staged.forEach(function(s, i){
      var row = el('div', 'rd-pick'); row.appendChild(el('span', null, s.label));
      var x = el('button', null, '✕'); x.type = 'button'; x.setAttribute('aria-label', 'Leave out ' + s.label);
      x.onclick = function(){ staged.splice(i, 1); drawBar(); renderDrop(); };
      row.appendChild(x); c.appendChild(row);
    });
    var go = el('button', 'rd-apply', '✓ Apply' + (staged.length ? ' ' + staged.length : '')); go.type = 'button';
    go.setAttribute('aria-disabled', staged.length && (sel || target) ? 'false' : 'true');
    go.onclick = function(){ if (staged.length && (sel || target)) applyStaged(); };
    c.appendChild(go);
    var off = el('button', 'rd-it', 'Turn Multiple off'); off.type = 'button';
    off.onclick = function(){ multi = false; staged = []; closeDrop(); };
    c.appendChild(off);
    return col;
  }

  // ---------- where the bar sits: out of the way of the text, or where you put it ----------
  var moved = null;
  try { moved = JSON.parse(A.lsGet('synapp.rbar') || 'null'); } catch (e){}
  var coarse = window.matchMedia && matchMedia('(pointer: coarse)').matches;
  function clampXY(x, y, w, h){ return [Math.max(4, Math.min(innerWidth - w - 4, x)), Math.max(4, Math.min(innerHeight - h - 4, y))]; }
  var scrolled = 0;
  function place(fit){   // fit: a menu just opened or moved on, so it may scroll the page to make room
    if (bar.hidden) return;
    bar.style.left = '0px'; bar.style.top = '0px';   // measure it at its full width
    var bw = bar.offsetWidth, bh = bar.offsetHeight, x, y;
    if (moved){ var m = clampXY(moved.x, moved.y, bw, bh); x = m[0]; y = m[1]; }
    else {
      var r = !target && sel && rangeOf(sel), ps = !target && sel ? paras(sel) : [];
      var sr = target ? target.anchor.getBoundingClientRect() : r ? r.getBoundingClientRect() : box.getBoundingClientRect();
      var top = Infinity, bottom = -Infinity;
      ps.forEach(function(p){ var b = p.getBoundingClientRect(); top = Math.min(top, b.top); bottom = Math.max(bottom, b.bottom); });
      if (!ps.length){ top = sr.top; bottom = sr.bottom; }
      var below = bottom + 10, above = top - bh - 10, fitsBelow = below + bh < innerHeight - 6, fitsAbove = above > 6;
      if (coarse) y = fitsBelow ? below : fitsAbove ? above : innerHeight - bh - 14;
      else y = fitsAbove ? above : fitsBelow ? below : innerHeight - bh - 14;
      x = sr.left + sr.width / 2 - bw / 2;
      var c2 = clampXY(x, y, bw, bh); x = c2[0]; y = c2[1];
    }
    bar.style.left = x + 'px'; bar.style.top = y + 'px';
    if (!drop.hidden){
      // the menu opens on the far side of the bar from your text, so it never covers what you're changing
      var room = {up: y - 10, down: innerHeight - (y + bh) - 10};
      var ps2 = target ? [target.anchor] : sel ? paras(sel) : [], textTop = ps2.length ? ps2[0].getBoundingClientRect().top : innerHeight / 2;
      var wantUp = moved ? room.down < room.up : y + bh / 2 < textTop;
      drop.style.maxHeight = '';
      var dh = drop.offsetHeight;
      // no room on its side: scroll the page a little so the menu fits there and your selection stays in view
      if (fit && !moved && Date.now() - scrolled > 400){
        var need = (wantUp ? dh - room.up : dh - room.down) + 8, sr2 = target ? target.anchor.getBoundingClientRect() : sel && rangeOf(sel) ? rangeOf(sel).getBoundingClientRect() : null;
        var tabh = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tabh')) || 0;
        if (need > 8 && sr2){
          var can = wantUp ? Math.min(need, innerHeight - 8 - sr2.bottom) : Math.min(need, sr2.top - tabh - 8);
          if (can > 8){ scrolled = Date.now(); window.scrollBy(0, wantUp ? -can : can); return place(false); }
        }
      }
      var up = wantUp ? (dh <= room.up || room.up >= room.down) : (dh > room.down && room.up > room.down);
      drop.style.maxHeight = Math.max(160, Math.min(460, up ? room.up : room.down)) + 'px';
      dh = drop.offsetHeight;
      var dw = drop.offsetWidth, dy = up ? Math.max(4, y - dh - 6) : y + bh + 6;
      var dx = Math.max(4, Math.min(innerWidth - dw - 4, x));
      drop.style.left = dx + 'px'; drop.style.top = dy + 'px';
    }
  }
  var placeQ = false;
  function placeSoon(){ if (placeQ) return; placeQ = true; requestAnimationFrame(function(){ placeQ = false; place(); }); }
  addEventListener('scroll', placeSoon, {passive: true});
  addEventListener('resize', placeSoon);
  function dragging(grip){
    var start = null, lastUp = 0;
    grip.addEventListener('pointerdown', function(e){
      e.preventDefault(); grip.setPointerCapture(e.pointerId);
      var r = bar.getBoundingClientRect(); start = {x: e.clientX, y: e.clientY, l: r.left, t: r.top, moved: false};
    });
    grip.addEventListener('pointermove', function(e){
      if (!start) return;
      var dx = e.clientX - start.x, dy = e.clientY - start.y;
      if (!start.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
      start.moved = true;
      var c = clampXY(start.l + dx, start.t + dy, bar.offsetWidth, bar.offsetHeight);
      moved = {x: c[0], y: c[1]}; place();
    });
    function end(){
      if (!start) return;
      if (start.moved) A.lsSet('synapp.rbar', JSON.stringify(moved));
      else if (Date.now() - lastUp < 380){ moved = null; A.lsSet('synapp.rbar', ''); place(); A.toast('The bar follows your text again'); }
      lastUp = start.moved ? 0 : Date.now(); start = null;
    }
    grip.addEventListener('pointerup', end); grip.addEventListener('pointercancel', end);
  }

  // ---------- opening and closing ----------
  var sel = null, down = false, selT = null;
  function showBar(){
    var first = bar.hidden;
    bar.hidden = false; if (first) drawBar();
    place(); refreshDrop(); placeSoon();
  }
  function hideAll(){ bar.hidden = true; drop.hidden = true; openId = null; path = []; if (target) endTarget(); }
  // open the bar on a look that lives elsewhere (Core Pool): every change goes straight to it
  function editLook(anchor, get, set, done){
    if (target) endTarget();
    sel = null; changed = false; multi = false; staged = [];
    target = {anchor: anchor, get: get, set: set, done: done};
    openId = null; path = []; drop.hidden = true;
    bar.hidden = false; drawBar(); place(); placeSoon();
  }
  function endTarget(){
    var t = target; if (!t) return;
    target = null; bar.hidden = true; drop.hidden = true; openId = null; path = [];
    if (t.done) t.done();
  }
  function check(){
    if (ours || A.tab() !== 'roller') return;
    var s = getSelection();
    var inBox = s.rangeCount && box.contains(s.getRangeAt(0).commonAncestorContainer);
    var o = current();
    if (!o){ if (inBox && s.isCollapsed){ sel = null; hideAll(); } return; }
    if (sel && o[0] === sel[0] && o[1] === sel[1] && !bar.hidden) return;
    if (mode === 'roll'){ sel = null; hideAll(); rollHere(o); return; }   // rolling: the preset goes on what you selected
    var fresh2 = !sel || o[0] !== sel[0] || o[1] !== sel[1];
    sel = o;
    if (fresh2 && changed){ changed = false; if (!bar.hidden) drawBar(); }
    showBar();
  }
  box.addEventListener('pointerdown', function(){ down = true; });
  document.addEventListener('pointerup', function(){ if (!down) return; down = false; setTimeout(check, 20); });
  // a long press on a phone starts a selection and cancels the pointer: wait for the handles instead
  document.addEventListener('pointercancel', function(){ if (!down) return; down = false; clearTimeout(selT); selT = setTimeout(check, 600); });
  document.addEventListener('selectionchange', function(){
    clearTimeout(selT);
    if (ours || down || A.tab() !== 'roller') return;
    selT = setTimeout(check, coarse ? 600 : 250);   // phone handles: wait until they settle
  });
  // the bar and its menus keep the selection: tapping them doesn't clear it
  [bar, drop].forEach(function(x){
    x.addEventListener('mousedown', function(e){ if (!e.target.closest('input,textarea,select')) e.preventDefault(); });
  });
  document.addEventListener('keydown', function(e){
    if (target && e.key === 'Escape'){ if (!drop.hidden) closeDrop(); else endTarget(); return; }
    if (A.tab() !== 'roller') return;
    if (e.key === 'Escape'){ if (!drop.hidden) closeDrop(); else if (!bar.hidden) hideAll(); return; }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !e.target.closest('input,textarea')){ e.preventDefault(); doUndo(); }
  });

  // ---------- tools: undo, clear, default passage, your own text ----------
  function msg(t, err){ var m = $('rl-msg'); m.className = 'msg' + (err ? ' err' : ''); m.textContent = t; }
  function fresh(text){ snapshot(); setText(text); sel = null; changed = false; hideAll(); }
  $('rl-undo').onclick = doUndo;
  $('rl-clear').onclick = function(){
    if (!box.querySelector('span.rx,[data-lh]')){ A.toast('No enhancers to clear'); return; }
    snapshot();
    box.querySelectorAll('span.rx').forEach(function(s){ s.removeAttribute('data-look'); });
    box.querySelectorAll('[data-lh]').forEach(function(p){ p.removeAttribute('data-lh'); p.style.lineHeight = ''; });
    tidy(); hideAll(); A.toast('Enhancers cleared. Undo brings them back.');
  };
  $('rl-reset').onclick = function(){ fresh(DEFAULT); msg(''); A.toast('Back to the default passage'); };
  function ownOpen(on){ $('rl-own').hidden = !on; $('rl-own-btn').setAttribute('aria-expanded', on ? 'true' : 'false'); if (on) $('rl-paste').focus(); }
  $('rl-own-btn').onclick = function(){ ownOpen($('rl-own').hidden); };
  $('rl-own-close').onclick = function(){ ownOpen(false); };
  $('rl-use').onclick = function(){
    var t = $('rl-paste').value.trim();
    if (!t){ A.toast('Paste or type some text first'); return; }
    fresh(t.slice(0, 20000)); ownOpen(false); $('rl-paste').value = ''; msg('');
    A.toast('Your text is in. Select some of it to start.');
  };
  var KINDS = ['.txt', '.md', '.markdown', '.pdf', '.docx', '.xlsx', '.xlsm'];
  function file(fl){
    if (!fl) return;
    var ext = (fl.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
    if (KINDS.indexOf(ext) < 0){ msg('The Roller takes .txt, .md, .pdf, .docx and .xlsx files.', true); return; }
    if (fl.size > A.maxBytes){ msg('Too large: the limit here is ' + A.mb(A.maxBytes) + '.', true); return; }
    msg('Reading ' + fl.name + '...');
    var got;
    if (ext === '.txt' || ext === '.md' || ext === '.markdown') got = fl.text().then(function(t){
      if (ext !== '.txt') t = t.replace(/^#{1,6}\s+/gm, '').replace(/(\*\*|__)(.+?)\1/g, '$2').replace(/^\s*[-*+]\s+/gm, '');
      return t;
    });
    else got = fetch('/api/units', {method: 'POST', body: fl, headers: {'X-File-Name': encodeURIComponent(fl.name)}}).then(function(r){
      if (!r.ok) return r.text().then(function(t){ throw new Error(t || ('error ' + r.status)); });
      return r.json();
    }).then(function(u){ return (u.texts || []).map(function(t){ return String(t).trim(); }).filter(Boolean).join(ext === '.pdf' || ext === '.docx' ? '\n\n' : '\n'); });
    got.then(function(t){
      if (!t.trim()){ msg('No text found in ' + fl.name + '.', true); return; }
      fresh(t.slice(0, 20000));
      msg('From ' + fl.name + (t.length > 20000 ? ': the first 20,000 characters.' : '.'));
      A.toast('Your file is in. Select some of it to start.');
    }).catch(function(e){ msg('Could not read ' + fl.name + ': ' + e.message, true); });
  }
  $('rl-file').onchange = function(){ file(this.files[0]); this.value = ''; };
  document.querySelector('.rl-up').addEventListener('keydown', function(e){ if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); $('rl-file').click(); } });

  // ---------- Settings, Fonts: which fonts the Roller offers ----------
  function drawFonts(){
    var list = $('font-list'); if (!list) return;
    var st = A.st(); st.fontsOff = st.fontsOff || [];
    list.textContent = '';
    Object.keys(A.fonts).forEach(function(k){
      var f = A.fonts[k], b = el('button', null, f.label); b.type = 'button';
      A.useFont(k); b.style.fontFamily = f.stack;
      var on = st.fontsOff.indexOf(k) < 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.title = on ? 'Shown in the Roller: tap to leave it out' : 'Left out: tap to show it in the Roller';
      b.onclick = function(){
        var i = st.fontsOff.indexOf(k);
        if (i >= 0) st.fontsOff.splice(i, 1);
        else {
          if (st.fontsOff.length >= Object.keys(A.fonts).length - 1){ A.toast('Keep at least one font'); return; }
          st.fontsOff.push(k);
        }
        A.save(); drawFonts(); refreshDrop();
      };
      list.appendChild(b);
    });
  }

  // ================= layers, preset rollers and rolling =================
  // A layer is a text and the enhancers it got: {id, text, match: 'word' | 'kind', cat, look}.
  // 'word' catches the same word or phrase anywhere (any case, whole words, like the Word Bank);
  // 'kind' catches everything the detector puts in that category (every number, every date...).
  var layers = [];
  try { layers = (JSON.parse(A.lsGet('synapp.rlayers') || '[]') || []).map(A.cleanLayer).filter(Boolean); } catch (e){ layers = []; }
  function keepLayers(){ A.lsSet('synapp.rlayers', JSON.stringify(layers)); drawLayers(); }
  function richOf(o){   // the look on the selection, as a layer keeps it: its first enhanced part, and the line spacing
    var r = rangeOf(o), l = {};
    if (r){
      var first = [].filter.call(box.querySelectorAll('span.rx'), function(s){ return r.intersectsNode(s); })[0];
      if (first) l = lookOf(first);
    }
    var p = paras(o)[0]; if (p && p.getAttribute('data-lh')) l.lh = +p.getAttribute('data-lh');
    return A.cleanRich(l);
  }
  function kindOf(text){   // the category the whole text belongs to, if the detector sees it as one thing
    var t = text.trim(), sp = A.detect(t);
    var whole = sp.filter(function(s){ return s.start <= 1 && s.end >= t.length - 1; })[0];
    return whole ? whole.cat : null;
  }
  function commitLayer(){
    if (!sel) return;
    var text = selText().replace(/\s+/g, ' ').trim(), look = richOf(sel);
    if (!text){ return; }
    if (!Object.keys(look).length){ A.toast('This part has no enhancers yet'); return; }
    var k = kindOf(text), short = text.length > 40 ? text.slice(0, 38) + '…' : text;
    var buttons = [{label: 'Just “' + short + '”', value: 'word'}];
    if (k) buttons.push({label: 'Everything like it: ' + A.catLabel(k), value: 'kind'});
    var pick = buttons.length > 1 ? A.ask('What should this layer catch?', 'When the roller rolls over other text, this look goes on the same words, or on everything of the same kind.', buttons) : Promise.resolve('word');
    pick.then(function(v){
      if (!v) return;
      var lay = A.cleanLayer({id: A.newId(), text: text, match: v, cat: k, look: look});
      if (!lay){ A.toast('Could not keep that layer'); return; }
      // the same text (or the same kind) again replaces its earlier layer
      layers = layers.filter(function(x){ return !(x.match === lay.match && (lay.match === 'kind' ? x.cat === lay.cat : x.text.toLowerCase() === lay.text.toLowerCase())); });
      layers.push(lay); keepLayers();
      changed = false; sel = null; hideAll(); getSelection().removeAllRanges();
      A.toast('Layer kept: ' + (v === 'kind' ? 'all ' + A.catLabel(k).toLowerCase() : '“' + short + '”') + '. Select the next part.');
    });
  }

  // a look in words, with its colors as dots
  var WEIGHTS = {100: 'Hairline', 200: 'Thin', 300: 'Thin', 400: 'Regular', 500: 'Medium', 600: 'Bold', 700: 'Bold', 800: 'Heavy', 900: 'Heavy'};
  var LINES = {1: 'thin', 2: 'regular', 3: 'bold', 5: 'heavy'};
  function describe(l){
    var out = el('small');
    function part(t, color){ var s = el('span', null, t); if (color){ var d = el('i'); d.style.background = color; s.insertBefore(d, s.firstChild); s.insertBefore(document.createTextNode(' '), d.nextSibling); } out.appendChild(s); }
    if (l.weight) part(WEIGHTS[l.weight] || l.weight);
    if (l.italic) part('Italic');
    if (l.caps) part('CAPS');
    if (l.font && A.fonts[l.font]) part(A.fonts[l.font].label);
    if (l.color) part('Font color', l.color);
    if (l.size) part(l.size + 'px');
    if (l.underline) part('Underline ' + (LINES[l.underline.w] || ''), l.underline.color);
    if (l.overline) part('Overline ' + (LINES[l.overline.w] || ''), l.overline.color);
    if (l.hl) part('Highlight' + (l.hl.h && l.hl.h !== 100 ? ' ' + l.hl.h + '% tall' : '') + (l.hl.w ? ' +' + l.hl.w + 'em wide' : ''), l.hl.color || '#f2c14e');
    if (l.ls != null) part('Letters ' + (l.ls > 0 ? '+' : '') + l.ls + 'em');
    if (l.ws != null) part('Words +' + l.ws + 'em');
    if (l.lh != null) part('Lines ' + l.lh);
    return out;
  }
  function sample(lay){
    var s = el('span', 'rx', lay.text); s.setAttribute('style', styleOf(lay.look)); return s;
  }
  function layerRow(lay, acts){
    var row = el('div', 'ly-row'), t = el('div', 'ly-t');
    t.appendChild(sample(lay));
    if (lay.match === 'kind'){ t.appendChild(document.createTextNode(' ')); t.appendChild(el('span', 'ly-kind', 'all ' + A.catLabel(lay.cat).toLowerCase())); }
    var a = el('div', 'acts');
    acts.forEach(function(x){ var b = el('button', 'pill' + (x.danger ? ' danger' : ''), x.label); b.type = 'button'; b.onclick = x.fn; a.appendChild(b); });
    row.append(t, a, describe(lay.look));
    return row;
  }
  function drawLayers(){
    var box2 = $('rl-layers'); box2.textContent = '';
    layers.forEach(function(lay, i){
      box2.appendChild(layerRow(lay, [
        {label: 'Show', fn: function(){ showLayer(lay); }},
        {label: 'Remove', danger: true, fn: function(){ layers.splice(i, 1); keepLayers(); }}
      ]));
    });
    $('rl-config').setAttribute('aria-disabled', layers.length ? 'false' : 'true');
    $('rl-layers-clear').hidden = !layers.length;
  }
  function showLayer(lay){   // select where the layer's text is in the passage, so it can be changed again
    var hit = matches(box, null, lay)[0];
    if (!hit){ A.toast('That text is not in this passage'); return; }
    var r = rangeOf(hit); if (!r) return;
    r.startContainer.parentElement.scrollIntoView({block: 'center'});
    var s = getSelection(); s.removeAllRanges(); s.addRange(r);
    sel = hit; changed = true; mode !== 'enhance' && setMode('enhance'); bar.hidden = true; showBar(); drawBar();
  }
  $('rl-layers-clear').onclick = function(){
    A.ask('Start a new set of layers?', 'The layers listed here are cleared. Saved preset rollers stay, and so does the passage.', [{label: 'Start new', value: 'y'}])
      .then(function(v){ if (v){ layers = []; keepLayers(); } });
  };
  $('rl-config').onclick = function(){
    if (!layers.length){ A.toast('Finish a section with the green check first'); return; }
    var st = A.st(); st.rollers = st.rollers || [];
    A.ask('Configure Roller', 'Name this roller. It keeps all ' + layers.length + (layers.length === 1 ? ' layer' : ' layers') + ' and rolls them over any text.', [{label: 'Save roller', value: 'ok'}], {input: ''})
      .then(function(name){
        if (name == null) return;
        name = (name || 'My roller').slice(0, 40);
        var same = st.rollers.filter(function(p){ return p.name.toLowerCase() === name.toLowerCase(); })[0];
        var go = same ? A.ask('Replace "' + same.name + '"?', 'A roller with this name exists. Its layers are replaced with these.', [{label: 'Replace', value: 'y'}]) : Promise.resolve('y');
        return go.then(function(v){
          if (!v) return;
          var p = {id: same ? same.id : A.newId(), name: name, hidden: false, layers: JSON.parse(JSON.stringify(layers))};
          if (same) st.rollers[st.rollers.indexOf(same)] = p; else st.rollers.push(p);
          if (st.rollers.length > 24){ A.toast('Up to 24 rollers: delete one in Settings first'); st.rollers.pop(); return; }
          A.save(); presetsChanged(); $('rl-preset').value = p.id;
          A.toast('Saved roller "' + name + '". Roll it here, in Free Rain or on a file.');
        });
      });
  };

  // ---------- rolling: where a preset's layers land ----------
  function escRe(x){ return x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function blockTexts(rt){   // each block's text and where it starts, so matches never run across paragraphs
    var out = [], pos = 0, cur = null;
    texts(rt).forEach(function(t){
      var b = t.parentElement.closest(BLOCKS) || rt;
      if (!rt.contains(b)) b = rt;
      if (!cur || cur.el !== b){ cur = {el: b, start: pos, text: ''}; out.push(cur); }
      cur.text += t.nodeValue; pos += t.nodeValue.length;
    });
    return out;
  }
  function matches(rt, o, lay){
    var found = [];
    blockTexts(rt).forEach(function(b){
      if (lay.match === 'kind'){
        A.detect(b.text).forEach(function(s){ if (s.cat === lay.cat) found.push([b.start + s.start, b.start + s.end]); });
      } else {
        var re; try { re = new RegExp('(?<![\\p{L}\\p{N}_])' + escRe(lay.text).replace(/\s+/g, '\\s+') + '(?![\\p{L}\\p{N}_])', 'giu'); } catch (e){ re = new RegExp(escRe(lay.text), 'gi'); }
        var m; while ((m = re.exec(b.text)) !== null){ if (!m[0].length){ re.lastIndex++; continue; } found.push([b.start + m.index, b.start + m.index + m[0].length]); }
      }
    });
    return o ? found.filter(function(f){ return f[0] < o[1] && f[1] > o[0]; }).map(function(f){ return [Math.max(f[0], o[0]), Math.min(f[1], o[1])]; }) : found;
  }
  function applyLook(rt, o, look){   // lay a whole look over what is there (each of its parts wins)
    var l2 = JSON.parse(JSON.stringify(look)), lh = l2.lh; delete l2.lh;
    if (lh != null) paras(o, rt).forEach(function(p){ p.style.lineHeight = lh; p.setAttribute('data-lh', lh); });
    if (!Object.keys(l2).length) return;
    targets(o, rt).forEach(function(s){ writeLook(s, Object.assign(lookOf(s), l2)); });
    tidy(rt);
  }
  function presetById(id){ return (A.st().rollers || []).filter(function(p){ return p.id === id; })[0] || null; }
  function roll(rt, o, id){   // returns how many places took a layer
    var p = presetById(id); if (!p) return 0;
    var n = 0;
    p.layers.forEach(function(lay){ matches(rt, o, lay).forEach(function(m){ applyLook(rt, m, lay.look); n++; }); });
    return n;
  }
  function rollHere(o){
    var id = $('rl-preset').value, p = presetById(id);
    if (!p){ A.toast('Save a roller first: finish layers, then Configure Roller'); return; }
    snapshot();
    var n = roll(box, o, id);
    getSelection().removeAllRanges();
    A.toast(n ? 'Rolled "' + p.name + '": ' + n + (n === 1 ? ' place' : ' places') : 'Nothing in that part matches "' + p.name + '"');
  }
  $('rl-roll-all').onclick = function(){ rollHere(null); };
  var mode = 'enhance';
  function setMode(m){
    mode = m;
    $('rl-mode').querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-v') === m ? 'true' : 'false'); });
    document.querySelector('.rl-roll').hidden = m !== 'roll';
    if (m === 'roll'){ hideAll(); sel = null; if (!visiblePresets().length) A.toast('No rollers yet: make layers, then Configure Roller'); }
  }
  $('rl-mode').addEventListener('click', function(e){ var b = e.target.closest('button'); if (b) setMode(b.getAttribute('data-v')); });

  // ---------- the Roll with lists (Roller, Free Rain, Synesthesize) and Settings, Preset rollers ----------
  function visiblePresets(){ return (A.st().rollers || []).filter(function(p){ return !p.hidden; }); }
  function fillPickers(){
    document.querySelectorAll('select[data-presets]').forEach(function(s){
      var keep = s.value, plain = s.id === 'rl-preset' ? null : (s.id === 'fr-preset' ? 'Colors' : 'No preset roller');
      s.textContent = '';
      if (plain != null){ var o0 = el('option', null, plain); o0.value = ''; s.appendChild(o0); }
      visiblePresets().forEach(function(p){ var o = el('option', null, p.name); o.value = p.id; s.appendChild(o); });
      if ([].some.call(s.options, function(o){ return o.value === keep; })) s.value = keep;
    });
    var o = $('o-preset'); if (o) o.hidden = !visiblePresets().length;
  }
  function presetsChanged(){ fillPickers(); drawPresets(); }
  function drawPresets(){
    var list = $('preset-list'); if (!list) return;
    var st = A.st(), all = st.rollers || [];
    list.textContent = '';
    if (!all.length){ list.appendChild(el('p', 'empty', 'No preset rollers yet. On the Roller tab, enhance a few parts of the passage, finish each with the green check, then tap Configure Roller.')); return; }
    all.forEach(function(p){
      var d = el('details', 'pr-item' + (p.hidden ? ' hid' : '')), sm = el('summary');
      sm.append(el('b', null, p.name), el('small', null, p.layers.length + (p.layers.length === 1 ? ' layer' : ' layers') + (p.hidden ? ', hidden' : '')));
      var acts = el('span', 'acts');
      function btn(t, fn, cls){ var b = el('button', 'pill' + (cls ? ' ' + cls : ''), t); b.type = 'button'; b.onclick = function(e){ e.preventDefault(); fn(); }; acts.appendChild(b); }
      btn('Add to Core Pool', function(){
        A.ask('Add "' + p.name + '" to the Core Pool?', 'Its ' + p.layers.length + (p.layers.length === 1 ? ' layer goes' : ' layers go') + ' on every reading from now on: words become core enhancers, kinds change the Formula. You can change or remove them in Core Pool.', [{label: 'Add to Core Pool', value: 'y'}])
          .then(function(v){ if (v){ var n = addLayers(p.layers); A.toast(n + (n === 1 ? ' layer' : ' layers') + ' added to the Core Pool'); } });
      });
      btn(p.hidden ? 'Show' : 'Hide', function(){ p.hidden = !p.hidden; A.save(); presetsChanged(); });
      btn('Delete', function(){
        A.ask('Delete "' + p.name + '"?', 'This roller and its ' + p.layers.length + (p.layers.length === 1 ? ' layer are' : ' layers are') + ' removed. Text it already rolled over keeps its looks.', [{label: 'Delete', value: 'y', danger: true}])
          .then(function(v){ if (v){ st.rollers.splice(st.rollers.indexOf(p), 1); A.save(); presetsChanged(); } });
      }, 'danger');
      sm.appendChild(acts); d.appendChild(sm);
      p.layers.forEach(function(lay){
        d.appendChild(layerRow(lay, [{label: 'Add to Core Pool', fn: function(){ addLayers([lay]); A.toast('Added to the Core Pool: ' + (lay.match === 'kind' ? 'all ' + A.catLabel(lay.cat).toLowerCase() : '“' + lay.text + '”')); }}]));
      });
      list.appendChild(d);
    });
  }
  // a preset rolled over a whole file in Synesthesize: its layers join the style the server gets
  function styleWith(style, id){
    var p = presetById(id); if (!p) return style;
    var s = JSON.parse(JSON.stringify(style));
    s.wordbank = s.wordbank || {on: true, words: []}; s.wordbank.on = true; s.look = s.look || {}; s.colors = s.colors || {};
    var words = [];
    p.layers.forEach(function(lay){
      var l = lay.look, flat = {};
      if (l.color) flat.color = l.color;
      if (l.hl && (l.hl.color || !l.color)) flat.bg = l.hl.color || '#f2c14e';
      if (l.font) flat.font = l.font;
      if (l.size) flat.size = Math.max(.8, Math.min(2.5, Math.round(l.size / 17 * 100) / 100));
      if (l.caps) flat.caps = true;
      if (l.weight >= 600) flat.bold = true;
      if (l.italic) flat.italic = true;
      if (l.underline) flat.underline = true;
      flat.rich = l;   // the whole look, for what can draw it
      if (lay.match === 'word') words.push(Object.assign({word: lay.text}, flat));
      else {
        var k = Object.assign({}, s.look[lay.cat] || {});
        if (l.caps) k['case'] = 'upper';
        if (l.weight) { k.bold = l.weight >= 600; k.thin = l.weight <= 300; }
        if (l.italic) k.italic = true;
        if (l.underline){ k.underline = 'solid'; if (l.underline.color) k.ul = l.underline.color; }
        if (l.size) k.scale = Math.max(.8, Math.min(2, Math.round(l.size / 17 * 100) / 100));
        k.rich = l;
        s.look[lay.cat] = k;
        var c = l.color || (l.hl && l.hl.color);
        if (c) s.colors[lay.cat] = {dark: c, light: c};
        if (s.off) delete s.off[lay.cat];
      }
    });
    s.wordbank.words = words.concat(s.wordbank.words || []).slice(0, 200);
    return s;
  }

  // ================= Core Pool: the Formula and your core enhancers =================
  // A category's look as a Roller look (the Formula row's starting point): the lens look and yours, plus its color.
  function catRich(n){
    var lk = A.coreLook(n), r = JSON.parse(JSON.stringify(lk.rich || {}));
    if (r.weight == null && (lk.bold || lk.thin)) r.weight = lk.bold ? 700 : 300;
    if (lk.italic && r.italic == null) r.italic = true;
    if (lk['case'] === 'upper' && r.caps == null) r.caps = true;
    if (lk.scale && lk.scale !== 1 && r.size == null) r.size = Math.round(17 * lk.scale);
    if (lk.underline && lk.underline !== 'none' && !r.underline){ r.underline = {w: 2}; if (lk.ul) r.underline.color = lk.ul; }
    var c = A.color(n); if (c && !r.color) r.color = c;
    return r;
  }
  function setCatRich(n, l){   // back to the core look: the plain fields Editor and files read, the rest as rich
    var st = A.st(), color = l.color, rich = A.cleanRich(l); delete rich.color;
    var lk = {'case': l.caps ? 'upper' : 'normal', bold: (l.weight || 400) >= 600, thin: !!l.weight && l.weight <= 300, italic: !!l.italic,
              underline: l.underline ? 'solid' : 'none', scale: l.size ? Math.max(.8, Math.min(2, Math.round(l.size / 17 * 100) / 100)) : 1};
    if (l.underline && l.underline.color) lk.ul = l.underline.color;
    if (Object.keys(rich).length) lk.rich = rich;
    st.look[n] = lk;
    st.colors[n] = st.colors[n] || {};
    var t = A.theme();
    if (color && color !== A.color(n)) st.colors[n][t] = color;   // only a color you changed is pinned
    else if (!color) delete st.colors[n][t];
    if (!Object.keys(st.colors[n]).length) delete st.colors[n];
    A.save(); A.apply();
  }
  function wordRich(w){   // a Word Bank word's look as a Roller look
    if (w.rich) return JSON.parse(JSON.stringify(w.rich));
    var r = {};
    if (w.color) r.color = w.color;
    if (w.bg) r.hl = {color: w.bg};
    if (w.font) r.font = w.font;
    if (w.size) r.size = Math.round(w.size * 17);
    if (w.caps) r.caps = true;
    if (w.bold) r.weight = 700;
    if (w.italic) r.italic = true;
    if (w.underline) r.underline = {w: 2};
    return r;
  }
  function setWordRich(w, l){   // the whole look as rich, plus the plain fields older readers (chat, kept-layout files) use
    var rich = A.cleanRich(l);
    ['color', 'bg', 'font', 'size', 'caps', 'bold', 'italic', 'underline', 'cat', 'rich'].forEach(function(k){ delete w[k]; });
    if (rich.color) w.color = rich.color;
    if (rich.hl) w.bg = rich.hl.color || '#f2c14e';
    if (rich.font) w.font = rich.font;
    if (rich.size) w.size = Math.max(.8, Math.min(2.5, Math.round(rich.size / 17 * 100) / 100));
    if (rich.caps) w.caps = true;
    if ((rich.weight || 400) >= 600) w.bold = true;
    if (rich.italic) w.italic = true;
    if (rich.underline) w.underline = true;
    if (Object.keys(rich).length) w.rich = rich;
  }
  var editingRow = null;
  function markEditing(row){ if (editingRow) editingRow.classList.remove('editing'); editingRow = row; if (row) row.classList.add('editing'); }
  function drawCore(){
    var fbox = $('cp-formula'), wbox = $('cp-words'); if (!fbox) return;
    var st = A.st(), pl = A.profileLabel();
    $('cp-prof').hidden = !pl;
    $('cp-prof').textContent = pl ? 'Editor is set to the specialty "' + pl + '". The Core Pool changes the core under it; that specialty can still lay its own looks on top.' : '';
    fbox.textContent = ''; fbox.className = 'card m-' + (st.mode || 'c');
    var lastLayer = null;
    A.cats().forEach(function(c){
      if (c.layer !== lastLayer){ if (c.layer === 'grammar') fbox.appendChild(el('p', 'cp-h', 'Grammar layer (when it is on)')); lastLayer = c.layer; }
      var row = el('div', 'cp-row' + (A.isOff(c.name) ? ' off' : ''));
      var sw = el('input', 'rsw'); sw.type = 'checkbox'; sw.setAttribute('role', 'switch'); sw.checked = !A.isOff(c.name); sw.setAttribute('aria-label', c.label + ' on or off');
      sw.onchange = function(){ st.off[c.name] = !sw.checked; A.save(); A.apply(); drawCore(); };
      var main = el('div', 'cp-main'); main.appendChild(el('b', null, c.label));
      var ex = el('span', 'lg-ex'); ex.innerHTML = A.example(c.name); main.appendChild(ex);
      main.appendChild(describe(catRich(c.name)));
      var acts = el('div', 'acts'), ed = el('button', 'pill', 'Edit'); ed.type = 'button';
      ed.onclick = function(){
        markEditing(row);
        editLook(row, function(){ return catRich(c.name); }, function(l){ setCatRich(c.name, l); ex.innerHTML = A.example(c.name); main.replaceChild(describe(catRich(c.name)), main.lastChild); },
          function(){ markEditing(null); drawCore(); });
      };
      var rs = el('button', 'pill', 'Default'); rs.type = 'button'; rs.title = 'Back to the default look';
      rs.onclick = function(){ delete st.look[c.name]; delete st.colors[c.name]; A.save(); A.apply(); drawCore(); };
      acts.append(ed, rs);
      row.append(sw, main, acts); fbox.appendChild(row);
    });
    // your words
    wbox.textContent = '';
    var words = st.wordbank.words;
    if (!st.wordbank.on) wbox.appendChild(el('p', 'hint', 'Your words are switched off in Editor, Word Bank. They are kept, but not used until you turn them back on there.'));
    if (!words.length) wbox.appendChild(el('p', 'empty', 'No core enhancers yet. Add a word or phrase above, or add the layers of a preset roller.'));
    words.forEach(function(w, i){
      var row = el('div', 'cp-row' + (w.off ? ' off' : ''));
      var sw = el('input', 'rsw'); sw.type = 'checkbox'; sw.setAttribute('role', 'switch'); sw.checked = !w.off; sw.setAttribute('aria-label', w.word + ' on or off');
      sw.onchange = function(){ if (sw.checked) delete w.off; else w.off = true; A.save(); A.apply(); drawCore(); };
      var main = el('div', 'cp-main'), sam = el('span', 'rx', w.word);
      if (w.cat){ sam.className = 'c c-' + w.cat; main.append(sam, el('small', null, 'Counts as ' + A.catLabel(w.cat))); }
      else { sam.setAttribute('style', styleOf(wordRich(w))); main.append(sam, describe(wordRich(w))); }
      var acts = el('div', 'acts'), ed = el('button', 'pill', 'Edit'), del = el('button', 'pill danger', 'Delete'); ed.type = del.type = 'button';
      ed.onclick = function(){
        markEditing(row);
        editLook(row, function(){ return wordRich(w); }, function(l){ setWordRich(w, l); A.save(); A.apply(); sam.className = 'rx'; sam.setAttribute('style', styleOf(wordRich(w))); main.replaceChild(describe(wordRich(w)), main.lastChild); },
          function(){
            markEditing(null);
            if (!w.cat && !Object.keys(wordRich(w)).length){ words.splice(words.indexOf(w), 1); A.save(); A.apply(); A.toast('"' + w.word + '" had no look, so it was left out'); }
            drawCore();
          });
      };
      del.onclick = function(){ words.splice(i, 1); A.save(); A.apply(); drawCore(); A.toast('"' + w.word + '" removed from the Core Pool'); };
      acts.append(ed, del);
      row.append(sw, main, acts); wbox.appendChild(row);
    });
    var any = visiblePresets().length || (st.rollers || []).length;
    $('cp-from').hidden = !any;
    var ps = $('cp-preset'); ps.textContent = '';
    (st.rollers || []).forEach(function(p){ var o = el('option', null, p.name + (p.hidden ? ' (hidden)' : '')); o.value = p.id; ps.appendChild(o); });
  }
  function addWord(text, look){   // a core enhancer: first in the list, so it wins
    var st = A.st(), words = st.wordbank.words;
    var w = words.filter(function(x){ return x.word.toLowerCase() === text.toLowerCase(); })[0];
    if (!w){ w = {id: A.newId(), word: text.slice(0, 80)}; words.unshift(w); }
    if (look) setWordRich(w, look);
    if (words.length > 200) words.length = 200;
    return w;
  }
  function addLayers(lays){   // preset layers into the Core Pool: words become core enhancers, kinds change the Formula
    var n = 0;
    lays.forEach(function(lay){
      if (lay.match === 'kind' && lay.cat){ setCatRich(lay.cat, Object.assign(catRich(lay.cat), lay.look)); n++; }
      else { addWord(lay.text, lay.look); n++; }
    });
    A.save(); A.apply();
    return n;
  }
  $('cp-add').onclick = function(){
    var t = $('cp-word').value.trim();
    if (!t){ A.toast('Type a word or phrase first'); return; }
    var w = addWord(t, null); A.save(); $('cp-word').value = '';
    drawCore();
    var row = [].filter.call($('cp-words').querySelectorAll('.cp-row'), function(r){ return r.querySelector('.cp-main').firstChild.textContent === w.word; })[0];
    if (row) row.querySelector('.acts .pill').click();   // straight into the bar to give it a look
  };
  $('cp-word').addEventListener('keydown', function(e){ if (e.key === 'Enter'){ e.preventDefault(); $('cp-add').click(); } });
  $('cp-add-all').onclick = function(){
    var p = presetById($('cp-preset').value); if (!p) return;
    var n = addLayers(p.layers); drawCore();
    A.toast(n + (n === 1 ? ' layer' : ' layers') + ' from "' + p.name + '" added to the Core Pool');
  };

  // ---------- the app tells the Roller which tab is open ----------
  window.synRoller = {
    tab: function(t){ hideAll(); if (t === 'settings'){ drawFonts(); drawPresets(); } if (t === 'core') drawCore(); fillPickers(); },
    file: file, roll: function(rt, o, id){ return roll(rt, o, id); }, styleWith: styleWith
  };
  setText(DEFAULT);
  $('rl-undo').disabled = true;
  drawLayers(); fillPickers();
  if (A.tab() === 'settings'){ drawFonts(); drawPresets(); }
  if (A.tab() === 'core') drawCore();
})();
