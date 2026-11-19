#!/usr/bin/env python3
"""Add a `citations` count to every paper in experts/*/papers.json.

    python3 tools/fetch_citations.py [slug ...]

Counts come from Europe PMC (citedByCount, by PMID) and, for papers without a
PMID, from Crossref (is-referenced-by-count, by DOI). The home page sorts
experts by the sum of these counts.
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def get_json(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def epmc(pmids):
    q = "EXT_ID:(" + " OR ".join(pmids) + ") AND SRC:MED"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": q, "format": "json", "resultType": "lite", "pageSize": 1000})
    d = get_json(url)
    if not d:
        return {}
    return {r["pmid"]: int(r.get("citedByCount") or 0) for r in d["resultList"]["result"] if r.get("pmid")}


def crossref(doi):
    d = get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    return int(d["message"].get("is-referenced-by-count") or 0) if d else None


def main():
    slugs = sys.argv[1:] or [p.parent.name for p in sorted((ROOT / "experts").glob("*/papers.json"))]
    for slug in slugs:
        path = ROOT / "experts" / slug / "papers.json"
        papers = json.loads(path.read_text())
        pmids = [p["pmid"] for p in papers if p.get("pmid")]
        counts = {}
        for i in range(0, len(pmids), 80):
            counts.update(epmc(pmids[i:i + 80]))
            time.sleep(0.3)
        for p in papers:
            if p.get("pmid") and p["pmid"] in counts:
                p["citations"] = counts[p["pmid"]]
            elif p.get("doi"):
                c = crossref(p["doi"])
                if c is not None:
                    p["citations"] = c
        path.write_text(json.dumps(papers, indent=1, ensure_ascii=False) + "\n")
        total = sum(p.get("citations", 0) for p in papers)
        missing = sum("citations" not in p for p in papers)
        print(f"{slug}: {total} citations across {len(papers)} papers ({missing} without a count)")


if __name__ == "__main__":
    main()
