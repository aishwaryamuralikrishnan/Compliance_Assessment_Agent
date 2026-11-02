"""The two judge calls (eval/README.md sections 1 and 6), on the `judge` slot through the app's model registry:
the key-finding judgement against the rubric (E6) and RAGAs-style faithfulness, own implementation (E5, E6)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import PROMPTS


def _prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# key findings and must_not
# --------------------------------------------------------------------------------------

class KeyFindingVerdict(BaseModel):
    """One expected key finding, judged against the assistant's findings."""

    index: int = Field(description="The 1-based number of the expected key finding this verdict is about.")
    reason: str = Field(description="One or two sentences: which assistant finding(s) you relied on, by number, and the decisive words.")
    verdict: Literal["matched", "partial", "missed"]
    severity_miscalibrated: bool = Field(default=False, description="True when the point and the provision are right and only the severity is wrong (the verdict is then missed).")
    assistant_findings: list[int] = Field(default_factory=list, description="1-based numbers of the assistant findings relied on; empty when missed.")


class MustNotVerdict(BaseModel):
    index: int = Field(description="The 1-based number of the must_not rule.")
    reason: str
    violated: bool
    quote: str = Field(default="", description="The offending words from the assessment, when violated.")


class FindingsJudgement(BaseModel):
    """The judgement of one assessment against its expected key findings and must_not rules."""

    key_findings: list[KeyFindingVerdict]
    must_not: list[MustNotVerdict]
    wrong_extras: list[str] = Field(default_factory=list, description="Assistant findings that match nothing expected AND are legally wrong (fabrication, contextual blindness, false escalation), one line each with the finding number; merely extra findings are not listed.")


def render_assessment(a: dict[str, Any]) -> str:
    lines = [f"Title: {a.get('title', '')}", f"Verdict: {a.get('verdict')} · risk {a.get('risk_level')} · high-risk AI {a.get('high_risk_ai')} · DPIA required {a.get('dpia_required')}",
             f"Summary: {a.get('summary', '')}", "Findings:"]
    for i, f in enumerate(a.get("findings") or [], 1):
        lines.append(f"  {i}. [{f.get('severity')}] {f.get('text')} (citations: {', '.join(f.get('citations') or []) or 'none'})")
    lines.append("Next steps: " + " | ".join(a.get("next_steps") or []))
    return "\n".join(lines)


def render_expected(case: dict[str, Any]) -> str:
    e = case["expected"]
    lines = ["Expected key findings:"]
    for i, k in enumerate(e["key_findings"], 1):
        alt = ", ".join(k.get("acceptable_alternatives") or []) or "none"
        lines.append(f"  {i}. topic: {k['topic']} · gist: {k['gist']} · provisions: {', '.join(k['provisions'])} · acceptable alternatives: {alt} "
                     f"· severity: {k['severity']} · citation level: {k.get('citation_level', 'article')}")
    lines.append("must_not rules:")
    for i, m in enumerate(e.get("must_not") or [], 1):
        lines.append(f"  {i}. {m}")
    extra = e.get("merely_extra") or []
    if extra:
        lines.append("Points the reviewer regards as merely extra for this feature (correct but not listed; never list them under wrong_extras):")
        for m in extra:
            lines.append(f"  - {m}")
    wrong = e.get("known_wrong") or []
    if wrong:
        lines.append("Points the reviewer regards as WRONG for this feature: if the assessment makes one of them, list it under wrong_extras with the finding number:")
        for m in wrong:
            lines.append(f"  - {m}")
    return "\n".join(lines)


