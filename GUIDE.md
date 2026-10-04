# Code-along: grep vs a database vs a memory layer as agent memory

This guide walks through the three experiments in this repo, in the order the articles use them. Each step says what the script does, what to run, what the output means, and which number in the articles it produced.

You need Python 3.11 or newer and ripgrep (`rg`). Steps 1 to 3 use only the standard library. Step 4 installs Cognee, and step 5 installs Playwright.

```bash
git clone https://github.com/yashksaini-coder/cognee-agent-memory-experiments
cd cognee-agent-memory-experiments
rg --version && python --version
```

All commands below run from the repo root. Generated data goes into `corpus/`, which is git-ignored.

## The question

Coding agents get far with glob and grep over a repository. Boris Cherny said Claude Code's "agentic search" is "just glob and grep, and it outperformed RAG". So why not save every conversation to a folder and let the agent grep its own memory? And if that fails, why not just put the conversations in a database?

The experiments answer both questions with numbers, on a corpus where the right answers are known in advance.

## Step 1. Generate a corpus with planted facts

`experiments/grep_memory/make_corpus.py` writes one Markdown file per support session, the way a file-based memory would: a header with the customer and date, then alternating user and agent turns.

```bash
for n in 1000 10000 100000; do python experiments/grep_memory/make_corpus.py corpus/$n $n; done
```

Each run prints one line:

```text
{"n": 10000, "bug_sessions": 49, "customers_with_plan_change": 76}
```

Have a look at what it made:

```bash
ls corpus/10000                    # pr-4812.md  sessions/  truth.json
cat corpus/10000/sessions/S004417.md
head -c 400 corpus/10000/pr-4812.md
python -c "import json; t=json.load(open('corpus/10000/truth.json')); print(t['bug_sessions'][:5], len(t['plan_changes']))"
```

Three things are planted, and `truth.json` records them so every later measurement can be scored:

1. **A billing bug** that about 0.5% of sessions report, in 8 different phrasings. Only one phrasing contains the words "billing bug". The others say "my invoice looked wrong", "our receipt dropped the extra seats", "the totals on our statement do not match", and so on. This is what makes literal search miss.
2. **A PR note**, `pr-4812.md`, written in engineering words ("fix payment sync delay dropping line items"). It lists the IDs of every session that reported the bug and never names a customer. This is what makes the multi-hop question possible at all.
3. **Plan changes.** About 1% of returning sessions move the customer to a new plan. Both the old statement ("is on the team plan") and the new one ("moved to the starter plan") stay on disk. This is what makes the stale-fact question.

Ordinary traffic also mentions "invoice" a lot (resend the invoice, change the invoice email, add a VAT number), on purpose: it is what makes the broad keyword expensive.

The generator is seeded (`SEED = 7`), so every machine gets the same 49 bug reports at 10k sessions and the same 484 at 100k. Timings will differ between machines. Counts will not.

## Step 2. grep as memory

`experiments/grep_memory/bench.py` runs the same six measurements at every corpus size you pass it, and prints one JSON object per size. Each timed query is the median of 7 runs with a warm page cache.

```bash
python experiments/grep_memory/bench.py corpus 1000 10000 100000 > my_grep_results.json
```

At 100k sessions this takes about a minute. Compare your file with the published `experiments/grep_memory/results.json`: your `ms` values will differ, your `recall`, `files` and `customers_found` values will match.

What each key in the output measures:

### `q_one_customer`: the full scan

```bash
rg -l ACME-1171 corpus/100000/sessions
```

A selective question. ripgrep still has to read every file to answer it, so the time grows with the folder: 12 ms at 1k sessions, 46 ms at 10k, 387 ms at 100k on the test machine. `cold_ms` repeats the lookup after dropping the page cache, which is what a memory folder looks like after a restart; it needs root and is `null` otherwise. Cold, the 100k lookup took 4.6 seconds.

