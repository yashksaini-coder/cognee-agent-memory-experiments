"""Render the figures: one 1600x900 PNG per figure, from HTML/SVG, with one shared style.

Usage: pip install playwright && playwright install chromium
       python figures/make_figures.py figures          (from the repo root)
Numbers in the charts come from experiments/*/results.json. Fonts: Carlito, DejaVu Sans.
"""

import json
import math
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]  # the folder that holds experiments/
GREP = json.loads((ROOT / "experiments/grep_memory/results.json").read_text())
DB = json.loads((ROOT / "experiments/db_memory/results.json").read_text())

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE, TINT = "#0b0b0b", "#52514e", "#8a8983", "#e6e5e0", "#fcfcfb", "#f1f0ec"

CSS = f"""
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: 1600px; height: 900px; }}
body {{ background: {SURFACE}; color: {INK}; font-family: Carlito, 'DejaVu Sans', sans-serif;
       padding: 64px 88px 56px; display: flex; flex-direction: column; }}
h1 {{ font-size: 52px; line-height: 1.12; font-weight: 700; letter-spacing: -0.5px; max-width: 1400px; }}
.sub {{ font-size: 27px; color: {INK2}; margin-top: 14px; max-width: 1380px; line-height: 1.3; }}
.main {{ flex: 1; display: flex; margin-top: 36px; min-height: 0; }}
.foot {{ font-size: 19px; color: {MUTED}; margin-top: 18px; }}
.mono {{ font-family: 'DejaVu Sans Mono', monospace; }}
.card {{ border: 1.5px solid {GRID}; border-radius: 14px; padding: 28px 30px; background: #ffffff; }}
.tint {{ background: {TINT}; border-color: {TINT}; }}
.k {{ font-size: 21px; color: {INK2}; text-transform: uppercase; letter-spacing: 1.4px; font-weight: 700; }}
.big {{ font-size: 76px; font-weight: 700; line-height: 1; letter-spacing: -1px; }}
.t {{ font-size: 30px; font-weight: 700; line-height: 1.2; }}
.p {{ font-size: 25px; color: {INK2}; line-height: 1.35; }}
.row {{ display: flex; gap: 28px; }}
.col {{ display: flex; flex-direction: column; gap: 22px; }}
.grow {{ flex: 1; }}
.center {{ justify-content: center; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 28px; width: 100%; height: 100%; }}
.fill {{ height: 100%; }}
.dot {{ display: inline-block; width: 16px; height: 16px; border-radius: 50%; margin-right: 10px; vertical-align: -1px; }}
.chip {{ display: inline-block; font-size: 22px; padding: 4px 14px; border-radius: 999px; margin-right: 8px; }}
table {{ border-collapse: collapse; width: 100%; height: 100%; font-size: 27px; }}
th {{ text-align: left; font-size: 20px; color: {INK2}; text-transform: uppercase; letter-spacing: 1.2px; padding: 0 16px 12px 0; }}
td {{ padding: 13px 16px 13px 0; border-top: 1.5px solid {GRID}; vertical-align: middle; }}
svg text {{ font-family: Carlito, 'DejaVu Sans', sans-serif; }}
"""


def page(title, sub, main, foot):
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"<h1>{title}</h1><div class='sub'>{sub}</div><div class='main'>{main}</div>"
            f"<div class='foot'>{foot}</div></body></html>")


def fmt_ms(v):
    return f"{v:,.0f} ms" if v >= 100 else (f"{v:.1f} ms" if v >= 1 else f"{v:.2f} ms")


# ---------- charts from measured data ----------

