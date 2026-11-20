#!/usr/bin/env python3
"""Build expert pages and the home page from experts/*/ data.

    python3 tools/build_experts.py

Writes <slug>/index.html and <slug>/corpus.json for every experts/<slug>/
that has expert.yaml, papers.json and claims.yaml, and rewrites index.html
from experts/roster.yaml. See experts/SCHEMA.md for the data format.
"""
import html
import json
import pathlib
import re
import urllib.parse

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPERTS = ROOT / "experts"
SITE = yaml.safe_load((EXPERTS / "site.yaml").read_text())
UPDATED = SITE.get("updated", "")
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400'
         '&family=Inter:wght@400;500;600&display=swap">')
e = html.escape


def asset_ver(path):
    """Short content hash for an asset URL, so browsers fetch new CSS/JS after each deploy."""
    import hashlib
    return hashlib.sha1((ROOT / path.lstrip("/")).read_bytes()).hexdigest()[:8]


NOW_YEAR = int(re.search(r"\d{4}", str(UPDATED)).group()) if re.search(r"\d{4}", str(UPDATED)) else 2026
SINCE = NOW_YEAR - 4


def hindex(cs):
    cs = sorted(cs, reverse=True)
    return sum(1 for i, c in enumerate(cs, 1) if c >= i)


def metrics(papers):
    def row(ps):
        cs = [p.get("citations") or 0 for p in ps]
        return {"papers": len(ps), "citations": sum(cs), "h": hindex(cs), "i10": sum(c >= 10 for c in cs)}
    return row(papers), row([p for p in papers if (p.get("year") or 0) >= SINCE])


def per_year(papers, span=20):
    years = [p["year"] for p in papers if p.get("year")]
    if not years:
        return []
    lo = max(min(years), NOW_YEAR - span + 1)
    return [(y, sum(1 for p in papers if p.get("year") == y), sum(p.get("citations") or 0 for p in papers if p.get("year") == y))
            for y in range(lo, NOW_YEAR + 1)]


def paper_keys(p):
    ks = set()
    if p.get("pmid"):
        ks.add("pmid:" + p["pmid"])
    if p.get("doi"):
        ks.add("doi:" + p["doi"].lower())
    return ks


def coauthor_map(all_papers):
    """slug -> [(other slug, number of shared papers)] for experts on the site."""
    owners = {}
    for slug, ps in all_papers.items():
        for p in ps:
            for k in paper_keys(p):
                owners.setdefault(k, set()).add(slug)
    out = {}
    for slug, ps in all_papers.items():
        shared = {}
        for p in ps:
            others = set().union(*(owners[k] for k in paper_keys(p))) - {slug} if paper_keys(p) else set()
            for o in others:
                shared[o] = shared.get(o, 0) + 1
        out[slug] = sorted(shared.items(), key=lambda x: (-x[1], x[0]))
    return out


