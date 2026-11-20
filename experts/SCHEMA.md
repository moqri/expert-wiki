# Expert page data

Each expert lives in `experts/<slug>/`, where `<slug>` is `firstname-lastname`
in lowercase (for example `mahdi-moqri`). The page is published at
`expert.wiki/<slug>/`. Write only data files; `python3 tools/build_experts.py`
renders the pages, the home page, and each expert's Q&A corpus.

```
experts/<slug>/
  expert.yaml    # who they are, summary, tags
  papers.json    # every paper of theirs we found (the Q&A corpus)
  claims.yaml    # key findings, one paper each
```

## expert.yaml

```yaml
slug: mahdi-moqri
name: Mahdi Moqri
credentials: PhD                 # optional
affiliation: Brigham and Women's Hospital and Harvard Medical School
department: Division of Genetics, Department of Medicine   # optional
areas: [Aging, Alzheimer's]      # home page areas; only these two for now
headline: One sentence on what their work is about, in plain words.
summary:                         # 2-4 short paragraphs, synthesized from papers.json only
  - First paragraph.
  - Second paragraph.
tags: [Biomarkers of aging, Epigenetic clocks]   # claim tags, in display order
search: 'Moqri M[Author]'        # the PubMed query used, so the corpus can be refreshed
links:                           # optional
  - {label: Lab website, url: https://...}
```

## papers.json

A JSON list, newest first. One entry per paper. Drop errata and drop a
preprint when its published version is in the list.

```json
{
  "id": "pmid-37657418",          // "pmid-<PMID>", or "doi-<doi with / and . replaced by ->" when there is no PMID
  "title": "Biomarkers of aging for the identification and evaluation of longevity interventions",
  "journal": "Cell",
  "year": 2023,
  "doi": "10.1016/j.cell.2023.08.003",
  "pmid": "37657418",             // "" if none
  "first_author": "Moqri",
  "n_authors": 28,
  "position": 1,                  // where the expert sits in the author list
  "type": "Review",               // Article, Review, Preprint, Letter, Comment, Meeting report, Editorial
  "abstract": "Full abstract text, unshortened."
}
```

Check every paper is really theirs (same person, not a namesake): look at
first name and affiliation.

## claims.yaml

The key findings. 15 to 30 claims. Every claim is backed by exactly one paper
from papers.json, uses only what that paper's abstract or full text says, and
has the same fields. No internal IDs or status words appear on the page.

```yaml
- rank: 1                         # importance, 1 = most important
  figure: "~90%"                  # short headline number or phrase
  figure_label: of age-related DNA methylation gain falls in PRC2 target regions
  statement: One or two plain sentences stating the finding.
  paper: pmid-39009581            # id from papers.json
  evidence: Genome-wide methylation analysis across somatic tissues   # study type and size
  tags: [Epigenetic clocks]       # from expert.yaml tags
```

`year` comes from the paper. Sort on the page is by rank (default) or newest.

## Reader-facing rules

- No "draft", "AI", "awaiting review" or "in progress" wording anywhere.
- Answers and summaries are described as drawn from the expert's published
  work, never as the expert's personal views.
- Plain language for patients and families; numbers wherever the paper has them.

## Claimed pages and verified findings

Each expert page has a "Claim this page" link. The expert marks every
finding as correct, edits it or flags it for removal, and sends the review,
which opens a prefilled GitHub issue (template `claim-page`). Before
applying it, confirm the sender's identity through the contact details on
their ORCID record or institutional page.

To apply a confirmed review:

```yaml
# expert.yaml
claimed: {by: Randall J. Bateman, on: 2026-11-20}   # replaces the claim link with "Findings reviewed by ..."

# claims.yaml, for each finding marked correct (or edited and confirmed)
  verified: 2026-11-20                              # shows "Expert verified"
```

Edits replace `statement` (and `figure`/`figure_label` if needed). Removals
delete the claim and re-number `rank`.

## New papers

`.github/workflows/new-papers.yml` runs `tools/check_new_papers.py` every
Monday. It searches PubMed with each expert's `search` query for records
added in the last 120 days and queues unseen matches in
`experts/<slug>/pending.json`, then opens a pull request. Pending papers are
never shown to readers; the expert sees them under "Claim this page" and
marks each one Mine or Not mine. Move confirmed papers into `papers.json`
(then run `tools/fetch_citations.py <slug>`), add rejected PMIDs to
`not_mine:` in expert.yaml so they are not queued again, and delete them
from `pending.json`. Optional `first_name:` and `last_name:` in expert.yaml
override the name match.

## Publication record

Each page shows papers, citations, and h-index for all papers and
for papers published in the last five years, a papers-per-year chart,
research interests (linking to the home page keyword filter), co-authors who
also have pages (shared PMIDs or DOIs), and follow links: `feed.xml` (Atom,
30 newest papers) and the expert's PubMed search, where readers can set up
email alerts.
