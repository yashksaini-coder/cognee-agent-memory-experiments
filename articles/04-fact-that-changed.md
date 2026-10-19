---
title: "A Customer Changed Plan. What grep, SQLite, Mem0, Graphiti and Cognee Each Do With the Old Fact"
published: false
description: "One customer moved from the team plan to the starter plan. I measured what grep and SQLite do with the superseded fact, then read how three memory layers handle it. They disagree about who decides, and that is the thing to choose on."
tags: ai, agents, memory, database
canonical_url:
---

> I write for Cognee. The grep and SQLite rows are measured on 2026-10-01: ripgrep 14.1.0, SQLite 3.45.1, Python 3.11, Linux. The Mem0, Graphiti and Cognee rows are read from each project's own documentation and source, cited inline. Scripts are linked at the end.

```console
$ rg -N -o -I "STARK-1135 (is on|moved to) the \w+ plan" sessions
STARK-1135 moved to the starter plan
STARK-1135 is on the team plan
```

One customer, two statements, no dates. STARK-1135 moved from team to starter on 28 Jan 2026. Both sentences are still on disk, because both were true once, and nothing in that output says which one is true now.

![Five rows: grep returns both statements with no dates; a SQLite UPDATE loses the old value; Mem0 keeps it additively; Graphiti keeps it stamped with invalid_at; Cognee keeps it tagged as superseded. The grep and SQLite rows are marked measured, the other three read from source.](../figures/v2/fact-that-changed.png)

Every memory system has an answer to this. The answers are different in a way that matters more than any benchmark score, because they differ in *who decides* — the system, your schema, or your application code.

## What the file and the table do, measured

Two rows of this table come from scripts in this repo, over 10,000 synthetic support sessions.

**grep returns both, in file order.** The output above is the whole result. No dates are attached because the dates live in the session headers, not on the matched lines. An agent that wants the current plan has to open both files, read the headers and compare them, on every single read. Worth noting: the newer statement happens to print first here, but that is filesystem order, not chronology. Nothing guarantees it.

**A SQLite `UPDATE` keeps the new value and drops the old one.** The loader upserts plans, so `customers` says `starter`, which is correct. `experiments/db_memory/results.json` records what was lost alongside it: `history_in_sessions` has the move — session `S000999`, 28 Jan 2026, `team` to `starter` — and the `customers` table has no trace of it. "Why did their invoice change in February?" is now unanswerable from the table.

Keeping the history means a `plan_history` table with `valid_from` and `valid_to`, and a time filter on every query that touches it. That is a schema decision, made for each fact that can change, before you know which facts will.

## What the three memory layers do

Here the sources change. I did not benchmark these against each other — that would need the same corpus, the same questions and the same keys for all three, and this repo has run none of it. What follows is each project's own stated mechanism, with the citation, because the mechanisms differ enough that you can choose on them.

