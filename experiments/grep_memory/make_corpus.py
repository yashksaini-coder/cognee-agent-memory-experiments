"""Generate a synthetic agent-memory corpus: one Markdown file per support session.

Shaped like what a support agent would write to disk if it "just saved every
conversation to files": a header, then alternating user/agent turns.

Planted ground truth (deterministic, seed 7):
- ~0.5% of sessions report the same billing-sync bug, in 8 different phrasings.
  Only one phrasing contains the words "billing bug".
- Every session ID that reports the bug is listed in one PR note
  (pr-4812.md), which never names a customer.
- Some customers change plan over time; both the old and new plan
  statements stay in their session files.

Usage: python make_corpus.py OUT_DIR N_SESSIONS
"""

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 7

CUSTOMERS = [f"{a}-{n}" for a in ("ACME", "GLOBEX", "INITECH", "UMBRELLA", "STARK", "WAYNE",
                                  "HOOLI", "PIEDPIPER", "VANDELAY", "MASSIVE")
             for n in range(1000, 1300)]

# The planted bug, phrased the way different customers actually describe it.
BUG_PHRASES = [
    "my invoice looked wrong this month, two line items are missing",
    "we were charged but the receipt shows the old amount",
    "the totals on our statement do not match what the card was charged",
    "line items vanish from the invoice after the payment goes through",
    "I think there is a billing bug, the PDF is missing the seat add-on",
    "finance says the amount we paid and the amount on the invoice differ",
    "our receipt dropped the extra seats we bought on Tuesday",
    "the charge went through but the bill still says the starter price",
]

# Ordinary traffic. Several of these mention "invoice" for unrelated reasons.
NOISE_USER = [
    "can you resend last month's invoice to finance@{c}.example",
    "how do I change the invoice email address",
    "please add our VAT number to future invoices",
    "the CSV export times out above 50k rows",
    "how do I invite a new admin to the workspace",
    "SSO login loops back to the sign-in page",
    "can we move the renewal date to the first of the month",
    "the API returns 429 when we sync more than 20 projects",
    "where do I download the audit log",
    "the dashboard is slow to load in the EU region",
    "we want to cancel the add-on for analytics",
    "is there a way to export all comments on a ticket",
    "our webhook stopped firing after the domain change",
    "can I get an invoice in EUR instead of USD",
    "the mobile app logs us out every morning",
]
NOISE_AGENT = [
    "I've resent it, it should arrive within a few minutes.",
    "You can change that under Settings > Billing > Contacts.",
    "I've opened a ticket with engineering and will update you here.",
    "That limit is per workspace; I can raise it for your plan.",
    "Here is the help-centre article that walks through it.",
    "Thanks, I can reproduce it on our side.",
    "I've applied the change; it takes effect on the next cycle.",
    "Could you share the request ID from the response headers?",
]
PLANS = ["starter", "team", "business", "enterprise"]


def turn_lines(rng, customer):
    lines = []
    for _ in range(rng.randint(4, 7)):
        lines.append("**user:** " + rng.choice(NOISE_USER).format(c=customer.lower()))
        lines.append("**agent:** " + rng.choice(NOISE_AGENT))
    return lines


def main(out_dir: str, n: int) -> None:
    rng = random.Random(SEED)
    out = Path(out_dir)
    sess_dir = out / "sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    start = date(2026, 1, 5)

    truth = {"bug_sessions": [], "bug_customers": [], "plan_changes": {}}
    plan_of = {}

    for i in range(n):
        sid = f"S{i:06d}"
        customer = rng.choice(CUSTOMERS)
        day = start + timedelta(days=int(i * 240 / n))
        lines = [f"# Session {sid}", f"customer: {customer}", f"date: {day.isoformat()}", ""]

        # Plan statements: first time we see a customer, then an occasional change.
        if customer not in plan_of:
            plan_of[customer] = rng.choice(PLANS[:2])
            lines.append(f"**agent:** Noted: {customer} is on the {plan_of[customer]} plan.")
        elif rng.random() < 0.01:
            new = rng.choice([p for p in PLANS if p != plan_of[customer]])
            truth["plan_changes"].setdefault(customer, []).append(
                {"session": sid, "date": day.isoformat(), "from": plan_of[customer], "to": new})
            plan_of[customer] = new
            lines.append(f"**agent:** Noted: {customer} moved to the {new} plan.")

        lines += turn_lines(rng, customer)

        if rng.random() < 0.005:
            phrase = rng.choice(BUG_PHRASES)
            pos = rng.randrange(4, len(lines))
            lines.insert(pos, "**user:** " + phrase)
            lines.insert(pos + 1, "**agent:** I've linked this to the open payments issue.")
            truth["bug_sessions"].append(sid)
            truth["bug_customers"].append(customer)

        (sess_dir / f"{sid}.md").write_text("\n".join(lines) + "\n")

    # The PR note: written by an engineer, in engineering words, no customer names.
    pr = [
        "# PR #4812: fix payment sync delay dropping line items",
        "",
        "Root cause: the payment webhook can arrive before the seat change is",
        "committed, so the invoice renders from the stale subscription row.",
        "",
        "Reported in sessions: " + ", ".join(truth["bug_sessions"]),
    ]
    (out / "pr-4812.md").write_text("\n".join(pr) + "\n")
    truth["n_sessions"] = n
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    print(json.dumps({"n": n, "bug_sessions": len(truth["bug_sessions"]),
                      "customers_with_plan_change": len(truth["plan_changes"])}))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
