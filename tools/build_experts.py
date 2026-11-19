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

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPERTS = ROOT / "experts"
SITE = yaml.safe_load((EXPERTS / "site.yaml").read_text())
UPDATED = SITE.get("updated", "")
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,600;1,400'
         '&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">')
e = html.escape


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
<link rel="stylesheet" href="/agingclocks/style.css">
<link rel="stylesheet" href="/assets/expert.css">
{extra}</head>
"""


def footer(left):
    return f"""  <footer>
    <span>{left}</span>
    <span class="updated">{e(UPDATED)}</span>
  </footer>"""


def expert_page(ex, papers, claims):
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
        items.append(f"""      <li class="claim" data-rank="{c['rank']}" data-year="{p['year']}" data-tags="{e('|'.join(ctags))}">
        <span class="rank">{c['rank']}</span>
        <div class="fig"><span class="n">{e(str(c['figure']))}</span><span class="fl">{e(c['figure_label'])}</span></div>
        <div class="body"><p class="stmt">{e(c['statement'])}</p><div class="c-top">{tagbtns}</div></div>
        <div class="ev">{src}<span class="d">{e(c.get('evidence', ''))}</span></div>
      </li>""")

    plist = []
    for p in papers:
        url = paper_url(p)
        t = f'<a href="{e(url)}">{e(p["title"])}</a>' if url else e(p["title"])
        r = role(p)
        meta = f'{e(p["journal"])} {p["year"]}' + (f' · {e(p["type"])}' if p.get("type") not in ("Article", "", None) else "") + (f" · {r}" if r else "")
        plist.append(f'        <li data-q="{e((p["title"] + " " + p["journal"]).lower())}">{t}<span class="d">{meta}</span></li>')

    summary = "\n".join(f"        <p>{e(s)}</p>" for s in ex.get("summary", []))
    aff = e(ex["affiliation"]) + (f'<span class="dept">{e(ex["department"])}</span>' if ex.get("department") else "")
    links = " · ".join(f'<a href="{e(l["url"])}">{e(l["label"])}</a>' for l in ex.get("links", []) or [])
    areas = "".join(f'<span class="area">{e(a)}</span>' for a in ex.get("areas", []))
    full = name + (f", {ex['credentials']}" if ex.get("credentials") else "")
    endpoint = SITE.get("ask_endpoint", "")
    first = name.split()[0]

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
      <p class="lede">{e(ex['headline'])}</p>
      <div class="summary">
{summary}
        <p class="meta">Drawn from {len(papers)} papers and preprints{(' · ' + links) if links else ''}</p>
      </div>
    </section>

    <section class="ask" id="ask" aria-labelledby="ask-h">
      <h2 id="ask-h">Ask about {e(name)}'s research</h2>
      <p class="hint">Answers are drawn only from {e(name)}'s published papers listed on this page, with each point linked to its paper. They describe what the papers report, not personal views or advice from {e(name)}. This is not medical advice.</p>
      <form id="ask-form" autocomplete="off">
        <label class="sr" for="ask-q">Your question</label>
        <textarea id="ask-q" name="q" rows="2" maxlength="600" placeholder="For example: which aging clocks best predict disease?" required></textarea>
        <button class="go" type="submit">Ask</button>
      </form>
      <div id="ask-out" aria-live="polite"></div>
    </section>

    <h2 class="sec">Key findings</h2>
    <div class="controls" id="controls" role="region" aria-label="Filter and sort findings">
      <div class="row" role="group" aria-label="Filter by tag"><span class="label">Tags</span>{''.join(chips)}</div>
      <div class="row" role="group" aria-label="Sort"><span class="label">Sort</span><button class="chip" type="button" data-sort="rank" aria-pressed="true">Most important</button><button class="chip" type="button" data-sort="year" aria-pressed="false">Newest</button><span class="count" id="count" aria-live="polite"></span></div>
    </div>
    <ol class="claims" id="claims">
{chr(10).join(items)}
    </ol>

    <details class="more" id="papers">
      <summary>All {len(papers)} papers</summary>
      <input class="filter" id="pfilter" type="search" placeholder="Filter papers by word" aria-label="Filter papers">
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
<script>window.EXPERT={json.dumps({"slug": slug, "endpoint": endpoint})};</script>
<script src="/assets/expert.js"></script>
</body>
</html>
"""


