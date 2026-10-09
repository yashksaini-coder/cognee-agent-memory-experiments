"""Render the approved figures in the dark-card house style: one 1600x900 PNG per figure.

Same numbers as make_figures.py, same sources, restructured for the blog and post layouts:
near-black cards on light grey, monospace for anything that is code, no colour.

Usage: pip install playwright && playwright install chromium
       python figures/make_figures_v2.py figures/v2        (from the repo root)

Covers only the eight figures for material cognee approved in the v1 review
(articles 01 and 02, M1, M6, M7). make_figures.py still renders all fourteen.
"""

import json
import math
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
GREP = json.loads((ROOT / "experiments/grep_memory/results.json").read_text())
DB = json.loads((ROOT / "experiments/db_memory/results.json").read_text())

BG, CARD, CARD2 = "#e4e4e2", "#1b1b1a", "#2a2a28"
WHITE, DIM, DIMMER = "#ffffff", "#9d9d98", "#6f6f6b"
INK, INK2, HAIR = "#1b1b1a", "#6d6d68", "#c9c9c4"
RULE = "#3d3d3a"

SANS = "Inter, 'Noto Sans', 'Liberation Sans', sans-serif"
MONO = "'JetBrains Mono', 'Liberation Mono', monospace"

CSS = f"""
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: 1600px; height: 900px; }}
body {{ background: {BG}; color: {INK}; font-family: {SANS};
        padding: 58px 72px 46px; display: flex; flex-direction: column; }}
h1 {{ font-size: 47px; line-height: 1.1; font-weight: 700; letter-spacing: -1.1px; max-width: 1400px; }}
.sub {{ font-size: 25px; color: {INK2}; margin-top: 12px; max-width: 1380px; line-height: 1.32; }}
.main {{ flex: 1; display: flex; margin-top: 30px; min-height: 0; }}
.foot {{ font-size: 18px; color: {INK2}; margin-top: 16px; }}
.mono {{ font-family: {MONO}; }}
.card {{ background: {CARD}; border-radius: 20px; padding: 30px 34px; color: {WHITE}; }}
.card2 {{ background: {CARD2}; border-radius: 14px; }}
.pill {{ display: inline-block; background: {CARD2}; border: 1.5px solid {RULE}; color: {WHITE};
         border-radius: 999px; font-size: 17px; font-weight: 700; letter-spacing: 1.7px;
         text-transform: uppercase; padding: 8px 20px; align-self: flex-start; }}
.pill-o {{ display: inline-block; border: 1.5px solid {RULE}; color: {DIM}; border-radius: 999px;
           font-size: 17px; padding: 4px 12px; margin: 0 5px 4px 0; font-family: {MONO}; }}
.pill-w {{ display: inline-block; background: {WHITE}; color: {CARD}; border-radius: 999px;
           font-size: 17px; padding: 4px 12px; margin: 0 5px 4px 0; font-family: {MONO}; font-weight: 700; }}
.k {{ font-size: 19px; color: {DIM}; text-transform: uppercase; letter-spacing: 1.6px; font-weight: 700; }}
.big {{ font-size: 86px; font-weight: 700; line-height: 1; letter-spacing: -2.5px; }}
.t {{ font-size: 29px; font-weight: 700; line-height: 1.22; }}
.p {{ font-size: 23px; color: {DIM}; line-height: 1.35; }}
.row {{ display: flex; gap: 26px; }}
.col {{ display: flex; flex-direction: column; gap: 20px; }}
.grow {{ flex: 1; }}
.center {{ justify-content: center; }}
table {{ border-collapse: collapse; width: 100%; font-size: 22px; }}
th {{ text-align: left; font-size: 18px; color: {DIM}; text-transform: uppercase;
      letter-spacing: 1.4px; padding: 0 16px 14px 0; font-weight: 700; }}
td {{ padding: 8px 14px 8px 0; border-top: 1.5px solid {RULE}; vertical-align: middle; color: {WHITE}; }}
svg text {{ font-family: {SANS}; }}
svg text.m {{ font-family: {MONO}; }}
"""


def page(title, sub, main, foot):
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"<h1>{title}</h1><div class='sub'>{sub}</div><div class='main'>{main}</div>"
            f"<div class='foot'>{foot}</div></body></html>")


def fmt_ms(v):
    return f"{v:,.0f} ms" if v >= 100 else (f"{v:.1f} ms" if v >= 1 else f"{v:.2f} ms")


def stat(k, big, p, size=86):
    return (f"<div class='card grow col center' style='gap:0'><div class='k'>{k}</div>"
            f"<div class='big' style='font-size:{size}px;margin-top:18px'>{big}</div>"
            f"<div class='p' style='margin-top:14px'>{p}</div></div>")