def grep_latency():
    sizes = [r["sessions"] for r in GREP]
    series = [
        ("grep, cold cache", ORANGE, [r["q_one_customer"]["cold_ms"] for r in GREP]),
        ("grep, warm cache", BLUE, [r["q_one_customer"]["ms"] for r in GREP]),
        ("index built once (SQLite FTS5)", AQUA, [r["fts5"]["q_one_customer_ms"] for r in GREP]),
    ]
    W, H, L, R, T, B = 1424, 610, 110, 330, 20, 60
    lo, hi = math.log10(0.01), math.log10(10000)
    X = lambda i: L + i * (W - L - R) / (len(sizes) - 1)
    Y = lambda v: T + (hi - math.log10(v)) / (hi - lo) * (H - T - B)
    g = []
    for tick in (0.01, 0.1, 1, 10, 100, 1000, 10000):
        y = Y(tick)
        label = f"{tick:,.0f}" if tick >= 1 else f"{tick:g}"
        g.append(f"<line x1='{L}' x2='{W - R}' y1='{y}' y2='{y}' stroke='{GRID}'/>"
                 f"<text x='{L - 16}' y='{y + 7}' text-anchor='end' font-size='22' fill='{INK2}'>{label}</text>")
    for i, s in enumerate(sizes):
        g.append(f"<text x='{X(i)}' y='{H - B + 40}' text-anchor='middle' font-size='24' fill='{INK2}'>{s:,} sessions</text>")
    for name, color, vals in series:
        pts_xy = [(i, v) for i, v in enumerate(vals) if v is not None]  # cold_ms is null when bench.py ran without root
        if not pts_xy:
            continue
        pts = " ".join(f"{X(i)},{Y(v)}" for i, v in pts_xy)
        g.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='4' stroke-linejoin='round' stroke-linecap='round'/>")
        for i, v in pts_xy:
            g.append(f"<circle cx='{X(i)}' cy='{Y(v)}' r='8' fill='{color}' stroke='{SURFACE}' stroke-width='3'/>")
        xe, ye = X(pts_xy[-1][0]) + 22, Y(pts_xy[-1][1])
        g.append(f"<text x='{xe}' y='{ye - 4}' font-size='27' font-weight='700' fill='{INK}'>{fmt_ms(pts_xy[-1][1])}</text>"
                 f"<text x='{xe}' y='{ye + 24}' font-size='21' fill='{INK2}'>{name}</text>")
    svg = f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>{''.join(g)}</svg>"
    return page("grep's cost grows with the memory. An index stays flat.",
                "Time to find one customer's sessions, in milliseconds (log scale)",
                svg,
                "Synthetic support sessions, one Markdown file each. ripgrep 14.1.0, SQLite 3.45.1, 2 vCPU. Measured 1 Oct 2026.")


def hbar(label, pct, note, color):
    w = max(pct, 0.6)
    return (f"<div style='margin-bottom:44px'><div class='p' style='color:{INK};font-weight:700;font-size:30px'>{label}</div>"
            f"<div style='display:flex;align-items:center;gap:16px;margin-top:10px'>"
            f"<div style='height:24px;width:{w * 3.4:.0f}px;background:{color};border-radius:0 4px 4px 0'></div>"
            f"<div style='font-size:30px;font-weight:700'>{pct:g}%</div><div class='p'>{note}</div></div></div>")


def grep_recall():
    r = GREP[-1]
    n = r["sessions"]
    bug = r["planted_bug_reports"]
    b_found = int(r["q_billing_bug"]["recall"].split("/")[0])
    i_found = int(r["q_invoice"]["recall"].split("/")[0])
    i_files = r["q_invoice"]["files"]
    left = ("<div class='card grow col center' style='gap:0'><div class='k'>Bug reports found</div><div style='height:40px'></div>"
            + hbar('search "billing bug"', round(100 * b_found / bug), f"{b_found} of {bug}", BLUE)
            + hbar('search "invoice"', round(100 * i_found / bug), f"{i_found} of {bug}", ORANGE) + "</div>")
    right = ("<div class='card grow col center' style='gap:0'><div class='k'>Share of all sessions returned</div><div style='height:40px'></div>"
             + hbar('search "billing bug"', round(100 * b_found / n, 2), f"{b_found:,} of {n:,}", BLUE)
             + hbar('search "invoice"', round(100 * i_files / n), f"{i_files:,} of {n:,}, about 3M tokens", ORANGE) + "</div>")
    return page("The precise keyword misses most reports. The broad one returns almost everything.",
                "One billing bug, described by customers in 8 different ways, across 100,000 sessions",
                f"<div class='row' style='width:100%'>{left}{right}</div>",
                "Token count estimated at 4 characters per token. Measured 1 Oct 2026 with ripgrep 14.1.0.")


