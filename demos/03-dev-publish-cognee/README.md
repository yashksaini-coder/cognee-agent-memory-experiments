# dev-publish + cognee: an editor's note from your own archive

An optional step for [yashksaini-coder/dev-publish](https://github.com/yashksaini-coder/dev-publish),
the hand-written-Markdown-to-dev.to publisher. After a post is successfully published,
ask cognee which **already-published** posts cover the same ground and print the answer
as paste-ready Markdown links — then remember the new post. Recall before remember, in
that order, inside one method, so a brand-new post can never be its own top hit.

This directory is a standalone copy. The upstream repo is untouched: nothing was cloned,
modified or pushed, and the dev-publish side of the change is vendored here as
`seam.patch` (read at `8b42526`, 2026-10-09) for the maintainer to apply by hand.

The published article body is never modified. `contentHash` is sha256 of the raw file
(dev-publish `src/frontmatter.ts:29`), so anything injected into `body_markdown`
diverges from the file, is invisible to `decideAction`, and goes stale forever on any
post the author never edits again.

## What it costs before you run anything

- `@cognee/cognee-ts@0.2.0` pulls a prebuilt native addon. Measured on this machine:
  `node_modules/` is **372 MB** after `npm install`
  (`@cognee/neon-linux-x64-gnu` `dist.unpackedSize` = 323,421,814 bytes per `npm view`).
- Prebuilts exist for **linux-x64-gnu, linux-arm64-gnu, darwin-arm64, win32-x64-msvc
  only**. On Intel macOS, Alpine/musl or win32-arm64, `npm install` exits 0 with a
  printed warning and the failure surfaces later, at `require()`.
- The cognee rows need an LLM: an OpenAI or Anthropic key, any OpenAI-compatible
  endpoint, or a local Ollama model (see `src/llm.ts` and `.env.example`). Ingestion is
  two LLM calls per chunk,
  and the keyed run seeds the archive through `relate()`, so each of the 5 prior posts
  also pays one `GRAPH_COMPLETION` recall whose answer is thrown away (it is what a
  real publish run would have done, five runs ago). Budget 6 recalls, 6 ingests.
- A missing install, or a platform with no prebuilt, prints one line and exits 1 -
  `cognee rows: failed: <reason>` - rather than a stack trace.
- **The pitch here is capability, not economics.** Cognee's own break-even for graph
  ingestion is "roughly 23–26 repeated queries against the same corpus"
  ([cognee.ai/ai-memory-tools-vs-databases](https://www.cognee.ai/ai-memory-tools-vs-databases)).
  A blog with six posts never reaches it. This demo shows no saving and claims none.

## Run it

```
npm install                 # dev deps + cognee; ~40 s and 372 MB, almost all addon
npm test                    # the self-check: 21 assertions, no key, no network
npm run demo                # offline mode: rows 1-3, no key needed
cp .env.example .env        # pick LLM_PROVIDER and a key; npm run demo loads .env
npm run demo                # all five rows once a provider is configured
```

Measured on this machine (Linux, Node v26.8.2, npm 11.19.1, vitest 2.1.9): `npm test` is
~0.2 s as vitest reports it (0.20-0.24 s over four runs) and ~0.55 s wall once node and
vitest startup are counted; `npm run demo` offline is 0.23-0.28 s wall over four runs
(`time npx tsx src/demo.ts`). Install is the slow part, and the 372 MB is most of it. The cognee rows time themselves: the runner prints `performance.now()` per seeding step
and for the whole cognee phase. The keyed run below took 134.6 s for that phase.

## The scoreboard

Five rows, same corpus, same process. Rows 1-3 are what dev-publish can do today with
`data/published.json`, computed not hardcoded. Rows 4 and 5 are cognee against itself:
row 4 is `search(searchType: "CHUNKS", onlyContext: true)`, a plain vector lookup with
no LLM completion; row 5 is `recall()` with the default `GRAPH_COMPLETION`. **The gap
between row 4 and row 5 is the only part of this that is actually about the graph.** If
row 5 returns nothing row 4 did not, the scoreboard says so in public.

### A real run (offline mode)

```
corpus: 5 published posts (9.3 KB), 1 being published
new post: fixtures/blogs/post-just-use-a-database-is-half-right.md
title: "Just use a database" is half right

contentHash   0/5
  sha256 of a different file matches nothing. this is the entire retrieval
  capability of data/published.json.

tag overlap   5/5   [ai agents database graph]
  2 fixtures/blogs/01-grep-as-agent-memory.md  (ai agents)
  3 fixtures/blogs/02-just-use-a-database.md  (ai agents database)
  2 fixtures/blogs/m1-agent-writes-back-not-rag.md  (ai agents)
  1 fixtures/blogs/m6-300-tokens-beat-113k.md  (ai)
  2 fixtures/blogs/m7-benchmarks-vs-production.md  (ai agents)

word overlap  5/5
  (0/5 prior posts share no content word with this one)
  56 fixtures/blogs/01-grep-as-agent-memory.md
  83 fixtures/blogs/02-just-use-a-database.md
  28 fixtures/blogs/m1-agent-writes-back-not-rag.md
  14 fixtures/blogs/m6-300-tokens-beat-113k.md
  11 fixtures/blogs/m7-benchmarks-vs-production.md
  for contrast, experiments/db_memory/results.json: 4/8 phrasings
  of one bug share no content word with the PR that fixed it

cognee rows: skipped (set COGNEE_LLM_API_KEY, or LLM_PROVIDER=ollama for a keyless local run)
there is no offline cognee mode in @cognee/cognee-ts@0.2.0: embeddingProvider:"mock"
removes embeddings only, and MOCK_LLM needs a crate feature the npm build does not ship.
```

**What to look for, and the one number that surprised me.** Row 1 is 0/5, as designed:
a content hash is an equality check, not a retrieval index. But rows 2 and 3 both come
back **5/5**, not 0/5 — the opposite of the contrast line printed right under row 3,
which the demo reads out of `experiments/db_memory/results.json`: on this repo's
synthetic support sessions, 4 of 8 customer phrasings of one bug share no content word
with the PR that fixed it. On one author's prose about one topic, keyword overlap does
not fail by missing things. It fails by matching everything: every prior post shares a
tag, and every prior post
shares between 11 and 83 content words. A ranking where the floor is 11 is not a
ranking. So the question cognee has to answer here is not *whether* there is prior
coverage — it is **which post, which claim, and at what URL** — and rows 4 and 5 are
where that gets tested.

### A real run (with a key)

Run on 2026-10-22 from an empty `.cognee/`, Linux, Node v26.8.2: `claude-haiku-4-5-20251001`
for extraction and completion, `nomic-embed-text` through a local Ollama for embeddings.
Verbatim stdout (log lines filtered out):

```
corpus: 5 published posts (9.3 KB), 1 being published
new post: fixtures/blogs/post-just-use-a-database-is-half-right.md
title: "Just use a database" is half right

contentHash   0/5
  sha256 of a different file matches nothing. this is the entire retrieval
  capability of data/published.json.

tag overlap   5/5   [ai agents database graph]
  2 fixtures/blogs/01-grep-as-agent-memory.md  (ai agents)
  3 fixtures/blogs/02-just-use-a-database.md  (ai agents database)
  2 fixtures/blogs/m1-agent-writes-back-not-rag.md  (ai agents)
  1 fixtures/blogs/m6-300-tokens-beat-113k.md  (ai)
  2 fixtures/blogs/m7-benchmarks-vs-production.md  (ai agents)

word overlap  5/5
  (0/5 prior posts share no content word with this one)
  56 fixtures/blogs/01-grep-as-agent-memory.md
  83 fixtures/blogs/02-just-use-a-database.md
  28 fixtures/blogs/m1-agent-writes-back-not-rag.md
  14 fixtures/blogs/m6-300-tokens-beat-113k.md
  11 fixtures/blogs/m7-benchmarks-vs-production.md
  for contrast, experiments/db_memory/results.json: 4/8 phrasings
  of one bug share no content word with the PR that fixed it

cognee rows: llm anthropic/claude-haiku-4-5-20251001 · embeddings ollama/nomic-embed-text 768d @ http://localhost:11434/api/embed

seeding: 1/5 fixtures/blogs/01-grep-as-agent-memory.md 33699 ms
seeding: 2/5 fixtures/blogs/02-just-use-a-database.md 26910 ms
seeding: 3/5 fixtures/blogs/m1-agent-writes-back-not-rag.md 14612 ms
seeding: 4/5 fixtures/blogs/m6-300-tokens-beat-113k.md 16902 ms
seeding: 5/5 fixtures/blogs/m7-benchmarks-vs-production.md 22780 ms

cognee as a vector store [search CHUNKS, onlyContext, no LLM]
  0.816 fixtures/blogs/02-just-use-a-database.md
  0.757 fixtures/blogs/m1-agent-writes-back-not-rag.md
  0.738 fixtures/blogs/01-grep-as-agent-memory.md
  0.702 fixtures/blogs/m7-benchmarks-vs-production.md
  0.640 fixtures/blogs/m6-300-tokens-beat-113k.md

cognee as a memory layer [recall, GRAPH_COMPLETION]
  related: fixtures/blogs/post-just-use-a-database-is-half-right.md
    - [grep as Agent Memory: What It Costs at 100,000 Sessions](https://dev.to/example/grep-as-agent-memory)
    - [The moment your agent writes back, it isn't RAG anymore](https://dev.to/example/agent-writes-back-not-rag)
    note: Based on the knowledge graph provided, the earlier posts that cover the same ground as "Just use a database" is half right are:  1. <link> 2. <link>  The first post discusses performance trade-offs between different memory storage approaches (grep vs indexed databases), which directly relates to the
    sources: graph 1.000

cognee phase: 134571 ms
```

**What it shows.** Row 4, the plain vector lookup, ranks every prior post and puts
`02-just-use-a-database.md` first (0.816). That is the right answer: the new post is the
short version of article 02. Row 5 is selective - two of five, both real URLs from
`published.json` - but it **left out 02**, the post row 4 ranked first, and kept 01 (grep)
and m1. So on this corpus the graph did not beat the vector lookup at finding the closest
prior post; what it added is a short list with a stated reason. A second run from an empty
store reproduced it exactly - the same five row-4 scores, the same two links, 02 left out
again. Six excerpts, one model: an observation, not a benchmark.

Getting here took two fixes for `@cognee/cognee-ts` 0.2.0 behaviour, both reproduced in
isolation before they were worked around (see Caveats).

The mechanism being tested, quoted so it can be checked: cognee documents that
`GRAPH_COMPLETION` embeds the query once, then searches "concurrently across every
vector index collection registered by the loaded DataPoint models — typically
`Entity_name`, `EntityType_name`, `TextSummary_text`, `DocumentChunk_text` — plus the
edge collection `EdgeType_relationship_name`", and expands 1 hop around those seeds
([docs.cognee.ai/core-concepts/main-operations/legacy-operations/search](https://docs.cognee.ai/core-concepts/main-operations/legacy-operations/search)).
That is the claim: two differently-worded posts connect through a shared *entity* or
*relationship phrase*, not a shared word. It depends on the LLM extraction having
pulled the same entity out of both, and it can fail.

## Where it drops into dev-publish

`src/index.ts`, inside `main()`'s per-file success path, as the new last statement of
the inner `try` that began at `:100` — immediately after
`saveState(cfg.statePath, map)` + `console.log(\`${verb}: ...\`)` at `:150-151`. The
whole diff is `seam.patch`: five files, 27 added lines, generated with `git diff` and
verified with `git apply --check` against the five fetched files at `8b42526`. One of
the five is `package.json`: the lazy `await import` is still an import as far as `tsc`
is concerned, so without the dependency `pnpm typecheck` fails with TS2307.

That spot and nowhere else, because:

- It is the only point in the program where the published `result.url` and
  `articleId`, the final rewritten `body`, the validated `blog.frontmatter` and the
  `verb` all exist and are known-good.
- It is downstream of the state write, so a cognee failure cannot corrupt
  `data/published.json` or duplicate an article. The call site swallows its own error
  and logs; it deliberately does not push to `failures`, or a memory outage would turn
  a successful publish into a red build.
- The `skip` branch returns early at `:56-60`, so unchanged posts are never
  re-ingested. The feature is driven by the same `contentHash` that drives publishing,
  for free.

Rejected: injecting related links into `body_markdown` before `input` is built at `:89`
(the published body would diverge from the file while `contentHash` still hashes the raw
file, so the injected section is invisible to `decideAction` and silently stale);
touching `decideAction`, which is pure and synchronous and must stay that way; a
separate CLI entrypoint, which would duplicate the loop, the local-assets guard and the
state handling.

## The corpus is six trimmed excerpts, and the URLs are fake

`fixtures/blogs/` holds 6 Markdown posts with dev-publish frontmatter added: each is the
opening ~40 lines of a write-up from this repo, 9.3 KB of body text across the five
archived ones. The archive is the five write-ups approved in the root README's review
table (articles 01 and 02, mini-posts m1, m6, m7); the one being published is
`posts/post-just-use-a-database-is-half-right.md`, the short version of article 02 —
chosen because genuine prior coverage exists, in different words.

Every dev.to URL in `fixtures/published.json` is a placeholder on `dev.to/example/...`.
Nothing in this repo is published yet (root README: "Canonical links will be added once
the articles are live"). The `contentHash` values are real sha256 digests of the fixture
files, so row 1 is a real computation.

## Caveats

- **A dataset in `@cognee/cognee-ts` 0.2.0 ingests once.** The second `remember()` into
  it returns `PipelineRunCompleted` in ~2 ms having stored nothing, and `add()` +
  `cognify()` reports `"alreadyCompleted": true` with 0 chunks. The first keyed run seeded
  five posts and the store held one. So `relate()` now remembers each post into its own
  dataset (`datasetFor()` in `src/memory.ts`), and recall stays unfiltered.
- **`search()` honours only the first name in `datasets`.** `["c", "b"]` returned c's
  chunks alone. Row 4 therefore searches unfiltered; the store holds nothing else.
- **No Claude 5.x model works with this SDK.** It always sends `temperature` (0 by
  default; `null` is rejected as "expected f64"), and every `claude-*-5*` model plus
  opus-4-7 and opus-4-8 answers 400 "`temperature` is deprecated for this model" -
  probed one by one. `src/llm.ts` refuses them up front; claude-haiku-4-5 and
  claude-sonnet-4-6 work.
- **The SDK keeps its metadata database in the cwd** (`sqlite:./cognee.db` by default),
  outside `systemRootDirectory`. `src/llm.ts` sets `relationalDbUrl` to
  `.cognee/cognee.db` so clearing `.cognee/` really resets the store. It also writes an
  anonymous telemetry id to `./.anon_id`, which no setting moved; it is git-ignored.
- **The overlap note is unvalidated prose.** `relate()` prints a `note:` line taken from
  `recall().searchResponse.result.data`, which is LLM text over a graph the same LLM
  built. Treat it as a prompt to the author, never as a finding. URLs are stripped out of
  it and rendered only from the intersection with `published.json` — the assertion
  named below is exactly that case, and it caught a real leak
  through the note line while this was being written. That is the *second* assertion,
  `drops a dev.to url that is not in published.json`.
- **Scores are printed, never used to decide.** `CogneeRecallItem.score` is a required
  number whose scale and direction are undocumented, and `GRAPH_COMPLETION` ranks
  triplets by *lowest* score. Any threshold would be invented, so there is none.
- **This does not run in CI.** A fresh GitHub Actions checkout has an empty
  `./.cognee/`, so the archive finds nothing there. The feature is local-only unless the
  store is cached or a backfill is written. `seam.patch` does not touch
  `.github/workflows/publish.yml`.
- **The seam is not covered by any test.** Stated at the top of `seam.patch` too. What
  *was* checked: applying `seam.patch` to the five files at `8b42526`, copying
  `src/llm.ts`, `src/memory.ts` and both test files in and running dev-publish's own
  gates - `tsc --noEmit` clean, `vitest run` 67 passed across 7 files, including the existing
  `config.test.ts` `toEqual` block the new config key would otherwise have broken. That
  says the seam compiles and reddens nothing; it still says nothing about its behaviour
  against a real dev.to key.
- **Row 3's tokenizer is a byte-for-byte port** of `experiments/db_memory/db_demo.py:28-33`
  (lowercase, `[a-z]+`, the same STOP set, `length > 2`), because a differently-written
  tokenizer under the same label produces a different count. The demo's count is still
  the demo's count: it is run on 6 blog posts, not on the 10,000 synthetic sessions
  behind `results.json`, and the two are not the same measurement.
- **The 4-of-8 contrast line is read from the file, not retyped.** `results.json` stores
  `complaint_vs_fix.phrasings_sharing_any_word: 4`, which is the count of phrasings that
  *do* share a word; the 4 that share none is `phrasings.length` minus that, and the
  subtraction happens in `src/demo.ts`. Both numbers are 4 here, which is exactly why
  quoting the key name alone would mislead. If the demo is copied out of this repo the
  line is skipped (`existsSync`) rather than guessed.
- **No vendor numbers are printed.** Nothing on cognee.ai/case-study is quantified;
  Bayer's "10,000 papers" and Wyoming's "30 days" are index blurbs and testimonials with
  no baseline or instrument, and this demo cites none of them.
- `MemorySdk` is three hand-transcribed method signatures rather than
  `Pick<Cognee, ...>`, so the test fake is a plain object naming only the three methods
  the module calls. It buys nothing in install terms, and an earlier draft of this file
  claimed otherwise: `tsc` resolves the `await import("@cognee/cognee-ts")` even though
  it is lazy, so a checkout without the package fails with TS2307 either way, and a
  type-only import would not need the platform addon on disk at all - checked by moving
  `@cognee/neon-linux-x64-gnu` (309 MB on disk) out of `node_modules` and typechecking
  `Pick<Cognee, "warm" | "recall" | "remember">` clean. `require()` needs the addon;
  `tsc` never does. `npm run typecheck` is clean with the package installed.

## Deliberately left out

- **Revision history / temporal query** — "what did I used to claim about X?" needs a
  second fixture shape and a second pair of API calls. It is the obvious next demo; the
  `plan_change` finding in `experiments/db_memory/results.json` is the same shape.
- **`update()` and `forget()`** — an edited post maps to the dataset it already has, and
  in 0.2.0 that dataset does not ingest again, so edits are not remembered.
  `update(dataId, newData, datasetName)` is the fix.
- **CI wiring** — see the caveat above.
