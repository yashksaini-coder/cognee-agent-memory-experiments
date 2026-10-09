"""Ask grep and cognee the same four memory questions, over the same 30 documents.

articles/01-grep-as-agent-memory.md measures grep at 1k/10k/100k sessions and says the
cognee side is unmeasured. This measures it, on the slice cognee can actually ingest
keylessly on a CPU: the 8 bug reports (one per phrasing in BUG_PHRASES), 20 ordinary
sessions, STARK-1135's plan change and the PR #4812 note - about 30 documents, 25k chars.

The grep column is recomputed here, in this process, over those same 30 documents, by
handing them to experiments/grep_memory/bench.py as a corpus. It is NOT the published
1k/10k/100k table; that row is printed underneath as context, and is not a race: 30
documents against 10,000 would flatter whichever side you pointed at.

Usage:
    python compare.py ../../experiments/grep_memory/corpus/10000               # both columns
    python compare.py ../../experiments/grep_memory/corpus/10000 --grep-only   # no cognee
    python compare.py --self-check            # asserts; needs no cognee and no corpus

    # the corpus first, if you have not generated it:
    python ../../experiments/grep_memory/make_corpus.py ../../experiments/grep_memory/corpus/10000 10000

Look for: the recall rows (how many of the 8 planted bug reports each side finds from one
query, since 7 of the 8 never use the words "billing bug"), and rounds / full-corpus-scans
on the multi-hop question. Keyless recall() returns chunks rather than an answer, so Q4 is
scored as recall@k and the verdict cell says "n/a keyless". Latency and precision are not
raced across the two columns; the token counts are slice-local on both sides. The reasons
are printed at the end.

Writes results.json next to this script.
"""

import asyncio
import json
import os
import re
import sys
import tempfile
import time
import types
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "grep_memory"))
sys.path.insert(0, str(REPO / "experiments" / "cognee_demo"))

import bench  # noqa: E402  the grep/FTS5 timings and the four questions, same scoring
import make_corpus  # noqa: E402
from make_corpus import BUG_PHRASES, PLANS  # noqa: E402

try:
    from run_cognee_demo import pick_docs  # noqa: E402
except ModuleNotFoundError:  # it imports cognee at module scope; we only want pick_docs
    sys.modules["cognee"] = types.ModuleType("cognee")
    from run_cognee_demo import pick_docs  # noqa: E402
    del sys.modules["cognee"]

DATASET = "support_demo"
SID = re.compile(r"S\d{6}")
# pr-4812.md lists every bug session id on one line. A chunk of it would hand cognee
# every sid for free, while grep's number comes from sessions/ only.
PR_SID_LIST = re.compile(r"Reported in sessions:.*")
CUSTOMER = re.compile(r"[A-Z]+-1\d{3}")

# The same four questions bench.py asks of grep.
QUESTIONS = [
    ("q_billing_bug", "billing bug"),
    ("q_invoice", "invoice"),
    ("multi_hop", "Which customers reported problems that PR #4812 fixed?"),
    ("stale_fact", "What plan is STARK-1135 on now?"),
]


def write_slice(corpus: Path, docs: list[str], dest: Path) -> dict:
    """Lay the ingested docs out as a corpus directory that bench.bench() can measure.

    truth.json is the full one filtered to the slice, so every denominator is 8 (the
    phrasings present) and not 49 (the 10k corpus) - cognee never saw the other 41.
    """
    full = json.loads((corpus / "truth.json").read_text())
    customer_of = dict(zip(full["bug_sessions"], full["bug_customers"]))
    sess = dest / "sessions"
    sess.mkdir(parents=True)
    sids = []
    for text in docs:
        sid = SID.search(text.split("\n", 1)[0])
        if sid:
            sids.append(sid.group())
            (sess / f"{sid.group()}.md").write_text(text)
        else:
            (dest / "pr-4812.md").write_text(text)  # the PR note, the only non-session doc
    bug = [s for s in sids if s in customer_of]
    plan = {c: [e for e in v if e["session"] in sids] for c, v in full["plan_changes"].items()}
    changed = sorted((c for c in plan if plan[c]), key=lambda c: c != "STARK-1135")
    plan = {c: plan[c] for c in changed}  # bench.py asks about the first key; keep the article's
    (dest / "truth.json").write_text(json.dumps(
        {"bug_sessions": bug, "bug_customers": [customer_of[s] for s in bug],
         "plan_changes": plan, "n_sessions": len(sids)}, indent=1))
    return {"docs": len(docs), "chars": sum(len(d) for d in docs), "sessions": len(sids),
            "bug_sessions": bug, "bug_customers": sorted({customer_of[s] for s in bug}),
            "phrasing_of": {s: next(p for p in BUG_PHRASES if p in (sess / f"{s}.md").read_text())
                            for s in bug}}


def load_cognee():
    """Imported here and not at the top: --grep-only and --self-check must run without it."""
    try:
        import cognee
    except ModuleNotFoundError:
        sys.exit("cognee is not installed. Run with --grep-only, or: "
                 "uv pip install 'cognee[gliner]==1.6.1'")
    return cognee


