---
title: '"Just use a database" is half right'
description: "Every conversation about agent memory hits the same objection. Here is the half of it that holds up, and the half that does not."
tags: [ai, agents, database, graph]
published: false
---

# Post: "Just use a database" is half right


## Post

![Five jobs stacked between 'Your agent' and 'Your database': decide what to keep, resolve entities, connect facts, track time, find a starting point. The middle three are about relationships.](../figures/db-five-jobs.png)

Every conversation about agent memory hits the same objection: just use a database.

It's half right. Cognee stores memory in databases: SQLite, LanceDB and a graph store by default, or all of it on a single Postgres. The database was never the hard part. The hard part is everything between your agent and the database.

### What a database is good at

`SELECT plan FROM customers WHERE id = 'ACME-1171'` comes back in a fraction of a millisecond, exact and indexed.

If your agent's questions have a key in them (settings, order status, feature flags), use a table. You don't need a memory layer.

### What an agent actually asks

"Did the fix for ACME's billing problem ship?"

There is no key in that sentence. The customer wrote "our receipt dropped the extra seats". The engineer's PR says "fix payment sync delay dropping line items". No foreign key connects them, because nobody wrote one.

We loaded 10,000 support sessions into SQLite to see whether words could stand in for the missing key. Customers described the same bug in 8 different ways:

- 4 of the 8 phrasings share no content word with the PR that fixed it.
- 1 shares only "invoice", which appears in 80% of all sessions.
- Only 3 share a word rare enough to join on.

![Table of 8 ways customers described the bug and the words each shares with the PR that fixed it: 4 share none, 1 shares only 'invoice'.](../figures/db-word-overlap.png)

Full-text search doesn't close that gap, because the gap is vocabulary. The link exists only as meaning, and something has to read both texts and write it down.

### Five jobs the database leaves to you

1. **Decide what's worth keeping.** A 40-message conversation holds one or two facts.
2. **Resolve entities.** "ACME", "ACME-1171" and "the customer on ticket 1182" may be one customer, or three.
3. **Connect facts.** Complaint → bug → fix → every customer the bug affected.
4. **Track time.** An `UPDATE` to the customer's plan keeps the new value and silently drops the old one.
5. **Find a starting point from a vague question**, not from an ID.
