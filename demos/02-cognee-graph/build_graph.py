"""Build cognee's knowledge graph over the eight-phrasings slice and make it inspectable.

Answers the review note on articles/02-just-use-a-database.md: "would be nice to have
an example of how cognee creates the graph, or visually inspect the graph". Takes the
same 30-document slice as ../../experiments/cognee_demo/run_cognee_demo.py (8 bug
sessions, one per phrasing, + 20 ordinary sessions + the PR #4812 note), runs
remember(), reads the graph straight back out of the graph store, and writes:

    graph.json   nodes and edges with cognee's own node types and relationship names
    graph.html   a standalone page that draws them - no CDN, no npm, no build step

Nodes that trace back to one of the eight phrasings are tagged, so the question the
article actually asks - do eight ways of describing one bug land on one entity? - is
the thing you see. The printed summary gives the number: how many distinct Entity
nodes the eight phrasings reached, and how many of those are shared by two or more.
cognee 1.6.1 has no coreference or merge step; entity identity is uuid5 over the
normalized name (cognee/infrastructure/engine/models/DataPoint.py:177), so expect the
eight to stay apart and the shared nodes to be whatever words they happen to have in
common. Keyless runs extract with GLiNER's frozen label bank, which has no billing or
invoice labels, so the names you get are not predictable in advance - that is the
point of measuring instead of drawing.

Usage:
    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python "cognee[gliner]==1.6.1"
    .venv/bin/python ../../experiments/grep_memory/make_corpus.py /tmp/corpus/10000 10000
    .venv/bin/python build_graph.py /tmp/corpus/10000        # needs cognee
    .venv/bin/python build_graph.py /tmp/corpus/10000 --prune  # empty the store first
    python3 build_graph.py --from-json                       # re-render graph.html only
    python3 build_graph.py --self-check                      # the one check; no cognee

Look for: nodes_by_type (is anything beyond DocumentChunk/Entity/EntityType there?),
edges_by_relation (the relationship names GLiNER or the LLM actually emitted), and
phrasing_entities.shared_by_2_or_more. In graph.html, tick "phrasing subgraph only"
to drop the 20 noise sessions and click a node to see its edges and source text.

cognee ships its own renderer (cognee.visualize_graph) and it is better than this one,
but its HTML pulls d3 from d3js.org at view time; this page is self-contained.
"""

import json
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "experiments" / "grep_memory"))
from make_corpus import BUG_PHRASES  # noqa: E402

DATASET = "support_demo"
GRAPH_JSON = HERE / "graph.json"
GRAPH_HTML = HERE / "graph.html"


def phrasings_in(docs):
    """[(session_id, phrase)] for the bug docs, in the order pick_docs() returned them."""
    out = []
    for text in docs:
        phrase = next((p for p in BUG_PHRASES if p in text), None)
        sid = re.search(r"S\d{6}", text)
        if phrase and sid:
            out.append((sid.group(0), phrase))
    return out


def tag_phrasings(nodes, edges, phrasings):
    """Tag every node that traces back to one of the phrasings with its index.

    A node is a seed only if its properties still carry the phrase itself.
    Session ids are deliberately NOT a seed key: pr-4812.md lists every bug
    session id verbatim ("Reported in sessions: S000038, S000103, ..."), so
    seeding on ids tags the PR chunk with all eight phrasings and then hands
    every entity the PR note mentions a fake "shared by 8" badge - which reads
    as the entity resolution cognee 1.6.1 does not do. Anything a seed points
    at - chunk -[contains]-> Entity - inherits the tag.
    """
    tags = {nid: set() for nid, _ in nodes}
    blobs = {nid: json.dumps(props, default=str).lower() for nid, props in nodes}
    for i, (_sid, phrase) in enumerate(phrasings):
        seeds = {nid for nid, b in blobs.items() if phrase in b}
        for nid in seeds:
            tags[nid].add(i)
        for src, tgt, _rel, _p in edges:
            if src in seeds and tgt in tags:
                tags[tgt].add(i)
    return {nid: sorted(t) for nid, t in tags.items()}