def db_overlap():
    rows = sorted(DB["complaint_vs_fix"]["phrasings"], key=lambda p: len(p["shared_with_pr"]))
    body = ""
    for p in rows:
        if p["shared_with_pr"]:
            chips = "".join(
                f"<span class='chip' style='background:{'#fde3d7' if p['pct_sessions_containing'][w] > 50 else '#d9f2e7'}'>{w}"
                f"{' · in ' + format(p['pct_sessions_containing'][w], 'g') + '% of sessions' if p['pct_sessions_containing'][w] > 50 else ''}</span>"
                for w in p["shared_with_pr"])
        else:
            chips = f"<span class='chip' style='background:{TINT};color:{INK2}'>none</span>"
        body += f"<tr><td style='width:58%'>“{p['phrase']}”</td><td>{chips}</td></tr>"
    table = f"<table><tr><th>How the customer said it</th><th>Words shared with the PR that fixed it</th></tr>{body}</table>"
    return page("4 of 8 complaints share no word with the PR that fixed them",
                "PR #4812: “fix payment sync delay dropping line items”",
                f"<div class='fill' style='width:100%'>{table}</div>",
                "10,000 synthetic support sessions in SQLite. Orange = a word too common to join on. Measured 1 Oct 2026.")


# ---------- diagrams ----------

def node(x, y, w, h, title, sub="", fill="#ffffff", stroke=GRID, bold=True):
    s = (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='14' fill='{fill}' stroke='{stroke}' stroke-width='2.5'/>"
         f"<text x='{x + w / 2}' y='{y + (h / 2 + 9 if not sub else h / 2 - 6)}' text-anchor='middle' font-size='27' "
         f"font-weight='{700 if bold else 400}' fill='{INK}'>{title}</text>")
    if sub:
        s += f"<text x='{x + w / 2}' y='{y + h / 2 + 26}' text-anchor='middle' font-size='21' fill='{INK2}'>{sub}</text>"
    return s


ARROW = (f"<defs><marker id='a' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
         f"<path d='M0 0L10 5L0 10z' fill='{INK2}'/></marker>"
         f"<marker id='ab' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
         f"<path d='M0 0L10 5L0 10z' fill='{BLUE}'/></marker></defs>")


def line(d, color=INK2, dash=False, marker="a", w=2.5):
    dash_attr = "stroke-dasharray='8 8'" if dash else ""
    return (f"<path d='{d}' fill='none' stroke='{color}' stroke-width='{w}' "
            f"{dash_attr} marker-end='url(#{marker})'/>")


def db_key_vs_question():
    left = (f"<div class='card grow col center' style='gap:34px'><div class='k'>A question with a key</div>"
            f"<div class='mono' style='font-size:26px;background:{TINT};padding:24px 26px;border-radius:10px;line-height:1.5'>"
            f"SELECT plan FROM customers<br>WHERE id = 'ACME-1171';</div>"
            f"<div><div class='big' style='font-size:104px'>0.048 ms</div><div class='p' style='margin-top:10px'>returns <b>starter</b>, exact and indexed</div></div></div>")
    svg = (f"<svg width='660' height='400' viewBox='0 0 660 400'>{ARROW}"
           + node(0, 0, 300, 100, "Complaint", "“receipt dropped the seats”")
           + node(360, 0, 300, 100, "PR #4812", "“fix payment sync delay”")
           + node(180, 230, 300, 100, "Customer", "ACME-1171")
           + f"<path d='M300 50H360' stroke='{ORANGE}' stroke-width='3' stroke-dasharray='8 8' fill='none'/>"
           + f"<path d='M150 100L270 230' stroke='{ORANGE}' stroke-width='3' stroke-dasharray='8 8' fill='none'/>"
           + f"<path d='M510 100L390 230' stroke='{ORANGE}' stroke-width='3' stroke-dasharray='8 8' fill='none'/>"
           + f"<text x='330' y='378' text-anchor='middle' font-size='24' fill='{INK2}'>no foreign key and no shared words connect these</text></svg>")
    right = (f"<div class='card grow col center'><div class='k'>A question an agent gets</div>"
             f"<div class='t'>“Did the fix for ACME's billing problem ship?”</div>{svg}</div>")
    return page("The database answers the first question. It can't join the second.",
                "Both live in the same SQLite database, loaded with 10,000 support sessions",
                f"<div class='row' style='width:100%'>{left}{right}</div>",
                "Dashed orange = a link that exists only as meaning. Something has to read both texts and write it down.")


