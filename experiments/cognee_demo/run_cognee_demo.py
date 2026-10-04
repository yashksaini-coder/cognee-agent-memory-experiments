"""Run the same support-memory questions through Cognee. Run this on your own machine.

Uses a small slice of the 10k-session corpus from ../grep_memory: the 8 bug
reports (one per phrasing), 20 ordinary sessions, and the PR #4812 note.
Small on purpose: keyless extraction runs on CPU.

Setup (keyless, local models, ~1 GB download on first run):
    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python "cognee[gliner]==1.6.1"
    .venv/bin/python ../grep_memory/make_corpus.py ../grep_memory/corpus/10000 10000
    .venv/bin/python run_cognee_demo.py ../grep_memory/corpus/10000

With LLM_API_KEY set, Cognee extracts with an LLM and recall() answers with
HYBRID_COMPLETION. Without it, recall() returns matching chunks (CHUNKS).
Paste the printed output into the article's "Run it yourself" section.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import cognee

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "grep_memory"))
from make_corpus import BUG_PHRASES  # noqa: E402

QUESTIONS = [
    "billing bug",
    "Which customers reported problems that PR #4812 fixed?",
    "What plan is STARK-1135 on now?",
]


def pick_docs(corpus: Path) -> list[str]:
    truth = json.loads((corpus / "truth.json").read_text())
    bug = truth["bug_sessions"]
    seen_phrases, docs = set(), []
    for sid in bug:  # one session per distinct phrasing
        text = (corpus / "sessions" / f"{sid}.md").read_text()
        phrase = next((p for p in BUG_PHRASES if p in text), None)
        if phrase and phrase not in seen_phrases:
            seen_phrases.add(phrase)
            docs.append(text)
    plan_sid = truth["plan_changes"]["STARK-1135"][0]["session"] if "STARK-1135" in truth["plan_changes"] else None
    noise = [p for p in sorted((corpus / "sessions").glob("*.md")) if p.stem not in bug][:20]
    docs += [p.read_text() for p in noise]
    if plan_sid:
        docs.append((corpus / "sessions" / f"{plan_sid}.md").read_text())
    docs.append((corpus / "pr-4812.md").read_text())
    return docs


async def main(corpus: str) -> None:
    docs = pick_docs(Path(corpus))
    print(f"cognee {cognee.__version__ if hasattr(cognee, '__version__') else ''} | "
          f"LLM key: {'yes' if os.getenv('LLM_API_KEY') else 'no (keyless)'} | docs: {len(docs)}")

    t = time.perf_counter()
    result = await cognee.remember(docs, dataset_name="support_demo")
    print(f"remember: {time.perf_counter() - t:.1f}s -> {result}")

    for q in QUESTIONS:
        t = time.perf_counter()
        items = await cognee.recall(q, datasets=["support_demo"])
        print(f"\nrecall({q!r}): {time.perf_counter() - t:.2f}s, {len(items)} items")
        for item in items[:3]:
            print("  ", str(item)[:300].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
