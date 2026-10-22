# M13: Two names for one thing make two nodes

**For:** Cognee's LinkedIn and X. **LinkedIn length:** 126 words. **X length:** 215 characters.

![Eight differently worded complaints about one bug, each reaching 9 to 17 entities. The node most of them shared, "open payments issue", joined 6, 7, 6 and 6 of the 8 across four builds, and came from the agent's reply, not any customer.](../figures/v2/a05-two-names-two-nodes.png)

## LinkedIn

Eight customers reported the same billing bug, each in different words. We ran their sessions through Cognee with an LLM doing extraction, four times. The eight reached 69 to 76 distinct entities.

One entity joined most of them: "open payments issue", in 6 or 7 of the 8. It didn't come from the customers. It came from the agent's reply in each session: "I've linked this to the open payments issue."

Graph memory joins mentions by name. Cognee's docs say it plainly: when one thing is extracted under several names, "it becomes several Entity nodes and its edges are split across all of them."

So name things consistently when your agent writes back. For duplicates already in the graph, run Cognee's entity consolidation, with dry_run=True first.

## X

8 phrasings of one bug → ~70 entities in the graph.

The node that joined most of them came from the agent's own reply, not the customers.

Graph memory joins by name. Have your agent write back with consistent names.

## Source

- [Entity deduplication](https://docs.cognee.ai/guides/memify-entity-deduplication), Cognee docs (fetched 22 Oct 2026)
- Measured: four builds of `demos/02-cognee-graph/build_graph.py` on 30 sessions, cognee 1.6.1, claude-haiku-4-5, 22 Oct 2026 (`entity-resolution-results.json`)