def five_jobs():
    jobs = [("Decide what to keep", "1 or 2 facts out of a 40-message conversation"),
            ("Resolve entities", "“ACME”, “ACME-1171”, “the customer on ticket 1182”"),
            ("Connect facts", "complaint → bug → fix → every customer affected"),
            ("Track time", "an UPDATE keeps the new plan and drops the old one"),
            ("Find a starting point", "from a vague question, not from an ID")]
    rows = "".join(
        f"<div style='display:flex;align-items:center;gap:22px;padding:15px 24px;border-radius:12px;"
        f"background:{'#e3eefb' if i in (1, 2, 3) else '#ffffff'};border:1.5px solid {'#b7d3f6' if i in (1, 2, 3) else GRID}'>"
        f"<div style='font-size:30px;font-weight:700;width:34px'>{i + 1}</div>"
        f"<div style='width:330px' class='t'>{t}</div><div class='p'>{p}</div></div>"
        for i, (t, p) in enumerate(jobs))
    bar = lambda s: f"<div style='text-align:center;padding:13px;border-radius:12px;background:{INK};color:#fff;font-size:27px;font-weight:700'>{s}</div>"
    main = f"<div class='col' style='width:100%;gap:12px'>{bar('Your agent')}{rows}{bar('Your database')}</div>"
    return page("The memory layer is the five jobs between your agent and the database",
                "Blue = jobs about relationships between facts, which is why a graph sits in the middle",
                main, "A database stores what you write and returns what you ask for. These five are left to your code.")


def grep_four_ways():
    r = GREP[-1]
    cold = r['q_one_customer']['cold_ms']
    cold_note = f", {cold / 1000:.1f} s with a cold cache" if cold is not None else ""
    tiles = [
        ("Every question scans everything", f"{r['q_one_customer']['ms']:,.0f} ms", f"per lookup{cold_note}. An index: {r['fts5']['q_one_customer_ms']:.1f} ms"),
        ("People don't repeat their words", "13%", "of bug reports found by searching “billing bug”"),
        ("Connected questions take several searches", "2 full scans", "and 4 rounds to link one PR to the customers it affected"),
        ("grep doesn't know what changed", "2 answers", "“team plan” and “starter plan”, with no dates"),
    ]
    cards = "".join(
        f"<div class='card col center' style='gap:14px'><div class='k'>{i + 1}. {k}</div>"
        f"<div class='big' style='font-size:92px'>{b}</div><div class='p' style='font-size:27px'>{p}</div></div>" for i, (k, b, p) in enumerate(tiles))
    return page("Four ways grep breaks as agent memory",
                "Measured on 100,000 synthetic support sessions saved as files",
                f"<div class='grid2'>{cards}</div>",
                "ripgrep 14.1.0, SQLite 3.45.1, 2 vCPU. Measured 1 Oct 2026.")


def m1():
    svg = (f"<svg width='1424' height='500' viewBox='0 0 1424 500'>{ARROW}"
           f"<text x='0' y='30' font-size='22' font-weight='700' fill='{INK2}' letter-spacing='1.4'>RAG: READ ONLY</text>"
           + node(0, 60, 300, 100, "Corpus", "docs someone else wrote")
           + node(400, 60, 300, 100, "Retriever") + node(800, 60, 300, 100, "LLM", "answers")
           + line("M300 110H400") + line("M700 110H800")
           + f"<text x='0' y='290' font-size='22' font-weight='700' fill='{INK2}' letter-spacing='1.4'>AGENT MEMORY: READ AND WRITE</text>"
           + node(0, 320, 300, 100, "Memory store", "evolves with use", fill="#e3eefb", stroke="#b7d3f6")
           + node(400, 320, 300, 100, "Retriever") + node(800, 320, 300, 100, "LLM", "answers")
           + line("M300 370H400") + line("M700 370H800")
           + line("M950 420V470H150V422", color=BLUE, marker="ab", w=3.5)
           + f"<text x='550' y='460' text-anchor='middle' font-size='23' font-weight='700' fill='{INK}'>writes back: preferences, outcomes, corrections</text>"
           "</svg>")
    return page("The moment your agent writes back, it isn't RAG anymore",
                "Read-only retrieval is a search problem. Read-write retrieval is a data-management problem.",
                f"<div style='width:100%;display:flex;align-items:center'>{svg}</div>", "Source: Cognee, AI Agent Memory: The Definitive Guide")


