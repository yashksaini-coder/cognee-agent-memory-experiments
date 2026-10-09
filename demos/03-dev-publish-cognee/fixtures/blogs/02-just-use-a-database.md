---
title: '"Just Use a Database": I Loaded 10,000 Agent Sessions into SQLite to Check'
description: "A database answers keyed questions instantly. Agents ask questions with no key in them. I measured where SQLite stops helping an agent."
tags: [ai, agents, database, sql]
published: true
---

> I write for Cognee. Tested on 2026-10-01: SQLite 3.45.1, Python 3.11, Linux. Scripts are linked at the end.

```text
SELECT plan FROM customers WHERE id = 'ACME-1171';      -> starter      0.048 ms

"Did the fix for ACME-1171's billing problem ship?"     -> no key, no join, no query
```

The first line is a database doing its job. The second is the question an agent actually gets. Everything needed to answer it is in the same database, and none of it can be joined.

![Left: a SQL lookup by customer ID returns 'starter' in 0.048 ms. Right: the question 'Did the fix for ACME's billing problem ship?' with a complaint, a PR and a customer that no key or shared word connects.](../figures/db-key-vs-question.png)

## The objection worth taking seriously

Every conversation about agent memory hits the same reply: just use a database. Postgres has run production systems for decades, SQLite ships with Python, and both store text fine.

The objection is half right. Cognee itself stores memory in databases: SQLite, LanceDB and a graph store by default, and it can run on a single Postgres. So the useful question isn't database or no database. It is which work the database leaves to your code.

This article is for engineers who have a database and an agent and are deciding whether they need anything in between. I loaded 10,000 support sessions into SQLite with a reasonable schema and checked four questions an agent gets every day.

## The setup

These are the same synthetic support sessions I used for [the grep article](01-grep-as-agent-memory.md): one per file, with a customer, a date and the user and agent turns. A loader script put them into three tables:

```sql
CREATE TABLE customers (id TEXT PRIMARY KEY, plan TEXT);
CREATE TABLE sessions  (id TEXT PRIMARY KEY, customer_id TEXT, day TEXT, body TEXT);
CREATE INDEX sessions_customer ON sessions(customer_id);
CREATE TABLE prs       (number INTEGER PRIMARY KEY, title TEXT, body TEXT);
```

The data contains a billing bug that 49 sessions report in 8 different phrasings, and PR #4812, which fixed it: "fix payment sync delay dropping line items".

## Keyed questions: the database wins

`SELECT plan FROM customers WHERE id = 'ACME-1171'` returns `starter` in 0.048 ms. Exact, indexed and boring, which is what you want.

If your agent's questions look like this, meaning user settings, feature flags, order status or anything with an ID in it, use a table and stop reading. A memory layer adds cost and gives you nothing here.

## Questions with no key: nothing to join on