async def measure_cognee(cognee, docs: list[str]) -> dict:
    """remember() the slice once, then ask the four questions. One recall() call each."""
    out = {"version": cognee.__version__, "dataset": DATASET,
           "keyless": not os.getenv("LLM_API_KEY")}
    t = time.perf_counter()
    result = await cognee.remember(docs, dataset_name=DATASET)
    out["remember_s"] = round(time.perf_counter() - t, 1)
    out["remember_status"] = getattr(result, "status", None)

    for name, q in QUESTIONS:
        t = time.perf_counter()
        items = await cognee.recall(q, datasets=[DATASET])
        text = "\n".join(getattr(i, "text", "") or "" for i in items)
        # Score the bug-recall rows on sessions cognee actually surfaced, not on the PR
        # note's id list - otherwise one chunk of pr-4812.md scores 8/8 for free.
        # ponytail: a session id appears only in its "# Session S0xxxxx" header, so a chunk
        # cut below the header carries no id and under-counts. Score on customer strings
        # instead if a real run shows that happening.
        out[name] = {
            "query": q, "s": round(time.perf_counter() - t, 2), "rounds": 1,
            "full_corpus_scans": 0, "items": len(items),
            "est_tokens_returned": bench.tokens(text),
            "sources": sorted({str(getattr(i, "source", "?")) for i in items}),
            # an empty graph answers with one marker item, not with nothing: do not read
            # that as "found no sessions".
            "warming_up": any(getattr(i, "status", None) == "memory_warming_up" for i in items),
            "sids": sorted(set(SID.findall(PR_SID_LIST.sub("", text)))),
            "pr_note_returned": "PR #4812" in text,
            "customers": sorted(set(CUSTOMER.findall(text))),
            "plans_mentioned": [p for p in PLANS if p in text.lower()],
            "first_line": text.split("\n", 1)[0][:200],
        }
    return out


def score(grep: dict, cog: dict | None, sl: dict) -> list[tuple[str, str, str, str]]:
    """(question, metric, grep cell, cognee cell). Both columns, the same documents."""
    n_bug = len(sl["bug_sessions"])
    bug, customers = set(sl["bug_sessions"]), set(sl["bug_customers"])

    def hit(found):
        return f"{len(set(found) & bug)}/{n_bug}"

    def files(n):
        return f'{n} file{"s" * (n != 1)}'

    rows = [
        ('Q1 "billing bug"', "bug reports found", grep["q_billing_bug"]["recall"],
         hit(cog["q_billing_bug"]["sids"]) if cog else "-"),
        ("", "text returned", files(grep["q_billing_bug"]["files"]),
         f'{cog["q_billing_bug"]["items"]} items, {cog["q_billing_bug"]["est_tokens_returned"]} tok'
         if cog else "-"),
        ('Q2 "invoice"', "bug reports found", grep["q_invoice"]["recall"],
         hit(cog["q_invoice"]["sids"]) if cog else "-"),
        ("", "text returned",
         f'{files(grep["q_invoice"]["files"])}, {grep["q_invoice"]["est_tokens_returned"]} tok',
         f'{cog["q_invoice"]["items"]} items, {cog["q_invoice"]["est_tokens_returned"]} tok'
         if cog else "-"),
        ("Q3 multi-hop", "rounds", str(grep["multi_hop"]["rounds"]),
         str(cog["multi_hop"]["rounds"]) if cog else "-"),
        ("", "full corpus scans", str(grep["multi_hop"]["full_corpus_scans"]),
         str(cog["multi_hop"]["full_corpus_scans"]) if cog else "-"),
        ("", "customers found",
         f'{grep["multi_hop"]["customers_found"]}/{grep["multi_hop"]["customers_expected"]}',
         f'{len(set(cog["multi_hop"]["customers"]) & customers)}/{len(customers)}' if cog else "-"),
    ]
    if "stale_fact" in grep:
        st = grep["stale_fact"]
        rows.append(("Q4 current plan", f'verdict (truth: {st["true_current"]})',
                     f'{len(st["plan_statements_returned"])} statements, no dates, no verdict',
                     verdict(cog["stale_fact"], st["true_current"], cog["keyless"])
                     if cog else "-"))
    rows.append(("write cost, once", "index / ingest",
                 f'FTS5 build {grep["fts5"]["build_s_once"]}s',
                 f'remember() {cog["remember_s"]}s' if cog else "-"))
    return rows


def verdict(sf: dict, true_plan: str, keyless: bool) -> str:
    """Keyless recall() returns chunks, so there is no answer to mark right or wrong."""
    said = ", ".join(sf["plans_mentioned"]) or "no plan"
    if sf["warming_up"]:
        return "memory still warming up (no graph yet)"
    if keyless:
        return f'n/a keyless: {sf["items"]} chunks, mentioning {said}'
    return f'{"correct" if sf["plans_mentioned"] == [true_plan] else "ambiguous"}: {said}'