def m2():
    Y, N = f"<span style='font-weight:700'><span class='dot' style='background:{AQUA}'></span>yes</span>", f"<span style='color:{MUTED}'>✗ no</span>"
    rows = [("1. Weights", "inside the model", "training or fine-tuning", N),
            ("2. Context", "this request", "your code, on every call", N),
            ("3. RAG", "an external corpus", "people who write the docs", "✓ but the agent can't add to it"),
            ("4. Agent memory", "an external store that evolves", "people, pipelines and the agent", Y)]
    body = "".join(f"<tr style='{'background:#e3eefb' if i == 3 else ''}'><td style='font-weight:700;padding-left:18px;white-space:nowrap'>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
                   for i, (a, b, c, d) in enumerate(rows))
    table = (f"<table style='font-size:31px'><tr><th style='padding-left:18px'>Layer</th><th>Where it lives</th><th>Who updates it</th>"
             f"<th>Carries state across sessions?</th></tr>{body}</table>")
    return page("Four places an AI's knowledge can live",
                "“My agent forgot” usually means you expected layer 2 to behave like layer 4",
                f"<div class='fill' style='width:100%'>{table}</div>", "Source: Cognee, AI Agent Memory: The Definitive Guide")


def three_cards(items, accent=None):
    return "".join(
        f"<div class='card grow col' style='gap:34px;padding:56px 36px'>"
        f"<div><div class='t' style='font-size:46px'>{t}</div><div class='p' style='font-size:28px;margin-top:10px'>{how}</div></div>"
        f"<div><div class='k'><span class='dot' style='background:{AQUA}'></span>{k1}</div><div class='p' style='color:{INK};margin-top:8px;font-size:29px'>{good}</div></div>"
        f"<div><div class='k'><span class='dot' style='background:{ORANGE}'></span>{k2}</div><div class='p' style='color:{INK};margin-top:8px;font-size:29px'>{bad}</div></div></div>"
        for i, (t, how, k1, good, k2, bad) in enumerate(items))


def m3():
    items = [("Vector store", "Embed facts, retrieve by similarity", "Good at", "Fast, simple, finds similar text",
              "Misses", "Entities, relationships, what is current"),
             ("Files", "A memory.md the agent edits", "Good at", "Transparent, editable, version-controlled",
              "Misses", "Retrieval beyond “load the file”"),
             ("Graph", "Entities as nodes, relationships as edges", "Good at", "Returns facts that are related, even when they aren't similar",
              "Costs", "A harder write path: extraction and entity resolution")]
    return page("Three ways to store agent memory, and what each one misses",
                "Each covers another's blind spot, so production memory ends up hybrid",
                f"<div class='row' style='width:100%'>{three_cards(items)}</div>",
                "Source: Cognee, AI Agent Memory: The Definitive Guide")


def m4():
    items = [("Factual", "The world and the user", "Example", "“Prefers short answers.”", "Needs to", "Stay current"),
             ("Experiential", "What worked before", "Example", "“Last time this migration failed because of X.”", "Needs to", "Generalise"),
             ("Working", "The task in progress", "Example", "The plan, intermediate results, what's done", "Needs to", "Be fast, then be thrown away")]
    return page("Facts, skills and scratch space: three kinds of agent memory",
                "Store them the same way and scratch notes end up in long-term memory",
                f"<div class='row' style='width:100%'>{three_cards(items)}</div>",
                "Source: Cognee, AI Agent Memory: The Definitive Guide")