def feed(ex, papers):
    """Atom feed of the 30 newest papers, so readers can follow an expert."""
    items = []
    for p in papers[:30]:
        u = paper_url(p) or f"https://expert.wiki/{ex['slug']}/"
        items.append(f"""  <entry>
    <title>{e(p['title'])}</title>
    <link href="{e(u)}"/>
    <id>{e(u)}</id>
    <updated>{p.get('year') or NOW_YEAR}-01-01T00:00:00Z</updated>
    <summary>{e(p.get('journal') or '')} {p.get('year') or ''}</summary>
  </entry>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{e(ex['name'])}: new papers · expert.wiki</title>
  <link href="https://expert.wiki/{ex['slug']}/"/>
  <link rel="self" href="https://expert.wiki/{ex['slug']}/feed.xml"/>
  <id>https://expert.wiki/{ex['slug']}/</id>
  <updated>{NOW_YEAR}-01-01T00:00:00Z</updated>
{chr(10).join(items)}
</feed>
"""


def cite_name(p):
    first = p.get("first_author") or ""
    n = p.get("n_authors") or 1
    who = first if n == 1 else (f"{first} and colleagues" if n > 2 else first)
    if n > 2:
        who = f"{first} et al."
    return f"{who} {p.get('year')}"


def paper_url(p):
    if p.get("doi"):
        return "https://doi.org/" + p["doi"]
    if p.get("pmid"):
        return "https://pubmed.ncbi.nlm.nih.gov/" + p["pmid"] + "/"
    return ""


def role(p):
    pos, n = p.get("position") or 0, p.get("n_authors") or 0
    if pos == 1:
        return "First author"
    if n and pos == n:
        return "Senior author"
    return ""


def load(slug_dir):
    ex = yaml.safe_load((slug_dir / "expert.yaml").read_text())
    papers = json.loads((slug_dir / "papers.json").read_text())
    claims = yaml.safe_load((slug_dir / "claims.yaml").read_text()) or []
    return ex, papers, claims


def head(title, desc, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{e(desc)}">
<title>{e(title)}</title>
{FONTS}
<link rel="stylesheet" href="/assets/site.css?v={asset_ver('/assets/site.css')}">
{extra}</head>
"""


def footer(left):
    return f"""  <footer>
    <span>{left}</span>
    <span class="updated">{e(UPDATED)}</span>
  </footer>"""


def expert_page(ex, papers, claims, coauthors=(), names=None, pending=()):
    byid = {p["id"]: p for p in papers}
    slug, name = ex["slug"], ex["name"]
    tags = ex.get("tags") or sorted({t for c in claims for t in c.get("tags", [])})
    counts = {t: sum(t in c.get("tags", []) for c in claims) for t in tags}
    claims = sorted(claims, key=lambda c: c["rank"])

    chips = [f'<button class="chip" type="button" data-filter="" aria-pressed="true">All<span class="n">{len(claims)}</span></button>']
    chips += [f'<button class="chip" type="button" data-filter="{e(t)}" aria-pressed="false">{e(t)}<span class="n">{counts[t]}</span></button>'
              for t in tags if counts[t]]

    items = []
    for c in claims:
        p = byid[c["paper"]]
        ctags = c.get("tags", [])
        tagbtns = "".join(f'<button class="tag" type="button" data-tag="{e(t)}">{e(t)}</button>' for t in ctags)
        url = paper_url(p)
        src = f'<a href="{e(url)}">{e(cite_name(p))} · <i>{e(p["journal"])}</i></a>' if url else f'{e(cite_name(p))} · <i>{e(p["journal"])}</i>'
        ver = '<span class="verified" title="Confirmed by ' + e(name) + (' on ' + e(str(c['verified'])) if c.get('verified') not in (True, None) else '') + '">Expert verified</span>' if c.get('verified') else ''
        items.append(f"""      <li class="claim" data-rank="{c['rank']}" data-year="{p['year']}" data-tags="{e('|'.join(ctags))}" data-paper="{e(c['paper'])}" data-cite="{e(cite_name(p) + ', ' + p['journal'])}">
        <span class="rank">{c['rank']}</span>
        <div class="fig"><span class="n">{e(str(c['figure']))}</span><span class="fl">{e(c['figure_label'])}</span></div>
        <div class="body"><p class="stmt">{e(c['statement'])}</p><div class="c-top">{tagbtns}{ver}</div></div>
        <div class="ev">{src}<span class="d">{e(c.get('evidence', ''))}</span></div>
      </li>""")

    plist = []
    for p in papers:
        url = paper_url(p)
        t = f'<a href="{e(url)}">{e(p["title"])}</a>' if url else e(p["title"])
        r = role(p)
        meta = f'{e(p["journal"])} {p["year"]}' + (f' · {e(p["type"])}' if p.get("type") not in ("Article", "", None) else "") + (f" · {r}" if r else "") + (f' · Cited by {p["citations"]:,}' if p.get("citations") else "")
        plist.append(f'        <li data-q="{e((p["title"] + " " + p["journal"]).lower())}" data-year="{p.get("year") or 0}" data-cites="{p.get("citations") or 0}" data-title="{e(p["title"].lower())}">{t}<span class="d">{meta}</span></li>')

    if ex.get("highlights"):
        byid = {q["id"]: q for q in papers}
        summary = '        <ul class="highlights">\n' + "\n".join(f"          <li>{rich(s, byid)}</li>" for s in ex["highlights"]) + "\n        </ul>"
    else:
        summary = "\n".join(f"        <p>{e(s)}</p>" for s in ex.get("summary", []))
    aff = e(ex["affiliation"]) + (f'<span class="dept">{e(ex["department"])}</span>' if ex.get("department") else "")
    links = " · ".join(f'<a href="{e(l["url"])}">{e(l["label"])}</a>' for l in ex.get("links", []) or [])
    areas = "".join(f'<span class="area">{e(a)}</span>' for a in ex.get("areas", []))
    full = name + (f", {ex['credentials']}" if ex.get("credentials") else "")
    endpoint = SITE.get("ask_endpoint", "")
    qs = ex.get("questions") or []
    examples = ('<div class="examples" role="group" aria-label="Example questions"><span class="label">Try</span>'
                + "".join(f'<button class="ex" type="button">{e(q)}</button>' for q in qs) + "</div>") if qs else ""
    first = name.split()[0]
    allm, recent = metrics(papers)
    ys = per_year(papers)
    peak = max((n for _, n, _ in ys), default=1) or 1
    bars = "".join(f'<span class="yb" style="height:{max(1, round(40 * n / peak))}px" title="{y}: {n} paper{"s" if n != 1 else ""}"></span>' for y, n, c in ys)
    chart = (f'<figure class="years"><div class="ybars" role="img" aria-label="Papers per year, {ys[0][0]} to {ys[-1][0]}">{bars}</div>'
             f'<figcaption>Papers per year, {ys[0][0]}–{ys[-1][0]}</figcaption></figure>') if ys else ""
    names = names or {}
    co = "".join(f'<li><a href="/{e(o)}/">{e(names.get(o, o))}</a> <span class="d">{n} paper{"s" if n != 1 else ""}</span></li>' for o, n in coauthors[:10])
    interests = ", ".join(f'<a href="/#k={e(kslug(t))}">{e(t)}</a>' for t in tags)
    pub = f"https://pubmed.ncbi.nlm.nih.gov/?term={urllib.parse.quote(ex['search'])}&sort=date" if ex.get("search") else ""
    record = f"""    <section class="record" aria-labelledby="rec-h">
      <h2 class="sec" id="rec-h">Publication record</h2>
      <div class="rec-grid">
        <div class="rec-num">
          <div class="rec-row">
          <table class="metrics">
            <thead><tr><th scope="col"></th><th scope="col">All</th><th scope="col">Since {SINCE}</th></tr></thead>
            <tbody>
              <tr><th scope="row">Papers</th><td>{allm['papers']:,}</td><td>{recent['papers']:,}</td></tr>
              <tr><th scope="row">Citations</th><td>{allm['citations']:,}</td><td>{recent['citations']:,}</td></tr>
              <tr><th scope="row">h-index</th><td>{allm['h']}</td><td>{recent['h']}</td></tr>
              <tr><th scope="row">i10-index</th><td>{allm['i10']}</td><td>{recent['i10']}</td></tr>
            </tbody>
          </table>
          {chart}
          </div>
          <p class="fine">Citations from Europe PMC and Crossref. "Since {SINCE}" covers papers published from {SINCE} on.</p>
        </div>
        <dl class="facts">
          <dt>Research interests</dt><dd>{interests}</dd>
          {f'<dt>Co-authors on expert.wiki</dt><dd><ul class="coauthors">{co}</ul></dd>' if co else ''}
          <dt>Follow</dt><dd><a href="feed.xml">New papers (RSS)</a> · {f'<a href="{e(pub)}">Email alerts through PubMed</a>' if pub else ''}</dd>
        </dl>
      </div>
    </section>
"""
    cl = ex.get("claimed") or {}
    nver = sum(1 for c in claims if c.get("verified"))
    claimed_line = (f'<p class="claimed">Findings reviewed by {e(name)}' + (f' · {nver} of {len(claims)} expert verified' if nver else '') + '</p>') if cl else \
        f'<p class="claim-link"><a href="#claim" id="claim-open">Are you {e(first)}? Claim this page</a> to verify or improve these findings.</p>'

    return head(f"{name} · expert.wiki", f"{name}: a summary of their published research, key findings, and answers drawn from their papers.") + f"""<body>
<a class="skip" href="#ask">Skip to ask a question</a>
<div class="wrap">
  <header class="top">
    <a class="mark" href="/">expert<span>.wiki</span></a><span class="crumb">{e(name)}</span>
  </header>
  <main id="main">
    <section class="intro person">
      <p class="label">{areas}</p>
      <h1>{e(full)}</h1>
      <p class="aff">{aff}</p>
      {claimed_line}
    </section>

{record}
    <section class="ask" id="ask" aria-labelledby="ask-h">
      <h2 id="ask-h">Ask about {e(name)}'s research</h2>
      <p class="hint">Answers are drawn only from {e(name)}'s published papers listed on this page, with each point linked to its paper. They describe what the papers report, not personal views or advice from {e(name)}. This is not medical advice.</p>
      <form id="ask-form" autocomplete="off">
        <label class="sr" for="ask-q">Your question</label>
        <textarea id="ask-q" name="q" rows="2" maxlength="600" placeholder="{e(qs[0] if qs else "Type a question about this research")}" required></textarea>
        <button class="go" type="submit">Ask</button>
      </form>
      {examples}
      <div id="ask-out" aria-live="polite"></div>
    </section>

    <section class="intro person about">
      <p class="lede">{e(ex['headline'])}</p>
      <div class="summary">
{summary}
        <p class="meta">Drawn from {len(papers)} papers and preprints{(' · ' + links) if links else ''}</p>
      </div>
    </section>

    <h2 class="sec">Key findings</h2>
    <div class="controls" id="controls" role="region" aria-label="Filter and sort findings">
      <div class="row" role="group" aria-label="Filter by tag"><span class="label">Tags</span>{''.join(chips)}</div>
      <div class="row" role="group" aria-label="Sort"><span class="label">Sort</span><button class="chip" type="button" data-sort="rank" aria-pressed="true">Most important</button><button class="chip" type="button" data-sort="year" aria-pressed="false">Newest</button><span class="count" id="count" aria-live="polite"></span></div>
    </div>
    <section class="claim-panel" id="claim" hidden aria-labelledby="claim-h">
      <h2 id="claim-h">Review these findings</h2>
      <p>Mark each finding as correct, edit its wording, or flag it for removal. You can also add findings that are missing. Your progress is saved in this browser. When you send the review, we confirm your identity through the contact details on your ORCID record or institutional page before publishing any change, and confirmed findings then show "Expert verified".</p>
      <p class="claim-progress" id="claim-progress" aria-live="polite"></p>
    </section>
    <ol class="claims" id="claims">
{chr(10).join(items)}
    </ol>

    <section class="claim-send" id="claim-send" hidden aria-labelledby="claim-send-h">
      <h2 id="claim-send-h">New papers, missing findings and sending</h2>
      <label for="claim-add">Findings to add (one per paragraph, with the paper's DOI or PMID)</label>
      <textarea id="claim-add" rows="4"></textarea>
      <div class="claim-who">
        <label>Your name<input id="claim-name" type="text" autocomplete="name"></label>
        <label>ORCID iD<input id="claim-orcid" type="text" placeholder="0000-0000-0000-0000"></label>
      </div>
      <label for="claim-note">Anything else (summary, tags, papers that are not yours)</label>
      <textarea id="claim-note" rows="3"></textarea>
      <p><button class="go" type="button" id="claim-submit">Send review</button> <button class="chip" type="button" id="claim-copy">Copy review as text</button> <button class="chip" type="button" id="claim-close">Close</button></p>
      <p class="note" id="claim-status" aria-live="polite"></p>
    </section>

    <details class="more" id="papers">
      <summary>All {len(papers)} papers</summary>
      <div class="row ptools"><input class="filter" id="pfilter" type="search" placeholder="Filter papers by word" aria-label="Filter papers"><span class="label">Sort</span><button class="chip" type="button" data-psort="year" aria-pressed="true">Newest</button><button class="chip" type="button" data-psort="cites" aria-pressed="false">Most cited</button><button class="chip" type="button" data-psort="title" aria-pressed="false">Title A–Z</button></div>
      <ol class="plist" id="plist">
{chr(10).join(plist)}
      </ol>
    </details>
    <details class="more" id="about">
      <summary>About this page</summary>
      <div class="about">
        <p>This page gathers {e(name)}'s published papers and preprints from PubMed and Europe PMC. The summary and key findings are written from those papers, and every finding cites exactly one of them.</p>
        <p>"Most important" puts the findings with the widest relevance first. "Newest" sorts by the year of each finding's paper.</p>
        <p>This site is for education and is not medical advice.</p>
      </div>
    </details>
  </main>
{footer('expert.wiki · <a href="/">All experts</a>')}
</div>
<script>window.EXPERT={json.dumps({"slug": slug, "name": name, "pending": [{k: q.get(k) for k in ("id", "title", "journal", "year", "doi", "pmid")} for q in pending], "endpoint": endpoint, "papers": len(papers), "abstracts": sum(1 for q in papers if q.get("abstract")), "claim_url": SITE.get("claim_url", "")})};</script>
<script src="/assets/expert.js?v={asset_ver('/assets/expert.js')}"></script>
</body>
</html>
"""


def corpus(ex, papers):
    keep = ("id", "title", "journal", "year", "doi", "pmid", "first_author", "n_authors", "type", "abstract")
    return {"expert": ex["name"], "slug": ex["slug"], "affiliation": ex["affiliation"],
            "papers": [{k: p.get(k) for k in keep} for p in papers]}


def paper_url(p):
    return f"https://doi.org/{p['doi']}" if p.get("doi") else (f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/" if p.get("pmid") else "")


def rich(text, byid):
    """Tiny markup for highlights: **bold**, *italic*, [text](paper:<id>) or [text](https://...)."""
    t = e(text)
    def link(m):
        label, ref = m.group(1), m.group(2)
        if ref.startswith("paper:"):
            p = byid.get(ref[6:])
            if not p:
                raise SystemExit(f"highlight links unknown paper {ref}")
            title = e(f"{p['title']} ({p['journal']} {p['year']})")
            return f'<a href="{e(paper_url(p))}" title="{title}">{label}</a>'
        return f'<a href="{ref}">{label}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", t)
    return t


def kslug(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')


def home(roster, built):
    areas = SITE["areas"]
    people = []
    for r in roster:
        slug = r["slug"]
        ex = built.get(slug, {})
        cites = ex.get("_cites")
        if cites is None:
            pj = EXPERTS / slug / "papers.json"
            cites = sum(p.get("citations", 0) for p in json.loads(pj.read_text())) if pj.exists() else 0
        people.append((cites, r, ex))
    surname = lambda r: r["name"].split()[-1].lower()
    people.sort(key=lambda x: (surname(x[1]), x[1]["name"].lower()))
    area_id = {a["name"]: a["id"] for a in areas}
    rows = []
    for cites, r, ex in people:
        slug = r["slug"]
        name = e(ex.get("name") or r["name"])
        link = f'<a href="/{slug}/">{name}</a>' if ex else name
        aff = e(ex.get("affiliation") or r["affiliation"])
        ids = " ".join(area_id[x] for x in r["areas"] if x in area_id)
        alltags = ex.get("tags") or []
        skills = "".join(f'<a class="skill" href="#k={e(kslug(t))}" data-k="{e(kslug(t))}">{e(t)}</a>' for t in alltags[:4])
        ks = "|".join(kslug(t) for t in alltags)
        cc = f'<span class="cites">{cites:,} citations</span>' if cites else ""
        rows.append(f'      <li class="person-row" data-areas="{ids}" data-last="{e(surname(r))}" data-cites="{cites}" data-k="{e(ks)}"><div class="who"><span class="pn">{link}</span><span class="pa">{aff}</span></div><div class="skills">{skills}</div>{cc}</li>')
    chips = [f'<button class="chip" type="button" data-area="" aria-pressed="true">All<span class="n">{len(people)}</span></button>']
    for a in areas:
        n = sum(a["name"] in r["areas"] for _, r, _ in people)
        chips.append(f'<button class="chip" type="button" data-area="{e(a["id"])}" aria-pressed="false">{e(a["name"])}<span class="n">{n}</span></button>')
    suggest = SITE["suggest_url"]
    return head("expert.wiki", "Leading researchers' published work, summarized, with questions answered from their papers.") + f"""<body>
<a class="skip" href="#experts">Skip to the experts</a>
<div class="wrap">
  <header class="top">
    <a class="mark" href="/">expert<span>.wiki</span></a><span class="crumb">Home</span>
  </header>
  <main id="main">
    <section class="intro">
      <p class="label">Science from the people who do it</p>
      <h1>Ask the experts, <em>through their published work.</em></h1>
      <p class="lede">{e(SITE['intro'])}</p>
      <p class="suggest"><a class="subtle" href="/review/">Review an abstract with an expert panel</a> · <a class="subtle" href="{e(suggest)}">Suggest the next topic</a></p>
    </section>
    <div class="controls" role="region" aria-label="Filter experts">
      <div class="row"><span class="grp" role="group" aria-label="Filter by area"><span class="label">Area</span>{''.join(chips)}</span><span class="grp sortgrp" role="group" aria-label="Sort experts"><span class="label">Sort</span><button class="chip" type="button" data-esort="name" aria-pressed="true">A–Z</button><button class="chip" type="button" data-esort="cites" aria-pressed="false">Most cited</button></span></div>
      <p class="count ecount"><span id="count" aria-live="polite"></span> <button class="kw" type="button" id="kw" hidden></button></p>
    </div>
    <ol class="people" id="experts">
{chr(10).join(rows)}
    </ol>
  </main>
{footer('expert.wiki · Built with the co-scientist pipeline by <a href="https://moqri.bwh.harvard.edu/">Mahdi Moqri</a>. Sister sites: <a href="https://apoe4.science">apoe4.science</a>, <a href="https://alzprevent.org">alzprevent.org</a> · <a href="' + e(suggest) + '">Suggest a topic</a>')}
</div>
<script>
(function(){{
  var list=document.getElementById('experts'),rows=[].slice.call(list.children),count=document.getElementById('count'),st={{area:'',sort:'name',k:''}},kw=document.getElementById('kw');
  function render(){{
    rows.sort(function(a,b){{return st.sort==='cites'?(+b.dataset.cites)-(+a.dataset.cites):a.dataset.last.localeCompare(b.dataset.last);}});
    var n=0;rows.forEach(function(li){{var ok=(!st.area||li.dataset.areas.split(' ').indexOf(st.area)>-1)&&(!st.k||li.dataset.k.split('|').indexOf(st.k)>-1);li.hidden=!ok;if(ok)n++;list.appendChild(li);}});
    [].forEach.call(document.querySelectorAll('[data-area]'),function(b){{b.setAttribute('aria-pressed',String(b.dataset.area===st.area));}});
    [].forEach.call(document.querySelectorAll('[data-esort]'),function(b){{b.setAttribute('aria-pressed',String(b.dataset.esort===st.sort));}});
    var kl=st.k&&document.querySelector('a.skill[data-k="'+st.k+'"]');kw.hidden=!st.k;if(st.k)kw.innerHTML='Keyword: <b></b> <span aria-hidden="true">×</span>',kw.querySelector('b').textContent=kl?kl.textContent:st.k.replace(/-/g,' '),kw.setAttribute('aria-label','Clear keyword filter');
    count.textContent=n+(n===1?' expert, ':' experts, ')+(st.sort==='cites'?'most cited first (citation counts from Europe PMC)':'A to Z by surname');
  }}
  document.addEventListener('click',function(ev){{
    var b=ev.target.closest('[data-area],[data-esort],a.skill,#kw');if(!b)return;
    if(b.hasAttribute('data-esort'))st.sort=b.dataset.esort;
    else if(b.id==='kw'){{st.k='';history.replaceState(null,'',st.area?'#'+st.area:location.pathname);}}
    else if(b.classList.contains('skill')){{ev.preventDefault();st.k=b.dataset.k;history.replaceState(null,'','#k='+st.k);document.querySelector('.controls').scrollIntoView({{block:'start'}});}}
    else{{st.area=b.dataset.area;history.replaceState(null,'',st.area?'#'+st.area:location.pathname);}}
    render();
  }});
  function fromHash(){{var h=decodeURIComponent(location.hash.slice(1));st.k='';if(h.indexOf('k=')===0)st.k=h.slice(2);else if(document.querySelector('[data-area="'+h+'"]'))st.area=h;render();}}
  window.addEventListener('hashchange',fromHash);fromHash();
}})();
</script>
</body>
</html>
"""


def review_page(roster, built):
    """Expert panel review: paste an abstract, pick experts, get one cited review per expert."""
    endpoint = SITE.get("ask_endpoint", "")
    idx = []
    for r in sorted(roster, key=lambda r: r["name"].split()[-1].lower()):
        ex = built.get(r["slug"])
        if not ex:
            continue
        idx.append({"slug": r["slug"], "name": ex["name"], "aff": ex["affiliation"], "areas": ex.get("areas", []),
                    "tags": ex.get("tags") or [], "head": ex.get("headline", "")})
    areas = SITE["areas"]
    chips = ['<button class="chip" type="button" data-rarea="" aria-pressed="true">All</button>']
    chips += [f'<button class="chip" type="button" data-rarea="{e(a["name"])}" aria-pressed="false">{e(a["name"])}</button>' for a in areas]
    return head("Expert panel review · expert.wiki", "Review an abstract or proposal against the published findings of a panel of experts.") + f"""<body>
<a class="skip" href="#review">Skip to the review form</a>
<div class="wrap">
  <header class="top">
    <a class="mark" href="/">expert<span>.wiki</span></a><span class="crumb">Expert panel review</span>
  </header>
  <main id="main">
    <section class="intro">
      <p class="label">Expert panel review</p>
      <h1>Review a submission <em>against the experts' published findings.</em></h1>
      <p class="lede">Paste an abstract, manuscript summary or specific aims and choose up to four experts. Each review notes where the submission agrees with, or is in tension with, that expert's published papers, and cites the paper for every point. Reviews describe what the papers report, not the experts' personal views.</p>
    </section>

    <section class="ask review" id="review" aria-labelledby="rv-h">
      <h2 id="rv-h">1. Submission</h2>
      <label class="sr" for="rv-text">Abstract or aims</label>
      <textarea id="rv-text" rows="9" maxlength="8000" placeholder="Paste an abstract, manuscript summary or specific aims (up to about 1,200 words)"></textarea>
      <h2>2. Panel</h2>
      <div class="row" role="group" aria-label="Filter experts by area"><span class="label">Area</span>{''.join(chips)}<input class="filter" id="rv-find" type="search" placeholder="Find an expert or topic" aria-label="Find an expert or topic"><button class="chip" type="button" id="rv-suggest">Suggest a panel from the text</button></div>
      <div class="panel-pick" id="rv-pick" role="group" aria-label="Experts"></div>
      <p class="note" id="rv-count" aria-live="polite"></p>
      <button class="go" type="button" id="rv-go">Review</button>
    </section>
    <div id="rv-out" class="rv-out" aria-live="polite"></div>
  </main>
{footer('expert.wiki · <a href="/">All experts</a>')}
</div>
<script>window.REVIEW={json.dumps({"endpoint": endpoint, "experts": idx}, ensure_ascii=False)};</script>
<script src="/assets/review.js?v={asset_ver('/assets/review.js')}"></script>
</body>
</html>
"""


def main():
    roster = yaml.safe_load((EXPERTS / "roster.yaml").read_text())
    built = {}
    dirs = [d for d in sorted(p for p in EXPERTS.iterdir() if p.is_dir())
            if all((d / f).exists() for f in ("expert.yaml", "papers.json", "claims.yaml"))]
    loaded = {d: load(d) for d in dirs}
    co = coauthor_map({ex["slug"]: papers for ex, papers, _ in loaded.values()})
    names = {ex["slug"]: ex["name"] for ex, _, _ in loaded.values()}
    for d in dirs:
        ex, papers, claims = loaded[d]
        pend = json.loads((d / "pending.json").read_text()) if (d / "pending.json").exists() else []
        ids = {p["id"] for p in papers}
        bad = [c["paper"] for c in claims if c["paper"] not in ids]
        if bad:
            raise SystemExit(f"{d.name}: claims cite unknown papers {bad}")
        out = ROOT / ex["slug"]
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(expert_page(ex, papers, claims, co.get(ex["slug"], []), names, pend))
        (out / "feed.xml").write_text(feed(ex, papers))
        (out / "corpus.json").write_text(json.dumps(corpus(ex, papers), ensure_ascii=False))
        ex["_cites"] = sum(p.get("citations", 0) for p in papers)
        built[ex["slug"]] = ex
        if ex["slug"] not in {r["slug"] for r in roster}:
            roster.append({"slug": ex["slug"], "name": ex["name"], "affiliation": ex["affiliation"], "areas": ex.get("areas", [])})
        print(f"built /{ex['slug']}/  {len(claims)} claims, {len(papers)} papers")
    (ROOT / "index.html").write_text(home(roster, built))
    (ROOT / "review").mkdir(exist_ok=True)
    (ROOT / "review" / "index.html").write_text(review_page(roster, built))
    (ROOT / "experts" / "built.json").write_text(json.dumps(sorted(built)) + "\n")
    print("built / home page")


if __name__ == "__main__":
    main()
