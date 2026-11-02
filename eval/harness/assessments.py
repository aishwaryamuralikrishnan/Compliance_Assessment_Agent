"""E6 (eval/README.md): every feature description of assessments.jsonl is run through `run_turn` as a product
manager would send it, and the assessment at the DPO's pause is scored: verdict, risk level, flags, must-cite
recall over the verified citations, the key findings by the judge with the rubric, must_not, faithfulness of the
findings to the passages and memory items the worker was given, and the run's figures. The module also writes
the human scoring sheet and, from a filled sheet, the judge-versus-human line."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .common import ResultWriter, load_rows, md_table, pairs, ratio, satisfied, usage_counter
from .judge import faithfulness, judge_findings

HUMAN_CASES = 5


def _memory_items(text: str) -> list[dict[str, Any]]:
    """What the worker read for this turn (the same recall, against the same store)."""
    from compliance_agent import db, memory

    try:
        mem = memory.recall(db.langgraph_store(), "lena.k", text)
    except Exception:
        return []
    out = []
    for kind in ("org_facts", "lessons"):
        for it in mem.get(kind) or []:
            out.append({"kind": kind, "text": it.get("text")})
    return out


def run_row(case: dict[str, Any], graph) -> dict[str, Any]:
    from compliance_agent.graph import pending_kind, run_turn
    from compliance_agent.state import UserContext

    events: list[dict[str, Any]] = []
    with usage_counter() as usage:
        for e in run_turn(UserContext("lena.k", "product_manager"), case["text"], graph=graph):
            events.append(e)
            if e["kind"] == "final":
                state = e["state"]
    v = state["values"]
    e = case["expected"]
    rec: dict[str, Any] = {"id": case["id"], "domain": case.get("domain"), "thread_id": state.get("thread_id"), "route": v.get("route"),
                           "pending": pending_kind(state), "usage": usage}
    custom = [x for x in events if x["kind"] == "custom"]
    rec["run"] = {"searches": len({x.get("call") for x in custom if x.get("node") == "search_regulation" and x.get("call")}),
                  "rewrites": sum(1 for x in custom if x.get("node") == "search_regulation" and x.get("event") == "rewrite"),
                  "regenerations": int(v.get("regenerations") or 0), "seconds": usage.get("seconds")}
    a = v.get("assessment")
    if not a:
        rec.update({"assessed": False, "ok": False, "note": f"no assessment (route {v.get('route')}, answer: {str(v.get('answer') or '')[:120]!r})"})
        return rec
    rec["assessed"] = True
    rec["assessment"] = {k: a.get(k) for k in ("assessment_id", "title", "verdict", "risk_level", "high_risk_ai", "dpia_required", "summary", "findings", "next_steps", "verified_citations", "unverified_citations")}
    found, missing = satisfied(e["must_cite"], a.get("verified_citations") or [])
    rec["scores"] = {
        "verdict_ok": a.get("verdict") == e["verdict"], "verdict": a.get("verdict"), "expected_verdict": e["verdict"],
        "dangerous_miss": e["verdict"] == "Do not build as described" and a.get("verdict") == "Proceed",
        "risk_ok": a.get("risk_level") == e["risk_level"],
        "high_risk_ai": {"got": bool(a.get("high_risk_ai")), "expected": e["high_risk_ai"]},
        "dpia_required": {"got": bool(a.get("dpia_required")), "expected": e["dpia_required"]},
        "must_cite": {"found": found, "missing": missing},
        "guardrail": {k: (v.get("guardrail") or {}).get(k) for k in ("citations_checked", "invalid", "unreachable", "pii_redactions", "regenerated")},
    }
    with usage_counter() as judge_usage:
        rec["judge"] = judge_findings(case, a)
        findings_text = "\n".join(f"[{f.get('severity')}] {f.get('text')} ({', '.join(f.get('citations') or [])})" for f in a.get("findings") or [])
        rec["faithfulness"] = faithfulness(findings_text, v.get("sources") or [], _memory_items(case["text"]), input_text=case["text"])
    rec["judge_usage"] = judge_usage
    kf = rec["judge"].get("key_findings") or []
    rec["scores"]["key_findings"] = {"matched": sum(1 for k in kf if k["verdict"] == "matched"), "partial": sum(1 for k in kf if k["verdict"] == "partial"),
                                     "missed": sum(1 for k in kf if k["verdict"] == "missed"), "severity_miscalibrated": sum(1 for k in kf if k.get("severity_miscalibrated")),
                                     "of": len(e["key_findings"])}
    rec["scores"]["must_not_violations"] = [m for m in (rec["judge"].get("must_not") or []) if m.get("violated")]
    rec["scores"]["wrong_extras"] = list(rec["judge"].get("wrong_extras") or [])
    s = rec["scores"]
    rec["ok"] = s["verdict_ok"] and s["high_risk_ai"]["got"] == s["high_risk_ai"]["expected"] and s["dpia_required"]["got"] == s["dpia_required"]["expected"]
    return rec


def run(ids: list[str] | None = None, limit: int | None = None) -> str:
    from compliance_agent.graph import get_graph

    graph = get_graph()
    cases = load_rows("assessments.jsonl", ids, limit)
    w = ResultWriter("E6")
    results = []
    for case in cases:
        try:
            rec = run_row(case, graph)
        except Exception as exc:
            rec = {"id": case["id"], "error": f"{type(exc).__name__}: {exc}", "ok": False, "assessed": False}
        w.case(rec)
        results.append(rec)
        s = rec.get("scores") or {}
        kf = s.get("key_findings") or {}
        print(f"  {rec['id']} {'ok ' if rec['ok'] else 'NO '} verdict {s.get('verdict', '-')!s:<26} flags hr {s.get('high_risk_ai', {}).get('got', '-')}/{s.get('high_risk_ai', {}).get('expected', '-')} "
              f"dpia {s.get('dpia_required', {}).get('got', '-')}/{s.get('dpia_required', {}).get('expected', '-')}  key findings {kf.get('matched', '-')}/{kf.get('partial', '-')}/{kf.get('missed', '-')} of {kf.get('of', '-')}  "
              f"faithful {(rec.get('faithfulness') or {}).get('score', '-')}  ${(rec.get('usage') or {}).get('cost', 0):.4f}" + (f"  {rec['note']}" if rec.get("note") else "") + (f"  ERROR {rec['error']}" if "error" in rec else ""))

    done = [r for r in results if r.get("assessed")]
    n = len(done)
    verdict_right = sum(1 for r in done if r["scores"]["verdict_ok"])
    dangerous = [r["id"] for r in done if r["scores"]["dangerous_miss"]]
    risk_right = sum(1 for r in done if r["scores"]["risk_ok"])
    flags = {}
    for flag in ("high_risk_ai", "dpia_required"):
        pos = [r for r in done if r["scores"][flag]["expected"]]
        neg = [r for r in done if not r["scores"][flag]["expected"]]
        flags[flag] = {"missed": sum(1 for r in pos if not r["scores"][flag]["got"]), "positives": len(pos),
                       "false": sum(1 for r in neg if r["scores"][flag]["got"]), "negatives": len(neg)}
    must_total = sum(len(r["scores"]["must_cite"]["found"]) + len(r["scores"]["must_cite"]["missing"]) for r in done)
    must_found = sum(len(r["scores"]["must_cite"]["found"]) for r in done)
    judged = [r for r in done if "key_findings" in r["scores"] and not r["judge"].get("error")]
    kf_of = sum(r["scores"]["key_findings"]["of"] for r in judged)
    kf_matched = sum(r["scores"]["key_findings"]["matched"] for r in judged)
    kf_partial = sum(r["scores"]["key_findings"]["partial"] for r in judged)
    kf_sev = sum(r["scores"]["key_findings"].get("severity_miscalibrated", 0) for r in judged)
    wrong_extras = [f"{r['id']}: {x}" for r in judged for x in r["scores"].get("wrong_extras") or []]
    violations = [f"{r['id']}: {m.get('quote') or m.get('reason')}" for r in judged for m in r["scores"]["must_not_violations"]]
    scores = [r["faithfulness"]["score"] for r in done if (r.get("faithfulness") or {}).get("score") is not None]
    f_mean = round(sum(scores) / len(scores), 3) if scores else None
    pr = pairs(cases, {r["id"]: bool(r.get("ok")) for r in results})
    cost = round(sum((r.get("usage") or {}).get("cost", 0) for r in results), 4)
    judge_cost = round(sum((r.get("judge_usage") or {}).get("cost", 0) for r in results), 4)
    run_totals = {"rewrites": sum(int(r["run"].get("rewrites") or 0) for r in done), "regenerations": sum(int(r["run"].get("regenerations") or 0) for r in done),
                  "seconds_mean": round(sum(float(r["run"].get("seconds") or 0) for r in done) / n, 1) if n else None} if done else {}
    summary = {
        "assessed": {"count": n, "of": len(results), "not_assessed": [f"{r['id']}: {r.get('note') or r.get('error')}" for r in results if not r.get("assessed")]},
        "verdict": {"right": verdict_right, "of": n, "wrong": [f"{r['id']} ({r['scores']['expected_verdict']} → {r['scores']['verdict']})" for r in done if not r["scores"]["verdict_ok"]]},
        "dangerous_misses": dangerous, "risk_level": {"right": risk_right, "of": n}, "flags": flags,
        "must_cite": {"found": must_found, "of": must_total, "misses": [f"{r['id']}: {', '.join(r['scores']['must_cite']['missing'])}" for r in done if r["scores"]["must_cite"]["missing"]]},
        "key_findings": {"matched": kf_matched, "partial": kf_partial, "severity_miscalibrated": kf_sev, "of": kf_of, "judged_cases": len(judged),
                         "judge_errors": [f"{r['id']}: {r['judge']['error']}" for r in done if r.get("judge", {}).get("error")]},
        "wrong_extras": wrong_extras,
        "must_not_violations": violations, "faithfulness": {"mean": f_mean, "over": len(scores)}, **pr,
        "run": run_totals, "cost": cost, "judge_cost": judge_cost,
    }
    md = "## E6 full assessments\n\n" + md_table(["metric", "result", "target"], [
        ["cases that produced an assessment", ratio(n, len(results)), "all"],
        ["verdict accuracy · of which dangerous (expected Do not build, got Proceed)", f"{ratio(verdict_right, n)} · {len(dangerous)}", "≥ 0.80 · 0"],
        ["risk level accuracy", ratio(risk_right, n), "reported"],
        ["high-risk AI flag: missed of positives · false of negatives", f"{flags['high_risk_ai']['missed']} of {flags['high_risk_ai']['positives']} · {flags['high_risk_ai']['false']} of {flags['high_risk_ai']['negatives']}" if flags else "–", "≤ 1 · ≤ 1"],
        ["DPIA flag: missed of positives · false of negatives", f"{flags['dpia_required']['missed']} of {flags['dpia_required']['positives']} · {flags['dpia_required']['false']} of {flags['dpia_required']['negatives']}" if flags else "–", "≤ 1 · ≤ 1"],
        ["must-cite recall (verified citations, article level)", ratio(must_found, must_total), "≥ 0.80"],
        ["key findings matched (judge + rubric, no severity tolerance)", f"{ratio(kf_matched, kf_of)} · partial {kf_partial}", "matched ≥ 0.75"],
        ["of the missed: right point and provision, wrong severity", str(kf_sev), "reported"],
        ["wrong extras (fabrication, contextual blindness, false escalation)", str(len(wrong_extras)), "reported"],
        ["must_not violations", str(len(violations)), "0"],
        ["faithfulness of findings (RAGAs definition, own implementation), mean", f"{f_mean} over {len(scores)}" if f_mean is not None else "–", "≥ 0.85"],
        ["confusable pairs both right (verdict and flags)", ratio(pr["pairs_right"], pr["pairs_total"]), "reported"],
        ["the run: cost (assessments · judge) · seconds per case (mean) · rewrites · regenerations", f"${cost} · ${judge_cost} · {run_totals.get('seconds_mean')} s · {run_totals.get('rewrites')} · {run_totals.get('regenerations')}" if run_totals else f"${cost} · ${judge_cost}", "reported"],
    ])
    for key, label in (("wrong", "Wrong verdicts"),):
        if summary["verdict"][key]:
            md += f"\n{label}: " + "; ".join(summary["verdict"][key]) + "\n"
    if dangerous:
        md += "Dangerous misses: " + ", ".join(dangerous) + "\n"
    if summary["must_cite"]["misses"]:
        md += "Must-cite misses: " + "; ".join(summary["must_cite"]["misses"]) + "\n"
    if violations:
        md += "must_not violations: " + "; ".join(violations) + "\n"
    if wrong_extras:
        md += "Wrong extras: " + "; ".join(wrong_extras) + "\n"
    if pr["pairs_failed"]:
        md += "Failed pairs: " + ", ".join(pr["pairs_failed"]) + "\n"
    if summary["assessed"]["not_assessed"]:
        md += "Not assessed: " + "; ".join(summary["assessed"]["not_assessed"]) + "\n"
    if summary["key_findings"]["judge_errors"]:
        md += "Judge errors: " + "; ".join(summary["key_findings"]["judge_errors"]) + "\n"
    md += "\n### Key findings, per case\n\n"
    for r in judged:
        md += f"**{r['id']}** ({r['scores']['verdict']}):\n"
        for k in r["judge"]["key_findings"]:
            md += f"- KF{k['index']} {k['verdict']}{' (severity miscalibrated)' if k.get('severity_miscalibrated') else ''}: {k['reason']}\n"
        if r["judge"].get("wrong_extras"):
            md += "- wrong extras: " + " | ".join(r["judge"]["wrong_extras"]) + "\n"
        md += "\n"
    folder = w.finish(summary, md)
    write_human_sheet(Path(folder), cases, results)
    return str(folder)


# --------------------------------------------------------------------------------------
# the human scoring sheet and the judge-versus-human line
# --------------------------------------------------------------------------------------

def write_human_sheet(folder: Path, cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> Path:
    """The first HUMAN_CASES assessed cases, without the judge's verdicts: the assistant's findings and the expected
    key findings, and one line per expected finding to fill with matched / partial / missed / unsure."""
    by_id = {c["id"]: c for c in cases}
    picked = [r for r in results if r.get("assessed")][:HUMAN_CASES]
    lines = ["# Human scoring sheet (E6)", "",
             "Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,",
             "WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with",
             "matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.", ""]
    for r in picked:
        c = by_id[r["id"]]
        a = r["assessment"]
        lines += [f"## {r['id']} · {a.get('title')}", "", f"Feature: {c['text']}", "", f"Assistant's verdict: {a.get('verdict')} · risk {a.get('risk_level')} · high-risk AI {a.get('high_risk_ai')} · DPIA {a.get('dpia_required')}", "",
                  "Assistant's findings:"]
        for i, f in enumerate(a.get("findings") or [], 1):
            lines.append(f"{i}. [{f.get('severity')}] {f.get('text')} ({', '.join(f.get('citations') or []) or 'no citation'})")
        lines += ["", "Expected key findings:"]
        for i, k in enumerate(c["expected"]["key_findings"], 1):
            alt = ", ".join(k.get("acceptable_alternatives") or []) or "none"
            lines.append(f"- KF{i}: {k['gist']} · provisions {', '.join(k['provisions'])} (alternatives: {alt}) · severity {k['severity']} · citation level {k.get('citation_level', 'article')}")
        lines.append("")
        for i, _ in enumerate(c["expected"]["key_findings"], 1):
            lines.append(f"- [{r['id']} KF{i}] verdict: ")
        lines.append("")
    path = folder / "human_scoring.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


_LINE = re.compile(r"\[(A-\d+) KF(\d+)\]\s*verdict:\s*(matched|partial|missed|unsure)", re.I)


def agreement(folder: str) -> str:
    """Reads human_scoring.md and cases.jsonl of an E6 run and appends the judge-versus-human line to summary.md."""
    f = Path(folder)
    human: dict[tuple[str, int], str] = {}
    for m in _LINE.finditer((f / "human_scoring.md").read_text(encoding="utf-8")):
        human[(m.group(1), int(m.group(2)))] = m.group(3).lower()
    judge: dict[tuple[str, int], str] = {}
    for line in (f / "cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        for k in (r.get("judge") or {}).get("key_findings") or []:
            judge[(r["id"], k["index"])] = k["verdict"]
    scored = {k: v for k, v in human.items() if v != "unsure"}
    unsure = [f"{k[0]} KF{k[1]}" for k, v in human.items() if v == "unsure"]
    agreed = [k for k, v in scored.items() if judge.get(k) == v]
    disagreed = [f"{k[0]} KF{k[1]}: human {v}, judge {judge.get(k, '?')}" for k, v in scored.items() if judge.get(k) != v]
    generous = sum(1 for k, v in scored.items() if judge.get(k) != v and ["missed", "partial", "matched"].index(judge.get(k, "missed")) > ["missed", "partial", "matched"].index(v))
    line = (f"\n## Judge versus human\n\nThe judge agreed with the human reader on {len(agreed)} of {len(scored)} findings"
            f" ({len(unsure)} marked unsure and left out); target ≥ 17 of 20. Disagreements: {'; '.join(disagreed) or 'none'}."
            + (f" In {generous} of the disagreements the judge was the more generous." if disagreed else "") + "\n")
    with (f / "summary.md").open("a", encoding="utf-8") as fh:
        fh.write(line)
    s = json.loads((f / "summary.json").read_text(encoding="utf-8"))
    s["judge_vs_human"] = {"agreed": len(agreed), "of": len(scored), "unsure": unsure, "disagreed": disagreed}
    (f / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    return line
