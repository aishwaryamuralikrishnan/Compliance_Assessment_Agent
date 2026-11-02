"""Drive the agent from the command line (development tool: no password check).

    # product manager: new thread with a feature description
    python scripts/chat.py --user lena.k "We're adding automated credit scoring to our BNPL checkout ..."

    # continue a thread (thread id is printed at the end of every turn)
    python scripts/chat.py --user lena.k --thread <id> "Please request DPO review for A-0004."

    # DPO: see the queue, then decide on a paused thread
    python scripts/chat.py --user m.weber --pending
    python scripts/chat.py --user m.weber --thread <id> --approve "Browsing data is a blocker; otherwise fine."
    python scripts/chat.py --user m.weber --thread <id> --reject "Not a processing activity we will run."

    # inspect a thread / the register
    python scripts/chat.py --thread <id> --state
    python scripts/chat.py --register
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compliance_agent import db, repo  # noqa: E402
from compliance_agent.graph import resume_turn, run_turn, thread_state  # noqa: E402
from compliance_agent.state import UserContext  # noqa: E402


def load_user(username: str) -> UserContext:
    with db.connection() as conn:
        row = conn.execute("SELECT username, role, display_name FROM users WHERE username = %s", (username,)).fetchone()
    if not row:
        sys.exit(f"unknown user {username!r} (seeded users: lena.k, m.weber)")
    return UserContext(row["username"], row["role"], row["display_name"])


def print_event(e: dict) -> None:
    k = e["kind"]
    if k == "custom":
        node, ev = e.get("node"), e.get("event")
        rest = {x: y for x, y in e.items() if x not in ("kind", "ns", "node", "event")}
        print(f"  [{node}] {ev}  {json.dumps(rest, default=str)[:260]}")
    elif k == "update" and e["ns"] == ():
        node = e["node"]
        if node in ("validate_input", "route", "memory_write"):
            d = {x: y for x, y in e["data"].items() if x not in ("messages", "input")}
            print(f"  <{node}> {json.dumps(d, default=str)[:200]}")
    elif k == "interrupt":
        v = e["value"]
        print(f"\n  *** PAUSED ({v.get('type')}): task #{v.get('task_id', '-')} for {v.get('assessment_id') or v.get('tool')} "
              f"requested by {v.get('requested_by')} - waiting for the DPO ***\n")


def print_result(state: dict) -> None:
    v = state["values"]
    print("\n" + "=" * 78)
    a = v.get("assessment")
    if a:
        print(f"ASSESSMENT {a['assessment_id']} · {a['title']} · {a['risk_level'].upper()} risk · high-risk AI: {a['high_risk_ai']} · DPIA: {a['dpia_required']}")
        print(f"{a['verdict']}. {a['summary']}\n")
        for f in a["findings"]:
            print(f"  [{f['severity']:<8}] {f['text']}  ({', '.join(f['citations']) or 'no citation'})")
        print("\n  Next steps:")
        for i, s in enumerate(a.get("next_steps", []), 1):
            print(f"   {i}. {s}")
        print(f"\n  Sources retrieved: {', '.join(a.get('sources', [])) or '-'}")
        g = v.get("guardrail", {})
        print(f"  Guardrail: {g.get('citations_checked', 0)} citations checked, invalid: {g.get('invalid', [])}, "
              f"PII redactions: {g.get('pii_redactions', 0)}, regenerated: {g.get('regenerated', 0)}")
        print(f"\n  {a.get('disclaimer', '')}")
    elif v.get("answer"):
        print("ANSWER:", v["answer"])
        if v.get("sources"):
            print("Sources:", ", ".join(s.get("citation", "") for s in v["sources"]))
    if state.get("pending_interrupt"):
        print("\nSTATUS: waiting for DPO decision on", state["pending_interrupt"].get("assessment_id") or state["pending_interrupt"].get("tool"))
    print(f"\nthread: {state['thread_id']}   route: {v.get('route')} ({v.get('route_reason', '')})")
    print("=" * 78)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("message", nargs="?")
    p.add_argument("--user", default="lena.k")
    p.add_argument("--thread")
    p.add_argument("--approve", metavar="COMMENT")
    p.add_argument("--reject", metavar="COMMENT")
    p.add_argument("--pending", action="store_true", help="list the DPO review queue")
    p.add_argument("--state", action="store_true", help="print the thread state")
    p.add_argument("--register", action="store_true", help="print the processing register")
    args = p.parse_args()

    if args.pending:
        for t in repo.pending_reviews():
            print(f"#{t['id']}  {t['assessment_id']}  {t['title']}  requested by {t['requested_by']}  thread {t['thread_id']}")
        return
    if args.register:
        for r in repo.list_register():
            print(f"{r['assessment_id']}  {r['title']}  {r['verdict']}  risk={r['risk_level']}  approved by {r['approved_by']} {r['approved_at']:%Y-%m-%d %H:%M}")
        return
    if args.state:
        print(json.dumps(thread_state(args.thread), default=str, indent=1)[:4000])
        return

    user = load_user(args.user)
    decision = None
    for flag, name in ((args.approve, "approve"), (args.reject, "reject")):
        if flag is not None:
            decision = {"decision": name, "comment": flag}
    if decision:
        if not args.thread:
            sys.exit("--thread is required to decide on a review")
        print(f"\n{user.display_name} ({user.role}) resumes thread {args.thread}: {decision['decision']}")
        gen = resume_turn(user, args.thread, decision)
    else:
        if not args.message:
            sys.exit("give a message, or --approve/--reject with --thread")
        print(f"\n{user.display_name} ({user.role}): {args.message[:120]}{'...' if len(args.message) > 120 else ''}\n")
        gen = run_turn(user, args.message, args.thread)

    final = None
    for e in gen:
        if e["kind"] == "final":
            final = e["state"]
        else:
            print_event(e)
    if final:
        print_result(final)


if __name__ == "__main__":
    main()