def to_payload(nodes, edges, phrasings, meta):
    tags = tag_phrasings(nodes, edges, phrasings)
    out_nodes = []
    for nid, props in nodes:
        ntype = str(props.get("type") or "Unknown")
        text = props.get("text") or props.get("description") or ""
        out_nodes.append({
            "id": nid,
            "name": str(props.get("name") or text[:60] or nid[:8]),
            "type": ntype,
            "text": str(text)[:400],
            "phrasings": tags.get(nid, []),
        })
    out_edges = [{"source": s, "target": t, "relation": rel,
                  "edge_text": str((props or {}).get("edge_text") or "")[:200]}
                 for s, t, rel, props in edges]
    payload = {"meta": meta,
               "phrasings": [{"session": s, "phrase": p} for s, p in phrasings],
               "nodes": out_nodes, "edges": out_edges}
    payload["summary"] = summarize(payload)
    return payload


def summarize(payload):
    by_type = Counter(n["type"] for n in payload["nodes"])
    by_rel = Counter(e["relation"] for e in payload["edges"])
    tagged = [n for n in payload["nodes"] if n["phrasings"] and n["type"] == "Entity"]
    per_phrasing = [sum(1 for n in tagged if i in n["phrasings"])
                    for i in range(len(payload["phrasings"]))]
    shared = sorted(((n["name"], n["phrasings"]) for n in tagged if len(n["phrasings"]) > 1),
                    key=lambda np: -len(np[1]))
    return {
        "nodes": len(payload["nodes"]), "edges": len(payload["edges"]),
        "nodes_by_type": dict(by_type.most_common()),
        "edges_by_relation": dict(by_rel.most_common()),
        "phrasing_entities": {
            "phrasings": len(payload["phrasings"]),
            "distinct_entities": len(tagged),
            "shared_by_2_or_more": len(shared),
            "per_phrasing": per_phrasing,
            "shared": shared[:15],
        },
    }


def print_summary(payload):
    s = payload["summary"]
    m = payload["meta"]
    print(f"{m.get('dataset')} | {m.get('docs')} docs | cognee {m.get('cognee_version', '?')} | "
          f"{'keyless' if m.get('keyless') else 'LLM key set'}"
          + (f" | slice of {m['corpus']}" if m.get("corpus") else ""))
    print(f"{s['nodes']} nodes, {s['edges']} edges")
    print("\nnodes by type")
    for k, v in s["nodes_by_type"].items():
        print(f"  {v:>6}  {k}")
    print("\nedges by relationship")
    for k, v in s["edges_by_relation"].items():
        print(f"  {v:>6}  {k}")
    pe = s["phrasing_entities"]
    print(f"\n{pe['phrasings']} phrasings of one bug reached "
          f"{pe['distinct_entities']} distinct Entity nodes ({pe['per_phrasing']} each)")
    print(f"shared by two or more phrasings: {pe['shared_by_2_or_more']}")
    for name, idx in pe["shared"]:
        print(f"  shared by {len(idx)}: {name}")


async def build(corpus: str) -> dict:
    try:
        import cognee
        from cognee.infrastructure.databases.graph import get_graph_engine
    except ImportError:
        sys.exit("cognee is not installed: uv pip install 'cognee[gliner]==1.6.1' "
                 "(or run with --from-json to re-render an existing graph.json)")
    import os
    sys.path.insert(0, str(HERE.parents[1] / "experiments" / "cognee_demo"))
    from run_cognee_demo import pick_docs

    docs = pick_docs(Path(corpus))
    if "--prune" in sys.argv:  # start from an empty store so counts are the slice's own
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

    t = time.perf_counter()
    result = await cognee.remember(docs, dataset_name=DATASET)
    elapsed = time.perf_counter() - t
    print(f"remember: {elapsed:.1f}s -> {result}")

    # get_graph_data() reads the whole graph into Python. Fine for 30 docs; cognee's own
    # interface docstring warns against it on million-node graphs.
    nodes, edges = await (await get_graph_engine()).get_graph_data()
    return to_payload(nodes, edges, phrasings_in(docs), {
        "dataset": DATASET, "docs": len(docs), "corpus": str(corpus),
        "cognee_version": cognee.__version__,
        "keyless": not os.getenv("LLM_API_KEY"),
        "remember_seconds": round(elapsed, 1),
    })


TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>cognee graph: one billing bug, eight phrasings</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#15161b; color:#e6e6e6;
         font:14px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif; }
  header { padding:14px 18px; border-bottom:1px solid #2a2c35; }
  h1 { font-size:16px; margin:0 0 4px; font-weight:600; }
  .meta, .legend { color:#9a9ca6; font-size:12px; }
  .legend { margin-top:8px; display:flex; flex-wrap:wrap; gap:4px 14px; align-items:center; }
  .legend i { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:5px; }
  label { margin-right:14px; color:#c7c9d1; font-size:12px; cursor:pointer; }
  main { display:flex; align-items:flex-start; }
  #wrap { flex:1; overflow:auto; max-height:calc(100vh - 150px); }
  aside { width:300px; padding:14px 18px; border-left:1px solid #2a2c35; font-size:12px;
          max-height:calc(100vh - 150px); overflow:auto; }
  aside h2 { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:#9a9ca6;
             margin:0 0 8px; }
  aside pre { white-space:pre-wrap; color:#b9bbc4; font-size:11px; }
  table { border-collapse:collapse; font-size:11px; width:100%; }
  td { padding:1px 6px 1px 0; color:#b9bbc4; } td.n { text-align:right; color:#e6e6e6; }
  text { font:11px ui-sans-serif,system-ui,sans-serif; fill:#d4d6de; pointer-events:none; }
  .elabel { font-size:9px; fill:#787a84; }
  .edge { stroke:#3b3e4a; fill:none; }
  .dim { opacity:.12; }
  circle { cursor:pointer; stroke:#15161b; stroke-width:1.5; }
  circle.p { stroke:#ffd166; stroke-width:2.5; }
  .nolabels .elabel { display:none; }
</style>
<header>
  <h1>cognee's graph over one billing bug, described eight ways</h1>
  <div class="meta" id="meta"></div>
  <div style="margin-top:8px">
    <label><input type="checkbox" id="only"> phrasing subgraph only</label>
    <label><input type="checkbox" id="lab"> edge labels</label>
    <span class="meta">click a node for its edges and source text</span>
  </div>
  <div class="legend" id="legend"></div>
</header>
<main>
  <div id="wrap"><svg id="g"></svg></div>
  <aside><div id="detail"></div><h2>summary</h2><div id="sum"></div></aside>
</main>
<script>
const DATA = __GRAPH_JSON__;
const ORDER = ["TextDocument","Document","DocumentChunk","TextSummary","Entity","EntityType"];
const COLORS = {TextDocument:"#8ab4f8", Document:"#8ab4f8", DocumentChunk:"#f6c177",
  TextSummary:"#9ccfd8", Entity:"#c4a7e7", EntityType:"#7ee787", NodeSet:"#eb6f92"};
const PALETTE = ["#e0def4","#f2a5a5","#a5d6f2","#d8f2a5","#f2d5a5"];
const color = t => COLORS[t] || PALETTE[[...t].reduce((a,c)=>a+c.charCodeAt(0),0) % PALETTE.length];
const svg = document.getElementById("g"), side = document.getElementById("detail");
const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
let sel = null;

document.getElementById("meta").textContent =
  [DATA.meta.dataset, DATA.meta.docs + " docs", "cognee " + (DATA.meta.cognee_version||"?"),
   DATA.meta.keyless ? "keyless (GLiNER)" : "LLM key set",
   DATA.summary.nodes + " nodes", DATA.summary.edges + " edges"]
  .concat(DATA.meta.corpus ? ["slice of " + DATA.meta.corpus] : []).join("  |  ");

function render() {
  const only = document.getElementById("only").checked;
  let nodes = only ? DATA.nodes.filter(n => n.phrasings.length) : DATA.nodes;
  const keep = new Set(nodes.map(n => n.id));
  const edges = DATA.edges.filter(e => keep.has(e.source) && keep.has(e.target));

  const cols = [...new Set(nodes.map(n => n.type))].sort((a,b) => {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  const pos = {};
  let rows = 1;
  cols.forEach((t, ci) => {
    const col = nodes.filter(n => n.type === t).sort((a,b) =>
      b.phrasings.length - a.phrasings.length || a.name.localeCompare(b.name));
    rows = Math.max(rows, col.length);
    col.forEach((n, i) => { pos[n.id] = {x: 150 + ci*300, y: 40 + i*30, n}; });
  });
  svg.setAttribute("width", 150 + cols.length*300);
  svg.setAttribute("height", 60 + rows*30);
  svg.classList.toggle("nolabels", !document.getElementById("lab").checked);

  const parts = [];
  for (const e of edges) {
    const a = pos[e.source], b = pos[e.target];
    const mx = (a.x+b.x)/2, my = (a.y+b.y)/2 - 14;
    parts.push(`<g class="e" data-s="${e.source}" data-t="${e.target}">`
      + `<path class="edge" d="M${a.x} ${a.y} Q${mx} ${my} ${b.x} ${b.y}"/>`
      + `<text class="elabel" x="${mx}" y="${my}" text-anchor="middle">${esc(e.relation)}</text></g>`);
  }
  for (const id in pos) {
    const {x, y, n} = pos[id];
    const r = 5 + Math.min(4, n.phrasings.length);
    parts.push(`<g class="nd" data-id="${id}">`
      + `<circle class="${n.phrasings.length ? "p" : ""}" cx="${x}" cy="${y}" r="${r}"`
      + ` fill="${color(n.type)}"><title>${esc(n.type + ": " + n.name)}</title></circle>`
      + `<text x="${x+r+5}" y="${y+4}">${esc(n.name.slice(0,30))}`
      + `${n.phrasings.length ? " [" + n.phrasings.map(i=>i+1).join(",") + "]" : ""}</text></g>`);
  }
  svg.innerHTML = parts.join("");
  svg.querySelectorAll(".nd").forEach(g =>
    g.querySelector("circle").onclick = () => pick(g.dataset.id));
  if (sel && pos[sel]) pick(sel); else { sel = null; }

  document.getElementById("legend").innerHTML = cols.map(t =>
    `<span><i style="background:${color(t)}"></i>${esc(t)}</span>`).join("")
    + `<span><i style="background:transparent;border:2px solid #ffd166"></i>from a phrasing</span>`;
}

function pick(id) {
  sel = id;
  const n = DATA.nodes.find(x => x.id === id);
  const inc = DATA.edges.filter(e => e.source === id || e.target === id);
  const near = new Set([id, ...inc.map(e => e.source), ...inc.map(e => e.target)]);
  svg.querySelectorAll(".nd").forEach(g =>
    g.classList.toggle("dim", !near.has(g.dataset.id)));
  svg.querySelectorAll(".e").forEach(g =>
    g.classList.toggle("dim", g.dataset.s !== id && g.dataset.t !== id));
  const name = x => (DATA.nodes.find(y => y.id === x) || {name: x}).name;
  side.innerHTML = `<h2>${esc(n.type)}</h2><b>${esc(n.name)}</b>`
    + (n.phrasings.length ? `<div class="meta">from phrasing ${n.phrasings.map(i=>i+1).join(", ")}: `
        + n.phrasings.map(i => esc(DATA.phrasings[i].session)).join(", ") + `</div>` : "")
    + `<pre>${esc(n.text)}</pre>`
    + `<h2>${inc.length} edges</h2>` + inc.map(e =>
        `<div>${e.source === id ? "-[" + esc(e.relation) + "]&gt; " + esc(name(e.target))
                                : esc(name(e.source)) + " -[" + esc(e.relation) + "]&gt;"}`
        + (e.edge_text ? `<div class="meta">${esc(e.edge_text)}</div>` : "") + `</div>`).join("")
    + `<p><a href="#" onclick="clear_();return false" style="color:#8ab4f8">clear</a></p>`;
}

function clear_() { sel = null; side.innerHTML = ""; render(); }

const rows = o => Object.entries(o).map(([k,v]) =>
  `<tr><td class="n">${v}</td><td>${esc(k)}</td></tr>`).join("");
const pe = DATA.summary.phrasing_entities;
document.getElementById("sum").innerHTML =
  `<table>${rows(DATA.summary.nodes_by_type)}</table>`
  + `<h2 style="margin-top:12px">edges by relationship</h2>`
  + `<table>${rows(DATA.summary.edges_by_relation)}</table>`
  + `<h2 style="margin-top:12px">entity resolution</h2>`
  + `<div class="meta">${pe.phrasings} phrasings of one bug reached `
  + `<b style="color:#e6e6e6">${pe.distinct_entities}</b> distinct Entity nodes; `
  + `<b style="color:#e6e6e6">${pe.shared_by_2_or_more}</b> shared by two or more.</div>`
  + (pe.shared.length ? `<table style="margin-top:6px">` + pe.shared.map(([nm, ix]) =>
      `<tr><td class="n">${ix.length}</td><td>${esc(nm)}</td></tr>`).join("") + `</table>` : "");

document.getElementById("only").onchange = render;
document.getElementById("lab").onchange = render;
render();
</script>
"""


def render(payload: dict, out: Path = GRAPH_HTML) -> Path:
    # \u003c is a legal JSON escape, so this also closes off <!-- and <script,
    # not just </script. The page needs no un-escaping step to read it back.
    blob = json.dumps(payload, default=str).replace("<", "\\u003c")
    out.write_text(TEMPLATE.replace("__GRAPH_JSON__", blob))
    return out


def self_check() -> None:
    """Two phrasings, one shared entity, one private entity each - end to end, no cognee."""
    nodes = [
        ("c1", {"type": "DocumentChunk", "text": "# Session S000038\n**user:** " + BUG_PHRASES[1]}),
        ("c2", {"type": "DocumentChunk", "text": "# Session S000103\n**user:** " + BUG_PHRASES[2]}),
        ("e_charge", {"type": "Entity", "name": "charge"}),
        ("e_receipt", {"type": "Entity", "name": "receipt"}),
        ("e_statement", {"type": "Entity", "name": "statement"}),
        ("t_concept", {"type": "EntityType", "name": "concept"}),
        ("noise", {"type": "DocumentChunk", "text": "# Session S000001\nSSO login loops"}),
        # The PR note names both sessions by id. It must stay untagged: see tag_phrasings.
        ("pr", {"type": "DocumentChunk",
                "text": "# PR #4812\nReported in sessions: S000038, S000103"}),
        ("e_webhook", {"type": "Entity", "name": "payment webhook"}),
    ]
    edges = [
        ("c1", "e_charge", "contains", {"edge_text": "Document chunk mentions charge"}),
        ("c1", "e_receipt", "contains", {"edge_text": "Document chunk mentions receipt"}),
        ("c2", "e_charge", "contains", {"edge_text": "Document chunk mentions charge"}),
        ("c2", "e_statement", "contains", {}),
        ("e_charge", "t_concept", "is_a", {}),
        ("pr", "e_webhook", "contains", {}),
    ]
    phrasings = [("S000038", BUG_PHRASES[1]), ("S000103", BUG_PHRASES[2])]
    payload = to_payload(nodes, edges, phrasings, {"dataset": "selfcheck", "docs": 4, "keyless": True})
    s = payload["summary"]

    assert s["nodes"] == 9 and s["edges"] == 6, s
    assert s["nodes_by_type"] == {"DocumentChunk": 4, "Entity": 4, "EntityType": 1}, s
    assert s["edges_by_relation"] == {"contains": 5, "is_a": 1}, s
    pe = s["phrasing_entities"]
    assert pe["distinct_entities"] == 3, pe          # charge, receipt, statement - NOT webhook
    assert pe["shared_by_2_or_more"] == 1, pe        # only "charge" is reached by both
    assert pe["shared"][0][0] == "charge", pe
    assert pe["per_phrasing"] == [2, 2], pe
    tags = {n["id"]: n["phrasings"] for n in payload["nodes"]}
    assert tags["noise"] == [] and tags["c1"] == [0] and tags["e_charge"] == [0, 1], tags
    assert tags["t_concept"] == [], tags             # two hops out, not tagged
    assert tags["pr"] == [] and tags["e_webhook"] == [], tags   # ids are not a seed key

    tmp = Path(tempfile.mkdtemp())
    html = render(payload, tmp / "graph.html").read_text()
    assert "charge" in html and "__GRAPH_JSON__" not in html
    assert "http://" not in html and "https://" not in html, "page must be dependency-free"
    assert "<" not in html.split("const DATA = ")[1].split(";\n")[0], "JSON must not carry <"
    assert json.loads(html.split("const DATA = ")[1].split(";\n")[0])

    (tmp / "graph.json").write_text(json.dumps(payload, indent=1))
    reloaded = json.loads((tmp / "graph.json").read_text())
    assert summarize(reloaded) == s
    print_summary(reloaded)
    print(f"\nOK: self-check passed (cognee not required); rendered {tmp / 'graph.html'}")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
    elif "--from-json" in sys.argv:
        if not GRAPH_JSON.exists():
            sys.exit(f"no {GRAPH_JSON.name} here yet - run `build_graph.py CORPUS_DIR` first")
        payload = json.loads(GRAPH_JSON.read_text())
        payload["summary"] = summarize(payload)
        print_summary(payload)
        print(f"\nwrote {render(payload)}")
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        import asyncio
        payload = asyncio.run(build(sys.argv[1]))
        GRAPH_JSON.write_text(json.dumps(payload, indent=1))
        print_summary(payload)
        print(f"\nwrote {GRAPH_JSON} and {render(payload)}")
    else:
        sys.exit(__doc__.split("Usage:")[1].split("Look for:")[0].strip())
