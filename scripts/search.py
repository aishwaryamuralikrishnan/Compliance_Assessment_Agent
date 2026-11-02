"""Inspect retrieval end to end from the command line.

    python scripts/search.py "Can we score credit applicants automatically using browsing behaviour?"
    python scripts/search.py "Annex III point 5(b)" --regulation AI_ACT
    python scripts/search.py "DPIA required for profiling" --no-grader      # single pass, no rewrite loop
    python scripts/search.py "Article 22 GDPR" --raw                        # show the three raw lists too
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compliance_agent.retrieval import search_with_loop  # noqa: E402
from compliance_agent.retrieval.search import fulltext_search, hybrid_search, vector_search  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--regulation", choices=["GDPR", "AI_ACT"])
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--no-grader", action="store_true", help="single hybrid+rerank pass, no grading / rewriting")
    p.add_argument("--raw", action="store_true", help="also print the raw vector / full-text / fused lists")
    p.add_argument("--json", action="store_true", help="dump the full trace as JSON")
    args = p.parse_args()

    if args.raw:
        print("== vector top-10");   [print(f"  {c.vector_distance:.3f}  {c.citation}") for c in vector_search(args.query, 10, args.regulation)]
        print("== full-text top-10"); [print(f"  {c.ts_rank:.3f}  {c.citation}") for c in fulltext_search(args.query, 10, args.regulation)]
        fused, trace = hybrid_search(args.query, args.regulation, k=10)
        print("== identifiers:", trace["identifiers"], "hits:", trace["identifier_hits"])
        print("== fused top-10"); [print(f"  {c.fused_score:.4f}  {c.citation:<28} {c.ranks}") for c in fused]
        print()

    def emit(ev: dict) -> None:
        e = ev.get("event")
        if e == "retrieve":
            print(f"-- attempt {ev['attempt']}: {ev['query']!r}")
        elif e == "graded":
            print(f"   grader: sufficient={ev['sufficient']} (grader confidence {ev['confidence']}) relevant={ev['relevant']}\n   reason: {ev['reason']}")
        elif e == "rewrite":
            print(f"   rewrite -> {ev['new_query']!r}  ({ev['why']})")
        elif e == "done":
            print(f"-- done after {ev['attempts']} attempt(s), sufficient={ev['sufficient']}")

    result = search_with_loop(args.query, regulation=args.regulation, k=args.k, emit=emit, use_grader=not args.no_grader)
    for a in result.attempts:
        print(f"   rerank[{a.number}] {a.rerank_trace.get('method')}: {[(c, round(s, 3) if s is not None else None) for c, s in a.rerank_trace.get('top', [])]}")
    print("\n== returned chunks")
    for c in result.chunks:
        print(f"\n[{c.citation}] {c.heading}  (rerank {c.rerank_score}, ranks {c.ranks})\n{c.text[:600]}{'...' if len(c.text) > 600 else ''}")
    if args.json:
        print(json.dumps(result.as_dict(), indent=1, default=str))


if __name__ == "__main__":
    main()
