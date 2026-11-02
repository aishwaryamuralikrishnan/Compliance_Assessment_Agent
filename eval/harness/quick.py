"""E5 (eval/README.md): every question of quick.jsonl is run through `run_turn` as a product manager would ask
it; a question the router sends down the quick path gets its answer scored on must-cite recall, invented
citations (before the guardrail marked them), faithfulness to the retrieved passages, and length."""
from __future__ import annotations

import re
from typing import Any

from .common import ResultWriter, load_rows, md_table, ratio, satisfied, usage_counter
from .judge import faithfulness


def _memory_items(text: str) -> list[dict[str, Any]]:
    """What the quick path read for this question (the same recall, against the same store, same k as direct_answer)."""
    from compliance_agent import db, memory

    try:
        mem = memory.recall(db.langgraph_store(), "lena.k", text, facts_k=4, lessons_k=2)
    except Exception:
        return []
    return [{"kind": kind, "text": it.get("text")} for kind in ("org_facts", "lessons") for it in (mem.get(kind) or [])]

_SENT = re.compile(r"[.!?](?:\s|$)")
_ABBR = re.compile(r"\b(Art|Arts|Rec|Recs|No|e\.g|i\.e|cf|para|paras)\.\s", re.IGNORECASE)


def count_sentences(text: str) -> int:
    """Sentences in an answer; citation abbreviations (\"Art. 22\", \"Rec. 71\") are not sentence ends."""
    return len([s for s in _SENT.split(_ABBR.sub(lambda m: m.group(0).replace(". ", " "), text)) if s.strip()])


def run_row(row: dict[str, Any], graph) -> dict[str, Any]:
    from compliance_agent.graph import run_turn
    from compliance_agent.nodes.guardrail import extract_citations
    from compliance_agent.state import UserContext

    events: list[dict[str, Any]] = []
    with usage_counter() as usage:
        for e in run_turn(UserContext("lena.k", "product_manager"), row["text"], graph=graph):
            events.append(e)
            if e["kind"] == "final":
                state = e["state"]
    v = state["values"]
    route = v.get("route")
    rec: dict[str, Any] = {"id": row["id"], "domain": row.get("domain"), "text": row["text"], "must": row["must"], "route": route,
                           "thread_id": state.get("thread_id"), "usage": usage}
    if route != "quick":
        rec.update({"quick": False, "ok": False, "note": f"routed {route}: not a quick answer, not scored" + (" (an assessment was produced and the thread is paused)" if route == "full" else "")})
        return rec
    answer = v.get("answer") or ""
    report = v.get("guardrail") or {}
    labels = [l for l in extract_citations(answer) if not answer.count(f"{l} [unverified]")]
    found, missing = satisfied(row["must"], labels)
    sentences = count_sentences(answer)
    sources = v.get("sources") or []
    rec.update({"quick": True, "answer": answer, "citations": labels, "found": found, "missing": missing, "ok": not missing and bool(answer.strip()),
                "invented": list(report.get("invalid") or []), "unreachable": list(report.get("unreachable") or []), "empty": not answer.strip(),
                "sentences": sentences, "sources": [s.get("citation") for s in sources]})
    with usage_counter() as judge_usage:
        # the quick path reads memory too (direct_answer: facts_k=4, lessons_k=2), so the judge sees the same items (README rule 8)
        rec["faithfulness"] = faithfulness(answer, sources, _memory_items(row["text"]), input_text=row["text"]) if answer.strip() else {"score": None, "note": "empty answer"}
    rec["judge_usage"] = judge_usage
    return rec


