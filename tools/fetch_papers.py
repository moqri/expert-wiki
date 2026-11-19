#!/usr/bin/env python3
"""Fetch an author's papers from PubMed into experts/<slug>/papers.json.

Usage: python3 tools/fetch_papers.py <slug> '<PubMed query>' [--first-name Mahdi] [--max 400]

Keeps only papers where an author with the expert's last name has the given
first name (to drop namesakes). Review the output by hand afterwards: drop
errata, preprints whose published version is present, and anything not theirs.
"""
import argparse
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("failed: " + url)


def text(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("query")
    ap.add_argument("--first-name", default="")
    ap.add_argument("--max", type=int, default=400)
    a = ap.parse_args()
    last = a.slug.split("-")[-1].lower()

    q = urllib.parse.urlencode({"db": "pubmed", "term": a.query, "retmax": a.max, "retmode": "json", "sort": "pub_date"})
    ids = json.loads(get(EUTILS + "esearch.fcgi?" + q))["esearchresult"]["idlist"]
    papers = []
    for i in range(0, len(ids), 100):
        xml = get(EUTILS + "efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(ids[i:i + 100]))
        for art in ET.fromstring(xml).findall(".//PubmedArticle"):
            authors = art.findall(".//AuthorList/Author")
            names = [(x.findtext("LastName") or x.findtext("CollectiveName") or "") for x in authors]
            pos = 0
            for n, x in enumerate(authors, 1):
                if (x.findtext("LastName") or "").lower() == last:
                    fn = x.findtext("ForeName") or ""
                    if not a.first_name or fn.lower().startswith(a.first_name.lower()):
                        pos = n
                        break
            if not pos:
                continue
            types = [t.text for t in art.findall(".//PublicationType")]
            if "Published Erratum" in types:
                continue
            kind = "Article"
            for key, label in [("Preprint", "Preprint"), ("Review", "Review"), ("Letter", "Letter"),
                               ("Comment", "Comment"), ("Editorial", "Editorial"),
                               ("Congress", "Meeting report"), ("Conference Proceedings", "Meeting report")]:
                if any(key in (t or "") for t in types):
                    kind = label
                    break
            pmid = art.findtext(".//PMID")
            doi = next((x.text for x in art.findall(".//ArticleIdList/ArticleId") if x.get("IdType") == "doi"), "")
            year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "0")[:4]
            papers.append({
                "id": "pmid-" + pmid,
                "title": text(art.find(".//ArticleTitle")).rstrip("."),
                "journal": art.findtext(".//Journal/ISOAbbreviation") or art.findtext(".//Journal/Title") or "",
                "year": int(year) if year.isdigit() else 0,
                "doi": doi,
                "pmid": pmid,
                "first_author": names[0] if names else "",
                "n_authors": len(names),
                "position": pos,
                "type": kind,
                "abstract": " ".join(text(t) for t in art.findall(".//Abstract/AbstractText")),
            })
        time.sleep(0.4)
    papers.sort(key=lambda p: -p["year"])
    out = pathlib.Path(__file__).resolve().parent.parent / "experts" / a.slug / "papers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(papers, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(papers)} papers -> {out}")


if __name__ == "__main__":
    main()
