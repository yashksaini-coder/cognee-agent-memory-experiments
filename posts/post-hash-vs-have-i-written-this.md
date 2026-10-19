# Post: My publisher knew the file changed. It had no idea I had written the post before

**For:** Cognee's LinkedIn and X, in the Post 2 format. The short version of article 03.
**Target phrase:** retrieval over your own archive. **Length:** 520 words.
**No disclosure line:** Cognee publishes this from its own accounts.

## Post

A content hash answers "did this file change" perfectly, and it cannot answer "have I written this before". We measured how far it gets on the second question anyway.

The tool is a small publisher: hand-written Markdown in, dev.to articles out, deliberately non-AI. It takes the sha256 of each file as a `contentHash`, compares it against the state file, and decides create, update or skip. Its archive is 5 published posts, 9.3 KB of body text, with 1 post being published.

### Three rows from one run

- `contentHash`: **0 of 5**. The sha256 of one file never matches the sha256 of a different file. That equality check is the entire retrieval capability of the state file.
- Tag overlap: **5 of 5**.
- Content-word overlap: **5 of 5**, with the per-post counts 83, 56, 28, 14 and 11.

The floor is 11. Not one prior post shares zero content words with the new one.

![Three rows from one run: contentHash 0/5, tag overlap 5/5, word overlap 5/5, with the five per-post shared-word counts 83 56 28 14 11 and a floor marked at 11.](../figures/v2/pub-hash-vs-topic.png)

### Two opposite failures, one mechanism

On the synthetic support corpus in our database write-up, word matching failed by missing. Customers described one billing bug in 8 phrasings, and 4 of the 8 share no content word with the PR that fixed it. There was nothing to join on.

On one author's archive, word matching fails by hitting. Every prior post shares a tag and between 11 and 83 content words. A ranking whose floor is 11 is not a ranking. It says every post covered this ground, which the author already knew, and not which one.

Same mechanism both times. Overlap is near zero when the writers are different people, and everywhere when the writer is one person on one subject. Either way the signal is gone.

### What the hash is genuinely good at

Answering "did this file change?" — perfectly, instantly, with no model, no key and nothing to rebuild. Do not take that away from it. A content hash is an equality check, and equality checks are exactly right for deciding whether to re-publish a file.

It is simply a different question from the one left over.

### The question left over

Not whether prior coverage exists. Which post, which claim, and at what URL, so a link can go into the new piece. That is retrieval over entities rather than over words: a post, a claim, a measurement, a URL. So the next step is `recall()` before `remember()` after each successful publish. Ask the archive first, then add the new post to it.

What that returns is not reported here. The run needs an OpenAI-compatible key, there was none on the machine, and the demo printed `cognee rows: skipped`. No number is claimed for it.

### Check the offline rows yourself

The three rows above are computed at run time, not stored, and they need no key and no network. The demo and the long version are in the repo:

```bash
cd demos/03-dev-publish-cognee
npm test        # 5 assertions, no key, no network
npm run demo    # the three rows above
```

Repo: [yashksaini-coder/cognee-agent-memory-experiments](https://github.com/yashksaini-coder/cognee-agent-memory-experiments). The full write-up, with the integration and what it costs: [A content hash knows the file changed](../articles/03-hash-knows-the-file-changed.md).

## X thread

1/ A publisher that hashes each Markdown file and decides create / update / skip. Archive: 5 published posts, 9.3 KB. We measured what it can retrieve from that archive before adding anything.

2/ contentHash: 0 of 5. Tag overlap: 5 of 5. Content-word overlap: 5 of 5, per-post 83 / 56 / 28 / 14 / 11. The floor is 11. No prior post shares zero words with the new one.

3/ On our synthetic support corpus, word matching failed the other way: 4 of 8 phrasings of one bug share no word with the PR that fixed it. Missing everything, or matching everything. Same mechanism.

4/ "Did this file change?" is answered perfectly by a hash. "Which post, which claim, which URL?" is retrieval over entities, not words. The cognee rows of this demo need a key and have not been run, so no number is claimed for them.
