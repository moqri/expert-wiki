# expert.wiki

Static site served by GitHub Pages at https://expert.wiki. Each expert page
summarizes one researcher's published work, lists key findings (one paper
each), and answers visitor questions from their papers.

- Data: `experts/<slug>/` (format in `experts/SCHEMA.md`), home page roster in `experts/roster.yaml`, site settings in `experts/site.yaml`
- Build: `python3 tools/build_experts.py` writes `/<slug>/index.html`, `/<slug>/corpus.json` and `/index.html`
- New expert: `python3 tools/fetch_papers.py <slug> '<PubMed query>' --first-name <First>`, then write `expert.yaml` and `claims.yaml`, then build
- Ask box backend: `worker/` (Cloudflare Worker, see `worker/README.md`)
- Older topic pages: `/agingclocks/`, `/apoe4/`