# ---------- article 01: grep ----------

def grep_latency():
    sizes = [r["sessions"] for r in GREP]
    series = [
        ("grep, cold cache", WHITE, "10 7", [r["q_one_customer"]["cold_ms"] for r in GREP]),
        ("grep, warm cache", WHITE, "", [r["q_one_customer"]["ms"] for r in GREP]),
        ("index built once (SQLite FTS5)", DIMMER, "", [r["fts5"]["q_one_customer_ms"] for r in GREP]),
    ]
    W, H, L, R, T, B = 1390, 560, 104, 350, 22, 58
    lo, hi = math.log10(0.01), math.log10(10000)
    X = lambda i: L + i * (W - L - R) / (len(sizes) - 1)
    Y = lambda v: T + (hi - math.log10(v)) / (hi - lo) * (H - T - B)
    g = []
    for tick in (0.01, 0.1, 1, 10, 100, 1000, 10000):
        y = Y(tick)
        lab = f"{tick:,.0f}" if tick >= 1 else f"{tick:g}"
        g.append(f"<line x1='{L}' x2='{W - R}' y1='{y}' y2='{y}' stroke='{RULE}'/>"
                 f"<text x='{L - 16}' y='{y + 7}' text-anchor='end' font-size='21' fill='{DIM}'>{lab}</text>")
    for i, s in enumerate(sizes):
        g.append(f"<text x='{X(i)}' y='{H - B + 38}' text-anchor='middle' font-size='22' fill='{DIM}'>{s:,} sessions</text>")
    for name, color, dash, vals in series:
        pts_xy = [(i, v) for i, v in enumerate(vals) if v is not None]  # cold_ms is null when bench.py ran without root
        if not pts_xy:
            continue
        d = "stroke-dasharray='" + dash + "'" if dash else ""
        pts = " ".join(f"{X(i)},{Y(v)}" for i, v in pts_xy)
        g.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='3.5' {d} "
                 f"stroke-linejoin='round' stroke-linecap='round'/>")
        for i, v in pts_xy:
            g.append(f"<circle cx='{X(i)}' cy='{Y(v)}' r='7' fill='{color}' stroke='{CARD}' stroke-width='3'/>")
        xe, ye = X(pts_xy[-1][0]) + 20, Y(pts_xy[-1][1])
        g.append(f"<text x='{xe}' y='{ye - 3}' font-size='27' font-weight='700' fill='{WHITE}'>{fmt_ms(pts_xy[-1][1])}</text>"
                 f"<text x='{xe}' y='{ye + 25}' font-size='20' fill='{DIM}'>{name}</text>")
    svg = f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>{''.join(g)}</svg>"
    body = (f"<div class='card grow col' style='gap:18px'>"
            f"<div class='mono' style='font-size:23px;color:{DIM}'>rg -l ACME-1171 sessions/</div>{svg}</div>")
    return page("grep's cost grows with the memory. An index stays flat.",
                "Time to find one customer's sessions, in milliseconds (log scale)",
                f"<div style='width:100%;display:flex'>{body}</div>",
                "Synthetic support sessions, one Markdown file each. ripgrep 14.1.0, SQLite 3.45.1, 2 vCPU. Measured 1 Oct 2026.")


def bar(label, pct, note, filled):
    w = max(pct * 4.2, 4)
    fill = (f"background:{WHITE}" if filled
            else f"background:repeating-linear-gradient(90deg,{DIM} 0 2px,transparent 2px 7px);border:1.5px solid {DIM}")
    return (f"<div>"
            f"<div class='mono' style='font-size:24px;color:{DIM}'>{label}</div>"
            f"<div style='display:flex;align-items:center;gap:20px;margin-top:16px'>"
            f"<div style='height:32px;width:{w:.0f}px;border-radius:0 4px 4px 0;{fill}'></div>"
            f"<div style='font-size:44px;font-weight:700;letter-spacing:-1px'>{pct:g}%</div>"
            f"<div class='p' style='font-size:23px'>{note}</div></div></div>")