def judge_findings(case: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    """Returns {"key_findings": [...], "must_not": [...], "extras": [...]} or {"error": "..."}; never raises."""
    from compliance_agent import models

    msgs = [("system", _prompt("judge_findings.md")),
            ("human", f"Feature description:\n{case['text']}\n\n{render_expected(case)}\n\nThe assistant's assessment:\n{render_assessment(assessment)}\n\n"
                      f"Judge every expected key finding ({len(case['expected']['key_findings'])}) and every must_not rule ({len(case['expected'].get('must_not') or [])}).")]
    try:
        r: FindingsJudgement = models.invoke_structured("judge", FindingsJudgement, msgs)  # type: ignore[assignment]
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    n = len(case["expected"]["key_findings"])
    by_index = {v.index: v for v in r.key_findings}
    kfs = []
    for i in range(1, n + 1):
        v = by_index.get(i)
        kfs.append({"index": i, "verdict": v.verdict if v else "missed", "reason": v.reason if v else "the judge returned no verdict for this finding",
                    "severity_miscalibrated": bool(v.severity_miscalibrated) if v else False, "assistant_findings": v.assistant_findings if v else []})
    mn = [{"index": v.index, "violated": v.violated, "reason": v.reason, "quote": v.quote} for v in r.must_not]
    return {"key_findings": kfs, "must_not": mn, "wrong_extras": list(r.wrong_extras)}


# --------------------------------------------------------------------------------------
# faithfulness (RAGAs definition, own implementation)
# --------------------------------------------------------------------------------------

class Statement(BaseModel):
    text: str
    kind: Literal["proposition", "citation", "restates_input", "not_factual"]


class Statements(BaseModel):
    """The text split into self-contained statements (step 1 of the faithfulness prompt)."""

    statements: list[Statement]


class StatementVerdict(BaseModel):
    index: int = Field(description="The 1-based number of the statement.")
    reason: str = Field(description="Why the material supports or does not support it, before the verdict.")
    verdict: Literal["supported", "not_supported", "not_factual"]


class Verdicts(BaseModel):
    """One verdict per statement (step 2 of the faithfulness prompt)."""

    items: list[StatementVerdict]


def faithfulness(text: str, passages: list[dict[str, Any]], memory_items: list[dict[str, Any]] | None = None, *, input_text: str = "") -> dict[str, Any]:
    """Returns {"score": float | None, "supported", "not_supported", "excluded", "statements": [...], "error"?}."""
    from compliance_agent import models

    if not text or not text.strip():
        return {"score": None, "supported": 0, "not_supported": 0, "excluded": 0, "statements": [], "note": "no text to judge"}
    system = _prompt("judge_faithfulness.md")
    try:
        s: Statements = models.invoke_structured("judge", Statements, [  # type: ignore[assignment]
            ("system", system),
            ("human", "Do step 1 only.\n\n" + (f"The feature description or question the assistant answered:\n{input_text}\n\n" if input_text else "") + f"Text to split:\n{text}")])
    except Exception as exc:
        return {"score": None, "error": f"step 1: {type(exc).__name__}: {str(exc)[:200]}"}
    statements = [{"index": i, "text": st.text, "kind": st.kind} for i, st in enumerate(s.statements, 1)]
    if not statements:
        return {"score": None, "supported": 0, "not_supported": 0, "excluded": 0, "statements": [], "note": "the judge extracted no statements"}
    checkable = [st for st in statements if st["kind"] in ("proposition", "citation")]
    if not checkable:
        return {"score": None, "supported": 0, "not_supported": 0, "excluded": len(statements), "statements": statements, "note": "no checkable statements"}
    material = "\n\n".join(f"[{p.get('citation')}] {p.get('heading', '')}\n{(p.get('text') or '')[:2500]}" for p in passages)
    if memory_items:
        material += "\n\nMemory items the assistant read:\n" + "\n".join(f"- ({m.get('ns') or m.get('kind') or 'memory'}) {m.get('text')}" for m in memory_items)
    # step 2 in batches of ten statements: a long list of verdicts with reasons would otherwise hit the output limit
    verdicts: dict[int, StatementVerdict] = {}
    errors: list[str] = []
    for start in range(0, len(checkable), 10):
        batch = checkable[start:start + 10]
        listed = "\n".join(f"{st['index']}. ({st['kind']}) {st['text']}" for st in batch)
        try:
            v: Verdicts = models.invoke_structured("judge", Verdicts, [  # type: ignore[assignment]
                ("system", system),
                ("human", f"Do step 2 only, for the {len(batch)} statements listed (keep their numbers).\n\nMaterial:\n{material}\n\nStatements to check:\n{listed}")])
            verdicts.update({it.index: it for it in v.items})
        except Exception as exc:
            errors.append(f"statements {batch[0]['index']}-{batch[-1]['index']}: {type(exc).__name__}: {str(exc)[:160]}")
    if errors and not verdicts:
        return {"score": None, "error": "step 2: " + "; ".join(errors), "statements": statements}
    sup = nsup = 0
    for st in checkable:
        it = verdicts.get(st["index"])
        st["verdict"] = it.verdict if it else "not_supported"
        st["reason"] = it.reason if it else "no verdict returned for this statement"
        if st["verdict"] == "supported":
            sup += 1
        elif st["verdict"] == "not_supported":
            nsup += 1
    excluded = len(statements) - sup - nsup
    score = round(sup / (sup + nsup), 3) if (sup + nsup) else None
    out = {"score": score, "supported": sup, "not_supported": nsup, "excluded": excluded, "statements": statements}
    if errors:
        out["partial_error"] = "; ".join(errors)          # some batches failed: the score covers the others and says so
    return out
