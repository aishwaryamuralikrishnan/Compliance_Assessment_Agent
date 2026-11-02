"""E3 + E4 (eval/README.md): every question of retrieval.jsonl is searched twice, with the agentic loop and with
one ungraded pass, and scored on whether the must provisions are among the returned passages (article level).
E4 reads the grades the loop made on the way: the grader's verdict per attempt against whether a must provision
was among that attempt's five passages, and a threshold sweep on the same logged grades."""
from __future__ import annotations

from typing import Any

from .common import ResultWriter, article_key, load_rows, md_table, ratio, satisfied, usage_counter

THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


def run_row(row: dict[str, Any]) -> dict[str, Any]:
    from compliance_agent.retrieval.loop import search_with_loop

    events: list[dict[str, Any]] = []
    with usage_counter() as usage:
        loop = search_with_loop(row["text"], k=5, emit=events.append)
        single = search_with_loop(row["text"], k=5, max_attempts=1, use_grader=False)
    loop_labels = [c.citation for c in loop.chunks]
    single_labels = [c.citation for c in single.chunks]
    found_l, missing_l = satisfied(row["must"], loop_labels)
    found_s, missing_s = satisfied(row["must"], single_labels)
    nice_l, _ = satisfied(row.get("nice") or [], loop_labels)
    grades = []
    for a in loop.attempts:
        top = [c for c, _ in (a.rerank_trace.get("top") or [])]
        truth = any(article_key(m) in {article_key(t) for t in top} for m in row["must"])
        g = a.grade
        grades.append({"attempt": a.number, "query": a.query, "said_sufficient": bool(g.sufficient), "model_sufficient": getattr(g, "model_sufficient", None),
                       "confidence": float(g.confidence), "relevant": len(g.relevant_chunk_ids), "truth_must_present": truth, "reason": g.reason, "top": top})
    return {
        "id": row["id"], "domain": row.get("domain"), "text": row["text"], "must": row["must"], "nice": row.get("nice") or [],
        "loop": {"labels": loop_labels, "found": found_l, "missing": missing_l, "nice_found": nice_l, "attempts": len(loop.attempts),
                 "rewrites": max(0, len(loop.attempts) - 1), "sufficient": loop.sufficient, "queries": loop.queries},
        "single": {"labels": single_labels, "found": found_s, "missing": missing_s},
        "loop_ok": not missing_l, "single_ok": not missing_s, "grades": grades, "usage": usage,
    }


