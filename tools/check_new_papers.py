#!/usr/bin/env python3
"""Find each expert's new PubMed papers and queue them for the expert to confirm.

    python3 tools/check_new_papers.py [slug ...]

Runs the `search` query from experts/<slug>/expert.yaml for papers added to
PubMed in the last 120 days, keeps those whose author list has the expert's
surname and first name (or initials), and writes the ones not already in
papers.json to experts/<slug>/pending.json. Pending papers are not shown to
readers; the expert confirms or rejects them in "Claim this page", and the
confirmed ones are moved into papers.json by hand (see experts/SCHEMA.md).
"""
import json
import pathlib
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_papers import EUTILS, get, text  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def matches(art, last, first):
    for x in art.findall(".//AuthorList/Author"):
        if (x.findtext("LastName") or "").lower() != last:
            continue
        fn = (x.findtext("ForeName") or "").replace(".", "").replace(" ", "")
        if fn.lower().startswith(first) or (len(fn) <= 3 and fn.isupper() and fn[:1].lower() == first[:1]):
            return True
    return False


def check(slug):
    d = ROOT / "experts" / slug
    ex = yaml.safe_load((d / "expert.yaml").read_text())
    query = ex.get("search")
    if not query:
        return 0
    last = (ex.get("last_name") or slug.split("-")[-1]).lower()
    first = (ex.get("first_name") or ex["name"].split()[0]).lower()
    have = {p.get("pmid") for p in json.loads((d / "papers.json").read_text())}
    pend_path = d / "pending.json"
    pending = json.loads(pend_path.read_text()) if pend_path.exists() else []
    rejected = set(ex.get("not_mine") or [])
    seen = have | {p["pmid"] for p in pending} | rejected
    q = urllib.parse.urlencode({"db": "pubmed", "term": query, "reldate": 120, "datetype": "edat", "retmax": 200, "retmode": "json"})
    ids = [i for i in json.loads(get(EUTILS + "esearch.fcgi?" + q))["esearchresult"]["idlist"] if i not in seen]
    new = []
    if ids:
        xml = get(EUTILS + "efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(ids))
        for art in ET.fromstring(xml).findall(".//PubmedArticle"):
            if not matches(art, last, first):
                continue
            pmid = art.findtext(".//PMID")
            doi = next((x.text for x in art.findall(".//ArticleIdList/ArticleId") if x.get("IdType") == "doi"), "")
            year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "0")[:4]
            new.append({"id": "pmid-" + pmid, "pmid": pmid, "doi": doi, "title": text(art.find(".//ArticleTitle")).rstrip("."),
                        "journal": art.findtext(".//Journal/ISOAbbreviation") or "", "year": int(year) if year.isdigit() else 0})
    if new:
        pend_path.write_text(json.dumps(pending + new, indent=1, ensure_ascii=False) + "\n")
    time.sleep(0.4)
    return len(new)


def main():
    slugs = sys.argv[1:] or json.loads((ROOT / "experts" / "built.json").read_text())
    for slug in slugs:
        n = check(slug)
        if n:
            print(f"{slug}: {n} new papers queued for confirmation")


if __name__ == "__main__":
    main()
