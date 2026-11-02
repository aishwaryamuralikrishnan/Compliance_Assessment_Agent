"""E7 (eval/README.md): the output guardrail receives a well-formed assessment with one fault planted and must take
the action its code promises. The assessment is built from a case's expected fields in assessments.jsonl, so the
planted fault is the only thing wrong with it. No model is called; the corpus is queried for the citations."""
from __future__ import annotations

import copy
from typing import Any

from .common import EvalError, ResultWriter, load_rows, md_table, node_context, ratio


def base_assessment(case: dict[str, Any]) -> dict[str, Any]:
    e = case["expected"]
    findings = [{"severity": k["severity"], "text": k["gist"][0].upper() + k["gist"][1:] + ".", "citations": list(k["provisions"])}
                for k in e["key_findings"]]
    cites = sorted({c for k in e["key_findings"] for c in k["provisions"]})
    return {
        "title": f"Evaluation case {case['id']} ({case['domain']})",
        "verdict": e["verdict"], "risk_level": e["risk_level"],
        "summary": f"{e['verdict']}: the decisive provisions are {', '.join(cites[:3])}.",
        "high_risk_ai": e["high_risk_ai"], "dpia_required": e["dpia_required"],
        "findings": findings, "next_steps": ["Address the findings above in the order given."],
    }


def plant(row: dict[str, Any], a: dict[str, Any]) -> tuple[Any, str]:
    """Returns (structured_response, what was planted) for the row's fault type."""
    from langchain_core.messages import AIMessage

    from compliance_agent.state import Assessment, StatusReply

    fault, p = row["fault"], row["plant"]
    a = copy.deepcopy(a)
    if fault == "unknown_citation":
        a["findings"][0]["citations"].append(p)
        return Assessment.model_validate(a), f"citation {p} added to finding 1"
    if fault == "pii_in_text":
        a["findings"][0]["text"] += " " + p
        return Assessment.model_validate(a), "personal data appended to finding 1"
    if fault == "schema_violation":
        a["findings"][0]["severity"] = p
        return a, f"severity of finding 1 set to {p!r} (as a dict: the schema rejects it)"
    if fault == "status_reply":
        return StatusReply(message=p), "a status reply instead of the assessment"
    raise EvalError(f"{row['id']}: unknown fault type {fault!r}")


def judge(row: dict[str, Any], result: Any, events: list[dict[str, Any]]) -> tuple[bool, str]:
    """Did the guardrail take the expected action?"""
    goto = getattr(result, "goto", None)
    update = getattr(result, "update", None) or {}
    regen = [e for e in events if e.get("node") == "output_guardrail" and e.get("event") == "regenerate"]
    expect = row["expect"]
    if expect == "regenerate":
        if goto != "worker" or not regen:
            return False, f"no regeneration (goto={goto!r}, events={[e.get('event') for e in events]})"
        ev = regen[-1]
        if row["fault"] == "unknown_citation" and row["plant"] not in (ev.get("invalid") or []):
            return False, f"regenerated, but the planted label is not named: {ev}"
        if row["fault"] == "schema_violation" and not ev.get("schema_error"):
            return False, f"regenerated for another reason, not the schema: {ev}"
        if row["fault"] == "status_reply" and "status reply" not in str(ev.get("reason", "")):
            return False, f"regenerated for another reason: {ev}"
        detail = str(ev.get('invalid') or ev.get('schema_error') or ev.get('reason')).splitlines()[0][:120]
        return True, f"regenerate: {detail}"
    if expect.startswith("redact:"):
        want = int(expect.split(":")[1])
        got = (update.get("guardrail") or {}).get("pii_redactions")
        text = ((update.get("assessment") or {}).get("findings") or [{}])[0].get("text", "")
        if got != want:
            return False, f"{got} redactions reported, expected {want} (goto={goto!r})"
        if "@" in text or "1234567" in text:
            return False, f"the personal data is still in the finding: {text!r}"
        return True, f"{got} redactions; finding ends: {text[-80:]!r}"
    raise EvalError(f"{row['id']}: unknown expectation {expect!r}")


def run(ids: list[str] | None = None, limit: int | None = None) -> str:
    from langchain_core.messages import AIMessage, HumanMessage

    import compliance_agent.nodes.guardrail as GR

    rows = load_rows("faults.jsonl", ids, limit)
    cases = {c["id"]: c for c in load_rows("assessments.jsonl")}
    w = ResultWriter("E7")
    results = []
    for row in rows:
        try:
            case = cases[row["base"]]
            sr, what = plant(row, base_assessment(case))
            state = {
                "input": case["text"], "route": "full", "regenerations": 0, "review_requested": False, "assessment": None,
                "answer": None, "sources": [], "guardrail": {}, "structured_response": sr,
                "messages": [HumanMessage(content=case["text"]), AIMessage(content="(draft)")],
            }
            with node_context(GR, thread_id=f"eval-{row['id']}") as events:
                result = GR.output_guardrail(state)
            ok, why = judge(row, result, events)
            rec = {"id": row["id"], "fault": row["fault"], "planted": what, "expect": row["expect"], "ok": ok, "why": why,
                   "events": [{k: v for k, v in e.items() if k != "node"} for e in events if e.get("node") == "output_guardrail"]}
        except Exception as exc:
            rec = {"id": row["id"], "fault": row.get("fault"), "ok": False, "why": f"{type(exc).__name__}: {exc}"}
        w.case(rec)
        results.append(rec)
        print(f"  {rec['id']} {rec.get('fault', ''):<18} {'ok ' if rec['ok'] else 'NO '} {rec['why']}")
    caught = sum(1 for r in results if r["ok"])
    md = "## E7 output guardrail\n\n" + md_table(["fault", "expected", "caught", "detail"],
                                              [[r.get("fault"), r.get("expect", ""), "yes" if r["ok"] else "NO", r["why"]] for r in results])
    md += f"\ncaught {ratio(caught, len(results))} · target: all (a miss is a bug, not a model result)\n"
    return str(w.finish({"caught": caught, "of": len(results), "missed": [r["id"] for r in results if not r["ok"]]}, md))