def run(ids: list[str] | None = None, limit: int | None = None) -> str:
    rows = load_rows("retrieval.jsonl", ids, limit)
    w = ResultWriter("E3")
    results = []
    for row in rows:
        try:
            rec = run_row(row)
        except Exception as exc:
            rec = {"id": row["id"], "error": f"{type(exc).__name__}: {exc}", "loop_ok": False, "single_ok": False, "must": row["must"], "grades": [],
                   "loop": {"found": [], "missing": row["must"], "attempts": 0, "rewrites": 0, "sufficient": False}, "single": {"found": [], "missing": row["must"]}}
        w.case(rec)
        results.append(rec)
        l, s = rec["loop"], rec["single"]
        print(f"  {rec['id']} loop {'ok ' if rec['loop_ok'] else 'NO '} ({l['attempts']} attempt(s), {l.get('rewrites', 0)} rewrite(s))  single {'ok ' if rec['single_ok'] else 'NO '}"
              + (f"  missing: {', '.join(l['missing'])}" if l["missing"] else "") + (f"  ERROR {rec['error']}" if "error" in rec else ""))

    must_total = sum(len(r["must"]) for r in results)
    loop_found = sum(len(r["loop"]["found"]) for r in results)
    single_found = sum(len(r["single"]["found"]) for r in results)
    nice_total = sum(len(r.get("nice") or []) for r in results)
    nice_found = sum(len(r["loop"].get("nice_found") or []) for r in results)
    n = len(results)
    attempts = [r["loop"]["attempts"] for r in results if r["loop"]["attempts"]]
    rewrites = sum(r["loop"].get("rewrites", 0) for r in results)
    insufficient = [r["id"] for r in results if r["loop"]["attempts"] and not r["loop"]["sufficient"]]
    cost = round(sum((r.get("usage") or {}).get("cost", 0) for r in results), 4)

    # E4: the grader's verdict against the truth, and the threshold sweep on the raw verdicts
    grades = [g for r in results for g in r["grades"]]
    tp = sum(1 for g in grades if g["said_sufficient"] and g["truth_must_present"])
    fp = sum(1 for g in grades if g["said_sufficient"] and not g["truth_must_present"])
    fn = sum(1 for g in grades if not g["said_sufficient"] and g["truth_must_present"])
    tn = sum(1 for g in grades if not g["said_sufficient"] and not g["truth_must_present"])
    sweep = []
    for t in THRESHOLDS:
        pred = [(g["model_sufficient"] is True and g["confidence"] >= t and g["relevant"] > 0, g["truth_must_present"]) for g in grades if g["model_sufficient"] is not None]
        sweep.append({"threshold": t, "false_pass": sum(1 for p, tr in pred if p and not tr), "false_fail": sum(1 for p, tr in pred if not p and tr),
                      "accepted": sum(1 for p, _ in pred if p), "of": len(pred)})
    confs = sorted(g["confidence"] for g in grades)

    summary = {
        "recall_loop": {"found": loop_found, "of": must_total}, "recall_single": {"found": single_found, "of": must_total},
        "nice_recall_loop": {"found": nice_found, "of": nice_total},
        "attempts_mean": round(sum(attempts) / len(attempts), 2) if attempts else None, "rewrites_total": rewrites, "insufficient": insufficient,
        "loop_misses": [f"{r['id']}: {', '.join(r['loop']['missing'])}" for r in results if r["loop"]["missing"]],
        "single_misses": [f"{r['id']}: {', '.join(r['single']['missing'])}" for r in results if r["single"]["missing"]],
        "cost": cost,
        "grader": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "grades": len(grades),
                   "precision": round(tp / (tp + fp), 2) if tp + fp else None, "recall": round(tp / (tp + fn), 2) if tp + fn else None,
                   "confidence_min_median_max": [confs[0], confs[len(confs) // 2], confs[-1]] if confs else None, "sweep": sweep},
    }
    md = "## E3 retrieval\n\n" + md_table(["metric", "result", "target"], [
        ["must-retrieve recall@5, agentic loop", ratio(loop_found, must_total), "≥ 0.85"],
        ["must-retrieve recall@5, single ungraded pass", ratio(single_found, must_total), "reported (the difference is what the loop buys)"],
        ["nice-to-retrieve recall@5, loop", ratio(nice_found, nice_total), "reported"],
        ["attempts per query (mean) · rewrites in all · queries ended insufficient", f"{summary['attempts_mean']} · {rewrites} · {len(insufficient)}", "reported"],
        ["model cost of the run (grader, rewrite; the reranker is not priced here)", f"${cost}", "–"],
    ])
    if summary["loop_misses"]:
        md += "\nLoop misses: " + "; ".join(summary["loop_misses"]) + "\n"
    if summary["single_misses"]:
        md += "Single-pass misses: " + "; ".join(summary["single_misses"]) + "\n"
    g = summary["grader"]
    md += "\n## E4 grader\n\n" + md_table(["grades", "said sufficient, must present (right)", "said sufficient, must absent (false pass)", "said insufficient, must present (false fail)", "said insufficient, must absent (right)", "precision", "recall"],
                                       [[g["grades"], tp, fp, fn, tn, g["precision"], g["recall"]]])
    md += "\nThreshold sweep on the same grades (what the loop would have accepted at each `accept_threshold`):\n\n" + md_table(
        ["threshold", "accepted", "false passes", "false fails"], [[s["threshold"], f"{s['accepted']} of {s['of']}", s["false_pass"], s["false_fail"]] for s in sweep])
    if g["confidence_min_median_max"]:
        md += f"\nGrader confidence: min {g['confidence_min_median_max'][0]:.2f}, median {g['confidence_min_median_max'][1]:.2f}, max {g['confidence_min_median_max'][2]:.2f}. "
    md += "The threshold is chosen as the lowest value with the fewest false passes at a tolerable number of false fails (to-do item 8).\n"
    errors = [f"{r['id']}: {r['error']}" for r in results if "error" in r]
    if errors:
        md += "\nErrors: " + "; ".join(errors) + "\n"
    return str(w.finish(summary, md))
