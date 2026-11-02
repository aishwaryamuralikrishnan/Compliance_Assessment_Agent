"""The evaluation report (eval/harness/report.py, GET /api/eval/report): built from the latest run per set, sections
and sets with their definitions, targets only where a share is measured, E6 per case with the verdict and severity
matrices, the notes merged in; 404 when there is no run; public, no session needed."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.test_api import api_users, make_client  # noqa: F401  (the fixture is used by name)


def _write(folder: Path, summary: dict, cases: list[dict] | None = None) -> None:
    folder.mkdir(parents=True)
    (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    if cases is not None:
        (folder / "cases.jsonl").write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")


HEADER = {"set": "x", "timestamp": "2026-10-27T14:00:00+00:00", "commit": "abc1234", "models": {"worker_full": "m"}, "database": "localhost/compliance_eval", "host": "h"}


@pytest.fixture()
def results(tmp_path, monkeypatch):
    base = tmp_path / "results"
    _write(base / "E12_20261027-1000", {"header": HEADER, "cases": 3, "route_accuracy": {"right": 3, "of": 3, "wrong": []}, "fallback": {"count": 0, "of": 3},
                                        "detection": {"injection": {"detected": 1, "of": 1, "missed": []}, "pii_redacted": {"detected": 1, "of": 1, "missed": []}, "off_topic": {"detected": 1, "of": 1, "missed": []}},
                                        "false_positives": {"count": 0, "of": 1, "ids": []}, "redactions_exact": {"right": 1, "of": 1}, "cost": 0.001, "confusions": {}})
    # an older E7 folder and a newer one: the newer wins
    _write(base / "E7_20261026-0900", {"header": HEADER, "cases": 4, "caught": 3, "of": 4, "missed": ["F-002"]})
    _write(base / "E7_20261027-1005", {"header": HEADER, "cases": 4, "caught": 4, "of": 4, "missed": []})
    _write(base / "E6_20261027-1100", {"header": HEADER, "cases": 2, "assessed": {"count": 2, "of": 2, "not_assessed": []},
                                        "verdict": {"right": 1, "of": 2, "wrong": ["A-002 (Proceed → Proceed with conditions)"]}, "dangerous_misses": [], "risk_level": {"right": 2, "of": 2},
                                        "flags": {"high_risk_ai": {"missed": 0, "positives": 1, "false": 0, "negatives": 1}, "dpia_required": {"missed": 2, "positives": 2, "false": 0, "negatives": 0}},
                                        "must_cite": {"found": 3, "of": 4, "misses": ["A-002: GDPR Art. 13"]},
                                        "key_findings": {"matched": 3, "partial": 1, "severity_miscalibrated": 1, "of": 5, "judged_cases": 2, "judge_errors": []},
                                        "wrong_extras": [], "must_not_violations": [], "faithfulness": {"mean": 0.9, "over": 2},
                                        "pairs_right": 0, "pairs_total": 1, "pairs_failed": ["A-001+A-002"], "run": {"rewrites": 2, "regenerations": 0, "seconds_mean": 40.0},
                                        "cost": 0.01, "judge_cost": 0.02, "judge_vs_human": {"agreed": 4, "of": 4, "unsure": [], "disagreed": []}},
           cases=[{"id": "A-001", "domain": "D7", "assessment": {"title": "t", "verdict": "Proceed", "risk_level": "low", "findings": [{"severity": "Covered"}, {"severity": "Covered"}]},
                   "scores": {"expected_verdict": "Proceed", "verdict_ok": True, "dangerous_miss": False, "risk_ok": True, "high_risk_ai": {"got": False, "expected": False},
                              "dpia_required": {"got": False, "expected": False}, "key_findings": {"matched": 2, "partial": 0, "missed": 0, "of": 2}, "must_cite": {"found": ["GDPR Art. 5"], "missing": []}},
                   "judge": {"key_findings": [{"index": 1, "verdict": "matched", "severity_miscalibrated": False, "assistant_findings": [1]}, {"index": 2, "verdict": "matched", "severity_miscalibrated": False, "assistant_findings": [2]}], "wrong_extras": []},
                   "faithfulness": {"score": 1.0}, "usage": {"cost": 0.004}, "judge_usage": {"cost": 0.01}, "run": {"seconds": 30.0, "searches": 4, "rewrites": 1}},
                  {"id": "A-002", "domain": "D2", "assessment": {"title": "t2", "verdict": "Proceed with conditions", "risk_level": "medium", "findings": [{"severity": "Blocker"}, {"severity": "Required"}]},
                   "scores": {"expected_verdict": "Proceed", "verdict_ok": False, "dangerous_miss": False, "risk_ok": True, "high_risk_ai": {"got": True, "expected": True},
                              "dpia_required": {"got": False, "expected": True}, "key_findings": {"matched": 1, "partial": 1, "missed": 1, "of": 3}, "must_cite": {"found": ["GDPR Art. 46", "GDPR Art. 28"], "missing": ["GDPR Art. 13"]}},
                   "judge": {"key_findings": [{"index": 1, "verdict": "missed", "severity_miscalibrated": True, "assistant_findings": [1]}, {"index": 2, "verdict": "matched", "severity_miscalibrated": False, "assistant_findings": [2]},
                                              {"index": 3, "verdict": "partial", "severity_miscalibrated": False, "assistant_findings": [2]}], "wrong_extras": []},
                   "faithfulness": {"score": 0.8}, "usage": {"cost": 0.006}, "judge_usage": {"cost": 0.01}, "run": {"seconds": 50.0, "searches": 6, "rewrites": 1}}])
    monkeypatch.setenv("EVAL_RESULTS_DIR", str(base))
    return base


def test_report_builds_from_the_latest_run_per_set_and_scores_the_targets(results):
    from eval.harness import report

    doc = report.build()
    assert doc["runs"]["E7"]["folder"] == "E7_20261027-1005" and doc["missing_sets"] == ["E3", "E5"]
    sets = {s["id"]: s for sec in doc["sections"] for s in sec["sets"]}
    assert [sec["id"] for sec in doc["sections"]] == ["guardrails", "retrieval", "end-to-end"]
    assert sets["E3"]["run"] is False and sets["E3"]["metrics"] == [] and sets["E3"]["what"]
    by = {x["key"]: x for s in sets.values() for x in s["metrics"]}
    # counts carry no target (29 Oct): stated, not judged
    assert by["caught"]["result"] == "4 of 4" and by["caught"]["target"] is None and by["caught"]["met"] is None
    assert by["injection"]["met"] is None and by["flag_dpia"]["met"] is None and by["flag_dpia"]["result"] == "2 of 2 · 0 of 0"
    # shares carry one, and dangerous misses the zero line
    assert by["verdict"]["result"] == "1 of 2" and by["verdict"]["value"] == 0.5 and by["verdict"]["target"] == "≥ 0.80" and by["verdict"]["met"] is False
    assert by["dangerous"]["target"] == "0" and by["dangerous"]["met"] is True
    assert by["judge"]["met"] is True and by["faithfulness_e6"]["target"] == "≥ 0.80" and by["faithfulness_e6"]["met"] is True
    assert all(x["definition"] for x in by.values())
    assert doc["targets_met"] + 3 == doc["targets_scored"]          # not met: E6 verdict, must-cite (3 of 4), key findings (3 of 5)
    e6 = doc["e6"]
    assert e6["verdict_matrix"]["counts"]["Proceed"] == {"Do not build as described": 0, "Proceed with conditions": 1, "Proceed": 1}
    # A-002 KF1: expected Required (A-002's first golden finding is Required) given as Blocker -> the severity matrix, read from the golden file
    assert e6["severity_matrix"]["counts"]["Required"]["Blocker"] == 1
    assert e6["key_findings"]["missed"] == 1 and e6["key_findings"]["missed_absent"] == 0
    assert [c["id"] for c in e6["per_case"]] == ["A-001", "A-002"] and e6["per_case"][1]["cost"] == 0.016 and e6["per_case"][1]["key_findings"]["severity_miscalibrated"] == 1
    assert doc["cost"][0] == {"set": "E12", "label": "E1 · E2", "harness": 0.001, "gateway": doc["notes"].get("gateway_cost", {}).get("E12"), "cases": 3}
    # the Legal domains tab: nine areas with the law each rests on; the pairs scored from the run, a pair with an unrun half left unscored
    assert [d["id"] for d in doc["domains"]] == ["D1", "D2", "D7", "D8", "D9", "D5", "D6", "D3", "D4"] and doc["domains"][3]["articles"][-1] == {"text": "Art. 26(6)", "law": "ai"}
    pairs = doc["pairs"]
    assert pairs["full"][0]["a"] == {"id": "A-002", "text": "a transfer the organisation's facts do not cover", "expected": "safeguards", "article": "Art. 46", "ok": False, "why": "conditions, DPIA missed"}
    assert pairs["full"][0]["b"]["ok"] is None and pairs["full"][0]["ok"] is None and pairs["full_right"] == {"right": 0, "of": 0}
    assert pairs["quick_e3"] == {"right": 0, "of": 0} and pairs["routing_right"] == {"right": 0, "of": 0}


def test_report_endpoint_is_public_and_reports_no_runs_as_404(api_users, results, tmp_path, monkeypatch):
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    graph = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(graph) as c:
        r = c.get("/api/eval/report")                                    # no session: the report is public (29 Oct)
        assert r.status_code == 200 and r.json()["runs"]["E6"]["cases"] == 2 and r.json()["commit"] == "abc1234"
        monkeypatch.setenv("EVAL_RESULTS_DIR", str(tmp_path / "empty"))
        r = c.get("/api/eval/report")
        assert r.status_code == 404 and "no evaluation runs" in r.json()["detail"]
