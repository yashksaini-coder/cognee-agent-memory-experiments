# M10: The index took the lookup from 386.7 ms to 0.32 ms and found exactly the same 63 reports

**For:** Cognee's LinkedIn and X. **LinkedIn length:** 146 words. **X length:** 182 characters.

![Two pairs of numbers from 100,000 sessions. Time to find one customer: 386.7 ms with a full scan, 0.32 ms with an index built once in 6.43 s. Bug reports found by the literal query: 63 of 484 with grep, 63 of 484 with the index.](../figures/v2/m10-index-same-recall.png)

## LinkedIn

"Just add an index" is the usual next reply after "just use a database". On 100,000 synthetic support sessions, the index fixed the speed and left recall where it was.

Speed: finding everything about customer ACME-1171 took 386.7 ms as a warm ripgrep scan. A SQLite FTS5 index, built once in 6.43 s, answered in 0.32 ms — over 1,200x. That is the half worth fixing, and the half that grows with every session added.

Recall: grep found 63 of the 484 planted bug reports for the literal query. The index found 63 of 484. An index removes the scan and still matches words, so the 421 reports that never used those words stay invisible. The broad query is not rescued either: 70,256 sessions returned against grep's 81,049.

What moves recall is work done at write time — embeddings, extracted edges — not a faster read.

## X

100k sessions. One customer lookup: 386.7 ms scanning, 0.32 ms indexed. Bug reports found by the literal query: 63/484 either way.

An index removes the scan. It still matches words.

## What I did not measure

- Whether embeddings find the other 421 reports. That needs a write-time pipeline, and no Cognee run in this repo has produced output yet: there is no LLM key and the package is not installed. `experiments/cognee_demo/run_cognee_demo.py` is there to run the same query on your own data.
- Index freshness. The 6.43 s build is a one-off over a static corpus. Memory is appended to constantly, and the cost of keeping an index current under writes is not in these numbers.
- Any index other than SQLite FTS5, and any machine other than the one below. The timings move with the hardware; the counts do not.

## Source

- `experiments/grep_memory/results.json`, the `sessions: 100000` record: `q_one_customer.ms` 386.7, `fts5.q_one_customer_ms` 0.32, `fts5.build_s_once` 6.43, `q_billing_bug.recall` 63/484, `fts5.q_billing_bug_recall` 63/484, `q_invoice.files` 81049, `fts5.q_invoice_files` 70256, `planted_bug_reports` 484
- Measured 2026-10-01 on 2 vCPU Intel Xeon @ 2.80 GHz, ripgrep 14.1.0, SQLite 3.45.1, Python 3.11
