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
  function offIn(node, o){ var r = document.createRange(); r.selectNodeContents(box); r.setEnd(node, o); return r.toString().length; }
  function current(){
    var s = getSelection();
    if (!s.rangeCount || s.isCollapsed) return null;
    var r = s.getRangeAt(0);
    if (!box.contains(r.commonAncestorContainer)) return null;
    var a = offIn(r.startContainer, r.startOffset), b = offIn(r.endContainer, r.endOffset);
    return a < b ? [a, b] : null;
  }
  function texts(){
    var w = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), list = [], t;
    while ((t = w.nextNode())) list.push(t);
    return list;
  }
  function rangeOf(o){
    var r = document.createRange(), pos = 0, started = false, last = null;
    var list = texts();
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
  function cssOf(k){
    var f = A.fonts[k]; if (!f) return '';
    A.useFont(k); return f.stack;
  }
  function styleOf(l){
    var d = [];
    if (l.weight) d.push('font-weight:' + l.weight);
    if (l.italic) d.push('font-style:italic');
    if (l.font) d.push('font-family:' + cssOf(l.font));
    if (l.size) d.push('font-size:' + l.size + 'px');
    if (l.caps) d.push('text-transform:uppercase');
    if (l.ls != null) d.push('letter-spacing:' + l.ls + 'em');
    if (l.ws != null) d.push('word-spacing:' + l.ws + 'em');
    var color = l.color;
    if (l.underline){
      d.push('text-decoration-line:underline;text-decoration-thickness:' + (l.underline.w || 2) + 'px;text-underline-offset:.22em;text-decoration-color:' + (l.underline.color || 'currentColor'));
    }
    var bg = [], pad = 0;
    if (l.overline){ var oc = l.overline.color || 'currentColor'; bg.push('linear-gradient(' + oc + ',' + oc + ') left top/100% ' + (l.overline.w || 2) + 'px no-repeat'); }
    if (l.hl){
      var hc = l.hl.color || '#f2c14e', h = l.hl.h || 100;
      bg.push('linear-gradient(' + hc + ',' + hc + ') center/100% ' + h + '% no-repeat');
      pad = l.hl.w != null ? l.hl.w : .08;
      if (!color && /^#[0-9a-f]{6}$/i.test(hc) && h >= 60) color = A.onColor(hc);   // text stays readable on a full band
    }
    if (bg.length) d.push('background:' + bg.join(','));
    if (pad) d.push('padding:0 ' + pad + 'em');
    if (color) d.push('color:' + color);
    return d.join(';');
  }
  function writeLook(span, l){
    if (!Object.keys(l).length){ span.removeAttribute('data-look'); span.removeAttribute('style'); return; }
    span.setAttribute('data-look', JSON.stringify(l)); span.setAttribute('style', styleOf(l));
  }

  // the spans that cover the selection, splitting text and spans at its edges
  function targets(o){
    var pos = 0, cut = [];
    texts().forEach(function(t){
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
  function tidy(){   // drop spans with no look left, join neighbors that look the same
    box.querySelectorAll('span.rx').forEach(function(s){
      if (!s.getAttribute('data-look')){ var p = s.parentNode; while (s.firstChild) p.insertBefore(s.firstChild, s); p.removeChild(s); }
    });
    box.querySelectorAll('span.rx').forEach(function(s){
      var n = s.nextSibling;
      while (n && n.nodeType === 1 && n.classList.contains('rx') && n.getAttribute('data-look') === s.getAttribute('data-look')){
        while (n.firstChild) s.appendChild(n.firstChild);
        var gone = n; n = n.nextSibling; gone.parentNode.removeChild(gone);
      }
    });
    box.normalize();
  }
  function paras(o){
    var r = rangeOf(o); if (!r) return [];
    return [].filter.call(box.children, function(p){ return r.intersectsNode(p); });
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

  // one change: {path, mode: set|toggle|bump|clear, value, by, min, max}
  function change(c, o){
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
    if (!sel){ A.toast('Select some text first'); return; }
    snapshot(key);
    change(c); reselect(); refreshDrop();
  }

  // ---------- Multiple: pick several, then apply them together ----------
  var multi = false, staged = [];
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
    if (!staged.length || !sel) return;
    snapshot();
    staged.forEach(function(x){ change(x.c); });
    var n = staged.length; staged = [];
    reselect(); closeDrop(); drawBar();
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
  function visible(items){ var one = !/\S\s+\S/.test(selText().trim()); return items.filter(function(it){ return !(it.words && one); }); }
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
    var level = b.children || [], now = sel ? lookAt(sel) : {};
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
    go.setAttribute('aria-disabled', staged.length && sel ? 'false' : 'true');
    go.onclick = function(){ if (staged.length && sel) applyStaged(); };
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
      var r = sel && rangeOf(sel), ps = sel ? paras(sel) : [];
      var sr = r ? r.getBoundingClientRect() : box.getBoundingClientRect();
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
      var ps2 = sel ? paras(sel) : [], textTop = ps2.length ? ps2[0].getBoundingClientRect().top : innerHeight / 2;
      var wantUp = moved ? room.down < room.up : y + bh / 2 < textTop;
      drop.style.maxHeight = '';
      var dh = drop.offsetHeight;
      // no room on its side: scroll the page a little so the menu fits there and your selection stays in view
      if (fit && !moved && Date.now() - scrolled > 400){
        var need = (wantUp ? dh - room.up : dh - room.down) + 8, sr2 = sel && rangeOf(sel) ? rangeOf(sel).getBoundingClientRect() : null;
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
  function hideAll(){ bar.hidden = true; drop.hidden = true; openId = null; path = []; }
  function check(){
    if (ours || A.tab() !== 'roller') return;
    var s = getSelection();
    var inBox = s.rangeCount && box.contains(s.getRangeAt(0).commonAncestorContainer);
    var o = current();
    if (!o){ if (inBox && s.isCollapsed){ sel = null; hideAll(); } return; }
    if (sel && o[0] === sel[0] && o[1] === sel[1] && !bar.hidden) return;
    sel = o; showBar();
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
    if (A.tab() !== 'roller') return;
    if (e.key === 'Escape'){ if (!drop.hidden) closeDrop(); else if (!bar.hidden) hideAll(); return; }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !e.target.closest('input,textarea')){ e.preventDefault(); doUndo(); }
  });

  // ---------- tools: undo, clear, default passage, your own text ----------
  function msg(t, err){ var m = $('rl-msg'); m.className = 'msg' + (err ? ' err' : ''); m.textContent = t; }
  function fresh(text){ snapshot(); setText(text); sel = null; hideAll(); }
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

  // ---------- the app tells the Roller which tab is open ----------
  window.synRoller = {
    tab: function(t){ if (t !== 'roller') hideAll(); if (t === 'settings') drawFonts(); },
    file: file
  };
  setText(DEFAULT);
  $('rl-undo').disabled = true;
  if (A.tab() === 'settings') drawFonts();
})();