def grep_recall():
    r = GREP[-1]
    n, bug = r["sessions"], r["planted_bug_reports"]
    b_found = int(r["q_billing_bug"]["recall"].split("/")[0])
    i_found = int(r["q_invoice"]["recall"].split("/")[0])
    i_files = r["q_invoice"]["files"]
    panel = lambda title, bars: (f"<div class='card grow col' style='gap:0'><div class='pill'>{title}</div>"
                                 f"<div style='flex:1;display:flex;flex-direction:column;justify-content:center;gap:56px'>"
                                 f"{bars}</div></div>")
    left = panel("Bug reports found",
                 bar('rg -i "billing bug"', round(100 * b_found / bug), f"{b_found} of {bug}", True)
                 + bar('rg -i invoice', round(100 * i_found / bug), f"{i_found} of {bug}", False))
    right = panel("Share of all sessions returned",
                  bar('rg -i "billing bug"', round(100 * b_found / n, 2), f"{b_found:,} of {n:,}", True)
                  + bar('rg -i invoice', round(100 * i_files / n), f"{i_files:,} of {n:,}, about 3M tokens", False))
    return page("The precise keyword misses most reports. The broad one returns almost everything.",
                "One billing bug, described by customers in 8 different ways, across 100,000 sessions",
                f"<div class='row' style='width:100%'>{left}{right}</div>",
                "Token count estimated at 4 characters per token. Measured 1 Oct 2026 with ripgrep 14.1.0.")


# ---------- article 02: database ----------

def db_key_vs_question():
    left = (f"<div class='card grow col center' style='gap:30px'>"
            f"<div class='pill'>A question with a key</div>"
            f"<div class='card2 mono' style='font-size:24px;padding:24px 26px;line-height:1.55;color:{WHITE}'>"
            f"SELECT plan FROM customers<br>WHERE id = 'ACME-1171';</div>"
            f"<div><div class='big' style='font-size:92px'>0.048 ms</div>"
            f"<div class='p' style='margin-top:12px'>returns <b style='color:{WHITE}'>starter</b>, exact and indexed</div></div></div>")

    def box(x, y, w, h, t, s):
        return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='13' fill='{CARD2}'/>"
                f"<text x='{x + w / 2}' y='{y + h / 2 - 5}' text-anchor='middle' font-size='25' font-weight='700' fill='{WHITE}'>{t}</text>"
                f"<text x='{x + w / 2}' y='{y + h / 2 + 24}' text-anchor='middle' font-size='19' fill='{DIM}'>{s}</text>")

    svg = (f"<svg width='640' height='380' viewBox='0 0 640 380'>"
           + box(0, 0, 290, 96, "Complaint", "“receipt dropped the seats”")
           + box(350, 0, 290, 96, "PR #4812", "“fix payment sync delay”")
           + box(175, 215, 290, 96, "Customer", "ACME-1171")
           + f"<path d='M290 48H350' stroke='{DIM}' stroke-width='2.5' stroke-dasharray='8 8' fill='none'/>"
           + f"<path d='M145 96L265 215' stroke='{DIM}' stroke-width='2.5' stroke-dasharray='8 8' fill='none'/>"
           + f"<path d='M495 96L375 215' stroke='{DIM}' stroke-width='2.5' stroke-dasharray='8 8' fill='none'/>"
           + f"<text x='320' y='356' text-anchor='middle' font-size='21' fill='{DIM}'>"
             f"no foreign key and no shared words connect these</text></svg>")
    right = (f"<div class='card grow col center' style='gap:22px'><div class='pill'>A question an agent gets</div>"
             f"<div class='t' style='font-size:31px'>“Did the fix for ACME's billing problem ship?”</div>{svg}</div>")
    return page("The database answers the first question. It can't join the second.",
                "Both live in the same SQLite database, loaded with 10,000 support sessions",
                f"<div class='row' style='width:100%'>{left}{right}</div>",
                "Dashed = a link that exists only as meaning. Something has to read both texts and write it down.")


def db_overlap():
    rows = sorted(DB["complaint_vs_fix"]["phrasings"], key=lambda p: len(p["shared_with_pr"]))
    body = ""
    for p in rows:
        if p["shared_with_pr"]:
            chips = "".join(
                (f"<span class='pill-w'>{w} · in {p['pct_sessions_containing'][w]:g}% of sessions</span>"
                 if p["pct_sessions_containing"][w] > 50 else f"<span class='pill-o'>{w}</span>")
                for w in p["shared_with_pr"])
        else:
            chips = f"<span class='pill-o' style='border-style:dashed'>none</span>"
        body += f"<tr><td style='width:62%'>“{p['phrase']}”</td><td>{chips}</td></tr>"
    table = (f"<table><tr><th>How the customer said it</th>"
             f"<th>Words shared with the PR that fixed it</th></tr>{body}</table>")
    card = (f"<div class='card grow col' style='gap:16px'>"
            f"<div class='mono' style='font-size:22px;color:{DIM}'># PR 4812: fix payment sync delay dropping line items</div>"
            f"{table}</div>")
    return page("4 of 8 complaints share no word with the PR that fixed them",
                "Every way a customer described one billing bug, against the words of the PR that fixed it",
                f"<div style='width:100%;display:flex'>{card}</div>",
                "10,000 synthetic support sessions in SQLite. A white chip marks a word too common to join on. Measured 1 Oct 2026.")


