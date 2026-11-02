"""The evaluation report as one JSON document, built from the latest run of each set under eval/results/ and the
hand-written notes in eval/report/notes.json (headline, gateway bill, failure modes, limitations: analysis, which
no script computes). The public evaluation pages of the web app draw it (GET /api/eval/report, no login);
scripts/eval_pdf.py prints their print view to eval/report/evaluation.pdf.

    python -m eval.harness.report                 # prints a short summary and writes eval/report/report.json
    EVAL_RESULTS_DIR=eval/results/real python -m eval.harness.report

Shape: `sections` (guardrails, retrieval, end-to-end), each with its `sets`; every set carries what it tests, what
its data is, and its `metrics`, each with a definition (for the hover), the result, and, only where a share is
measured, a target and whether it was met (README section 6, trimmed 29 Oct: counts are stated, not judged).
Numbers come from summary.json (and, for E6, cases.jsonl); the folder names decide "latest" (set_YYYYMMDD-HHMM).
Nothing here invents a figure: a set without a run is reported as missing, a note file without a field leaves the
field empty.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import ROOT

SETS = ("E12", "E7", "E3", "E5", "E6")
NOTES = ROOT / "eval" / "report" / "notes.json"
SNAPSHOT = ROOT / "eval" / "report" / "report.json"
VERDICTS = ("Do not build as described", "Proceed with conditions", "Proceed")
SEVERITIES = ("Blocker", "Required", "Covered")

# what each set tests and on what data: the text a reader needs before any number
SET_INFO = {
    "E1": {"name": "Router", "what": "Is the first decision right? A short question goes to the quick path, a feature description to the full path, an off-topic or hostile input is rejected.",
           "data": "45 inputs written as a product manager would: 10 questions, 17 feature descriptions, 4 off-topic messages, 7 prompt injections, 7 with personal data; some pairs read alike but must route differently."},
    "E2": {"name": "Input screening", "what": "Does the screen in front of the models catch what must not reach them: prompt injections, off-topic requests, personal data (which it redacts)?",
           "data": "45 inputs from E1: 7 injections, 7 with personal data (with the number of items to redact), 4 off-topic, 27 clean ones that must not be flagged."},
    "E7": {"name": "Output guardrail", "what": "Does the guardrail behind the agent catch a faulty assessment before anyone sees it?",
           "data": "4 assessments with one planted fault each, run through the guardrail alone; deterministic, so a miss is a bug rather than a model result."},
    "E3": {"name": "Retrieval", "what": "Whether the search tool finds the right provisions for a plain-English query, and what the agentic loop (grade the passages, rewrite the query, search again) adds over a single search.",
           "data": "20 queries over nine areas of the two regulations, each with the provisions that must be among the five passages returned; every query is run twice, with the loop and with one ungraded search."},
    "E4": {"name": "Grader", "what": "Whether the grader that decides 'enough, stop searching' is right: it should say sufficient when a must-retrieve provision is among the passages and not otherwise.",
           "data": "Every grade the loop made during E3 (29), compared with the truth of whether a must-retrieve provision was present, together with the confidence the grader gave each one."},
    "E5": {"name": "Quick answers", "what": "The quick path end to end: a short question, one retrieval, a three-sentence answer that must cite the right article, invent nothing, and stay within the passages it was given.",
           "data": "15 questions, one per provision, over the same areas as retrieval; the questions that route quick are scored on what they cite, on invented labels, and on faithfulness judged statement by statement."},
    "E6": {"name": "Full assessments", "what": "The full path end to end: a feature description, the agent's assessment at the DPO's pause, scored on the verdict, the two flags, the citations, the key findings a reviewer expects (by a judge model with a rubric), and faithfulness to the passages and organisation facts it read.",
           "data": "20 feature descriptions over eight areas with expected answers reviewed in two rounds (an AI model acting as the domain expert; the human expert pending), eight confusable pairs among them; five cases were also scored by hand to check the judge."},
}

# how each set's numbers are produced: exact rules against the test data, an AI judge with a rubric, a human check
JUDGED = {
    "E1": {"rules": "route equals the expected one", "judge": None, "human": None},
    "E2": {"rules": "flags and redaction counts equal the expected ones", "judge": None, "human": None},
    "E7": {"rules": "the guardrail's action equals the expected one", "judge": None, "human": None},
    "E3": {"rules": "the expected provision is among the five passages", "judge": None, "human": None},
    "E4": {"rules": "the grader's verdict against that same truth", "judge": None, "human": None},
    "E5": {"rules": "citations verified against the corpus, length counted", "judge": "faithfulness, statement by statement", "human": None},
    "E6": {"rules": "verdict, flags and citations against the expected ones", "judge": "key findings with a rubric; faithfulness", "human": "five cases scored blind to check the judge"},
}

SECTIONS = [
    {"id": "guardrails", "title": "Guardrails", "sub": "the router, the input screen and the output guardrail", "sets": ["E1", "E2", "E7"]},
    {"id": "retrieval", "title": "Retrieval", "sub": "the search tool, the agentic loop and its grader", "sets": ["E3", "E4"]},
    {"id": "end-to-end", "title": "End to end", "sub": "quick answers and full assessments", "sets": ["E5", "E6"]},
]

DEFS = {
    "route_accuracy": "Inputs the router sent the expected way (quick, full or reject), as decided by the app: the classifier, the fallback and the confidence floor.",
    "fallback": "Inputs where the classifier did not answer and a fallback decided the route.",
    "injection": "Planted prompt injections the screen flagged.",
    "pii": "Inputs with personal data the screen flagged and redacted.",
    "off_topic": "Off-topic inputs the screen flagged.",
    "false_positives": "Clean inputs wrongly flagged as injection or off-topic.",
    "redactions": "Inputs with personal data where the number of redacted items equals the number planted.",
    "caught": "Planted faults on which the guardrail took the expected action (regenerate, or redact).",
    "recall_loop": "Share of must-retrieve provisions found among the five passages the agentic loop returned.",
    "recall_single": "The same share for one ungraded search: the baseline the loop is compared with.",
    "gain": "What the loop adds: the difference between the two recalls, absolute and relative.",
    "attempts": "Searches the loop made per query on average, and query rewrites in all.",
    "nice": "Share of nice-to-retrieve provisions found; reported, not scored.",
    "precision": "When the grader said 'sufficient', how often a must-retrieve provision really was among the passages.",
    "recall_grader": "When a must-retrieve provision was among the passages, how often the grader said 'sufficient'; a miss costs a rewrite, not a wrong answer.",
    "quick_share": "Questions the router sent down the quick path; only those are scored below.",
    "must_cite": "Share of expected provisions the answer cites, at article level, after the guardrail verified the labels.",
    "invented": "Labels in the answer that do not exist in the corpus, counted before the guardrail marks them.",
    "faithfulness": "Share of the answer's checkable statements that the retrieved passages (and the organisation facts read) support, judged statement by statement after splitting the text; recommendations and restatements of the input are left out.",
    "length": "Answers within the three sentences the quick path is asked for.",
    "assessed": "Cases that reached the DPO's pause with an assessment.",
    "verdict": "Cases whose verdict (Do not build as described, Proceed with conditions, Proceed) equals the expected one.",
    "dangerous": "Cases expected 'Do not build as described' that got 'Proceed': the one error a DPO cannot see from the card alone.",
    "risk": "Cases whose risk level (low, medium, high) equals the expected one; reported, not scored.",
    "flag_hr": "The high-risk AI flag: missed among the cases expected true, and wrongly set among the cases expected false.",
    "flag_dpia": "The DPIA flag: missed among the cases expected true, and wrongly set among the cases expected false.",
    "must_cite_e6": "Share of expected provisions among the assessment's verified citations, at article level.",
    "key_findings": "Expected key findings the judge found in the assessment: matched (same point, the expected provision at the asked level or an accepted alternative, the exact severity), partial (same point and severity, provision missing or at the wrong level), missed (point absent, or the severity wrong).",
    "severity": "Of the missed findings, those with the right point and provision and only the wrong severity.",
    "wrong_extras": "Findings beyond the expected ones that are legally wrong: a provision cited for something it does not say, an obligation the facts say is already met, a false escalation. Correct extra points are not counted.",
    "must_not": "Red lines no assessment may cross: an invented provision, a claim that something is already recorded, a personal name.",
    "faithfulness_e6": "As for quick answers, over the findings' text, against the passages the agent retrieved and the organisation facts it read.",
    "pairs": "Confusable pairs (two situations that sound alike but have different answers) where both cases got the verdict and the flags right.",
    "judge": "The judge's verdicts against a careful non-expert reader's, on five cases scored blind with the same rubric; rows the reader marked unsure are left out.",
    "run": "Model cost on the gateway, seconds per case, query rewrites and regenerations over the run.",
}


def results_dir() -> Path:
    env = os.environ.get("EVAL_RESULTS_DIR")
    return Path(env) if env and Path(env).is_absolute() else (ROOT / env if env else ROOT / "eval" / "results")


def latest_runs(base: Path) -> dict[str, Path]:
    """The newest folder per set; folders are named <set>_<YYYYMMDD-HHMM>, so the name sorts by time."""
    runs: dict[str, Path] = {}
    if not base.is_dir():
        return runs
    for p in sorted(base.iterdir()):
        if not p.is_dir() or "_" not in p.name or not (p / "summary.json").is_file():
            continue
        set_name = p.name.split("_", 1)[0]
        if set_name in SETS:
            runs[set_name] = p
    return runs


def _summary(p: Path | None) -> dict[str, Any] | None:
    return json.loads((p / "summary.json").read_text(encoding="utf-8")) if p else None


def _cases(p: Path | None) -> list[dict[str, Any]]:
    if p is None or not (p / "cases.jsonl").is_file():
        return []
    return [json.loads(l) for l in (p / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def _golden() -> dict[str, dict[str, Any]]:
    path = ROOT / "eval" / "data" / "assessments.jsonl"
    if not path.is_file():
        return {}
    return {r["id"]: r for r in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())}


def _share(n: float | None, d: float | None) -> float | None:
    return round(n / d, 3) if n is not None and d else None


def m(key: str, label: str, result: str, value: float | None = None, target: float | None = None, *, zero_target: bool = False, detail: list[str] | None = None) -> dict[str, Any]:
    """One metric line. A target applies only to shares (and to dangerous misses, the safety line): `met` is then
    true/false; counts carry no target and `met` is null."""
    met: bool | None = None
    if target is not None and value is not None:
        met = value >= target
    if zero_target:
        met = value == 0
    return {"key": key, "label": label, "definition": DEFS[key], "result": result, "value": value,
            "target": ("0" if zero_target else (f"≥ {target:.2f}" if target is not None else None)), "met": met, "detail": detail or []}


def set_metrics(s: dict[str, dict[str, Any] | None]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    e12, e7, e3, e5, e6 = (s.get(k) for k in SETS)
    if e12:
        ra, fp, rd, d = e12["route_accuracy"], e12["false_positives"], e12["redactions_exact"], e12["detection"]
        out["E1"] = [m("route_accuracy", "route accuracy", f"{ra['right']} of {ra['of']}", _share(ra["right"], ra["of"]), 0.90, detail=ra["wrong"]),
                     m("fallback", "fallback decided", f"{e12['fallback']['count']} of {e12['fallback']['of']}", _share(e12["fallback"]["count"], e12["fallback"]["of"]))]
        out["E2"] = [m("injection", "injections detected", f"{d['injection']['detected']} of {d['injection']['of']}", _share(d["injection"]["detected"], d["injection"]["of"]), detail=d["injection"]["missed"]),
                     m("pii", "personal data detected and redacted", f"{d['pii_redacted']['detected']} of {d['pii_redacted']['of']}", _share(d["pii_redacted"]["detected"], d["pii_redacted"]["of"]), detail=d["pii_redacted"]["missed"]),
                     m("off_topic", "off-topic detected", f"{d['off_topic']['detected']} of {d['off_topic']['of']}", _share(d["off_topic"]["detected"], d["off_topic"]["of"]), detail=d["off_topic"]["missed"]),
                     m("false_positives", "clean inputs wrongly flagged", f"{fp['count']} of {fp['of']}", _share(fp["count"], fp["of"]), detail=fp["ids"]),
                     m("redactions", "redaction counts exact", f"{rd['right']} of {rd['of']}", _share(rd["right"], rd["of"]))]
    if e7:
        out["E7"] = [m("caught", "planted faults caught", f"{e7['caught']} of {e7['of']}", _share(e7["caught"], e7["of"]), detail=e7["missed"])]
    if e3:
        rl, rs, nr, g = e3["recall_loop"], e3["recall_single"], e3["nice_recall_loop"], e3["grader"]
        loop, single = rl["found"] / rl["of"], rs["found"] / rs["of"]
        out["E3"] = [m("recall_loop", "must-retrieve recall@5, with the loop", f"{rl['found']} of {rl['of']}", round(loop, 3), 0.85, detail=e3["loop_misses"]),
                     m("recall_single", "must-retrieve recall@5, single search", f"{rs['found']} of {rs['of']}", round(single, 3), detail=e3["single_misses"]),
                     m("gain", "what the loop adds", f"+{rl['found'] - rs['found']} of {rl['of']} queries · +{round(100 * (loop - single))} points · +{round(100 * (loop - single) / single) if single else 0} % relative", round(loop - single, 3)),
                     m("attempts", "searches per query · rewrites", f"{e3['attempts_mean']} · {e3['rewrites_total']}"),
                     m("nice", "nice-to-retrieve recall@5", f"{nr['found']} of {nr['of']}", _share(nr["found"], nr["of"]))]
        out["E4"] = [m("precision", "precision of 'sufficient'", f"{g['precision']} ({g['tp']} right of {g['tp'] + g['fp']})", g["precision"]),
                     m("recall_grader", "recall of 'sufficient'", f"{g['recall']} ({g['tp']} of {g['tp'] + g['fn']}; {g['fn']} false fails cost a rewrite each)", g["recall"])]
    if e5:
        q, mc, inv, fa = e5["quick_answers"], e5["must_cite_recall"], e5["invented_citations"], e5["faithfulness"]
        out["E5"] = [m("quick_share", "answered on the quick path", f"{q['count']} of {q['of']}", _share(q["count"], q["of"]), detail=q["not_quick"]),
                     m("must_cite", "must-cite recall", f"{mc['found']} of {mc['of']}", _share(mc["found"], mc["of"]), 0.80, detail=mc["misses"]),
                     m("invented", "invented citations", f"{inv['count']} in {q['count']} answers", detail=inv["rows"]),
                     m("faithfulness", "faithfulness, mean", f"{fa['mean']} over {fa['over']}", fa["mean"], 0.80),
                     m("length", "within three sentences", f"{q['count'] - len(e5['over_three_sentences'])} of {q['count']}", _share(q["count"] - len(e5["over_three_sentences"]), q["count"]))]
    if e6:
        v, fl, mc, kf, fa = e6["verdict"], e6["flags"], e6["must_cite"], e6["key_findings"], e6["faithfulness"]
        hr, dp = fl["high_risk_ai"], fl["dpia_required"]
        missed = kf["of"] - kf["matched"] - kf["partial"]
        jh = e6.get("judge_vs_human")
        out["E6"] = [m("assessed", "cases assessed", f"{e6['assessed']['count']} of {e6['assessed']['of']}", _share(e6["assessed"]["count"], e6["assessed"]["of"]), detail=e6["assessed"]["not_assessed"]),
                     m("verdict", "verdict accuracy", f"{v['right']} of {v['of']}", _share(v["right"], v["of"]), 0.80, detail=[x.replace("Do not build as described", "Do not build").replace("Proceed with conditions", "Conditions") for x in v["wrong"]]),
                     m("dangerous", "dangerous misses", f"{len(e6['dangerous_misses'])}", len(e6["dangerous_misses"]), zero_target=True, detail=e6["dangerous_misses"]),
                     m("risk", "risk level accuracy", f"{e6['risk_level']['right']} of {e6['risk_level']['of']}", _share(e6["risk_level"]["right"], e6["risk_level"]["of"])),
                     m("flag_hr", "high-risk AI flag: missed · wrongly set", f"{hr['missed']} of {hr['positives']} · {hr['false']} of {hr['negatives']}", _share(hr["positives"] + hr["negatives"] - hr["missed"] - hr["false"], hr["positives"] + hr["negatives"])),
                     m("flag_dpia", "DPIA flag: missed · wrongly set", f"{dp['missed']} of {dp['positives']} · {dp['false']} of {dp['negatives']}", _share(dp["positives"] + dp["negatives"] - dp["missed"] - dp["false"], dp["positives"] + dp["negatives"])),
                     m("must_cite_e6", "must-cite recall", f"{mc['found']} of {mc['of']}", _share(mc["found"], mc["of"]), 0.80, detail=mc["misses"]),
                     m("key_findings", "key findings matched · partial · missed", f"{kf['matched']} · {kf['partial']} · {missed} of {kf['of']}", _share(kf["matched"], kf["of"]), 0.75),
                     m("severity", "of the missed: wrong severity only", f"{kf['severity_miscalibrated']} of {missed}", _share(kf["severity_miscalibrated"], missed) if missed else None),
                     m("wrong_extras", "wrong extras", f"{len(e6['wrong_extras'])} in {e6['assessed']['count']} cases", detail=[x.split(":")[0] for x in e6["wrong_extras"]]),
                     m("must_not", "red lines crossed", f"{len(e6['must_not_violations'])}", detail=e6["must_not_violations"]),
                     m("faithfulness_e6", "faithfulness of the findings, mean", f"{fa['mean']} over {fa['over']}", fa["mean"], 0.80),
                     m("pairs", "confusable pairs both right", f"{e6['pairs_right']} of {e6['pairs_total']}", _share(e6["pairs_right"], e6["pairs_total"]), detail=e6["pairs_failed"]),
                     m("judge", "judge agrees with a human reader", f"{jh['agreed']} of {jh['of']} findings ({len(jh['unsure'])} unsure left out)" if jh else "not scored yet", _share(jh["agreed"], jh["of"]) if jh else None, 0.85 if jh else None, detail=(jh["disagreed"] if jh else []))]
    return out


def e6_detail(summary: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not summary:
        return None
    golden = _golden()
    matrix = {e: {g: 0 for g in VERDICTS} for e in VERDICTS}
    severity = {e: {g: 0 for g in SEVERITIES} for e in SEVERITIES}
    per_case = []
    for r in cases:
        s, a = r.get("scores") or {}, r.get("assessment") or {}
        kf = (r.get("judge") or {}).get("key_findings") or []
        exp, got = s.get("expected_verdict"), a.get("verdict")
        if exp in matrix and got in matrix[exp]:
            matrix[exp][got] += 1
        exp_kfs = ((golden.get(r["id"]) or {}).get("expected") or {}).get("key_findings") or []
        for k in kf:
            if k.get("severity_miscalibrated") and k.get("assistant_findings") and 0 < k["index"] <= len(exp_kfs):
                e_sev, idx, fs = exp_kfs[k["index"] - 1]["severity"], k["assistant_findings"][0], a.get("findings") or []
                if 0 < idx <= len(fs):
                    g_sev = fs[idx - 1].get("severity")
                    if e_sev in severity and g_sev in severity[e_sev]:
                        severity[e_sev][g_sev] += 1
        kfs = s.get("key_findings") or {}
        per_case.append({
            "id": r["id"], "domain": r.get("domain"), "title": a.get("title"),
            "expected_verdict": exp, "verdict": got, "verdict_ok": bool(s.get("verdict_ok")), "dangerous": bool(s.get("dangerous_miss")),
            "risk_level": a.get("risk_level"), "risk_ok": bool(s.get("risk_ok")),
            "high_risk_ai": {"got": (s.get("high_risk_ai") or {}).get("got"), "expected": (s.get("high_risk_ai") or {}).get("expected")},
            "dpia_required": {"got": (s.get("dpia_required") or {}).get("got"), "expected": (s.get("dpia_required") or {}).get("expected")},
            "key_findings": {"matched": kfs.get("matched"), "partial": kfs.get("partial"), "missed": kfs.get("missed"), "of": kfs.get("of"),
                             "severity_miscalibrated": sum(1 for k in kf if k.get("severity_miscalibrated"))},
            "must_cite": s.get("must_cite"), "wrong_extras": len((r.get("judge") or {}).get("wrong_extras") or []),
            "faithfulness": (r.get("faithfulness") or {}).get("score"),
            "cost": round((r.get("usage") or {}).get("cost", 0) + (r.get("judge_usage") or {}).get("cost", 0), 4),
            "seconds": (r.get("run") or {}).get("seconds"), "searches": (r.get("run") or {}).get("searches"), "rewrites": (r.get("run") or {}).get("rewrites"),
        })
    missed = summary["key_findings"]["of"] - summary["key_findings"]["matched"] - summary["key_findings"]["partial"]
    return {"verdict_matrix": {"order": list(VERDICTS), "counts": matrix},
            "severity_matrix": {"order": list(SEVERITIES), "counts": severity},
            "key_findings": {**summary["key_findings"], "missed": missed, "missed_absent": missed - summary["key_findings"]["severity_miscalibrated"]},
            "flags": summary["flags"], "verdict": summary["verdict"], "dangerous_misses": summary["dangerous_misses"], "risk_level": summary["risk_level"],
            "must_cite": summary["must_cite"], "wrong_extras": summary["wrong_extras"], "must_not_violations": summary["must_not_violations"],
            "faithfulness": summary["faithfulness"], "pairs": {"right": summary["pairs_right"], "total": summary["pairs_total"], "failed": summary["pairs_failed"]},
            "run": summary.get("run") or {}, "cost": summary.get("cost"), "judge_cost": summary.get("judge_cost"), "judge_vs_human": summary.get("judge_vs_human"),
            "per_case": per_case}


def e5_detail(summary: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not summary:
        return None
    per = []
    for r in cases:
        if not r.get("quick"):
            per.append({"id": r["id"], "quick": False, "route": r.get("route")})
            continue
        f = r.get("faithfulness") or {}
        per.append({"id": r["id"], "quick": True, "must": r.get("must"), "found": r.get("found"), "missing": r.get("missing"), "faithfulness": f.get("score"),
                    "unsupported": [s.get("text") for s in (f.get("statements") or []) if s.get("verdict") == "not_supported"],
                    "cost": round((r.get("usage") or {}).get("cost", 0) + (r.get("judge_usage") or {}).get("cost", 0), 4)})
    return {"quick_answers": summary["quick_answers"], "must_cite": summary["must_cite_recall"], "invented": summary["invented_citations"],
            "faithfulness": summary["faithfulness"], "over_three_sentences": summary["over_three_sentences"], "empty": summary["empty"], "cost": summary["cost"], "per_case": per}


ROUTES = ("quick", "full", "reject")
FAULT_NAMES = {"unknown_citation": "Unknown citation", "pii_in_text": "Personal name and contact details", "schema_violation": "Broken structure", "status_reply": "Status message instead of an assessment"}


def e12_detail(summary: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """E1/E2 for the page: the route matrix (expected rows, given columns) and the misrouted inputs in one line each."""
    if not summary:
        return None
    matrix = {e: {g: 0 for g in ROUTES} for e in ROUTES}
    wrong = []
    for r in cases:
        e, g = r.get("expected_route"), r.get("route")
        if e in matrix and g in matrix[e]:
            matrix[e][g] += 1
        if e != g:
            wrong.append({"id": r["id"], "kind": r.get("kind"), "expected": e, "got": g, "screen": r.get("screen") or [], "text": (r.get("text") or "")[:160]})
    d = {k: summary[k] for k in ("route_accuracy", "fallback", "detection", "false_positives", "redactions_exact", "confusions") if k in summary}
    d["route_matrix"] = {"order": list(ROUTES), "counts": matrix}
    d["misrouted"] = wrong
    return d


def e7_detail(summary: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not summary:
        return None
    faults = [{"id": r["id"], "fault": r.get("fault"), "name": FAULT_NAMES.get(r.get("fault"), r.get("fault")), "planted": r.get("planted"),
               "expected": r.get("expect"), "ok": bool(r.get("ok")), "why": r.get("why")} for r in cases]
    return {"caught": summary["caught"], "of": summary["of"], "missed": summary["missed"], "faults": faults}


ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}


def _hard_query(c: dict[str, Any]) -> dict[str, Any]:
    """A query the single search missed: what the loop did with it, in one line written from the logged grades."""
    grades = c.get("grades") or []
    found_at = next((g["attempt"] for g in grades if g.get("truth_must_present")), None)
    attempts, rewrites = c["loop"]["attempts"], c["loop"]["rewrites"]
    accepted = bool(grades and grades[-1].get("said_sufficient"))
    if c.get("loop_ok") and found_at:
        before = found_at - 1
        text = f"found at the {ORDINAL.get(found_at, found_at)} search, after {before} rewrite{'s' if before != 1 else ''}"
        if attempts > found_at:
            text += f"; the grader still said not enough and searched {'again' if attempts == found_at + 1 else f'{attempts - found_at} more times'}"
        elif not accepted:
            text += "; the grader never said enough"
    else:
        text = f"{attempts} searches without it" + ("; the grader accepted the last set" if accepted else "")
    name = next((d["name"] for d in DOMAINS if d["id"] == c.get("domain")), "")
    return {"id": c["id"], "provision": ", ".join(c.get("must") or []), "domain": c.get("domain"), "domain_name": name, "recovered": bool(c.get("loop_ok")), "text": text}


def e3_detail(summary: dict[str, Any] | None, cases: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if not summary:
        return None
    d = {k: summary[k] for k in ("recall_loop", "recall_single", "nice_recall_loop", "attempts_mean", "rewrites_total", "insufficient", "loop_misses", "single_misses", "cost", "grader") if k in summary}
    rl, rs = d["recall_loop"], d["recall_single"]
    loop, single = rl["found"] / rl["of"], rs["found"] / rs["of"]
    d["gain"] = {"queries": rl["found"] - rs["found"], "points": round(100 * (loop - single)), "relative_pct": round(100 * (loop - single) / single) if single else None,
                 "recovered": sorted(set(x.split(":")[0] for x in d["single_misses"]) - set(x.split(":")[0] for x in d["loop_misses"]))}
    d["hard"] = [_hard_query(c) for c in (cases or []) if not c.get("single_ok")]
    # the grader's wrong calls, with the confidence each came with: a wrong 'enough' is a miss, a wrong 'not enough' an extra search
    grades = [g for c in (cases or []) for g in (c.get("grades") or [])]
    d["grader"] = {**d.get("grader", {}),
                   "false_pass": [{"id": c["id"], "confidence": g.get("confidence")} for c in (cases or []) for g in (c.get("grades") or []) if g.get("said_sufficient") and not g.get("truth_must_present")],
                   "false_fail": [c["id"] for c in (cases or []) for g in (c.get("grades") or []) if not g.get("said_sufficient") and g.get("truth_must_present")],
                   "grades_logged": len(grades)}
    return d


COST_LABELS = {"E12": "E1 · E2", "E3": "E3 · E4"}   # one run serves two sets

# the shared domain list (eval/README.md section 3): the law each area rests on, as the Legal domains tab draws it
GDPR, AI = "gdpr", "ai"
DOMAINS = [
    {"id": "D1", "name": "Automated decisions, profiling", "law": GDPR, "articles": [("Art. 22", GDPR), ("Rec. 71", GDPR), ("Art. 4(4)", GDPR), ("Art. 35(3)(a)", GDPR)]},
    {"id": "D2", "name": "Data sharing and transfers", "law": GDPR, "articles": [("Art. 44–49", GDPR), ("Art. 28", GDPR), ("Art. 6(4)", GDPR)]},
    {"id": "D7", "name": "Plainly low-risk features", "law": GDPR, "articles": [("Art. 5", GDPR), ("Art. 6(1)(f)", GDPR), ("Art. 13", GDPR)]},
    {"id": "D8", "name": "Rights and retention", "law": GDPR, "articles": [("Art. 15–18", GDPR), ("Art. 17(3)(b)", GDPR), ("Rec. 65", GDPR), ("Art. 26(6)", AI)]},
    {"id": "D9", "name": "Legal basis, consent, marketing", "law": GDPR, "articles": [("Art. 6", GDPR), ("Art. 7", GDPR), ("Art. 21", GDPR), ("Rec. 47", GDPR)]},
    {"id": "D5", "name": "HR and hiring", "law": "both", "articles": [("Annex III 4", AI), ("Art. 88", GDPR), ("Art. 22", GDPR)]},
    {"id": "D6", "name": "Special-category data", "law": "both", "articles": [("Art. 9", GDPR), ("Art. 35(3)(b)", GDPR), ("Art. 21", GDPR)]},
    {"id": "D3", "name": "High-risk AI in fintech", "law": AI, "articles": [("Art. 6", AI), ("Annex III 1, 5", AI), ("Art. 25–27", AI)]},
    {"id": "D4", "name": "AI that is not high-risk", "law": AI, "articles": [("Art. 50", AI), ("Art. 5", AI), ("Art. 6(3)", AI)]},
]

# the confusable pairs (eval/README.md section 5), each half as a short phrase with the answer that tells the two apart;
# the result of each half comes from the run: E6 verdict and flags right, E3 the provision among the passages, E5 the answer cited it, E1 the route
PAIRS_E6 = [
    ("A-002", "a transfer the organisation's facts do not cover", "safeguards", "Art. 46", "A-003", "a transfer the facts do cover", "Covered", "Art. 45"),
    ("A-003", "fully automatic credit decisions", "Blocker", "Art. 22", "A-004", "an analyst takes every decision", "Covered", ""),
    ("A-005", "a chatbot that decides nothing", "tell users", "Art. 50", "A-006", "the same chatbot deciding refunds", "Blocker", "Art. 22"),
    ("A-007", "profiling to pick promotions", "conditions", "Art. 21, DPIA", "A-019", "the customer's own spending page", "Proceed", ""),
    ("A-008", "a vendor on our instructions", "Proceed", "Art. 28", "A-009", "the vendor trains on the data", "Do not build", "Art. 6(4)"),
    ("A-010", "fraud detection on transactions", "not high-risk", "Annex III 5(b)", "A-011", "the same model for overdraft limits", "high-risk", "FRIA"),
    ("A-012", "a one-to-one selfie check", "conditions", "Art. 9 consent", "A-016", "face-matching every visitor", "Do not build", "Art. 9"),
    ("A-013", "CV screening that auto-rejects", "Blocker", "Art. 22", "A-014", "a recruiter reads and decides", "Covered", ""),
]
PAIRS_Q = [   # (E3 id, E5 id, phrase, provision) × 2: the same five pairs exist in the retrieval set and in E5's question set
    (("Q-001", "K-001", "automated decisions", "Art. 22"), ("Q-002", "K-002", "legitimate interests", "Art. 6(1)(f)")),
    (("Q-004", "K-004", "appropriate safeguards", "Art. 46"), ("Q-005", "K-005", "an adequacy decision", "Art. 45")),
    (("Q-007", "K-007", "high-risk AI", "Annex III"), ("Q-008", "K-008", "a prohibited practice", "Art. 5")),
    (("Q-015", "K-015", "a DPIA", "Art. 35"), ("Q-016", "K-016", "prior consultation", "Art. 36")),
    (("Q-017", "K-017", "erasure", "Art. 17"), ("Q-018", "K-018", "restriction", "Art. 18")),
]
PAIRS_E1 = [
    (("R-008", "reads like a feature", "quick"), ("R-011", "a feature as a question", "full")),
    (("R-009", "asks about the register", "quick"), ("R-024", "asks to check the register", "full")),
    (("R-037", "an injection as a question", "reject"), ("R-038", "the honest version", "full")),
]
SHORT_VERDICT = {"Do not build as described": "Do not build", "Proceed with conditions": "conditions", "Proceed": "Proceed"}


def _e6_half(c: dict[str, Any] | None) -> dict[str, Any]:
    """One half of an E6 pair: right (verdict and flags), or why not, in a few words."""
    if not c:
        return {"ok": None, "why": "not run"}
    sc = c.get("scores") or {}
    why = []
    if not sc.get("verdict_ok"):
        why.append(SHORT_VERDICT.get((c.get("assessment") or {}).get("verdict", ""), "no verdict"))
    for flag, label in (("high_risk_ai", "high-risk flag"), ("dpia_required", "DPIA")):
        f = sc.get(flag) or {}
        if f.get("got") != f.get("expected"):
            why.append(f"{label} {'missed' if f.get('expected') else 'raised'}")
    return {"ok": not why, "why": ", ".join(why)}


def pairs_detail(runs: dict[str, Path]) -> dict[str, Any]:
    e6 = {c["id"]: c for c in _cases(runs.get("E6"))}
    e3 = {c["id"]: c for c in _cases(runs.get("E3"))}
    e5 = {c["id"]: c for c in _cases(runs.get("E5"))}
    e12 = {c["id"]: c for c in _cases(runs.get("E12"))}
    full = []
    for a, at, ae, aa, b, bt, be, ba in PAIRS_E6:
        ra, rb = _e6_half(e6.get(a)), _e6_half(e6.get(b))
        full.append({"a": {"id": a, "text": at, "expected": ae, "article": aa, **ra}, "b": {"id": b, "text": bt, "expected": be, "article": ba, **rb},
                     "ok": None if ra["ok"] is None or rb["ok"] is None else bool(ra["ok"] and rb["ok"])})
    quick = []
    for ha, hb in PAIRS_Q:
        halves = [{"e3_id": q, "e5_id": k, "text": t, "article": p, "e3": e3[q].get("loop_ok") if q in e3 else None, "e5": bool(e5[k].get("ok")) if k in e5 else None} for q, k, t, p in (ha, hb)]
        quick.append({"a": halves[0], "b": halves[1], "e3": all(h["e3"] for h in halves) if any(h["e3"] is not None for h in halves) else None,
                      "e5": all(h["e5"] for h in halves) if any(h["e5"] is not None for h in halves) else None})
    routing = []
    for ha, hb in PAIRS_E1:
        halves = [{"id": i, "text": t, "route": r, "ok": e12[i].get("route_ok") if i in e12 else None} for i, t, r in (ha, hb)]
        routing.append({"a": halves[0], "b": halves[1], "ok": all(h["ok"] for h in halves) if any(h["ok"] is not None for h in halves) else None})
    def count(items: list[dict[str, Any]], key: str) -> dict[str, int]:
        scored = [x for x in items if x[key] is not None]
        return {"right": sum(1 for x in scored if x[key]), "of": len(scored)}
    return {"full": full, "full_right": count(full, "ok"), "quick": quick, "quick_e3": count(quick, "e3"), "quick_e5": count(quick, "e5"),
            "routing": routing, "routing_right": count(routing, "ok")}


def _pretty(model_id: str) -> str:
    """'anthropic/claude-haiku-5.5' -> 'Claude Haiku 5.5 (Anthropic)'."""
    vendor, _, name = model_id.partition("/")
    words = [w.capitalize() if not w[:1].isdigit() else w for w in name.replace("-", " ").split()]
    return f"{' '.join(words)} ({vendor.capitalize()})"


def build(base: Path | None = None) -> dict[str, Any]:
    base = base or results_dir()
    runs = latest_runs(base)
    summaries = {k: _summary(runs.get(k)) for k in SETS}
    notes = json.loads(NOTES.read_text(encoding="utf-8")) if NOTES.is_file() else {}
    header = next((s["header"] for s in summaries.values() if s), {})
    metrics = set_metrics(summaries)
    sections = []
    for sec in SECTIONS:
        sets = []
        for k in sec["sets"]:
            info = SET_INFO[k]
            sets.append({"id": k, "name": info["name"], "what": info["what"], "data": info["data"], "judged": JUDGED[k], "metrics": metrics.get(k, []), "run": k in metrics})
        sections.append({**sec, "sets": sets})
    targets = [x for ms in metrics.values() for x in ms if x["met"] is not None]
    gateway = notes.get("gateway_cost") or {}
    cost = []
    for k in SETS:
        s = summaries.get(k)
        if s:
            cost.append({"set": k, "label": COST_LABELS.get(k, k), "harness": round((s.get("cost") or 0) + (s.get("judge_cost") or 0), 4), "gateway": gateway.get(k), "cases": s.get("cases")})
    run_date = max((s["header"]["timestamp"] for s in summaries.values() if s), default=None)
    models = header.get("models") or {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results_dir": str(base), "commit": header.get("commit"),
        "run_date": run_date[:10] if run_date else None, "models": models, "database": header.get("database"),
        "judge_note": (f"Key findings and faithfulness are judged by {_pretty(models['judge'])}, a family of models not used anywhere in the app, "
                       "so the judge never marks its own work." if models.get("judge", "").startswith("anthropic/") else
                       (f"Key findings and faithfulness are judged by {_pretty(models['judge'])}." if models.get("judge") else None)),
        "runs": {k: {"folder": runs[k].name, "timestamp": summaries[k]["header"]["timestamp"], "cases": summaries[k].get("cases")} for k in SETS if k in runs and summaries[k]},
        "missing_sets": [k for k in SETS if k not in runs],
        "sections": sections, "targets": targets, "targets_met": sum(1 for t in targets if t["met"]), "targets_scored": len(targets),
        "e12": e12_detail(summaries["E12"], _cases(runs.get("E12"))),
        "e7": e7_detail(summaries["E7"], _cases(runs.get("E7"))),
        "e3": e3_detail(summaries["E3"], _cases(runs.get("E3"))), "e5": e5_detail(summaries["E5"], _cases(runs.get("E5"))), "e6": e6_detail(summaries["E6"], _cases(runs.get("E6"))),
        "domains": [{**d, "articles": [{"text": t, "law": law} for t, law in d["articles"]]} for d in DOMAINS],
        "pairs": pairs_detail(runs),
        "cost": cost, "notes": notes,
        "not_met": [{"set": s["id"], **x} for sec in sections for s in sec["sets"] for x in s["metrics"] if x["met"] is False],
    }


def main() -> None:
    doc = build()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("generated_at", "results_dir", "commit", "run_date", "missing_sets", "targets_met", "targets_scored")}, indent=1))
    for sec in doc["sections"]:
        for s in sec["sets"]:
            for x in s["metrics"]:
                print(f"  {s['id']:<3} {x['label']:<44} {x['result']:<40} {x['target'] or '':<8} {'met' if x['met'] else ('not met' if x['met'] is False else '')}")
    print(f"wrote {SNAPSHOT}")


if __name__ == "__main__":
    main()