def render(grep: dict, cog: dict | None, sl: dict, published: dict) -> str:
    rows = score(grep, cog, sl)
    wq, wm, wg = (max(len(r[i]) for r in rows) + 2 for i in range(3))
    mode = ("absent (--grep-only)" if not cog else
            f'{cog["version"]}, {"keyless (no LLM_API_KEY)" if cog["keyless"] else "LLM_API_KEY set"}')
    n, head = sl["docs"], f'grep ({sl["docs"]} docs)'  # 3.11: no nested same quotes in f-strings
    out = [
        f'corpus for BOTH columns: {n} documents, {sl["chars"]:,} chars '
        f'({sl["sessions"]} sessions + the PR note)',
        f'planted bug reports in the slice: {len(sl["bug_sessions"])}, one per phrasing - '
        f'{", ".join(sl["bug_sessions"])}',
        f'cognee: {mode}',
        *(["WARNING: recall() returned the memory_warming_up marker - the graph was not "
           "built, so the cognee cells below are not measurements."]
          if cog and any(cog[n]["warming_up"] for n, _ in QUESTIONS) else []),
        "",
        f'{"question":{wq}} {"metric":{wm}} {head:{wg}} cognee ({n} docs)',
    ]
    out += [f"{q:{wq}} {m:{wm}} {g:{wg}} {c}" for q, m, g, c in rows]
    pub = published["q_billing_bug"]["recall"]
    out += [
        "",
        f'context, NOT a row above: the published grep table at {published["sessions"]:,} sessions '
        f'({published["corpus_mb"]} MB) finds {pub} bug reports for the same literal query, '
        f'returns {published["q_invoice"]["files"]:,} files for "invoice", and needs the same 4 '
        f'rounds / 2 full scans for the multi-hop question.',
        f'not compared, on purpose: query latency and precision. The slice is {n} documents and '
        f'the published numbers are 1k-100k, grep returns every matching file while recall() '
        f'returns top-k, and the published runs were a different machine. The token counts in '
        f'the table are slice-local on both sides - text the agent has to read to answer - and '
        f'are not the published 1k-100k figures.',
        *([f'every cognee cell is one recall() call. grep here is deterministic (fixed seed); '
           f'cognee retrieval is not seeded, so read these as a single observed run, not as '
           f'point values - take a median over repeated runs before publishing them.']
          if cog else []),
    ]
    return "\n".join(out)


def run(corpus: Path, with_cognee: bool) -> dict:
    docs = pick_docs(corpus)
    cognee = load_cognee() if with_cognee else None
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "slice"
        sl = write_slice(corpus, docs, dest)
        grep = bench.bench(tmp, "slice")
    grep["sessions"] = sl["sessions"]
    cog = asyncio.run(measure_cognee(cognee, docs)) if cognee else None
    published = next(r for r in json.loads(
        (REPO / "experiments" / "grep_memory" / "results.json").read_text())
        if r["sessions"] == 10000)
    return {"generated": date.today().isoformat(), "corpus": str(corpus), "slice": sl,
            "grep_slice": grep, "cognee": cog, "grep_published_context": published,
            "table": render(grep, cog, sl, published)}


def self_check() -> None:
    """Generate a small corpus, run the grep column on its slice, assert the scoring holds."""
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "1000"
        make_corpus.main(str(corpus), 1000)
        res = run(corpus, with_cognee=False)

    sl, grep = res["slice"], res["grep_slice"]
    assert sl["docs"] == sl["sessions"] + 1, sl  # every doc but the PR note is a session
    assert len(sl["bug_sessions"]) == len(set(sl["phrasing_of"].values())), sl  # one per phrasing

    literal = sum(1 for s in sl["bug_sessions"] if "billing bug" in sl["phrasing_of"][s])
    assert grep["q_billing_bug"]["recall"] == f'{literal}/{len(sl["bug_sessions"])}', grep
    assert grep["q_billing_bug"]["files"] == literal, grep  # grep finds only the literal
    assert grep["fts5"]["q_billing_bug_recall"] == grep["q_billing_bug"]["recall"], grep
    assert grep["q_invoice"]["files"] > grep["q_billing_bug"]["files"], grep
    assert (grep["multi_hop"]["rounds"], grep["multi_hop"]["full_corpus_scans"]) == (4, 2), grep
    assert grep["multi_hop"]["customers_found"] == grep["multi_hop"]["customers_expected"], grep
    st = grep["stale_fact"]
    assert len(st["plan_statements_returned"]) >= 2, st  # both statements, no verdict
    assert all(st["true_current"] not in s or "moved to" in s for s in st["plan_statements_returned"]), st

    assert res["cognee"] is None, "the grep-only path must not need cognee"
    assert "n/a keyless" not in res["table"] and f'grep ({sl["docs"]} docs)' in res["table"]
    print(res["table"])
    print("\nOK: grep column runs and scores with cognee absent")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self-check" in args:
        self_check()
    else:
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            sys.exit(__doc__.split("Usage:")[1].split("Look for:")[0].rstrip())
        out = run(Path(paths[0]), with_cognee="--grep-only" not in args)
        print(out.pop("table"))
        (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")
        print(f'\nwrote {HERE / "results.json"}')
