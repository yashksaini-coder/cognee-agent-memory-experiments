"""What a plain relational database gives an agent, measured on the same support data.

Loads the 10k-session corpus from ../grep_memory into SQLite with a sensible
schema (customers, sessions, a PR table) and checks four things:

1. A keyed lookup (customer -> plan) is instant and exact.
2. The question "did the fix for this customer's problem ship?" has no join key:
   how many of the 8 ways customers described the bug share a content word with
   the PR that fixed it, and how common are those shared words?
3. A plan change: an UPDATE loses the old value; keeping history means every
   query must filter on time.
4. New relation types: how many schema changes it takes to store the relations
   an extractor could find in this data, vs one generic edges table.

Usage: python db_demo.py ../grep_memory/corpus/10000
"""

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "grep_memory"))
from make_corpus import BUG_PHRASES  # noqa: E402

STOP = set("""a an and are as at be but by for from has have i in is it its my of on or our so
that the their there this to was we were with after still what which two""".split())


def words(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2}


def main(corpus):
    d = Path(corpus)
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE customers (id TEXT PRIMARY KEY, plan TEXT);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, customer_id TEXT, day TEXT, body TEXT);
        CREATE INDEX sessions_customer ON sessions(customer_id);
        CREATE TABLE prs (number INTEGER PRIMARY KEY, title TEXT, body TEXT);
    """)
    plan_re = re.compile(r"(\S+) (?:is on|moved to) the (\w+) plan")
    for p in sorted((d / "sessions").glob("*.md")):
        text = p.read_text()
        cust = re.search(r"^customer: (\S+)", text, re.M).group(1)
        day = re.search(r"^date: (\S+)", text, re.M).group(1)
        con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (p.stem, cust, day, text))
        for c, plan in plan_re.findall(text):
            con.execute("INSERT INTO customers VALUES (?,?) ON CONFLICT(id) DO UPDATE SET plan=excluded.plan",
                        (c, plan))
    pr = (d / "pr-4812.md").read_text()
    title, body = pr.splitlines()[0], "\n".join(pr.splitlines()[1:4])  # body without the session list
    con.execute("INSERT INTO prs VALUES (4812, ?, ?)", (title, body))
    out = {}

    # 1. Keyed lookup.
    t = time.perf_counter()
    plan = con.execute("SELECT plan FROM customers WHERE id = 'ACME-1171'").fetchone()
    out["keyed_lookup"] = {"query": "SELECT plan FROM customers WHERE id = 'ACME-1171'",
                           "result": plan[0], "ms": round((time.perf_counter() - t) * 1000, 3)}

    # 2. Is there anything to join a complaint to its fix on?
    n_sessions = con.execute("SELECT count(*) FROM sessions").fetchone()[0]
    pr_words = words(title + " " + body)
    rows = []
    for phrase in BUG_PHRASES:
        shared = sorted(words(phrase) & pr_words)
        df = {w: round(100 * con.execute("SELECT count(*) FROM sessions WHERE body LIKE ?",
                                         (f"%{w}%",)).fetchone()[0] / n_sessions, 1) for w in shared}
        rows.append({"phrase": phrase, "shared_with_pr": shared, "pct_sessions_containing": df})
    out["complaint_vs_fix"] = {"pr": title, "phrasings": rows,
                               "phrasings_sharing_any_word": sum(1 for r in rows if r["shared_with_pr"])}

    # 3. Plan change: what the customers table remembers.
    truth = json.loads((d / "truth.json").read_text())
    who, changes = next(iter(truth["plan_changes"].items()))
    out["plan_change"] = {"customer": who, "history_in_sessions": changes,
                          "customers_table_says": con.execute(
                              "SELECT plan FROM customers WHERE id = ?", (who,)).fetchone()[0]}

    # 4. Relation types an extractor could pull from this data.
    relations = ["customer reported problem", "problem fixed by PR", "PR changed module",
                 "customer on plan (with dates)", "agent promised follow-up", "session mentions invoice",
                 "engineer authored PR", "problem duplicates problem"]
    out["schema"] = {"relation_types": relations,
                     "join_tables_needed": len(relations),
                     "generic_alternative": "CREATE TABLE edges (src TEXT, rel TEXT, dst TEXT, valid_from TEXT, source_id TEXT)"}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
