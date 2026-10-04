"""Measure what grep costs when it is an agent's memory.

For each corpus size: wall time per ripgrep query (warm page cache, median of 7; the multi-hop total is a single run),
bytes scanned, how much text a query returns (tokens estimated at 4 chars/token),
whether literal queries find the planted bug reports, a two-round multi-hop
question, a stale-fact lookup, and the same lookups against a SQLite FTS5 index.

Usage: python bench.py ROOT_DIR SIZE [SIZE ...]   (expects ROOT_DIR/<size>/ from make_corpus.py)
"""

import json
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

RUNS = 7


def rg(args, cwd):
    t = time.perf_counter()
    p = subprocess.run(["rg", *args], cwd=cwd, capture_output=True, text=True)
    return time.perf_counter() - t, p.stdout


def timed(args, cwd):
    times, out = [], ""
    for _ in range(RUNS):
        dt, out = rg(args, cwd)
        times.append(dt)
    return statistics.median(times), out


def tokens(text):
    return round(len(text) / 4)


def corpus_bytes(d):
    return sum(f.stat().st_size for f in Path(d).rglob("*.md"))


def bench(root, size):
    d = Path(root) / str(size)
    truth = json.loads((d / "truth.json").read_text())
    bug = set(truth["bug_sessions"])
    res = {"sessions": size, "corpus_mb": round(corpus_bytes(d) / 1e6, 1),
           "planted_bug_reports": len(bug)}

    # 1. A literal search for the words an agent would use.
    t, out = timed(["-l", "-i", "billing bug", "sessions"], d)
    found = {Path(p).stem for p in out.split()}
    res["q_billing_bug"] = {"ms": round(t * 1000, 1), "files": len(found),
                            "recall": f"{len(found & bug)}/{len(bug)}"}

    # 2. A broader keyword: finds more, returns far more text.
    t, out = timed(["-n", "-i", "invoice", "sessions"], d)
    files = {Path(line.split(":", 1)[0]).stem for line in out.splitlines()}
    res["q_invoice"] = {"ms": round(t * 1000, 1), "matching_lines": len(out.splitlines()),
                        "files": len(files), "est_tokens_returned": tokens(out),
                        "recall": f"{len(files & bug)}/{len(bug)}",
                        "precision_pct": round(100 * len(files & bug) / max(len(files), 1), 2)}

    # 2b. A selective lookup: one customer's history.
    who = truth["bug_customers"][0]
    t, out = timed(["-l", who, "sessions"], d)
    res["q_one_customer"] = {"customer": who, "ms": round(t * 1000, 1), "files": len(out.split())}

    # 3. Multi-hop: which customers did the bug fixed in PR #4812 affect?
    t1, out1 = rg(["-l", "PR #4812", "."], d)                  # round 1: find the PR note (full scan)
    t = time.perf_counter()
    pr_text = "".join((d / p).read_text() for p in out1.split())  # round 2: read it
    t1 += time.perf_counter() - t
    ids = sorted(set(re.findall(r"S\d{6}", pr_text)))
    pattern = "|".join(ids) if ids else "NOMATCH"
    t2, out2 = rg(["-l", pattern, "sessions"], d)              # round 3: find those sessions (full scan)
    t3, out3 = rg(["-N", "^customer:", *out2.split()], d) if out2 else (0.0, "")  # round 4: read customers
    customers = sorted({line.rsplit(":", 1)[1].strip() for line in out3.splitlines()})
    res["multi_hop"] = {"rounds": 4, "full_corpus_scans": 2,
                        "ms_total": round((t1 + t2 + t3) * 1000, 1),
                        "est_tokens_returned": tokens(out1 + pr_text + out2 + out3),
                        "customers_found": len(customers),
                        "customers_expected": len(set(truth["bug_customers"]))}

    # 3b. Cold page cache: the same customer lookup after dropping caches (needs root).
    try:
        subprocess.run(["sync"], check=True)
        Path("/proc/sys/vm/drop_caches").write_text("3\n")
        t, _ = rg(["-l", who, "sessions"], d)
        res["q_one_customer"]["cold_ms"] = round(t * 1000, 1)
    except OSError:
        res["q_one_customer"]["cold_ms"] = None

    # 4. Stale fact: one customer whose plan changed.
    changed = next(iter(truth["plan_changes"]), None)
    if changed:
        t, out = rg(["-N", "-o", "-I", "--sort", "path", f"{changed} (is on|moved to) the \\w+ plan", "sessions"], d)
        res["stale_fact"] = {"customer": changed, "plan_statements_returned": out.splitlines(),
                             "true_current": truth["plan_changes"][changed][-1]["to"]}

    # 5. An index built once at write time: SQLite FTS5.
    db = d / "fts.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE s USING fts5(sid UNINDEXED, body)")
    t = time.perf_counter()
    con.executemany("INSERT INTO s VALUES (?, ?)",
                    ((p.stem, p.read_text()) for p in sorted((d / "sessions").glob("*.md"))))
    con.commit()
    build = time.perf_counter() - t
    qt = []
    for _ in range(RUNS):
        t = time.perf_counter()
        hits = con.execute("SELECT sid FROM s WHERE s MATCH 'invoice'").fetchall()
        qt.append(time.perf_counter() - t)
    qc = []
    for _ in range(RUNS):
        t = time.perf_counter()
        hc = con.execute("SELECT sid FROM s WHERE s MATCH ?", (f'"{who}"',)).fetchall()
        qc.append(time.perf_counter() - t)
    qb = con.execute("SELECT sid FROM s WHERE s MATCH '\"billing bug\"'").fetchall()
    res["fts5"] = {"build_s_once": round(build, 2),
                   "q_invoice_ms": round(statistics.median(qt) * 1000, 2),
                   "q_invoice_files": len(hits),
                   "q_one_customer_ms": round(statistics.median(qc) * 1000, 2),
                   "q_one_customer_files": len(hc),
                   "q_billing_bug_recall": f"{len({h[0] for h in qb} & bug)}/{len(bug)}"}
    con.close()
    return res


if __name__ == "__main__":
    root = sys.argv[1]
    results = [bench(root, int(s)) for s in sys.argv[2:]]
    print(json.dumps(results, indent=1))