def corpus(ex, papers):
    keep = ("id", "title", "journal", "year", "doi", "pmid", "first_author", "n_authors", "type", "abstract")
    return {"expert": ex["name"], "slug": ex["slug"], "affiliation": ex["affiliation"],
            "papers": [{k: p.get(k) for k in keep} for p in papers]}


def home(roster, built):
    areas = SITE["areas"]
    blocks = []
    for area in areas:
        rows = []
        for r in roster:
            if area["name"] not in r["areas"]:
                continue
            slug = r["slug"]
            aff = built.get(slug, {}).get("affiliation") or r["affiliation"]
            name = e(r["name"])
            link = f'<a href="/{slug}/">{name}</a>' if slug in built else name
            others = "".join(f'<span class="area">{e(a)}</span>' for a in r["areas"] if a != area["name"])
            rows.append(f'        <li class="person-row"><span class="pn">{link}</span><span class="pa">{e(aff)}</span>{others}</li>')
        blocks.append(f"""    <section class="area-block" id="{e(area['id'])}">
      <h2>{e(area['name'])}</h2>
      <p class="blurb">{e(area['blurb'])}</p>
      <ul class="people">
{chr(10).join(rows)}
      </ul>
    </section>""")
    suggest = SITE["suggest_url"]
    return head("expert.wiki", "Leading researchers' published work, summarized, with questions answered from their papers.") + f"""<body>
<a class="skip" href="#aging">Skip to the experts</a>
<div class="wrap">
  <header class="top">
    <a class="mark" href="/">expert<span>.wiki</span></a><span class="crumb">Home</span>
  </header>
  <main id="main">
    <section class="intro">
      <p class="label">Science from the people who do it</p>
      <h1>Ask the research, <em>expert by expert.</em></h1>
      <p class="lede">{e(SITE['intro'])}</p>
      <p class="suggest"><a class="go" href="{e(suggest)}">Suggest the next topic</a></p>
    </section>
{chr(10).join(blocks)}
    <section class="area-block" id="topics">
      <h2>Topic pages</h2>
      <ul class="people">
        <li class="person-row"><span class="pn"><a href="/agingclocks/">Aging clocks</a></span><span class="pa">What epigenetic clocks measure and how well they work</span></li>
        <li class="person-row"><span class="pn"><a href="/apoe4/">APOE4</a></span><span class="pa">The strongest common genetic risk for Alzheimer's</span></li>
      </ul>
    </section>
  </main>
{footer('expert.wiki · Built with the co-scientist pipeline by <a href="https://moqri.bwh.harvard.edu/">Mahdi Moqri</a>. Sister sites: <a href="https://apoe4.science">apoe4.science</a>, <a href="https://alzprevent.org">alzprevent.org</a> · <a href="' + e(suggest) + '">Suggest a topic</a>')}
</div>
</body>
</html>
"""


def main():
    roster = yaml.safe_load((EXPERTS / "roster.yaml").read_text())
    built = {}
    for d in sorted(p for p in EXPERTS.iterdir() if p.is_dir()):
        if not all((d / f).exists() for f in ("expert.yaml", "papers.json", "claims.yaml")):
            continue
        ex, papers, claims = load(d)
        ids = {p["id"] for p in papers}
        bad = [c["paper"] for c in claims if c["paper"] not in ids]
        if bad:
            raise SystemExit(f"{d.name}: claims cite unknown papers {bad}")
        out = ROOT / ex["slug"]
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(expert_page(ex, papers, claims))
        (out / "corpus.json").write_text(json.dumps(corpus(ex, papers), ensure_ascii=False))
        built[ex["slug"]] = ex
        if ex["slug"] not in {r["slug"] for r in roster}:
            roster.append({"slug": ex["slug"], "name": ex["name"], "affiliation": ex["affiliation"], "areas": ex.get("areas", [])})
        print(f"built /{ex['slug']}/  {len(claims)} claims, {len(papers)} papers")
    (ROOT / "index.html").write_text(home(roster, built))
    (ROOT / "experts" / "built.json").write_text(json.dumps(sorted(built)) + "\n")
    print("built / home page")


if __name__ == "__main__":
    main()