def five_jobs():
    jobs = [("Decide what to keep", "1 or 2 facts out of a 40-message conversation"),
            ("Resolve entities", "“ACME”, “ACME-1171”, “the customer on ticket 1182”"),
            ("Connect facts", "complaint → bug → fix → every customer affected"),
            ("Track time", "an UPDATE keeps the new plan and drops the old one"),
            ("Find a starting point", "from a vague question, not from an ID")]
    rows = ""
    for i, (t, p) in enumerate(jobs):
        rel = i in (1, 2, 3)  # resolve entities / connect facts / track time are the relationship jobs
        rows += (f"<div style='flex:1;display:flex;align-items:center;gap:22px;padding:0 26px;border-radius:13px;"
                 f"background:{CARD2 if rel else CARD};"
                 f"border-left:6px solid {WHITE if rel else CARD}'>"
                 f"<div class='mono' style='font-size:25px;color:{DIM};width:30px'>{i + 1}</div>"
                 f"<div class='t' style='width:330px;color:{WHITE}'>{t}</div>"
                 f"<div class='p' style='flex:1'>{p}</div>"
                 + (f"<div style='font-size:16px;font-weight:700;letter-spacing:1.5px;color:{WHITE}'>RELATIONSHIP</div>"
                    if rel else "") + "</div>")
    endcap = lambda s: (f"<div style='text-align:center;padding:16px;border-radius:13px;background:{CARD};"
                        f"color:{WHITE};font-size:26px;font-weight:700;letter-spacing:0.3px'>{s}</div>")
    main = (f"<div class='col' style='width:100%;gap:10px'>{endcap('Your agent')}{rows}{endcap('Your database')}</div>")
    return page("The memory layer is the five jobs between your agent and the database",
                "The three marked jobs are about relationships between facts, which is why a graph sits in the middle",
                main, "A database stores what you write and returns what you ask for. These five are left to your code.")


# ---------- mini-posts ----------

def m1():
    def box(x, y, w, h, t, s="", light=False):
        bg = CARD2 if light else "none"
        stroke = f"stroke='{RULE}' stroke-width='2'" if not light else ""
        return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='13' fill='{bg}' {stroke}/>"
                f"<text x='{x + w / 2}' y='{y + (h / 2 + 9 if not s else h / 2 - 5)}' text-anchor='middle' "
                f"font-size='26' font-weight='700' fill='{WHITE}'>{t}</text>"
                + (f"<text x='{x + w / 2}' y='{y + h / 2 + 24}' text-anchor='middle' font-size='19' fill='{DIM}'>{s}</text>" if s else ""))

    arrow = (f"<defs><marker id='a' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
             f"orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='{DIM}'/></marker>"
             f"<marker id='aw' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
             f"orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='{WHITE}'/></marker></defs>")
    ln = lambda d, c=DIM, m="a", w=2.5, dash="": (
        f"<path d='{d}' fill='none' stroke='{c}' stroke-width='{w}' "
        f"{'stroke-dasharray=' + chr(39) + dash + chr(39) if dash else ''} marker-end='url(#{m})'/>")

    svg = (f"<svg width='1390' height='520' viewBox='0 0 1390 520'>{arrow}"
           f"<text x='0' y='22' font-size='18' font-weight='700' fill='{DIM}' letter-spacing='1.7'>RAG · READ ONLY</text>"
           + box(0, 52, 280, 96, "Corpus", "docs someone else wrote")
           + box(430, 52, 280, 96, "Retriever") + box(860, 52, 280, 96, "LLM", "answers")
           + ln("M280 100H430") + ln("M710 100H860")
           + f"<text x='355' y='92' text-anchor='middle' font-size='18' class='m' fill='{DIM}'>retrieve(q)</text>"
           + f"<text x='0' y='292' font-size='18' font-weight='700' fill='{DIM}' letter-spacing='1.7'>AGENT MEMORY · READ AND WRITE</text>"
           + box(0, 322, 280, 96, "Memory store", "evolves with use", light=True)
           + box(430, 322, 280, 96, "Retriever") + box(860, 322, 280, 96, "LLM", "answers")
           + ln("M280 370H430") + ln("M710 370H860")
           + f"<text x='355' y='362' text-anchor='middle' font-size='18' class='m' fill='{DIM}'>recall(q)</text>"
           + ln("M1000 418V478H140V424", WHITE, "aw", 3, "9 7")
           + f"<text x='550' y='468' text-anchor='middle' font-size='21' font-weight='700' fill='{WHITE}'>"
             f"writes back: preferences, outcomes, corrections</text>"
           "</svg>")
    return page("The moment your agent writes back, it isn't RAG anymore",
                "Read-only retrieval is a search problem. Read-write retrieval is a data-management problem.",
                f"<div class='card grow' style='display:flex;align-items:center'>{svg}</div>",
                "Source: Cognee, AI Agent Memory: The Definitive Guide")


