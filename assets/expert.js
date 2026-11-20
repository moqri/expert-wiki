(function () {
  var X = window.EXPERT || {};

  // ---- Key findings: tag filter and sort ----
  var list = document.getElementById('claims');
  if (list) {
    var items = [].slice.call(list.children), count = document.getElementById('count'), state = { tag: '', sort: 'rank' };
    var press = function (sel, attr, val) {
      [].forEach.call(document.querySelectorAll(sel), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute(attr) === val)); });
    };
    var render = function () {
      items.sort(function (a, b) {
        if (state.sort === 'year') { var d = (+b.dataset.year) - (+a.dataset.year); if (d) return d; }
        return (+a.dataset.rank) - (+b.dataset.rank);
      });
      var shown = 0;
      items.forEach(function (li) {
        var ok = !state.tag || li.dataset.tags.split('|').indexOf(state.tag) > -1;
        li.hidden = !ok; if (ok) shown++; list.appendChild(li);
      });
      press('[data-filter]', 'data-filter', state.tag); press('[data-sort]', 'data-sort', state.sort);
      count.textContent = 'Showing ' + shown + ' of ' + items.length + ', ' + (state.sort === 'year' ? 'newest first' : 'most important first');
    };
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-filter],[data-sort],.tag'); if (!b) return;
      if (b.hasAttribute('data-sort')) state.sort = b.dataset.sort;
      else {
        state.tag = b.hasAttribute('data-filter') ? b.dataset.filter : b.dataset.tag;
        if (b.classList.contains('tag')) document.getElementById('controls').scrollIntoView({ block: 'start' });
      }
      render();
    });
    render();
  }

  // ---- All papers: word filter ----
  var pf = document.getElementById('pfilter');
  if (pf) pf.addEventListener('input', function () {
    var q = pf.value.toLowerCase().trim();
    [].forEach.call(document.querySelectorAll('#plist li'), function (li) { li.hidden = q && li.dataset.q.indexOf(q) < 0; });
  });

  // ---- All papers: sort ----
  var plist = document.getElementById('plist');
  if (plist) document.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-psort]'); if (!b) return;
    var k = b.dataset.psort, lis = [].slice.call(plist.children);
    lis.sort(function (x, y) {
      if (k === 'title') return x.dataset.title.localeCompare(y.dataset.title);
      var d = (+y.dataset[k]) - (+x.dataset[k]); return d || ((+y.dataset.year) - (+x.dataset.year));
    }).forEach(function (li) { plist.appendChild(li); });
    [].forEach.call(document.querySelectorAll('[data-psort]'), function (c) { c.setAttribute('aria-pressed', String(c === b)); });
  });


  // ---- Claim this page: the expert marks each finding correct, edits it, or flags it for removal ----
  var panel = document.getElementById('claim');
  if (panel && list) {
    var send = document.getElementById('claim-send'), prog = document.getElementById('claim-progress'), cstat = document.getElementById('claim-status');
    var KEY = 'claim:' + X.slug, saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
    saved.items = saved.items || {};
    var save = function () { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {} };
    var lis = [].slice.call(list.children);
    var paint = function () {
      var n = 0;
      lis.forEach(function (li) {
        var r = saved.items[li.dataset.rank] || {}, box = li.querySelector('.claim-act');
        li.dataset.decision = r.d || '';
        if (r.d) n++;
        [].forEach.call(box.querySelectorAll('[data-d]'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.d === r.d)); });
        var ed = box.querySelector('.claim-edit'); ed.hidden = r.d !== 'edit' && r.d !== 'remove';
        ed.querySelector('textarea').placeholder = r.d === 'remove' ? 'Why should this finding be removed? (optional)' : 'Corrected wording';
      });
      prog.textContent = n + ' of ' + lis.length + ' findings reviewed';
    };
    var open = function () {
      if (!panel.hidden) return;
      panel.hidden = false; send.hidden = false; document.body.classList.add('claiming');
      lis.forEach(function (li) {
        var stmt = li.querySelector('.stmt').textContent, r = saved.items[li.dataset.rank] || {};
        var box = document.createElement('div'); box.className = 'claim-act';
        box.innerHTML = '<div class="row" role="group" aria-label="Your review of this finding">' +
          '<button class="chip" type="button" data-d="ok" aria-pressed="false">Correct</button>' +
          '<button class="chip" type="button" data-d="edit" aria-pressed="false">Edit</button>' +
          '<button class="chip" type="button" data-d="remove" aria-pressed="false">Remove</button></div>' +
          '<div class="claim-edit" hidden><textarea rows="3" aria-label="Your edit or comment"></textarea></div>';
        box.querySelector('textarea').value = r.text != null ? r.text : stmt;
        box.querySelector('textarea').addEventListener('input', function (ev) { (saved.items[li.dataset.rank] = saved.items[li.dataset.rank] || {}).text = ev.target.value; save(); });
        box.addEventListener('click', function (ev) {
          var b = ev.target.closest('[data-d]'); if (!b) return;
          var it = saved.items[li.dataset.rank] = saved.items[li.dataset.rank] || {};
          it.d = it.d === b.dataset.d ? '' : b.dataset.d;
          if (it.d === 'remove' && (it.text == null || it.text === stmt)) it.text = '';
          if (it.d === 'edit' && !it.text) it.text = stmt;
          box.querySelector('textarea').value = it.text != null ? it.text : stmt;
          save(); paint();
        });
        li.querySelector('.body').appendChild(box);
      });
      ['claim-add', 'claim-name', 'claim-orcid', 'claim-note'].forEach(function (id) {
        var el = document.getElementById(id); el.value = saved[id] || '';
        el.addEventListener('input', function () { saved[id] = el.value; save(); });
      });
      // Show every finding while reviewing.
      var all = document.querySelector('[data-filter=""]'); if (all) all.click();
      paint(); panel.scrollIntoView({ block: 'start' });
    };
    var q = function (s) { return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, ' ') + '"'; };
    var report = function () {
      var lines = ['page: expert.wiki/' + X.slug + '/', 'reviewer: ' + q(saved['claim-name'] || ''), 'orcid: ' + q(saved['claim-orcid'] || ''), 'findings:'];
      lis.forEach(function (li) {
        var r = saved.items[li.dataset.rank] || {};
        if (!r.d) return;
        lines.push('  - rank: ' + li.dataset.rank, '    paper: ' + li.dataset.paper, '    decision: ' + (r.d === 'ok' ? 'correct' : r.d));
        if (r.d === 'edit') lines.push('    new_statement: ' + q(r.text || ''));
        if (r.d === 'remove' && r.text) lines.push('    reason: ' + q(r.text));
      });
      if ((saved['claim-add'] || '').trim()) lines.push('add: |', saved['claim-add'].trim().split('\n').map(function (l) { return '  ' + l; }).join('\n'));
      if ((saved['claim-note'] || '').trim()) lines.push('note: |', saved['claim-note'].trim().split('\n').map(function (l) { return '  ' + l; }).join('\n'));
      return lines.join('\n');
    };
    document.addEventListener('click', function (ev) {
      var t = ev.target.closest('#claim-open,#claim-submit,#claim-copy,#claim-close'); if (!t) return;
      if (t.id === 'claim-open') { ev.preventDefault(); history.replaceState(null, '', '#claim'); open(); return; }
      if (t.id === 'claim-close') { history.replaceState(null, '', location.pathname); location.reload(); return; }
      var text = report();
      if (t.id === 'claim-copy') {
        (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { cstat.textContent = 'Copied. Paste it into an email or the claim form.'; }, function () { cstat.textContent = 'Copy failed; select the text below.'; cstat.insertAdjacentHTML('beforeend', '<pre></pre>'); cstat.querySelector('pre').textContent = text; });
        return;
      }
      if (!(saved['claim-name'] || '').trim()) { cstat.textContent = 'Please add your name first.'; document.getElementById('claim-name').focus(); return; }
      var u = (X.claim_url || '') + '&title=' + encodeURIComponent('Claim page: ' + X.name) + '&page=' + encodeURIComponent('expert.wiki/' + X.slug + '/') + '&orcid=' + encodeURIComponent(saved['claim-orcid'] || '') + '&review=' + encodeURIComponent(text);
      if (!X.claim_url) { cstat.textContent = 'Sending is not set up yet. Use "Copy review as text".'; return; }
      if (u.length > 7500) { cstat.textContent = 'The review is too long to send in one link. Use "Copy review as text" and paste it into the form that opens.'; u = u.replace(/&review=.*$/, ''); }
      window.open(u, '_blank', 'noopener');
    });
    if (location.hash === '#claim') open();
  }

  // ---- Ask ----
  var form = document.getElementById('ask-form');
  if (!form) return;
  var out = document.getElementById('ask-out'), qbox = document.getElementById('ask-q'), btn = form.querySelector('button');
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var url = function (p) { return p.doi ? 'https://doi.org/' + p.doi : (p.pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + p.pmid + '/' : ''); };
  var srcItem = function (p, i) {
    var t = url(p) ? '<a href="' + esc(url(p)) + '">' + esc(p.title) + '</a>' : esc(p.title);
    return '<li id="src-' + (i + 1) + '">' + t + '<span class="d">' + esc(p.journal) + ' ' + p.year + (p.quote ? ' · “' + esc(p.quote) + '”' : '') + '</span></li>';
  };
  [].forEach.call(document.querySelectorAll('.examples .ex'), function (b) {
    b.addEventListener('click', function () { qbox.value = b.textContent; form.requestSubmit(); });
  });
  qbox.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); form.requestSubmit(); } });

  var corpusP = null;
  var corpus = function () { return corpusP || (corpusP = fetch('corpus.json').then(function (r) { return r.json(); })); };
  var STOP = 'a an and are as at be by can do does for from how in is it of on or that the this to was what when which who why with you your about his her their they there these those has have had not'.split(' ');
  var words = function (s) { return (s.toLowerCase().match(/[a-z0-9+\-]{2,}/g) || []).filter(function (w) { return STOP.indexOf(w) < 0; }); };

  var localSearch = function (q) {
    return corpus().then(function (c) {
      var qw = words(q), N = c.papers.length, df = {};
      if (!qw.length) return [];
      c.papers.forEach(function (p) {
        p._w = words(p.title + ' ' + p.title + ' ' + (p.abstract || ''));
        var seen = {}; p._w.forEach(function (w) { if (!seen[w]) { seen[w] = 1; df[w] = (df[w] || 0) + 1; } });
      });
      var scored = c.papers.map(function (p) {
        var s = 0; qw.forEach(function (w) {
          var tf = p._w.filter(function (x) { return x === w || (w.length > 4 && x.indexOf(w.slice(0, -1)) === 0); }).length;
          if (tf) s += Math.log(1 + N / (df[w] || 1)) * (tf / (tf + 1.5));
        });
        var sents = (p.abstract || '').split(/(?<=\.)\s+/), best = '', bs = -99;
        // Prefer sentences that share words with the question AND report a result, over background sentences.
        sents.forEach(function (t, j) {
          var tw = words(t), k = qw.filter(function (w) { return tw.some(function (x) { return x === w || (w.length > 4 && x.indexOf(w.slice(0, -1)) === 0); }); }).length;
          if (!k) return;
          var sc = k + 0.5 * (j / Math.max(1, sents.length - 1));
          if (/\b(we (found|show|observed|identified|demonstrate)|found|showed|shows|revealed|was associated|were associated|associated with|predicted|outperformed|improved|reduced|increased|higher|lower|accuracy|AUC|hazard|odds|\d+(\.\d+)?%|conclusions?:)/i.test(t)) sc += 1.5;
          if (/\b(remains? (unclear|unknown)|is (unclear|unknown|needed)|have been|has been|aims? to|here,? we|we (aimed|sought)|background:|objectives?:|introduction:|could|may)\b/i.test(t)) sc -= 1.2;
          if (t.length < 40) sc -= 1;
          if (sc > bs) { bs = sc; best = t; }
        });
        return { p: p, s: s, quote: best.length > 260 ? best.slice(0, 257) + '…' : best };
      }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 5);
      return scored.map(function (x) { var p = Object.assign({}, x.p); p.quote = x.quote; return p; });
    });
  };

  var showLocal = function (q, lead) {
    return localSearch(q).then(function (ps) {
      if (!ps.length) { out.innerHTML = '<p class="note">None of the papers here mention that. Try other words.</p>'; return; }
      // Short written answer: the most relevant sentence from each of the top papers, each cited.
      var seen = {}, parts = [];
      ps.slice(0, 3).forEach(function (p, i) {
        var t = (p.quote || '').trim(); if (!t || seen[t]) return; seen[t] = 1;
        if (!/[.!?…]$/.test(t)) t += '.';
        var who = (p.year ? 'A ' + p.year + ' paper' : 'One paper') + (p.journal ? ' in ' + p.journal : '');
        parts.push(esc(who) + ' reports: ' + esc(t) + '<sup><a href="#src-' + (i + 1) + '">' + (i + 1) + '</a></sup>');
      });
      var ans = parts.length ? '<div class="answer"><p>' + parts.join(' ') + '</p></div>' : '';
      out.innerHTML = (lead ? '<p class="note">' + esc(lead) + '</p>' : '') + ans +
        '<p class="note">Searched ' + (X.papers || 'all') + ' papers; quoted from the abstracts of the ' + ps.length + ' most relevant below.</p>' +
        '<ol class="srcs">' + ps.map(function (p, i) { var c = Object.assign({}, p); delete c.quote; return srcItem(c, i); }).join('') + '</ol>';
    });
  };

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var q = qbox.value.trim(); if (!q) return;
    btn.disabled = true;
    // Progress with an estimated time, learned from this visitor's previous answers.
    var est = 20; try { est = Math.min(60, Math.max(8, +localStorage.getItem('askSecs') || 20)); } catch (e) {}
    if (!X.endpoint) est = 2;
    var t0 = Date.now();
    var nRead = X.endpoint ? Math.min(40, X.abstracts || 40) : (X.abstracts || 0);
    var reading = X.papers ? (X.endpoint && nRead < X.papers ? 'Reading the ' + nRead + ' most relevant of ' + X.papers + ' papers…' : 'Reading ' + (X.endpoint ? nRead : X.papers) + ' papers…') : 'Reading the papers…';
    out.innerHTML = '<div class="reading"><p class="note" id="ask-status"></p><div class="bar"><span id="ask-bar"></span></div></div>';
    var st = document.getElementById('ask-status'), bar = document.getElementById('ask-bar');
    var tick = function () {
      var el = (Date.now() - t0) / 1000, left = Math.ceil(est - el);
      if (!st.isConnected) return;
      st.textContent = reading + ' ' + (left > 0 ? 'about ' + left + ' second' + (left === 1 ? '' : 's') + ' left' : 'almost done, taking a little longer than usual');
      bar.style.width = Math.min(95, 100 * (1 - Math.exp(-el / (est * 0.6)))) + '%';
    };
    tick(); var timer = setInterval(tick, 250);
    var done = function () {
      clearInterval(timer); btn.disabled = false;
      if (X.endpoint) { var secs = (Date.now() - t0) / 1000; try { localStorage.setItem('askSecs', String(Math.round((est + secs) / 2))); } catch (e) {} }
    };
    if (!X.endpoint) { showLocal(q).then(done, done); return; }
    fetch(X.endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ expert: X.slug, question: q }) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        var used = [], idx = {};
        var html = d.blocks.map(function (b) {
          var sup = (b.cites || []).map(function (i) {
            if (!(i in idx)) { idx[i] = used.length; used.push(d.sources[i]); }
            return '<a href="#src-' + (idx[i] + 1) + '">' + (idx[i] + 1) + '</a>';
          });
          return esc(b.text).replace(/\n\n+/g, '</p><p>') + (sup.length ? '<sup>' + sup.join(',') + '</sup>' : '');
        }).join('');
        out.innerHTML = '<div class="answer"><p>' + html + '</p></div>' +
          (used.length ? '<ol class="srcs">' + used.map(function (p, i) { var c = Object.assign({}, p); delete c.quote; return srcItem(c, i); }).join('') + '</ol>' : '') +
          '<p class="note">Read ' + d.sources.length + (X.papers > d.sources.length ? ' of ' + X.papers : '') + ' papers; the answer cites ' + used.length + '. Drawn from published papers, not the researcher\'s personal views. Not medical advice.</p>';
      })
      .catch(function () { return showLocal(q, 'The answer service is busy, so here is what the most relevant papers say:'); })
      .then(done, done);
  });
})();
