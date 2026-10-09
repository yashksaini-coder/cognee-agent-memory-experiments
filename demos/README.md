# Demos

Three runnable demos, one per request cognee made in the v1 review. Each answers a specific
piece of feedback on material that was approved; nothing here is a demo for its own sake.

| Demo | Answers | For |
| --- | --- | --- |
| [01-cognee-vs-grep](01-cognee-vs-grep/) | *"I would like to see also the experiment with cognee so we can actually show to the people that we are better than grep than just saying it"* | [Article 01](../articles/01-grep-as-agent-memory.md) ✅ |
| [02-cognee-graph](02-cognee-graph/) | *"Would be nice to have an example on how cognee creates the graph, or visually inspect the graph"* · *"Maybe we can take one concept like entity resolution"* | [Article 02](../articles/02-just-use-a-database.md) ✅ |
| [03-dev-publish-cognee](03-dev-publish-cognee/) | Cognee as a feature inside a real tool, not a benchmark harness | [dev-publish](https://github.com/yashksaini-coder/dev-publish) |

Each demo runs without Cognee installed, in a mode that still does real work. That mode is
what its self-check exercises, so the repo stays verifiable on a machine with no API key.

## 01 · cognee vs grep

Asks both sides the same four questions `experiments/grep_memory/bench.py` asks of grep, over
the same documents: the literal `"billing bug"` query, the broad `"invoice"` query, the
multi-hop PR → customers question, and the stale plan fact. Prints a side-by-side table and
writes `results.json`.

```bash
python compare.py --self-check                         # the check: no corpus, no cognee
python compare.py ../../experiments/grep_memory/corpus/10000 --grep-only
python compare.py ../../experiments/grep_memory/corpus/10000   # both columns, needs cognee
```

The grep column is `bench.py`'s own code and scoring, re-run on the slice — not re-derived.
The slice is ~30 documents, because keyless extraction runs on CPU. The script prints that
count in every column heading and keeps the published 1k–100k numbers below the table, marked
as context rather than a row, so nothing reads as a like-for-like benchmark.

## 02 · how cognee builds the graph

Runs the entity-resolution slice through Cognee, dumps the real nodes and edges to
`graph.json`, and renders a standalone `graph.html` you can open. Node colour by cognee node
type, edges labelled with the real relationship names, and the nodes that came from the eight
differently-worded complaints marked, so entity resolution is the thing you look at.

```bash
python3 build_graph.py --self-check              # the check: no cognee
python3 build_graph.py --from-json               # re-render graph.html from an existing dump
python3 build_graph.py /tmp/corpus/10000         # build the real graph, needs cognee
```

`graph.html` has no CDN, no npm and no build step — inline SVG and a few lines of plain JS.

## 03 · cognee inside dev-publish

[dev-publish](https://github.com/yashksaini-coder/dev-publish) is a deliberately non-AI tool
that publishes Markdown to dev.to. It already reasons about exact matches: it hashes each post
and decides create / update / skip. Hashing can answer *"did this file change?"* and cannot
answer *"have I covered this topic before?"* — the same gap
`experiments/db_memory/results.json` measures, where 4 of 8 differently-worded descriptions of
one bug share no content word with the PR that fixed it.

So the feature recalls prior coverage before publishing, links genuinely related posts from
`data/published.json`, and remembers the new one. `seam.patch` is the dev-publish diff,
vendored rather than applied, naming the commit it was written against.

```bash
npm install --omit=prod
npm test          # the check: 5 assertions, no key, no network, no cognee
npm run demo      # offline mode, from committed fixtures
```

Uses the TypeScript SDK, [`@cognee/cognee-ts`](https://docs.cognee.ai/typescript/getting-started),
so it is an ordinary module beside `state.ts` and `devto.ts` rather than a Python sidecar.
`node_modules` is large (the native bindings alone are ~309 MB) and is git-ignored.

## Caveats

- The Cognee paths in demos 01 and 02 were **not** executed here — no API key and no Cognee
  install on the authoring machine. The grep, offline and self-check paths were. Each script
  prints its own mode and timings rather than claiming a number it did not measure.
- Keyless `recall()` returns chunks, not an answer, so demo 01 scores recall@k on those
  questions instead of correctness, and says so in the output.
