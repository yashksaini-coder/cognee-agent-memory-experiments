# Post: "Just use a database" is half right

**For:** Cognee's LinkedIn and X, in the Post 2 format. This replaces Post 3, as Veljko asked on 29 Sep: "DB vs memory layer → importance of graph".
**Target phrase:** database vs memory layer for AI agents. **Length:** 515 words.
**No disclosure line:** Cognee publishes this from its own accounts.

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

Build those five and you have built a memory layer, whether or not you call it one.

### Why the graph is the centre of it

Jobs 2, 3 and 4 are about relationships between facts. A relational schema handles relationships with one join table per relation type, designed up front. Our small dataset already had 8 relation types, from "customer reported problem" to "PR changed module", and next month's data will bring types nobody planned.

A graph stores relationships as data rather than schema, so a new type of link needs no migration. That's why Cognee extracts entities and relationships into a graph at write time and uses vectors only to find where to start:

```python
await cognee.remember(session_texts, dataset_name="support")
await cognee.recall("Did the fix for ACME's billing problem ship?", datasets=["support"])
```

### When a database is enough

- Your questions are known in advance and carry a key.
- The schema is fixed.
- Nothing needs to connect across sources or across time.

The moment questions arrive in natural language and the answers span sources and change over time, you need the layer above the database.

## X thread

1/ "Just use a database" is half right. Cognee runs on databases. The hard part is what sits between your agent and the DB.

2/ We loaded 10k support sessions into SQLite. Customers described one billing bug 8 ways. 4 of them share no word with the PR that fixed it. There's nothing to join on.

3/ Five jobs a DB leaves to you: deciding what to keep, merging duplicate entities, linking facts that share no words, tracking what changed, and finding a starting point from a vague question.

4/ Three of those five are about relationships, so the graph sits at the centre. A relational schema needs a join table per relation type, designed up front. A graph stores edges as data.
