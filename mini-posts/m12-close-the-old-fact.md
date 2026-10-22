# M12: A new fact should close the old one, not sit beside it

**For:** Cognee's LinkedIn and X. **LinkedIn length:** 116 words. **X length:** 217 characters.

![Three cards for STARK-1135, who moved from the team plan to the starter plan on 2026-01-28. grep returns both plan statements with no dates. SQL UPDATE keeps starter and loses team and the date. A temporal graph keeps team valid until 2026-01-28 and starter valid from it.](../figures/v2/m12-close-the-old-fact.png)

## LinkedIn

Customers change plans. People move cities. Agent memory has to handle the fact that replaces another one.

Most stores don't. On 10,000 synthetic support sessions:
→ grep returned both plan statements, with no dates and no way to tell which is current
→ SQL's UPDATE kept the new plan and dropped the old one, along with when it changed

Cognee's temporal knowledge graph guide describes a third option: "the old edge's valid interval is closed at the new fact's start, and the new edge is opened." The history stays, and retrieval can prefer what is current.

So when you test a memory system, change one fact and ask again. Then ask what it used to be.

## X

A customer changed plan. grep returns both plans, undated. SQL UPDATE drops the old one.

A temporal graph closes the old fact's validity window and keeps the history.

Test memory by changing one fact and asking again.

## Source

- [Temporal Knowledge Graph](https://www.cognee.ai/temporal-knowledge-graph), Cognee, 19 Oct 2026
- Measured: [experiments/grep_memory](../experiments/grep_memory/results.json) and [experiments/db_memory](../experiments/db_memory/results.json) in this repo
