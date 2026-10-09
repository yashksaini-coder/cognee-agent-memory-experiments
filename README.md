# cognee-agent-memory-experiments

What it costs to use **grep**, a **SQLite database**, or a **memory layer (Cognee)** as an AI agent's long-term memory, measured on up to 100,000 synthetic support sessions.

Everything here is reproducible with the Python standard library and ripgrep. The numbers behind two articles come from these scripts, and every figure is rendered from the committed `results.json` files.

![Line chart: time to find one customer's sessions. grep with a cold cache rises from 81 ms at 1,000 sessions to 4,614 ms at 100,000; grep with a warm cache from 12 ms to 387 ms; an index built once peaks at 0.32 ms.](figures/grep-latency.png)

## The headline numbers

One question, "show me everything about customer ACME-1171", asked of a memory that is a folder of Markdown files:

| sessions | corpus | `rg` one customer, warm cache | `rg`, cold cache | SQLite FTS5 index |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0.8 MB | 12.1 ms | 81.1 ms | 0.03 ms |
| 10,000 | 7.5 MB | 46.4 ms | 534.7 ms | 0.05 ms |
| 100,000 | 74.2 MB | 386.7 ms | 4,614.3 ms | 0.32 ms |

Searching the same 100,000 sessions for the exact words `"billing bug"` finds 63 of the 484 planted bug reports. Searching for `"invoice"` finds 427 of them, and returns 81,049 sessions (about 3 million tokens) to get there.

Measured 2026-10-01 on 2 vCPU Intel Xeon @ 2.80 GHz, ripgrep 14.1.0, SQLite 3.45.1, Python 3.11. Your machine will give different timings and the same counts.

## Quick start

Requirements: Python 3.11+ and [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) on your PATH. Nothing to `pip install` for the first two experiments.

```bash
git clone https://github.com/yashksaini-coder/cognee-agent-memory-experiments
cd cognee-agent-memory-experiments

# 1. generate the corpora (seeded, so the planted facts are identical on every machine)
for n in 1000 10000 100000; do python experiments/grep_memory/make_corpus.py corpus/$n $n; done

# 2. grep as memory: latency, recall, tokens returned, multi-hop, stale facts, FTS5 comparison
python experiments/grep_memory/bench.py corpus 1000 10000 100000 > my_grep_results.json

# 3. a relational database as memory: keyed lookup, word overlap, lost history, schema growth
python experiments/db_memory/db_demo.py corpus/10000 > my_db_results.json

# 4. (optional) the same questions through Cognee, see GUIDE.md step 4
python experiments/cognee_demo/run_cognee_demo.py corpus/10000
```

Step by step, with what each number means and what to look for in the output: **[GUIDE.md](GUIDE.md)**.

## What is in the repo

```
experiments/
  grep_memory/
    make_corpus.py      generates N support sessions as Markdown files + a PR note + truth.json
    bench.py            times ripgrep queries, measures recall and tokens, builds an FTS5 index
    results.json        the published run at 1k, 10k and 100k sessions
  db_memory/
    db_demo.py          loads the corpus into SQLite and asks four questions an agent gets
    results.json        the published run at 10k sessions
  cognee_demo/
    run_cognee_demo.py  remember() a slice of the corpus into Cognee, recall() the same questions
figures/
  make_figures.py       renders every PNG below from the two results.json files (needs playwright)
  grep-*.png db-*.png   charts used in the articles
  m1-*.png .. m8-*.png  explainer slides used in short posts
demos/                  one runnable demo per demo request in cognee's review
articles/               the two long-form write-ups, with the numbers they cite
posts/                  two short educational posts, one per article
mini-posts/             M1-M8, one idea each, with its explainer slide
GUIDE.md                the code-along
```

## The three experiments in one paragraph each

**grep as memory** (`bench.py`). Every query is a full scan, so cost grows with the folder. A literal query finds 13% of the bug reports because customers described one bug in 8 ways. A broad query finds 88% but returns 81% of the corpus. A connected question ("which customers did PR #4812's bug affect?") needs 4 rounds and 2 full scans, and only works because the synthetic PR note lists session IDs. A customer whose plan changed gets two contradictory answers with no dates. An FTS5 index removes the scan and nothing else.

**A database as memory** (`db_demo.py`). A keyed lookup is 0.048 ms and exact. A question with no key in it ("did the fix for ACME's billing problem ship?") has nothing to join on: 4 of the 8 complaint phrasings share no content word with the PR that fixed them, and one shares only "invoice", which is in 80.5% of sessions. An `UPDATE` to a customer's plan keeps the new value and drops the history. Eight relation types an extractor could find in this data mean eight schema decisions up front, or one generic edges table that something has to fill.

**A memory layer** (`run_cognee_demo.py`). The same slice of sessions goes through `cognee.remember()` (chunk, embed, extract entities and relations into a graph) and `cognee.recall()`. It runs keyless on CPU with local models, or with an LLM key. It is not benchmarked here; the script exists so you can measure it on your own data.

## Write-ups

The text lives here too, so every claim sits next to the script that produced it.

### Articles

| File | Title | Figures | APPROVED |
| --- | --- | --- | --- |
| [01-grep-as-agent-memory.md](articles/01-grep-as-agent-memory.md) | grep as Agent Memory: What It Costs at 100,000 Sessions | `grep-latency`, `grep-recall` | ✅ |
| [02-just-use-a-database.md](articles/02-just-use-a-database.md) | "Just Use a Database": I Loaded 10,000 Agent Sessions into SQLite to Check | `db-key-vs-question`, `db-word-overlap`, `db-five-jobs` | ✅ |

### Posts

| File | Title | Figures | APPROVED |
| --- | --- | --- | --- |
| [post-why-grep-is-expensive-as-agent-memory.md](posts/post-why-grep-is-expensive-as-agent-memory.md) | Why grep is expensive as agent memory | `grep-four-ways`, `grep-latency` | — |
| [post-just-use-a-database-is-half-right.md](posts/post-just-use-a-database-is-half-right.md) | "Just use a database" is half right | `db-five-jobs`, `db-word-overlap` | — |

### Mini-posts

One idea each, with its explainer slide and both a LinkedIn and an X version.

| File | Title | Figure | APPROVED |
| --- | --- | --- | --- |
| [m1-agent-writes-back-not-rag.md](mini-posts/m1-agent-writes-back-not-rag.md) | The moment your agent writes back, it isn't RAG anymore | `m1-rag-vs-memory` | ✅ |
| [m2-four-places-knowledge-lives.md](mini-posts/m2-four-places-knowledge-lives.md) | Four places an AI's knowledge can live | `m2-four-places` | ❌ |
| [m3-three-ways-to-store-memory.md](mini-posts/m3-three-ways-to-store-memory.md) | Three ways to store agent memory, and what each one misses | `m3-three-stores` | ❌ |
| [m4-facts-skills-scratch-space.md](mini-posts/m4-facts-skills-scratch-space.md) | Facts, skills and scratch space | `m4-three-kinds` | ❌ |
| [m5-fits-in-context-skip-memory-layer.md](mini-posts/m5-fits-in-context-skip-memory-layer.md) | If the history fits in the context window, skip the memory layer | `m5-benchmark-sizes` | ❌ |
| [m6-300-tokens-beat-113k.md](mini-posts/m6-300-tokens-beat-113k.md) | A 300-token prompt beat a 113k-token one | `m6-context-rot` | ✅ |
| [m7-benchmarks-vs-production.md](mini-posts/m7-benchmarks-vs-production.md) | Benchmarks score memory. Production scores behaviour | `m7-doordash` | ✅ |
| [m8-reading-a-benchmark-claim.md](mini-posts/m8-reading-a-benchmark-claim.md) | How to read an AI memory benchmark claim | `m8-benchmark-claims` | ❌ |

✅ approved by cognee, ❌ not approved, — not yet reviewed. Verdicts are from the v1 review of M1-M8 and both articles; the two short posts were not in that round.

Figures are referenced as `../figures/*.png`, so they render in the repo. Publishing to DEV, LinkedIn or X means uploading the PNG there and swapping the path for the hosted URL. Canonical links will be added once the articles are live.

## Caveats

- The corpus is synthetic. It is shaped like support data, but real conversations use even more vocabulary.
- Token counts are estimated at 4 characters per token.
- The cold-cache measurement writes to `/proc/sys/vm/drop_caches` and needs root on Linux; without it `cold_ms` is `null`.
- Timings depend on the machine. Counts (bug reports found, sessions returned, customers found) are deterministic: `make_corpus.py` uses a fixed seed.

## License

MIT. See [LICENSE](LICENSE).
