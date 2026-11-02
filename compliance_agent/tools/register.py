"""Processing-register tool: lookup_register (read).

There is no tool that writes the register: the entry is written by the tool gate when the DPO
approves a request_dpo_review interrupt (nodes/middleware.py), never by a worker call."""
from __future__ import annotations

from langchain_core.tools import tool

from .. import repo


@tool(response_format="content_and_artifact")
def lookup_register(query: str) -> tuple[str, dict]:
    """Find existing entries in the organisation's processing register.

    Pass an assessment id ("A-0012") or a few keywords describing the activity (e.g.
    "credit scoring"). Use it before drafting an assessment so you can say "this is already
    registered as A-0012" instead of assessing the same activity twice.
    """
    try:
        rows = repo.search_register(query)
    except Exception as exc:
        return f"lookup_register failed: {exc}", {"error": str(exc)}
    if not rows:
        return f"No register entries match '{query}'.", {"entries": []}
    lines = []
    for r in rows:
        lines.append(
            f"- {r['assessment_id']}: {r['title']} — {r['verdict']} (risk {r['risk_level']}, "
            f"high-risk AI: {r['high_risk_ai']}, DPIA: {r['dpia_required']}); approved by {r['approved_by']} "
            f"on {r['approved_at']:%Y-%m-%d}; citations: {', '.join(r['citations'][:6])}"
        )
    return "\n".join(lines), {"entries": [{k: (str(v) if k.endswith('_at') else v) for k, v in r.items() if k != 'assessment'} for r in rows]}
