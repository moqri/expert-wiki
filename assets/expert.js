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
        var sents = (p.abstract || '').split(/(?<=\.)\s+/), best = '', bs = 0;
        sents.forEach(function (t) { var tw = words(t), k = qw.filter(function (w) { return tw.indexOf(w) > -1; }).length; if (k > bs) { bs = k; best = t; } });
        return { p: p, s: s, quote: best.length > 260 ? best.slice(0, 257) + '…' : best };
      }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 5);
      return scored.map(function (x) { var p = Object.assign({}, x.p); p.quote = x.quote; return p; });
    });
  };

  var showLocal = function (q, lead) {
    return localSearch(q).then(function (ps) {
      if (!ps.length) { out.innerHTML = '<p class="note">None of the papers here mention that. Try other words.</p>'; return; }
      out.innerHTML = '<p class="note">' + esc(lead || 'The papers most relevant to your question:') + '</p><ol class="srcs">' + ps.map(srcItem).join('') + '</ol>';
    });
  };

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var q = qbox.value.trim(); if (!q) return;
    btn.disabled = true; out.innerHTML = '<p class="note">Reading the papers…</p>';
    var done = function () { btn.disabled = false; };
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
          '<p class="note">Drawn from published papers, not the researcher\'s personal views. Not medical advice.</p>';
      })
      .catch(function () { return showLocal(q, 'The answer service is busy, so here are the most relevant papers instead:'); })
      .then(done, done);
  });
})();
