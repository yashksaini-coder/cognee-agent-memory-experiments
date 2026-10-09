---
title: "grep as Agent Memory: What It Costs at 100,000 Sessions"
description: "I saved 100k synthetic support sessions to disk and measured what grep costs as an agent's memory: latency, tokens, missed phrasings and stale facts."
tags: [ai, agents, llm, performance]
published: true
---

> I write for Cognee. Tested on 2026-10-01: ripgrep 14.1.0, SQLite 3.45.1, Python 3.11, 2 vCPU Intel Xeon @ 2.80 GHz, Linux. Scripts are linked at the end.

```text
sessions   corpus    rg one customer (warm)   rg (cold cache)   FTS5 index
   1,000    0.8 MB          12.1 ms                81.1 ms         0.03 ms
  10,000    7.5 MB          46.4 ms               534.7 ms         0.05 ms
 100,000   74.2 MB         386.7 ms             4,614.3 ms         0.32 ms
```

That is one question, "show me everything about customer ACME-1171", asked of an agent whose memory is a folder of Markdown files. grep reads every file on every call, so the time grows with the folder. The last column is the same lookup against an index built once at write time.

![Line chart: time to find one customer's sessions. grep with a cold cache rises from 81 ms at 1,000 sessions to 4,614 ms at 100,000; grep with a warm cache from 12 ms to 387 ms; an index built once stays under 0.32 ms.](../figures/grep-latency.png)

## Why grep is a fair contender

"Claude Code's 'agentic search' is really just glob and grep, and it outperformed RAG." Boris Cherny said that in [an interview with The Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/building-claude-code-with-boris-cherny). His team had tried local vector databases, and stale indexes and permission problems made them worse than plain search.

So "save every conversation to files and let the agent grep them" is a serious proposal. This article tests it on the workload agent memory actually has. It is for anyone building an agent that has to remember users across sessions and who is deciding whether a memory layer is worth the setup.

## The test corpus

I generated support-agent sessions, one Markdown file each, and stored them the way a file-based memory would: a header, then user and agent turns.

```markdown
# Session S004417
customer: GLOBEX-1042
date: 2026-03-11

**user:** can you resend last month's invoice to finance@globex-1042.example
**agent:** I've resent it, it should arrive within a few minutes.
**user:** the CSV export times out above 50k rows
...
```

Three things are planted so the answers can be checked:

- **A billing bug** that about 0.5% of sessions report, in 8 phrasings. Only one of them contains the words "billing bug". The others say "my invoice looked wrong", "our receipt dropped the extra seats" and so on.
- **A PR note** (`pr-4812.md`) written in engineering words: "fix payment sync delay dropping line items". It lists the affected session IDs and names no customer.
- **Plan changes**: some customers move plans, and both the old and the new statement stay on disk.

