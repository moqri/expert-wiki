// expert.wiki "Ask" endpoint: answers a question using only one expert's papers.
//
// POST { expert: "<slug>", question: "..." }
// -> { blocks: [{ text, cites: [sourceIndex] }], sources: [{ title, journal, year, doi, pmid }] }
//
// The papers come from https://expert.wiki/<slug>/corpus.json, built by tools/build_experts.py.
import Anthropic from "@anthropic-ai/sdk";

const SLUG = /^[a-z]+(-[a-z]+)+$/;
const MAX_PAPERS = 40; // larger corpora are narrowed to the most relevant papers first
const STOP = new Set("a an and are as at be by can do does for from how in is it of on or that the this to was what when which who why with you your about his her their they there these those has have had not".split(" "));

const words = (s) => (String(s).toLowerCase().match(/[a-z0-9+\-]{2,}/g) || []).filter((w) => !STOP.has(w));

function cors(env, req) {
  const origin = req.headers.get("origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "https://expert.wiki").split(",").map((s) => s.trim());
  return {
    "access-control-allow-origin": allowed.includes(origin) ? origin : allowed[0],
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    vary: "origin",
  };
}

const json = (body, status, headers) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

async function loadCorpus(env, slug, ctx) {
  const url = `${env.SITE_URL || "https://expert.wiki"}/${slug}/corpus.json`;
  const cache = caches.default;
  let res = await cache.match(url);
  if (!res) {
    res = await fetch(url);
    if (!res.ok) return null;
    res = new Response(res.body, res);
    res.headers.set("cache-control", "public, max-age=3600");
    ctx.waitUntil(cache.put(url, res.clone()));
  }
  return res.json();
}

// Keep the papers that share the most words with the question (simple BM25-style score).
function narrow(papers, question) {
  if (papers.length <= MAX_PAPERS) return papers;
  const q = words(question);
  const docs = papers.map((p) => words(`${p.title} ${p.title} ${p.abstract || ""}`));
  const df = {};
  docs.forEach((d) => new Set(d).forEach((w) => (df[w] = (df[w] || 0) + 1)));
  const scored = papers.map((p, i) => {
    let s = 0;
    for (const w of q) {
      const tf = docs[i].filter((x) => x === w).length;
      if (tf) s += Math.log(1 + papers.length / df[w]) * (tf / (tf + 1.5));
    }
    return { p, s, i };
  });
  scored.sort((a, b) => b.s - a.s || a.i - b.i);
  return scored.slice(0, MAX_PAPERS).map((x) => x.p);
}

export default {
  async fetch(req, env, ctx) {
    const h = cors(env, req);
    if (req.method === "OPTIONS") return new Response(null, { headers: h });
    if (req.method !== "POST") return json({ error: "POST only" }, 405, h);

    if (env.LIMITER) {
      const ip = req.headers.get("cf-connecting-ip") || "anon";
      const { success } = await env.LIMITER.limit({ key: ip });
      if (!success) return json({ error: "Too many questions. Please wait a minute." }, 429, h);
    }

    let body;
    try { body = await req.json(); } catch { return json({ error: "Bad JSON" }, 400, h); }
    const slug = String(body.expert || "");
    const question = String(body.question || "").trim().slice(0, 600);
    if (!SLUG.test(slug) || !question) return json({ error: "Need expert and question" }, 400, h);

    const corpus = await loadCorpus(env, slug, ctx);
    if (!corpus) return json({ error: "Unknown expert" }, 404, h);
    const papers = narrow(corpus.papers.filter((p) => p.abstract), question);

    const documents = papers.map((p, i) => ({
      type: "document",
      source: { type: "text", media_type: "text/plain", data: `${p.title}\n\n${p.abstract}` },
      title: `${p.first_author}${p.n_authors > 1 ? " et al." : ""} ${p.year}, ${p.journal}`,
      citations: { enabled: true },
      ...(i === papers.length - 1 ? { cache_control: { type: "ephemeral" } } : {}),
    }));

    const system =
      `You answer questions on expert.wiki using only the published papers of ${corpus.expert} (${corpus.affiliation}), ` +
      `which are attached as documents (title and abstract of each). Rules:\n` +
      `- Use only what the attached papers say. Cite them for every factual point.\n` +
      `- Describe findings as what the papers or studies report ("A 2025 study found..."), never as ${corpus.expert}'s personal opinion or advice, and never speak as ${corpus.expert}.\n` +
      `- If the papers do not address the question, say so plainly in one or two sentences and suggest what they do cover. Do not fill gaps from general knowledge.\n` +
      `- Write for a general reader: plain words, short paragraphs, numbers where the papers give them. Keep it under about 200 words.\n` +
      `- Do not give personal medical advice; for decisions about care, suggest talking with a clinician.`;

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
    let msg;
    try {
      msg = await client.beta.messages.create({
        model: env.MODEL || "claude-opus-5-5",
        max_tokens: 2000,
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
        output_config: { effort: env.EFFORT || "low" },
        system,
        messages: [{ role: "user", content: [...documents, { type: "text", text: question }] }],
      });
    } catch (err) {
      console.error("anthropic error", err?.status, err?.message);
      return json({ error: "Answer service unavailable" }, 502, h);
    }
    if (msg.stop_reason === "refusal") {
      return json({ blocks: [{ text: "This question can't be answered here. Try asking about the research itself.", cites: [] }], sources: [] }, 200, h);
    }

    const blocks = [];
    for (const b of msg.content) {
      if (b.type !== "text") continue;
      const cites = [...new Set((b.citations || []).map((c) => c.document_index).filter((n) => Number.isInteger(n)))];
      blocks.push({ text: b.text, cites });
    }
    const sources = papers.map((p) => ({ title: p.title, journal: p.journal, year: p.year, doi: p.doi, pmid: p.pmid }));
    return json({ blocks, sources }, 200, h);
  },
};
