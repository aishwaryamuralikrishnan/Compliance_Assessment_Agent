"""Housekeeping for the demo database: see and prune the register and the long-term memory.

    python scripts/admin.py register                       # list register entries (newest first)
    python scripts/admin.py register --dedupe              # keep the newest entry per title, delete the rest
    python scripts/admin.py register --delete A-0012 A-0015
    python scripts/admin.py memory                         # list every memory item with its key and author
    python scripts/admin.py memory --dedupe                # per namespace: keep the first of items with the same text / note
    python scripts/admin.py memory --delete <key> [<key> ...]
    python scripts/admin.py memory --clear-learned         # remove every learned item, keep the seeded ones
    python scripts/admin.py reset                          # fresh demo state: assessments, review tasks, register, threads,
                                                           # learned memory all gone; corpus, users and seeded memory stay
    python scripts/admin.py prune-threads --days 30        # remove the saved state (checkpoints) of finished conversations
                                                           # older than 30 days; paused or pending threads are kept, and
                                                           # assessments, review tasks, register and memory are never touched
    python scripts/admin.py prune-threads --days 30 --dry-run   # only list what would go

Every destructive command prints what it will do and asks for confirmation; pass --yes to skip the question.
Deleting a register entry also sets its assessment back to 'approved' so the id stays consistent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compliance_agent import config, db, memory  # noqa: E402

NAMESPACES = [("org/facts", memory.ORG_FACTS), ("org/lessons", memory.ORG_LESSONS)]


def confirm(question: str, yes: bool) -> bool:
    if yes:
        return True
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# --------------------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------------------

def cmd_register(args: argparse.Namespace) -> None:
    with db.connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM register ORDER BY approved_at DESC").fetchall()]
    if not rows:
        print("register is empty")
        return
    for r in rows:
        print(f"{r['assessment_id']:8} {r['approved_at']:%Y-%m-%d %H:%M}  {r['title'][:60]:60}  {r['verdict']:26}  by {r['approved_by']} for {r['requested_by']}")
    victims: list[str] = []
    if args.dedupe:
        seen: set[str] = set()
        for r in rows:                                   # newest first: the first of each title survives
            key = r["title"].strip().lower()
            if key in seen:
                victims.append(r["assessment_id"])
            seen.add(key)
        print(f"\n--dedupe: {len(victims)} duplicate(s) by title: {', '.join(victims) or '-'}")
    if args.delete:
        wanted = {a.upper() for a in args.delete}
        victims += [r["assessment_id"] for r in rows if r["assessment_id"] in wanted]
        missing = wanted - {r["assessment_id"] for r in rows}
        if missing:
            print(f"not in the register: {', '.join(sorted(missing))}")
    victims = sorted(set(victims))
    if not victims:
        return
    if not confirm(f"delete {len(victims)} register entr{'y' if len(victims) == 1 else 'ies'}?", args.yes):
        print("nothing deleted")
        return
    with db.connection() as conn:
        conn.execute("DELETE FROM register WHERE assessment_id = ANY(%s)", (victims,))
        conn.execute("UPDATE assessments SET status = 'approved', updated_at = now() WHERE assessment_id = ANY(%s) AND status = 'recorded'", (victims,))
    print(f"deleted {len(victims)}: {', '.join(victims)}")


# --------------------------------------------------------------------------------------
# memory
# --------------------------------------------------------------------------------------

def _all_namespaces(store) -> list[tuple[str, tuple]]:
    """org/facts, org/lessons and every user's prefs namespace found in the Store."""
    out = list(NAMESPACES)
    try:
        for ns in store.list_namespaces(prefix=("user",)):
            if len(ns) == 3 and ns[2] == "prefs":
                out.append(("/".join(ns), tuple(ns)))
    except Exception:
        pass
    return out


def _norm(s: str) -> str:
    return " ".join(str(s or "").split()).lower()