def m5():
    W, H, L, R = 1424, 500, 250, 60
    lo, hi = math.log10(1000), math.log10(20_000_000)
    X = lambda v: L + (math.log10(v) - lo) / (hi - lo) * (W - L - R)
    g = [f"<rect x='{L}' y='10' width='{X(128_000) - L}' height='400' fill='{TINT}'/>",
         f"<text x='{L + 16}' y='46' font-size='23' fill='{INK2}'>Fits in the prompt.</text>",
         f"<text x='{L + 16}' y='76' font-size='23' fill='{INK2}'>Pasting the whole history is a fair baseline here.</text>"]
    for tick, lab in ((1000, "1k"), (10_000, "10k"), (100_000, "100k"), (1_000_000, "1M"), (10_000_000, "10M")):
        g.append(f"<line x1='{X(tick)}' x2='{X(tick)}' y1='10' y2='410' stroke='{GRID}'/>"
                 f"<text x='{X(tick)}' y='446' text-anchor='middle' font-size='22' fill='{INK2}'>{lab}</text>")
    g.append(f"<line x1='{X(128_000)}' x2='{X(128_000)}' y1='10' y2='410' stroke='{INK}' stroke-width='2.5'/>"
             f"<text x='{X(128_000) + 14}' y='46' font-size='23' font-weight='700' fill='{INK}'>128k context window</text>")
    rows = [("LoCoMo", 26_000, None, "about 26k"), ("LongMemEval-S", 115_000, None, "about 115k"),
            ("BEAM", 128_000, 10_000_000, "128k to 10M")]
    for i, (name, a, b, lab) in enumerate(rows):
        y = 170 + i * 90
        g.append(f"<text x='{L - 20}' y='{y + 8}' text-anchor='end' font-size='27' font-weight='700' fill='{INK}'>{name}</text>"
                 f"<line x1='{L}' x2='{X(a)}' y1='{y}' y2='{y}' stroke='{GRID}'/>")
        if b:
            g.append(f"<rect x='{X(a)}' y='{y - 12}' width='{X(b) - X(a)}' height='24' rx='4' fill='{BLUE}'/>"
                     f"<text x='{X(b) + 14}' y='{y + 8}' font-size='24' fill='{INK2}'>{lab}</text>")
        else:
            g.append(f"<circle cx='{X(a)}' cy='{y}' r='11' fill='{BLUE}' stroke='{SURFACE}' stroke-width='3'/>"
                     f"<text x='{X(a) + 22}' y='{y + 8}' font-size='24' fill='{INK2}'>{lab}</text>")
    g.append(f"<text x='{W - R}' y='480' text-anchor='end' font-size='21' fill='{MUTED}'>history size in tokens (log scale)</text>")
    svg = f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>{''.join(g)}</svg>"
    return page("If the history fits in the context window, skip the memory layer",
                "How big the conversation histories in three memory benchmarks are",
                f"<div style='width:100%;display:flex;align-items:center'>{svg}</div>", "Source: Cognee, AI Memory Benchmarks: The Complete Guide")


