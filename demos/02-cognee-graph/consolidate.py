"""Merge near-duplicate entities in the graph build_graph.py built, and re-count.

build_graph.py measures how many Entity nodes eight phrasings of one bug reach. This
is the follow-up: cognee 1.6.1's opt-in consolidation step
(cognee.memify_pipelines.consolidate_entities) clusters Entity nodes whose *name
embeddings* are at least `similarity_threshold` apart in cosine terms, plus exact
normalized-name matches, then merges each cluster into one canonical node. It runs
after extraction, on an existing graph; remember() never calls it.

Default mode is a read-only sweep: for each threshold it runs cognee's own detection
step and prints what *would* merge - clusters, and which of them touch the
phrasing entities - and the phrasing counts after that merge. Nothing is mutated.
--apply THRESHOLD runs the real pipeline and writes graph.consolidated.json/.html.
--protect TYPE,TYPE keeps entities of those EntityTypes out of every merge - the
pipeline's own protect_node_types. Identifiers need it: an embedding sees
"wayne-1210" and "wayne-1238" as near-identical names.

Usage (same env as build_graph.py, after a build_graph.py run on the same corpus):
    .venv/bin/python consolidate.py CORPUS_DIR                 # sweep, read-only
    .venv/bin/python consolidate.py CORPUS_DIR --apply 0.85    # merge, then re-dump
    .venv/bin/python consolidate.py CORPUS_DIR --protect session,customer,date
    .venv/bin/python consolidate.py CORPUS_DIR --ask [--runs N] # score recall, N asks (3)

--ask scores what this is for: can recall name the customers who hit the bug? The PR
note in the slice lists session ids but no customers, so the answer has to come from
the eight sessions themselves. Truth is the customer line of each bug session.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from build_graph import DATASET, GRAPH_JSON, HERE, phrasings_in, render, summarize, to_payload

THRESHOLDS = [0.95, 0.9, 0.85, 0.8, 0.75]
PROTECT = (sys.argv[sys.argv.index("--protect") + 1].split(",")
           if "--protect" in sys.argv else [])


def after_merge(payload: dict, clusters: list) -> dict:
    """Phrasing counts if every cluster collapsed into one node - computed, not applied."""
    rep = {}
    for cluster in clusters:
        ids = [str(m["id"]) for m in cluster]
        for i in ids:
            rep[i] = ids[0]
    reached: dict[str, set] = {}
    for n in payload["nodes"]:
        if n["type"] == "Entity" and n["phrasings"]:
            reached.setdefault(rep.get(n["id"], n["id"]), set()).update(n["phrasings"])
    return {"distinct_entities": len(reached),
            "shared_by_2_or_more": sum(1 for p in reached.values() if len(p) > 1),
            "widest": max((len(p) for p in reached.values()), default=0)}


async def scoped(dataset_name: str):
    from cognee.context_global_variables import set_database_global_context_variables
    from cognee.modules.data.methods import get_authorized_existing_datasets
    from cognee.modules.users.methods import get_default_user

    user = await get_default_user()
    ds = (await get_authorized_existing_datasets([dataset_name], "write", user))[0]
    return set_database_global_context_variables(ds.id, user.id)


async def sweep(payload: dict) -> None:
    from cognee.tasks.memify.consolidate_entities import detect_entity_duplicates

    tagged = {n["id"]: n for n in payload["nodes"] if n["type"] == "Entity" and n["phrasings"]}
    before = payload["summary"]["phrasing_entities"]
    print(f"before: {before['distinct_entities']} distinct entities, "
          f"{before['shared_by_2_or_more']} shared by 2+\n")
    async with await scoped(DATASET):
        for t in THRESHOLDS:
            found = await detect_entity_duplicates(
                config={"similarity_threshold": t, "protect_node_types": PROTECT})
            clusters = found["clusters"]
            touching = [c for c in clusters if any(str(m["id"]) in tagged for m in c)]
            a = after_merge(payload, clusters)
            print(f"threshold {t:.2f}: {len(clusters)} clusters, "
                  f"{sum(len(c) - 1 for c in clusters)} nodes would go | phrasing entities "
                  f"{a['distinct_entities']}, shared by 2+ {a['shared_by_2_or_more']}, "
                  f"widest {a['widest']}/{len(payload['phrasings'])}")
            for c in touching:
                print("    " + " = ".join(sorted({repr(m["name"]) for m in c})))


async def apply(corpus: str, threshold: float) -> dict:
    import cognee
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.memify_pipelines.consolidate_entities import consolidate_entities_pipeline
    sys.path.insert(0, str(HERE.parents[1] / "experiments" / "cognee_demo"))
    from run_cognee_demo import pick_docs

    await consolidate_entities_pipeline(
        similarity_threshold=threshold, dataset=DATASET, protect_node_types=PROTECT or None)
    async with await scoped(DATASET):
        nodes, edges = await (await get_graph_engine()).get_graph_data()
    docs = pick_docs(Path(corpus))
    return to_payload(nodes, edges, phrasings_in(docs), {
        "dataset": DATASET, "docs": len(docs), "corpus": str(corpus),
        "cognee_version": cognee.__version__, "consolidated_at": threshold, "protected": PROTECT,
    })


QUESTION = ("Which customers reported the billing problem where invoice line items "
            "go missing after a payment? List every customer id.")


async def ask(corpus: str, runs: int = 3) -> None:
    import cognee
    sys.path.insert(0, str(HERE.parents[1] / "experiments" / "cognee_demo"))
    from run_cognee_demo import pick_docs

    docs = pick_docs(Path(corpus))
    truth = {re.search(r"customer: (\S+)", d).group(1).upper()
             for d in docs if "open payments issue" in d}
    every = {c.upper() for d in docs for c in re.findall(r"customer: (\S+)", d)}
    print(f"truth: {len(truth)} customers {sorted(truth)}")
    for i in range(runs):
        answer = " ".join(str(r) for r in await cognee.recall(QUESTION, datasets=[DATASET]))
        named = {c.upper() for c in re.findall(r"\b[A-Za-z]+-\d{4}\b", answer)} & every
        print(f"ask {i + 1}: {len(named & truth)}/{len(truth)} right, "
              f"{len(named - truth)} wrong {sorted(named - truth)}")


if __name__ == "__main__":
    if "--ask" in sys.argv:
        runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3
        asyncio.run(ask(sys.argv[1], runs))
        sys.exit()
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        sys.exit(__doc__.split("Usage")[1])
    if not GRAPH_JSON.exists():
        sys.exit(f"no {GRAPH_JSON.name} yet - run build_graph.py {sys.argv[1]} first")
    payload = json.loads(GRAPH_JSON.read_text())
    payload["summary"] = summarize(payload)
    if "--apply" in sys.argv:
        t = float(sys.argv[sys.argv.index("--apply") + 1])
        merged = asyncio.run(apply(sys.argv[1], t))
        out = HERE / "graph.consolidated.json"
        out.write_text(json.dumps(merged, indent=1))
        pe = merged["summary"]["phrasing_entities"]
        print(f"after --apply {t}: {merged['summary']['nodes']} nodes, "
              f"{pe['distinct_entities']} phrasing entities, {pe['shared_by_2_or_more']} shared by 2+")
        print(f"wrote {out} and {render(merged, HERE / 'graph.consolidated.html')}")
    else:
        asyncio.run(sweep(payload))
