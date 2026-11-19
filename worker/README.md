# Ask endpoint (Cloudflare Worker)

Answers visitor questions on each expert page using only that expert's
papers (`/<slug>/corpus.json`), with citations to the papers. GitHub Pages
can't hold an API key, so this small Worker does.

## Deploy once (about 5 minutes)

1. Create a free Cloudflare account, then on your computer:

   ```sh
   cd worker
   npm install
   npx wrangler login
   npx wrangler secret put ANTHROPIC_API_KEY   # paste a key from console.anthropic.com
   npx wrangler deploy
   ```

   The last command prints a URL like `https://expert-wiki-ask.<you>.workers.dev`.

2. Put that URL in `experts/site.yaml` as `ask_endpoint`, run
   `python3 tools/build_experts.py`, and commit. Until then the ask box
   searches the papers in the browser instead.

3. Set a monthly spend limit for the key's workspace in the Anthropic Console
   (Settings, Limits), so a traffic spike can't run up a bill.

## Settings (`wrangler.toml`)

- `MODEL`: `claude-opus-5-5` by default. `claude-haiku-5-5` is far cheaper
  per question if traffic grows.
- `EFFORT`: `low` keeps answers fast.
- `LIMITER`: 8 questions per minute per visitor.
- `ALLOWED_ORIGINS`: sites allowed to call it.

Expert pages with more than 40 papers send the 40 most relevant abstracts
for each question.