def m6():
    W, H, L, R = 760, 440, 150, 150
    X = lambda v: L + v / 0.30 * (W - L - R)
    g = []
    for tick in (0, 0.1, 0.2, 0.3):
        g.append(f"<line x1='{X(tick)}' x2='{X(tick)}' y1='40' y2='330' stroke='{GRID}'/>"
                 f"<text x='{X(tick)}' y='366' text-anchor='middle' font-size='22' fill='{INK2}'>{tick:g}</text>")
    for i, (name, a, b) in enumerate((("128k tier", 0.24, 0.28), ("10M tier", 0.10, 0.13))):
        y = 120 + i * 130
        g.append(f"<text x='{L - 18}' y='{y + 8}' text-anchor='end' font-size='26' font-weight='700' fill='{INK}'>{name}</text>"
                 f"<rect x='{X(a)}' y='{y - 12}' width='{X(b) - X(a)}' height='24' rx='4' fill='{BLUE}'/>"
                 f"<text x='{X(b) + 14}' y='{y + 8}' font-size='25' font-weight='700' fill='{INK}'>{a:.2f} to {b:.2f}</text>")
    g.append(f"<text x='{L}' y='410' font-size='21' fill='{MUTED}'>BEAM score of long-context models, no memory layer</text>")
    svg = f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>{''.join(g)}</svg>"
    left = (f"<div class='col' style='width:560px;gap:26px'>"
            f"<div class='card grow col center' style='gap:0'><div class='k'>LongMemEval, 115k-token history</div><div class='big' style='margin-top:14px'>30–60%</div>"
            f"<div class='p' style='margin-top:10px'>of performance lost by long-context LLMs</div></div>"
            f"<div class='card grow col center' style='gap:0'><div class='k'>Context rot</div><div class='big' style='margin-top:14px'>300 &gt; 113k</div>"
            f"<div class='p' style='margin-top:10px'>focused 300-token prompts beat full 113k-token prompts</div></div></div>")
    return page("Fitting the history isn't the same as using it",
                "What long-context models do when the answer is buried in a long history",
                f"<div class='row' style='width:100%;gap:60px'>{left}<div class='card grow col center'><div class='k'>BEAM</div>{svg}</div></div>",
                "Source: Cognee, AI Memory Benchmarks: The Complete Guide")


def m7():
    tiles = [("Grocery checkout conversion", "+24%", "relative, vs sessions without memory"),
             ("Restaurant-assistant conversion", "+15%", "relative, vs sessions without memory"),
             ("Misunderstood user intent", "−33%", "less likely with memory")]
    cards = "".join(f"<div class='card grow col' style='gap:26px;padding:90px 34px'><div class='k'>{k}</div>"
                    f"<div class='big' style='font-size:150px'>{b}</div><div class='p' style='font-size:28px'>{p}</div></div>" for k, b, p in tiles)
    return page("Benchmarks score memory. Production scores behaviour.",
                "DoorDash ran memory on vs memory off for its Ask DoorDash assistant, over 7 days in production",
                f"<div class='row' style='width:100%'>{cards}</div>",
                "Source: DoorDash engineering blog, Building Ask DoorDash (Part 2): Intelligence, 18 Jun 2026")


def m8():
    qs = [("Which subset?", "LongMemEval has S (about 115k tokens) and M (about 1.5M). BEAM runs from 128k to 10M."),
          ("Which judge?", "Most memory benchmarks use an LLM judge, and different judges give different scores."),
          ("How many runs?", "Judges vary between runs, and small datasets amplify it. LoCoMo's public release is 10 conversations."),
          ("Tuned on what?", "Were prompts and retrieval settings chosen on the same questions that were scored?")]
    cards = "".join(f"<div class='card col center' style='gap:16px'>"
                    f"<div class='t' style='font-size:46px'>{i + 1}. {q}</div><div class='p' style='font-size:29px'>{p}</div></div>"
                    for i, (q, p) in enumerate(qs))
    return page("How to read an AI memory benchmark claim",
                "Same benchmark, different number? Check these four things before comparing",
                f"<div class='grid2'>{cards}</div>",
                "Source: Cognee, AI Memory Benchmarks: The Complete Guide")


FIGURES = {
    "grep-latency": grep_latency, "grep-recall": grep_recall, "grep-four-ways": grep_four_ways,
    "db-key-vs-question": db_key_vs_question, "db-word-overlap": db_overlap, "db-five-jobs": five_jobs,
    "m1-rag-vs-memory": m1, "m2-four-places": m2, "m3-three-stores": m3, "m4-three-kinds": m4,
    "m5-benchmark-sizes": m5, "m6-context-rot": m6, "m7-doordash": m7, "m8-benchmark-claims": m8,
}

if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1600, "height": 900})
        for name, fn in FIGURES.items():
            pg.set_content(fn())
            over = pg.evaluate("[document.body.scrollHeight, document.body.scrollWidth]")
            pg.screenshot(path=str(out / f"{name}.png"))
            print(name, "overflow!" if over[0] > 900 or over[1] > 1600 else "ok", over)
        browser.close()
