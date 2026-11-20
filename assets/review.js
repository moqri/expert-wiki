(function () {
  var R = window.REVIEW || { experts: [] }, MAX = 4;
  var $ = function (id) { return document.getElementById(id); };
  var text = $('rv-text'), pick = $('rv-pick'), find = $('rv-find'), count = $('rv-count'), go = $('rv-go'), out = $('rv-out');
  var st = { area: '', q: '', chosen: [] };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var url = function (p) { return p.doi ? 'https://doi.org/' + p.doi : (p.pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + p.pmid + '/' : ''); };
  var STOP = 'a an and are as at be by can do does for from how in is it of on or that the this to was what when which who why with you your about his her their they there these those has have had not we our using study studies here into than more between among'.split(' ');
  var words = function (s) { return (String(s).toLowerCase().match(/[a-z0-9+\-]{3,}/g) || []).filter(function (w) { return STOP.indexOf(w) < 0; }); };
  var byslug = {}; R.experts.forEach(function (x) { byslug[x.slug] = x; });

  function renderPick() {
    var q = st.q.toLowerCase();
    pick.innerHTML = R.experts.filter(function (x) {
      if (st.chosen.indexOf(x.slug) > -1) return true;
      if (st.area && x.areas.indexOf(st.area) < 0) return false;
      return !q || (x.name + ' ' + x.aff + ' ' + x.tags.join(' ') + ' ' + x.head).toLowerCase().indexOf(q) > -1;
    }).map(function (x) {
      var on = st.chosen.indexOf(x.slug) > -1;
      return '<button class="pp" type="button" data-slug="' + esc(x.slug) + '" aria-pressed="' + on + '"><b>' + esc(x.name) + '</b><span>' + esc(x.tags.slice(0, 3).join(' · ')) + '</span></button>';
    }).join('');
    count.textContent = st.chosen.length ? st.chosen.length + ' of ' + MAX + ' chosen: ' + st.chosen.map(function (s) { return byslug[s].name; }).join(', ') : 'Choose up to ' + MAX + ' experts.';
    [].forEach.call(document.querySelectorAll('[data-rarea]'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.rarea === st.area)); });
  }

  // Rank experts by overlap between the submission and their topic tags and headline.
  function suggest() {
    var tw = words(text.value); if (!tw.length) { count.textContent = 'Paste the submission first, then ask for a panel.'; return; }
    var set = {}; tw.forEach(function (w) { set[w] = (set[w] || 0) + 1; });
    var scored = R.experts.map(function (x) {
      var s = 0; words(x.tags.join(' ') + ' ' + x.tags.join(' ') + ' ' + x.head).forEach(function (w) { if (set[w]) s += 1 + Math.log(set[w]); });
      return { slug: x.slug, s: s };
    }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; });
    st.chosen = scored.slice(0, MAX).map(function (x) { return x.slug; });
    if (!st.chosen.length) count.textContent = 'No expert topics matched; choose experts below.';
    renderPick();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('.pp,[data-rarea],#rv-suggest'); if (!b) return;
    if (b.id === 'rv-suggest') return suggest();
    if (b.hasAttribute('data-rarea')) st.area = b.dataset.rarea;
    else {
      var s = b.dataset.slug, i = st.chosen.indexOf(s);
      if (i > -1) st.chosen.splice(i, 1); else if (st.chosen.length < MAX) st.chosen.push(s);
      else { count.textContent = 'At most ' + MAX + ' experts. Remove one first.'; return; }
    }
    renderPick();
  });
  find.addEventListener('input', function () { st.q = find.value.trim(); renderPick(); });

  function sources(used) {
    return used.length ? '<ol class="srcs">' + used.map(function (p) {
      var t = url(p) ? '<a href="' + esc(url(p)) + '">' + esc(p.title) + '</a>' : esc(p.title);
      return '<li>' + t + '<span class="d"><i>' + esc(p.journal) + '</i> ' + p.year + (p.quote ? ' · “' + esc(p.quote) + '”' : '') + '</span></li>';
    }).join('') + '</ol>' : '';
  }

  function renderReview(card, d) {
    var used = [], idx = {}, html = '';
    d.blocks.forEach(function (b) {
      var sup = (b.cites || []).map(function (i) {
        if (!(i in idx)) { idx[i] = used.length; used.push(d.sources[i]); }
        return idx[i] + 1;
      });
      html += esc(b.text) + (sup.length ? '<sup>' + sup.join(',') + '</sup>' : '');
    });
    // Headings from the model arrive as plain lines; render paragraphs and bold the three section names.
    html = html.split(/\n\n+/).map(function (p) { return '<p>' + p.replace(/\n/g, '<br>') + '</p>'; }).join('')
      .replace(/(#+ |\*\*)?(Consistent with published findings|In tension with published findings|Relevant evidence the submission could use)(\*\*)?:?/g, '<strong class="rh">$2</strong>');
    card.querySelector('.rv-body').innerHTML = '<div class="answer">' + html + '</div>' + sources(used) +
      '<p class="note">Read ' + d.sources.length + ' papers; the review cites ' + used.length + '.</p>';
  }

  // Fallback when the review service is unavailable: the most relevant passages from the expert's papers.
  function localReview(card, slug, q) {
    return fetch('/' + slug + '/corpus.json').then(function (r) { return r.json(); }).then(function (c) {
      var qw = words(q), set = {}; qw.forEach(function (w) { set[w] = 1; });
      var df = {}, N = c.papers.length;
      c.papers.forEach(function (p) { p._w = words(p.title + ' ' + (p.abstract || '')); var seen = {}; p._w.forEach(function (w) { if (!seen[w]) { seen[w] = 1; df[w] = (df[w] || 0) + 1; } }); });
      var top = c.papers.map(function (p) {
        var s = 0, seen = {}; p._w.forEach(function (w) { if (set[w] && !seen[w]) { seen[w] = 1; s += Math.log(1 + N / df[w]); } });
        var best = '', bs = 0; (p.abstract || '').split(/(?<=\.)\s+/).forEach(function (t) { var k = words(t).filter(function (w) { return set[w]; }).length; if (k > bs && t.length > 40) { bs = k; best = t; } });
        return { p: p, s: s, quote: best.length > 260 ? best.slice(0, 257) + '…' : best };
      }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 4);
      var used = top.map(function (x) { var p = Object.assign({}, x.p); p.quote = x.quote; return p; });
      card.querySelector('.rv-body').innerHTML = (used.length ? '<p class="note">The review service is unavailable, so these are the most relevant passages from ' + esc(c.expert) + "'s papers.</p>" + sources(used)
        : '<p class="note">None of ' + esc(c.expert) + "'s papers here address this submission.</p>");
    });
  }

  go.addEventListener('click', function () {
    var q = text.value.trim();
    if (!q) { text.focus(); count.textContent = 'Paste the submission first.'; return; }
    if (!st.chosen.length) suggest();
    if (!st.chosen.length) return;
    go.disabled = true;
    out.innerHTML = st.chosen.map(function (s) {
      var x = byslug[s];
      return '<article class="rv-card" data-slug="' + esc(s) + '"><h3><a href="/' + esc(s) + '/">' + esc(x.name) + '</a></h3><p class="aff">' + esc(x.aff) + '</p><div class="rv-body"><p class="note">Reading ' + esc(x.name) + "'s papers…</p></div></article>";
    }).join('') + '<p class="note rv-foot">Each review is drawn only from that expert\'s published papers and describes what the papers report, not the expert\'s personal views.</p>';
    out.scrollIntoView({ block: 'start', behavior: 'smooth' });
    var jobs = st.chosen.map(function (s) {
      var card = out.querySelector('[data-slug="' + s + '"]');
      if (!R.endpoint) return localReview(card, s, q);
      return fetch(R.endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ expert: s, mode: 'review', text: q }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { renderReview(card, d); })
        .catch(function () { return localReview(card, s, q); });
    });
    Promise.all(jobs.map(function (j) { return j.catch(function () {}); })).then(function () { go.disabled = false; });
  });

  renderPick();
})();