def run(ids: list[str] | None = None, limit: int | None = None) -> str:
    from compliance_agent.graph import get_graph

    graph = get_graph()
    rows = load_rows("quick.jsonl", ids, limit)
    w = ResultWriter("E5")
    results = []
    for row in rows:
        try:
            rec = run_row(row, graph)
        except Exception as exc:
            rec = {"id": row["id"], "error": f"{type(exc).__name__}: {exc}", "ok": False, "quick": False, "must": row["must"]}
        w.case(rec)
        results.append(rec)
        f = (rec.get("faithfulness") or {}).get("score")
        print(f"  {rec['id']} route {rec.get('route', '?'):<6} {'ok ' if rec['ok'] else 'NO '} cites {', '.join(rec.get('citations') or []) or '-':<40} "
              f"invented {len(rec.get('invented') or [])} faithful {f if f is not None else '-'}" + (f"  {rec['note']}" if rec.get("note") else "") + (f"  ERROR {rec['error']}" if "error" in rec else ""))

    quick = [r for r in results if r.get("quick")]
    must_total = sum(len(r["must"]) for r in quick)
    found = sum(len(r.get("found") or []) for r in quick)
    invented = sum(len(r.get("invented") or []) for r in quick)
    scores = [r["faithfulness"]["score"] for r in quick if (r.get("faithfulness") or {}).get("score") is not None]
    f_mean = round(sum(scores) / len(scores), 3) if scores else None
    long_ = [r["id"] for r in quick if r.get("sentences", 0) > 3]
    empty = [r["id"] for r in quick if r.get("empty")]
    not_quick = [f"{r['id']} ({r.get('route')})" for r in results if not r.get("quick") and "error" not in r]
    cost = round(sum((r.get("usage") or {}).get("cost", 0) + (r.get("judge_usage") or {}).get("cost", 0) for r in results), 4)
    summary = {"quick_answers": {"count": len(quick), "of": len(results), "not_quick": not_quick},
               "must_cite_recall": {"found": found, "of": must_total, "misses": [f"{r['id']}: {', '.join(r['missing'])}" for r in quick if r.get("missing")]},
               "invented_citations": {"count": invented, "rows": [f"{r['id']}: {', '.join(r['invented'])}" for r in quick if r.get("invented")]},
               "faithfulness": {"mean": f_mean, "over": len(scores), "errors": [f"{r['id']}: {r['faithfulness'].get('error')}" for r in quick if (r.get('faithfulness') or {}).get('error')]},
               "over_three_sentences": long_, "empty": empty, "cost": cost}
    md = "## E5 quick answers\n\n" + md_table(["metric", "result", "target"], [
        ["questions answered on the quick path", ratio(len(quick), len(results)), "reported"],
        ["must-cite recall", ratio(found, must_total), "≥ 0.80"],
        ["invented citations (before the guardrail; E7 tests that the guardrail catches them)", f"{invented} across {len(quick)} answers", "reported"],
        ["faithfulness (RAGAs definition, own implementation), mean", f"{f_mean} over {len(scores)}" if f_mean is not None else "–", "≥ 0.90"],
        ["answers over three sentences", ratio(len(long_), len(quick)), "reported"],
        ["empty answers", ratio(len(empty), len(quick)), "reported"],
        ["model cost of the run (answers and judge)", f"${cost}", "–"],
    ])
    for key, label in (("not_quick", "Not routed quick"), ):
        if summary["quick_answers"][key]:
            md += f"\n{label}: " + ", ".join(summary["quick_answers"][key]) + "\n"
    if summary["must_cite_recall"]["misses"]:
        md += "Must-cite misses: " + "; ".join(summary["must_cite_recall"]["misses"]) + "\n"
    if summary["invented_citations"]["rows"]:
        md += "Invented: " + "; ".join(summary["invented_citations"]["rows"]) + "\n"
    if summary["faithfulness"]["errors"]:
        md += "Faithfulness not computed: " + "; ".join(summary["faithfulness"]["errors"]) + "\n"
    errors = [f"{r['id']}: {r['error']}" for r in results if "error" in r]
    if errors:
        md += "\nErrors: " + "; ".join(errors) + "\n"
    return str(w.finish(summary, md))
