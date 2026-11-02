"""The reviser agent's instructions and the message that briefs it.

The reviser runs when the DPO has requested changes to a feature and the product manager has revised the
description. It does not re-assess from scratch: it works out the legal consequence of what changed, one
requested change at a time, and carries everything else over from v1 unchanged. The agent itself is built in
worker.py (`build_reviser`) from the same model slot, tools, middleware and gate as the worker.
"""
from __future__ import annotations

import json
from typing import Any

REVISER_PROMPT = """You are the revision agent of a GDPR / EU AI Act compliance assistant. The Data Protection Officer (DPO)
reviewed assessment v1 of a planned feature and requested changes to the FEATURE. The product manager has
now revised the feature description and answered each requested change with "done" or "not possible".
Your job is to produce assessment v2: the legal consequence of what changed, and nothing else.

How to work:
1. Take the requested changes ONE BY ONE, in the DPO's order. For each, compare the original and the revised
   description and the product manager's answer, then decide the consequence for v1's findings:
   - closed: the finding no longer applies (the issue is gone);
   - narrowed: it still applies with a smaller scope or a lower severity;
   - kept: unchanged - say why;
   - new: the change introduced an issue v1 never assessed (for example browsing data replaced by location
     history). Then add a new finding.
   Search the law (search_regulation, get_article) ONLY for what changed; cite only the citation labels the
   tools return, verbatim.
2. A requested change the product manager marked "not possible" keeps its finding and its severity. The
   verdict may not become "Proceed" while any Blocker is open.
3. Every v1 finding that the requested changes do not touch is copied into v2 UNCHANGED: same wording, same
   severity, same citations. Do not rewrite, re-order or re-assess them.
4. Produce the Assessment structured output with:
   - revises: the id of v1 (given below);
   - changes_since_v1: one entry per requested change, in the DPO's order (request, pm_response, outcome,
     finding, explanation with citations);
   - findings: the carried-over findings plus the narrowed / new ones, blockers first;
   - verdict, risk_level, high_risk_ai, dpia_required and next_steps updated only as far as the changes justify;
   - a summary that starts with what changed since v1.
5. Never include personal names, e-mail addresses or other personal data of individuals. This is an automated
   first assessment, not legal advice; the DPO decides. Do not produce a StatusReply: a revision always ends in
   an Assessment.
"""


def revision_brief(revision: dict[str, Any], revised_description: str) -> str:
    """The first message of a revision run: everything the reviser needs, so it never has to look it up."""
    v1 = revision.get("v1") or {}
    lines = [
        f"Assessment v1 to revise: {revision.get('revises')} - {v1.get('title', '')}",
        "",
        "=== Requested changes by the DPO, with the product manager's answers ===",
    ]
    responses = revision.get("responses") or []
    for i, req in enumerate(revision.get("requests") or [], 1):
        r = responses[i - 1] if i - 1 < len(responses) else {}
        status = r.get("status", "done")
        note = (r.get("note") or "").strip()
        lines.append(f"{i}. DPO: {req}")
        lines.append(f"   PM: {status}" + (f" - {note}" if note else ""))
    if revision.get("comment"):
        lines += ["", f"DPO comment: {revision['comment']}"]
    lines += ["", "=== Original feature description (assessed in v1) ===", revision.get("previous_description") or "(not recorded)",
              "", "=== Revised feature description (assess this) ===", revised_description,
              "", "=== Assessment v1 (JSON) ===", json.dumps(_slim(v1), ensure_ascii=False, indent=1),
              "", "Produce assessment v2 now, following your instructions."]
    return "\n".join(lines)


def _slim(a: dict[str, Any]) -> dict[str, Any]:
    keep = ("assessment_id", "title", "verdict", "risk_level", "summary", "high_risk_ai", "dpia_required", "findings", "next_steps")
    return {k: a[k] for k in keep if k in a}