**Mem0 is additive.** Its docs state that "the automatic extraction path is additive", using a move from Austin to Seattle as the example: the new fact is stored and the old one is not silently rewritten. Correcting or removing a memory is an explicit call your application makes — "use explicit `update` or `delete` operations when your application needs to correct or remove a memory" ([Mem0, memory types](https://docs.mem0.ai/core-concepts/memory-types)). So STARK-1135 would end up with both facts stored and no automatic verdict, and the deciding logic lives in your code.

**Graphiti marks when a fact stopped being true.** Zep's Graphiti uses "explicit bi-temporal tracking" and names "temporal edge invalidation" as its mechanism for contradictions ([Graphiti overview](https://help.getzep.com/graphiti/graphiti/overview)). In its source, an edge carries `created_at`, `valid_at`, `invalid_at` and `expired_at`, where `invalid_at` is documented as the "datetime of when the fact stopped being true" ([`graphiti_core/edges.py`](https://github.com/getzep/graphiti/blob/main/graphiti_core/edges.py)). The old plan edge is not deleted; it is stamped, and point-in-time queries can still reach it.

**Cognee tags the superseded assertion and keeps it.** In the installed 1.6.1 package, `cognee/modules/graph/utils/temporal_conflict_resolver.py` opens with the rule:

> When a *functional* (single-valued) relationship holds more than one target for the same source — e.g. two documents name a different current CEO — the most recent assertion is the current fact and the older ones are outdated. This module tags the outdated ones instead of deleting them, so the history and its provenance stay in the graph and retrieval can tell a current fact from a replaced one.

Ranking is by the edge's own `updated_at`, with position breaking ties, so the same input produces the same winner every time. It is exposed as a cognify task, `cognee.tasks.graph.resolve_temporal_contradictions`.

## The difference is who decides, not whether it works

All three keep the old fact. The interesting divergence is one line further down in that same Cognee file:

> Nothing is applied automatically: the caller names the relationships that are single-valued. Most cognee relationships (`knows`, `mentions`, ...) are legitimately many-valued and must never be collapsed, and there is no cardinality metadata to tell them apart.

That is a design position, and it is the clearest difference between these three. Resolving a contradiction requires knowing that a relationship can only have one value at a time. "Current plan" is single-valued. "Mentions" is not — a session mentioning `invoice` does not stop mentioning it because a later session also does. Collapsing a many-valued relationship by recency does not correct a fact; it deletes information.

So:

- **Mem0** does not resolve, and hands the decision to your application code at write time.
- **Graphiti** resolves inside the system, stamping validity on edges as facts arrive.
- **Cognee** will resolve, deterministically and non-destructively, but only for relationships *you* declare single-valued — because it will not guess cardinality for you.

None of those is the right answer in general. They are the right answer for different data.

## How to decide which you want

Look at your own facts before you look at anyone's benchmark. The question is what proportion of them can hold exactly one value at a time.

**Mostly single-valued facts** — current plan, current address, current owner, current status. Automatic invalidation earns its keep, because nearly every contradiction is a genuine supersession. Graphiti's model does this work for you.

**Mostly many-valued facts** — mentions, topics, participants, symptoms, tags. Automatic recency resolution is actively harmful here: the second mention would retire the first. An opt-in model like Cognee's is the safer default, and the cost is that you write the list of single-valued relationships yourself.

**You need the old value, not just the current one.** Audit trails, "why did this change in February", anything you have to explain to a customer. Rule out a plain `UPDATE` immediately. All three memory layers keep the superseded fact; a table does not unless you build the history table yourself.

**Your corrections come from outside the text.** If a human or another service decides what is true, rather than it being inferable from document recency, Mem0's explicit `update`/`delete` is the honest fit — you were going to make that call in application code anyway.

A useful test on your own data costs very little: take twenty facts your agent would store, and label each one single- or many-valued. If the list is overwhelmingly single-valued, automatic resolution is a feature. If it is mixed, the ability to resolve *some* relationships and leave the rest alone is the thing you are actually shopping for.

## What I did not measure

- **No memory layer was benchmarked here.** The Mem0, Graphiti and Cognee rows are documentation and source, not runs. I have not put the same corpus, the same questions and the same keys to all three, and until someone does, treat the mechanism comparison as a guide to what to test, not as a result.
- **Cognee's resolver is opt-in and I did not run it.** `resolve_temporal_contradictions` is a real exported task in 1.6.1, wired into the pipeline, but nothing in this repo has executed it and so nothing here reports what it produced.
- **The corpus is synthetic.** The plan-change statements are generated by `make_corpus.py` with a fixed seed, which is why the grep and SQLite rows reproduce exactly and why they are easier than real text.
- **Mechanisms move.** Every citation above is to a version: Cognee 1.6.1 as installed, Graphiti and Mem0 as documented on 19 Oct 2026. Check them before quoting them.

## Run it yourself

The two measured rows are in [yashksaini-coder/cognee-agent-memory-experiments](https://github.com/yashksaini-coder/cognee-agent-memory-experiments):

```bash
python3 experiments/grep_memory/make_corpus.py corpus/10000 10000 # the sessions, seeded
python3 experiments/grep_memory/bench.py corpus 10000             # prints the stale_fact block
python3 experiments/db_memory/db_demo.py corpus/10000             # prints plan_change
```

Cognee's [AI agent memory guide](https://www.cognee.ai/blog/fundamentals/agent-memory) covers the write path these mechanisms sit in.