def cmd_memory(args: argparse.Namespace) -> None:
    from langgraph.store.postgres import PostgresStore

    with PostgresStore.from_conn_string(config.database_url(), index=db.store_index_config()) as store:
        victims: list[tuple[tuple, str, str]] = []
        for label, ns in _all_namespaces(store):
            items = memory.list_namespace(store, ns, limit=500)
            items.sort(key=lambda v: str(v.get("created_at") or ""))     # oldest first: the first copy survives
            print(f"\n{label} · {len(items)} item(s)")
            seen_text: set[str] = set()
            seen_orig: set[str] = set()
            for it in items:
                flag = ""
                learned = it.get("source") != "seed"
                dup = _norm(it.get("text")) in seen_text or (it.get("original") and _norm(it.get("original")) in seen_orig)
                if args.dedupe and dup and learned:
                    flag = "  <- duplicate"
                    victims.append((ns, it["key"], it.get("text", "")))
                elif args.clear_learned and learned:
                    flag = "  <- learned"
                    victims.append((ns, it["key"], it.get("text", "")))
                elif args.delete and it["key"] in args.delete:
                    flag = "  <- delete"
                    victims.append((ns, it["key"], it.get("text", "")))
                seen_text.add(_norm(it.get("text")))
                if it.get("original"):
                    seen_orig.add(_norm(it.get("original")))
                print(f"  {it['key']:34} {str(it.get('created_at') or '')[:16]:16} {it.get('source', ''):18} {it.get('author', ''):8} {str(it.get('text'))[:90]}{flag}")
        if not victims:
            return
        if not confirm(f"\ndelete {len(victims)} memory item(s)?", args.yes):
            print("nothing deleted")
            return
        for ns, key, _ in victims:
            store.delete(ns, key)
        print(f"deleted {len(victims)}")


# --------------------------------------------------------------------------------------
# reset
# --------------------------------------------------------------------------------------

def cmd_reset(args: argparse.Namespace) -> None:
    print("This removes: every assessment, review task and register entry, every conversation thread (checkpoints),")
    print("and every learned memory item. It keeps: the legal corpus, the two users, the seeded memory.")
    if not confirm("reset the demo state?", args.yes):
        print("nothing changed")
        return
    with db.connection() as conn:
        n = {}
        for table in ("register", "review_tasks", "assessments"):
            n[table] = conn.execute(f"DELETE FROM {table}").rowcount
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                n[table] = conn.execute(f"DELETE FROM {table}").rowcount
            except Exception:
                n[table] = "n/a"
    print("deleted rows:", ", ".join(f"{k}={v}" for k, v in n.items()))
    args.dedupe, args.delete, args.clear_learned = False, None, True
    cmd_memory(args)


# --------------------------------------------------------------------------------------
# threads (checkpoint retention)
# --------------------------------------------------------------------------------------

def cmd_prune_threads(args: argparse.Namespace) -> None:
    from compliance_agent import retention

    found = retention.candidates(args.days)
    finished = [t for t in found if t.finished]
    kept = [t for t in found if not t.finished]
    print(f"{len(found)} thread(s) with no activity for more than {args.days} day(s): {len(finished)} finished, {len(kept)} still open")
    for t in finished:
        print(f"  prune  {t.thread_id}  last activity {t.last_activity:%Y-%m-%d %H:%M}  {t.checkpoints} checkpoint(s)")
    for t in kept:
        print(f"  keep   {t.thread_id}  last activity {t.last_activity:%Y-%m-%d %H:%M}  {'; '.join(t.open_reasons)}")
    if args.dry_run or not finished:
        print("nothing changed" if args.dry_run or not finished else "")
        return
    if not confirm(f"delete the checkpoints of {len(finished)} finished thread(s)?", args.yes):
        print("nothing changed")
        return
    result = retention.prune(args.days)
    print(f"removed {result['checkpoints_removed']} checkpoint(s) from {len(result['pruned'])} thread(s); {len(result['kept'])} open thread(s) kept")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="list / prune the processing register")
    r.add_argument("--dedupe", action="store_true", help="keep the newest entry per title")
    r.add_argument("--delete", nargs="+", metavar="A-0012", help="delete these entries")
    r.set_defaults(func=cmd_register)
    m = sub.add_parser("memory", help="list / prune the long-term memory")
    m.add_argument("--dedupe", action="store_true", help="remove learned items that repeat an earlier item's text or note")
    m.add_argument("--delete", nargs="+", metavar="KEY", help="delete items by key")
    m.add_argument("--clear-learned", action="store_true", help="remove every learned item, keep the seeded ones")
    m.set_defaults(func=cmd_memory)
    x = sub.add_parser("reset", help="fresh demo state (keeps corpus, users, seeded memory)")
    x.set_defaults(func=cmd_reset)
    t = sub.add_parser("prune-threads", help="remove the checkpoints of finished conversations older than N days")
    t.add_argument("--days", type=int, default=30, help="keep threads with activity in the last N days (default 30)")
    t.add_argument("--dry-run", action="store_true", help="list what would be removed, change nothing")
    t.set_defaults(func=cmd_prune_threads)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