![Line chart: grep's cost grows with the memory. An index stays flat.](figures/grep-latency.png)

### `q_billing_bug` and `q_invoice`: literal search vs how people talk

```bash
rg -il "billing bug" corpus/100000/sessions | wc -l     # 63 files
rg -il "invoice" corpus/100000/sessions | wc -l          # 81,049 files
```

The precise query finds 63 of 484 bug reports (13%), because only one of the 8 phrasings contains those words. The broad query finds 427 of 484 (88%), but matches 81% of all sessions. `est_tokens_returned` is the size of what the agent would have to read, at 4 characters per token: about 3 million tokens at 100k sessions. `precision_pct` is how much of that is relevant: 0.53%.

![Bar charts: the precise keyword misses most reports, the broad one returns almost everything.](figures/grep-recall.png)

### `multi_hop`: a connected question

"Which customers were affected by the bug that PR #4812 fixed?" The script does what an agent would do:

1. `rg -l "PR #4812" .` to find the PR note (a full scan)
2. read it, pull out the session IDs
3. `rg -l "S000123|S000456|..." sessions` to find those sessions (a second full scan)
4. `rg -N "^customer:" <those files>` to read the customer line of each

`rounds`, `full_corpus_scans`, `ms_total` and `customers_found` versus `customers_expected` are reported. It finds all 442 customers at 100k, in about 900 ms. Note why it works: the synthetic PR note lists session IDs. A real PR says "fixes the sync delay" and nothing more, and then round 3 has nothing to search for.

### `stale_fact`: grep doesn't know what changed

```bash
rg -N -o -I --sort path "STARK-1135 (is on|moved to) the \w+ plan" corpus/100000/sessions
```

Both statements come back, with no dates. ripgrep searches files in parallel and its output order is unspecified unless you pass `--sort`; the published `results.json` was captured without it, which is why its two lines are in the opposite order. `true_current` is read from `truth.json`. To know it, the agent would have to open both files, compare the dates, and do that again on every question.

### `fts5`: an index built once at write time

The script loads the same sessions into a SQLite FTS5 virtual table, times the build, then times the same queries. The build is paid once (6.4 s at 100k); the one-customer lookup is then 0.32 ms instead of 387 ms. The point of this column is what the index does *not* fix: `q_billing_bug_recall` is still 63/484, because an index matches words, and the problem is that people use different words.

(You may notice FTS5's `invoice` query returns fewer files than ripgrep's. FTS5 matches the token `invoice`; `rg -i invoice` also matches `invoices`. Neither number is used in the articles.)

## Step 3. A relational database as memory

`experiments/db_memory/db_demo.py` loads the 10k corpus into an in-memory SQLite database with a reasonable schema and asks four questions. It imports the bug phrasings from `make_corpus.py`, so keep the two directories side by side.

```bash
python experiments/db_memory/db_demo.py corpus/10000 > my_db_results.json
```

```sql
CREATE TABLE customers (id TEXT PRIMARY KEY, plan TEXT);
CREATE TABLE sessions  (id TEXT PRIMARY KEY, customer_id TEXT, day TEXT, body TEXT);
CREATE INDEX sessions_customer ON sessions(customer_id);
CREATE TABLE prs       (number INTEGER PRIMARY KEY, title TEXT, body TEXT);
```

### `keyed_lookup`: the database doing its job

`SELECT plan FROM customers WHERE id = 'ACME-1171'` returns `starter` in 0.048 ms. If your agent's questions look like this, with an ID in them, use a table and stop here.

![Left: a SQL lookup by customer ID. Right: a complaint, a PR and a customer that no key or shared word connects.](figures/db-key-vs-question.png)

### `complaint_vs_fix`: nothing to join on

"Did the fix for this customer's billing problem ship?" needs a link from a complaint to PR #4812. No foreign key exists. The fallback is to join on words, so the script takes the content words of each of the 8 complaint phrasings, intersects them with the content words of the PR title and body, and for each shared word counts how many sessions contain it (`LIKE '%word%'`).

`phrasings_sharing_any_word` is 4: half the complaints share nothing with the fix. One of the remaining four shares only "invoice", which is in 80.5% of sessions and therefore joins the complaint to almost everything. Three share a word rare enough to be useful.

![Table of 8 ways customers described the bug and the words each shares with the PR that fixed it.](figures/db-word-overlap.png)

### `plan_change`: UPDATE forgets

The loader upserts the plan every time it sees a plan statement. `customers_table_says` is `starter`, which is correct, and `history_in_sessions` shows the change from `team` on 2026-01-28 that the table no longer knows about.

### `schema`: one migration per relation type

The script lists 8 relation types an extractor could find in this data ("customer reported problem", "problem fixed by PR", "customer on plan, with dates", ...). In a relational schema each one is a decision made before the first row arrives: a join table, a foreign-key column, or a history table. The alternative it prints is one generic `edges (src, rel, dst, valid_from, source_id)` table, which is a graph stored in SQL. Either way, something has to read the conversation and write the rows.

![Five jobs between your agent and your database: decide what to keep, resolve entities, connect facts, track time, find a starting point.](figures/db-five-jobs.png)

## Step 4. The same questions through Cognee (optional)

`experiments/cognee_demo/run_cognee_demo.py` takes a small slice of the 10k corpus (the 8 bug reports, one per phrasing; 20 ordinary sessions; the plan-change session; the PR note) and runs it through `cognee.remember()`, then asks three questions with `cognee.recall()`. The slice is small on purpose: keyless extraction runs on CPU.

Keyless setup, with local models (about 1 GB downloaded on first run):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "cognee[gliner]==1.6.1"
.venv/bin/python experiments/cognee_demo/run_cognee_demo.py corpus/10000
```

With `LLM_API_KEY` set, Cognee extracts with an LLM and `recall()` returns a completed answer. Without it, `recall()` returns matching chunks. The script prints how long `remember()` took, then the top 3 items for each of:

- `billing bug`: does recall find the phrasings that share no words with the query?
- `Which customers reported problems that PR #4812 fixed?`: can it follow complaint → PR → customer?
- `What plan is STARK-1135 on now?`: does it prefer the newer fact?

This step is deliberately not benchmarked in the articles. Extraction costs an LLM call per chunk, or CPU time, and that is the price you pay instead of a full scan on every read. Run it on your own data to see whether it is worth it for you.

## Step 5. Regenerate the figures (optional)

Every chart is rendered from the two `results.json` files, so if you want figures with your own timings, point the script at your results and re-render:

```bash
pip install playwright && playwright install chromium
python figures/make_figures.py figures
```

The script reads `experiments/grep_memory/results.json` and `experiments/db_memory/results.json` relative to the repo root. To render from your own run, copy your output over those two files first (or edit the two paths at the top of the script). The fonts used are Carlito and DejaVu Sans; with other fonts installed the layout may shift slightly. The script prints `ok` or `overflow!` per figure.

## Reading the results honestly

- **Synthetic data.** The corpus is shaped like support data but is far more regular than real conversations.
- **Token counts** are estimated at 4 characters per token, not measured with a tokenizer.
- **grep is the right tool for code**, where identifiers are exact and the repo is always current, and for any memory small enough to read whole.
- **The database is the right tool for keyed questions.** The memory layer earns its cost only when questions arrive in natural language and answers span sources and time.
- **The memory layer is not measured here.** Its cost moves to write time. Step 4 lets you measure it.

## Published numbers at a glance

From `experiments/grep_memory/results.json` (2026-10-01, 2 vCPU Intel Xeon @ 2.80 GHz, ripgrep 14.1.0, SQLite 3.45.1):

| | 1k | 10k | 100k |
| --- | ---: | ---: | ---: |
| corpus size | 0.8 MB | 7.5 MB | 74.2 MB |
| planted bug reports | 8 | 49 | 484 |
| `rg "billing bug"` recall | 1/8 | 9/49 | 63/484 |
| `rg "invoice"` recall | 8/8 | 41/49 | 427/484 |
| `rg "invoice"` sessions returned | 811 | 8,053 | 81,049 |
| `rg "invoice"` est. tokens returned | 29.7k | 302k | 3.0M |
| one customer, warm | 12.1 ms | 46.4 ms | 386.7 ms |
| one customer, cold | 81.1 ms | 534.7 ms | 4,614.3 ms |
| FTS5 build, once | 0.08 s | 0.54 s | 6.43 s |
| FTS5 one customer | 0.03 ms | 0.05 ms | 0.32 ms |
| multi-hop total | 29.9 ms | 97.3 ms | 897.5 ms |
| multi-hop customers found | 8/8 | 48/48 | 442/442 |

From `experiments/db_memory/results.json` (10k sessions): keyed lookup 0.048 ms; 4 of 8 complaint phrasings share no word with PR #4812; "invoice" appears in 80.5% of sessions; STARK-1135 moved team → starter on 2026-01-28 and the `customers` table remembers only `starter`.