def m6():
    W, H, L, R = 700, 420, 160, 160
    X = lambda v: L + v / 0.30 * (W - L - R)
    g = []
    for tick in (0, 0.1, 0.2, 0.3):
        g.append(f"<line x1='{X(tick)}' x2='{X(tick)}' y1='40' y2='320' stroke='{RULE}'/>"
                 f"<text x='{X(tick)}' y='356' text-anchor='middle' font-size='21' fill='{DIM}'>{tick:g}</text>")
    for i, (name, a, b) in enumerate((("128k tier", 0.24, 0.28), ("10M tier", 0.10, 0.13))):
        y = 118 + i * 126
        g.append(f"<text x='{L - 18}' y='{y + 8}' text-anchor='end' font-size='25' font-weight='700' fill='{WHITE}'>{name}</text>"
                 f"<rect x='{X(a)}' y='{y - 11}' width='{X(b) - X(a)}' height='22' rx='3' fill='{WHITE}'/>"
                 f"<text x='{X(b) + 14}' y='{y + 8}' font-size='24' font-weight='700' fill='{WHITE}'>{a:.2f} to {b:.2f}</text>")
    g.append(f"<text x='{L}' y='402' font-size='19' fill='{DIM}'>BEAM score of long-context models, no memory layer</text>")
    svg = f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>{''.join(g)}</svg>"
    left = (f"<div class='col' style='width:560px;gap:24px'>"
            + stat("LongMemEval, 115k-token history", "30–60%", "of performance lost by long-context LLMs")
            + stat("Context rot", "300 &gt; 113k", "focused 300-token prompts beat full 113k-token prompts") + "</div>")
    right = f"<div class='card grow col center' style='gap:10px'><div class='pill'>BEAM</div>{svg}</div>"
    return page("Fitting the history isn't the same as using it",
                "What long-context models do when the answer is buried in a long history",
                f"<div class='row' style='width:100%;gap:26px'>{left}{right}</div>",
                "Source: Cognee, AI Memory Benchmarks: The Complete Guide")


def m7():
    tiles = [("Grocery checkout conversion", "+24%", "relative, vs sessions without memory"),
             ("Restaurant-assistant conversion", "+15%", "relative, vs sessions without memory"),
             ("Misunderstood user intent", "−33%", "less likely with memory")]
    cards = "".join(f"<div class='card grow col' style='gap:24px;padding:80px 34px'><div class='k'>{k}</div>"
                    f"<div class='big' style='font-size:140px'>{b}</div>"
                    f"<div class='p' style='font-size:25px'>{p}</div></div>" for k, b, p in tiles)
    return page("Benchmarks score memory. Production scores behaviour.",
                "DoorDash ran memory on vs memory off for its Ask DoorDash assistant, over 7 days in production",
                f"<div class='row' style='width:100%'>{cards}</div>",
                "Source: DoorDash engineering blog, Building Ask DoorDash (Part 2): Intelligence, 18 Jun 2026")


FIGURES = {
    "grep-latency": grep_latency, "grep-recall": grep_recall,
    "db-key-vs-question": db_key_vs_question, "db-word-overlap": db_overlap, "db-five-jobs": five_jobs,
    "m1-rag-vs-memory": m1, "m6-context-rot": m6, "m7-doordash": m7,
}

if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chromium")  # full build; the headless shell is a separate download
        pg = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        for name, fn in FIGURES.items():
            pg.set_content(fn())
            over = pg.evaluate("""() => {
                const b = document.body, bad = [];
                if (b.scrollHeight > 900 || b.scrollWidth > 1600) bad.push('body');
                // only the fixed-height flex containers can actually clip their contents;
                // 2px tolerance because line-height rounding trips every heading otherwise
                for (const el of document.querySelectorAll('.card, .main'))
                    if (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)
                        bad.push(el.className);
                return bad;
            }""")
            pg.screenshot(path=str(out / f"{name}.png"))
            bad += bool(over)
            print(name, ("CLIPPED " + ", ".join(over[:3])) if over else "ok")
        browser.close()
    sys.exit(1 if bad else 0)
