"""What does the grader say? Run the retrieval loop over a few queries and tabulate every grade.

    python scripts/probe_grader.py                      # the built-in set: vague, plain-English and precise queries
    python scripts/probe_grader.py --model google/gemini-3.1-flash      # grade with another model (the `grader` slot
                                                                       # stays as configured; this run only)
    python scripts/probe_grader.py "auto-decline shoppers score phone model" "GDPR Art. 22 automated decision"
    python scripts/probe_grader.py --file queries.txt   # one query per line

The header prints the grader model and its gateway list price with the cost of ten grades at a typical size. For each
attempt: the query, the grader's verdict, its confidence, how many of the five passages it marked relevant, and what
it said was missing; `returned:` is what the loop finally handed back. The last block counts verdicts by confidence
band. What to compare between models: do the plain-English queries end sufficient with the decisive article in the
returned list, and does `missing` name a provision (good) or ask for a judgement the law does not state (bad)?
`grader.accept_threshold` in config/models.yaml is set from the bands once a model is chosen (item 8).
Needs the database (retrieval) and OPENROUTER_API_KEY from the environment / .env; one query costs well under a cent.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from probe_slot import price_of  # noqa: E402  (scripts/probe_slot.py, same folder)

from compliance_agent import config, models  # noqa: E402
from compliance_agent.retrieval import search_with_loop  # noqa: E402

GRADE_TOKENS_IN, GRADE_TOKENS_OUT = 2000, 60      # a typical grade: five passages of up to 1,500 characters, a short verdict

# Vague (a product manager's words, no legal term), plain English about a provision, and precise. A well-set grader
# should send the first group back at least sometimes and accept the last group on the first pass.
DEFAULT_QUERIES = [
    "auto-decline shoppers based on a score from their phone model",
    "selling customer scores to a credit bureau later",
    "nobody looks at the declines",
    "warning label shown to staff based on pages a customer browsed",
    "can a computer reject a credit application without a person",
    "sending customer data to a partner in the United States",
    "automated individual decision-making profiling legal effects",
    "data protection impact assessment profiling creditworthiness",
    "high-risk AI system creditworthiness natural persons Annex III",
    "transfers on the basis of an adequacy decision",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("queries", nargs="*")
    p.add_argument("--file", help="text file with one query per line")
    p.add_argument("--regulation", choices=["GDPR", "AI_ACT"])
    p.add_argument("--model", help="grade with this model id for this run instead of the configured `grader` slot")
    args = p.parse_args()

    queries = list(args.queries)
    if args.file:
        queries += [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not queries:
        queries = DEFAULT_QUERIES

    spec = config.models_config()["slots"]["grader"]           # the cached config: a change here lasts for this process only
    if args.model:
        spec["model"], spec["name"] = args.model, args.model
    threshold = float(spec.get("accept_threshold", 0.6))
    print(f"grader slot: {spec['model']}  accept_threshold={threshold}")
    try:
        line = price_of(spec["model"])
        print("  " + line)
        if line.startswith("price: $"):
            inp, out = (float(x) for x in re.findall(r"\$([0-9.]+)", line)[:2])
            per10 = 10 * (GRADE_TOKENS_IN * inp + GRADE_TOKENS_OUT * out) / 1e6
            print(f"  ≈ ${per10:.4f} per 10 grades at {GRADE_TOKENS_IN} in / {GRADE_TOKENS_OUT} out tokens each (an assessment makes 8-12)")
    except Exception as exc:
        print(f"  price: lookup failed: {type(exc).__name__}: {exc}")
    print()

    rows: list[tuple[str, int, bool, float, int, str]] = []
    rewrites = 0
    errors: list[str] = []

    for q in queries:
        print(f"== {q!r}")
        grades: list[dict] = []

        def emit(ev: dict) -> None:
            nonlocal rewrites
            e = ev.get("event")
            if e == "graded" and "top" in ev:            # the loop's own grade, not the diminishing-returns note
                grades.append(ev)
                reason = ev["reason"]
                if reason.startswith("grader error"):
                    # the loop's safety net: a grader call that fails accepts the passages as-is (confidence 0). In the
                    # app that is reported in the trace; here it means the model cannot grade, and the line says why.
                    errors.append(reason)
                    print(f"   attempt {ev['attempt']}: GRADER ERROR - passages accepted as-is, nothing was graded: {reason}")
                    return
                print(f"   attempt {ev['attempt']}: {'sufficient  ' if ev['sufficient'] else 'INSUFFICIENT'} "
                      f"confidence {ev['confidence']:.2f}  relevant {len(ev['relevant'])}/{len(ev['top'])}  "
                      f"{'' if ev['sufficient'] else 'missing: ' + reason}")
            elif e == "rewrite":
                rewrites += 1
                print(f"   rewrite -> {ev['new_query']!r}")

        result = search_with_loop(q, regulation=args.regulation, k=5, emit=emit)
        for a, g in zip(result.attempts, grades):
            rows.append((q, a.number, g["sufficient"], float(g["confidence"]), len(g["relevant"]), g["reason"]))
        print(f"   returned: {[c.citation for c in result.chunks]}\n")

    print("== summary")
    if errors:
        print(f"{len(errors)} of {len(rows)} grader calls FAILED; this model cannot serve the slot as configured. First error:\n   {errors[0]}")
        if len(errors) == len(rows):
            return
    print(f"{len(queries)} queries, {len(rows)} grades, {rewrites} rewrites")
    bands = Counter()
    for _, _, suff, conf, _, _ in rows:
        band = f"{int(conf * 10) / 10:.1f}-{int(conf * 10) / 10 + 0.1:.1f}" if conf < 1.0 else "1.0"
        bands[(band, "sufficient" if suff else "insufficient")] += 1
    for (band, verdict), n in sorted(bands.items()):
        print(f"   confidence {band:<8} {verdict:<13} {n}")
    first = [r for r in rows if r[1] == 1]
    accepted_first = sum(1 for r in first if r[2])
    print(f"   first attempt accepted: {accepted_first}/{len(first)}")
    confs = sorted(r[3] for r in first)
    if confs:
        print(f"   first-attempt confidence: min {confs[0]:.2f}, median {confs[len(confs) // 2]:.2f}, max {confs[-1]:.2f}")
    print("\nIf the vague queries at the top of the set are accepted at the same confidence as the precise ones at the "
          "bottom, the grader's confidence carries no signal on this model and the threshold cannot fix it; if the "
          "vague ones sit lower, set accept_threshold just above them and re-run.")


if __name__ == "__main__":
    main()
