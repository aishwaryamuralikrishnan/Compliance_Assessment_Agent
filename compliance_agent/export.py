"""Register export for audits: a PDF with the overview table and every recorded assessment in full.

    register_pdf(rows, generated_by="m.weber") -> bytes      rows from repo.list_register()

Pure reportlab (platypus), built-in Helvetica, so no font files are needed. Text is reduced to Latin-1
(the built-in fonts cover nothing else); the few symbols the app uses are mapped to ASCII.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import repo

log = logging.getLogger(__name__)

_SUBS = {"→": "->", "←": "<-", "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
         "…": "...", " ": " ", "•": "-", "✓": "yes", "✗": "no"}


def _txt(s: Any) -> str:
    s = "" if s is None else str(s)
    for k, v in _SUBS.items():
        s = s.replace(k, v)
    return escape(s.encode("latin-1", "replace").decode("latin-1"))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=17, leading=21, alignment=TA_LEFT, spaceAfter=2),
        "meta": ParagraphStyle("m", parent=base["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontSize=12.5, leading=15, spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=9.5, leading=12, spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9, leading=12),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=7.8, leading=9.8),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontSize=7.8, leading=9.8, fontName="Helvetica-Bold"),
        "small": ParagraphStyle("s", parent=base["Normal"], fontSize=8, leading=10.5, textColor=colors.HexColor("#555555")),
    }


def _yes(b: Any) -> str:
    return "yes" if b else "no"


def _dpo_comment(row: dict[str, Any]) -> str | None:
    try:
        task = repo.review_task_for_thread(row.get("thread_id") or "", status="approved")
    except Exception as exc:
        log.warning("could not read the DPO comment for %s: %s: %s", row.get("assessment_id"), type(exc).__name__, exc)
        return None
    return (task or {}).get("dpo_comment") or None


def register_pdf(rows: list[dict[str, Any]], *, generated_by: str, organisation: str | None = None) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Processing register", author=generated_by, subject="Register of processing activities assessed under the GDPR and the EU AI Act")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list[Any] = [
        Paragraph("Processing register", st["title"]),
        Paragraph(_txt(f"{organisation + ' - ' if organisation else ''}{len(rows)} recorded assessment(s) - exported {now} by {generated_by} - "
                       "entries are written only by the Data Protection Officer's approval; the assessments are an automated first pass, not legal advice."), st["meta"]),
        Spacer(1, 6),
    ]

    # ---- overview table --------------------------------------------------------------
    head = ["Id", "Title", "Verdict", "Risk", "High-risk AI", "DPIA", "Requested by", "Approved by", "Approved at"]
    data = [[Paragraph(_txt(h), st["cellb"]) for h in head]]
    for r in rows:
        data.append([
            Paragraph(_txt(r["assessment_id"]), st["cell"]), Paragraph(_txt(r["title"]), st["cell"]), Paragraph(_txt(r["verdict"]), st["cell"]),
            Paragraph(_txt(r["risk_level"]), st["cell"]), Paragraph(_yes(r["high_risk_ai"]), st["cell"]), Paragraph(_yes(r["dpia_required"]), st["cell"]),
            Paragraph(_txt(r["requested_by"]), st["cell"]), Paragraph(_txt(r["approved_by"]), st["cell"]),
            Paragraph(_txt(r["approved_at"].strftime("%Y-%m-%d %H:%M") if hasattr(r["approved_at"], "strftime") else r["approved_at"]), st["cell"]),
        ])
    widths = [16 * mm, 70 * mm, 40 * mm, 14 * mm, 20 * mm, 14 * mm, 24 * mm, 24 * mm, 26 * mm]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9ca3af")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [table, Spacer(1, 4),
              Paragraph("High-risk AI: the assessment classified the activity as a high-risk AI system under the AI Act (Annex III). "
                        "DPIA: a data protection impact assessment is required before processing (GDPR Art. 35).", st["small"])]
    if not rows:
        story.append(Paragraph("The register is empty.", st["body"]))

    # ---- one section per entry -------------------------------------------------------
    for r in rows:
        a = r.get("assessment") or {}
        block: list[Any] = [
            Paragraph(_txt(f"{r['assessment_id']} - {r['title']}"), st["h"]),
            Paragraph(_txt(f"Verdict: {r['verdict']} - risk {r['risk_level']} - high-risk AI: {_yes(r['high_risk_ai'])} - DPIA required: {_yes(r['dpia_required'])}"), st["body"]),
            Paragraph(_txt(f"Requested by {r['requested_by']}; approved and recorded by {r['approved_by']} on "
                           f"{r['approved_at'].strftime('%Y-%m-%d %H:%M') if hasattr(r['approved_at'], 'strftime') else r['approved_at']}."), st["small"]),
        ]
        if a.get("summary"):
            block.append(Paragraph(_txt(a["summary"]), st["body"]))
        comment = _dpo_comment(r)
        if comment:
            block.append(Paragraph("<b>DPO comment:</b> " + _txt(comment), st["body"]))
        findings = a.get("findings") or []
        if findings:
            block.append(Paragraph("Findings", st["h3"]))
            fdata = [[Paragraph("Severity", st["cellb"]), Paragraph("Finding", st["cellb"]), Paragraph("Provisions", st["cellb"])]]
            for f in findings:
                fdata.append([Paragraph(_txt(f.get("severity")), st["cell"]), Paragraph(_txt(f.get("text")), st["cell"]),
                              Paragraph(_txt(", ".join(f.get("citations") or [])), st["cell"])])
            ft = Table(fdata, colWidths=[20 * mm, 170 * mm, 58 * mm], repeatRows=1)
            ft.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9ca3af")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
            block.append(ft)
        if a.get("next_steps"):
            block.append(Paragraph("Next steps", st["h3"]))
            for i, s_ in enumerate(a["next_steps"], 1):
                block.append(Paragraph(_txt(f"{i}. {s_}"), st["body"]))
        cites = r.get("citations") or a.get("verified_citations") or []
        if cites:
            block.append(Paragraph("<b>Provisions cited:</b> " + _txt(", ".join(cites)), st["small"]))
        if a.get("revises"):
            block.append(Paragraph("History", st["h3"]))
            for h in repo.assessment_history(r["assessment_id"]):
                d = h.get("decision") or {}
                when = h["created_at"].strftime("%Y-%m-%d %H:%M") if hasattr(h.get("created_at"), "strftime") else ""
                line = f"v{h['version']} {h['assessment_id']} ({when}): {h.get('assessment', {}).get('verdict', '')}"
                if d:
                    line += f" - {d['status'].replace('_', ' ')} by {d.get('resolved_by')}" + (f": {d['dpo_comment']}" if d.get("dpo_comment") else "")
                block.append(Paragraph(_txt(line), st["small"]))
            for c in a.get("changes_since_v1") or []:
                block.append(Paragraph(_txt(f"- {c.get('outcome')}: DPO asked '{c.get('request')}'; PM: {c.get('pm_response')}; {c.get('explanation')}"), st["small"]))
        story.append(KeepTogether(block[:3]))
        story += block[3:]
        story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()


def assessment_markdown(a: dict[str, Any]) -> str:
    """The assessment card as Markdown (the *Download (Markdown)* button; served by the web API as well)."""
    lines = [f"# {a.get('assessment_id')} · {a.get('title')}", "",
             f"**Verdict:** {a.get('verdict')}  ·  **Risk:** {a.get('risk_level')}  ·  **High-risk AI:** {a.get('high_risk_ai')}  ·  **DPIA required:** {a.get('dpia_required')}", "",
             a.get("summary", ""), ""]
    if a.get("revises"):
        lines += [f"## Changes since {a['revises']}", ""]
        for c in a.get("changes_since_v1") or []:
            lines.append(f"- **{c.get('outcome')}** — DPO: {c.get('request')} · PM: {c.get('pm_response')} · {c.get('explanation')}")
        lines.append("")
    lines += ["## Findings", ""]
    for f in a.get("findings", []):
        lines.append(f"- **{f['severity']}** — {f['text']} _( {', '.join(f.get('citations', []))} )_")
    lines += ["", "## Next steps", ""] + [f"{i}. {s}" for i, s in enumerate(a.get("next_steps", []), 1)]
    lines += ["", f"_Sources: {', '.join(a.get('sources', []))}_", "", f"_{a.get('disclaimer', '')}_"]
    return "\n".join(lines)
