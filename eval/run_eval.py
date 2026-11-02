"""Run one evaluation set (eval/README.md) and write results/<set>_<timestamp>/.

    python -m eval.run_eval E7                      # the output guardrail on planted faults (no model calls)
    python -m eval.run_eval E12                     # the router and the input screen on routing.jsonl
    python -m eval.run_eval E12 --ids R-008,R-011   # a few rows
    python -m eval.run_eval E3                      # retrieval with and without the loop, and the grader (E4)
    python -m eval.run_eval E5                      # quick answers (runs the app; the judge scores faithfulness)
    python -m eval.run_eval E6                      # full assessments (runs the app; the judge scores the findings)
    python -m eval.run_eval agreement eval/results/E6_<timestamp>   # after filling human_scoring.md
    python -m eval.run_eval check                   # validate the golden files without running anything

Sets that run the app (E12, E3, E5, E6, E7) need EVAL_DATABASE_URL, a copy of the seeded database made with
`CREATE DATABASE compliance_eval TEMPLATE compliance;` (README section 2); the harness refuses the demo database.
OPENROUTER_API_KEY comes from the environment / .env as for the app.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.harness import common  # noqa: E402

SETS = {"E12": "routing", "E7": "faults", "E3": "retrieval", "E5": "quick", "E6": "assessments"}
BUILT = {"E12", "E7", "E3", "E5", "E6"}


def check() -> int:
    problems = 0
    for name in ("routing.jsonl", "retrieval.jsonl", "quick.jsonl", "assessments.jsonl", "faults.jsonl"):
        try:
            rows = common.load_rows(name)
            print(f"{name}: {len(rows)} rows, ids {rows[0]['id']} … {rows[-1]['id']}")
        except Exception as exc:
            problems += 1
            print(f"{name}: {exc}")
    cases = {c["id"] for c in common.load_rows("assessments.jsonl")}
    for f in common.load_rows("faults.jsonl"):
        if f["base"] not in cases:
            problems += 1
            print(f"faults.jsonl {f['id']}: base {f['base']} is not in assessments.jsonl")
    for name in ("routing.jsonl", "retrieval.jsonl", "quick.jsonl", "assessments.jsonl"):
        rows = common.load_rows(name)
        ids = {r["id"] for r in rows}
        for r in rows:
            other = r.get("confusable_with")
            if other and other not in ids:
                print(f"{name} {r['id']}: pair {other} is not in the file yet (fine while the set is being written)")
    print("problems:", problems)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("set", choices=[*SETS, "all", "check", "agreement"])
    p.add_argument("folder", nargs="?", help="agreement: the E6 results folder with the filled human_scoring.md")
    p.add_argument("--ids", help="comma-separated row ids to run")
    p.add_argument("--limit", type=int)
    args = p.parse_args(argv)
    if args.set == "check":
        return check()
    if args.set == "agreement":
        if not args.folder:
            print("agreement needs the E6 results folder")
            return 2
        from eval.harness import assessments
        print(assessments.agreement(args.folder))
        return 0
    sets = [s for s in SETS if s in BUILT] if args.set == "all" else [args.set]
    for s in sets:
        if s not in BUILT:
            print(f"{s} is not built yet (eval/README.md, to-do item 6)")
            return 2
    try:
        common.require_eval_db()
    except common.EvalError as exc:
        print(f"refused: {exc}")
        return 2
    ids = [x.strip() for x in args.ids.split(",")] if args.ids else None
    for s in sets:
        print(f"== {s}")
        if s == "E12":
            from eval.harness import routing
            folder = routing.run(ids, args.limit)
        elif s == "E7":
            from eval.harness import faults
            folder = faults.run(ids, args.limit)
        elif s == "E3":
            from eval.harness import retrieval
            folder = retrieval.run(ids, args.limit)
        elif s == "E5":
            from eval.harness import quick
            folder = quick.run(ids, args.limit)
        elif s == "E6":
            from eval.harness import assessments
            folder = assessments.run(ids, args.limit)
        else:
            continue
        print(f"results: {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
