"""Find explicit legal identifiers in a query so they become exact metadata lookups.

Real questions often name the provision ("does Article 22 apply?", "Annex III point 5(b)",
"Recital 71 of the GDPR"); keyword and vector search are weaker than a WHERE clause for
those. Everything here is regex-only, no model calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

Regulation = str  # "GDPR" | "AI_ACT"

_REG_PATTERNS: list[tuple[re.Pattern[str], Regulation]] = [
    (re.compile(r"\b(?:GDPR|General Data Protection Regulation|Regulation \(EU\) 2016/679|2016/679)\b", re.I), "GDPR"),
    (re.compile(r"\b(?:AI Act|Artificial Intelligence Act|Regulation \(EU\) 2024/1689|2024/1689|AIA)\b", re.I), "AI_ACT"),
]

_ROMAN = r"[IVXLC]+"
RE_ARTICLE = re.compile(
    r"\bArt(?:icle|\.)?\s*(\d{1,3})([a-z]?)"              # Article 22 / Art. 22 / Art 75a
    r"(?:\s*\(\s*(\d{1,2})([a-z]?)\s*\))?"                # (1) / (1a)
    r"(?:\s*\(\s*([a-z]{1,2})\s*\))?",                    # (b)   -> point, kept for display only
    re.I,
)
RE_RECITAL = re.compile(r"\bRec(?:ital|\.)\s*\(?(\d{1,3})\)?", re.I)
RE_ANNEX = re.compile(
    r"\bAnnex\s+(" + _ROMAN + r")\b"
    r"(?:[\s,]*(?:point|pt\.?|para(?:graph)?|section)?\s*(\d{1,2})"   # point 5 / 5
    r"(?:\s*\(\s*([a-z]{1,2})\s*\))?)?",                                 # (b)
    re.I,
)


@dataclass
class IdentifierFilter:
    """One exact lookup. `label` is how it was written, for the trace."""

    label: str
    regulation: Regulation | None = None
    article: int | None = None
    article_letter: str | None = None
    paragraph: int | None = None
    paragraph_letter: str | None = None
    point: str | None = None
    recital: int | None = None
    annex: str | None = None

    @property
    def kind(self) -> str:
        if self.recital is not None:
            return "recital"
        if self.annex is not None:
            return "annex"
        return "article"


@dataclass
class ParsedQuery:
    regulations: list[Regulation] = field(default_factory=list)
    identifiers: list[IdentifierFilter] = field(default_factory=list)

    @property
    def single_regulation(self) -> Regulation | None:
        return self.regulations[0] if len(self.regulations) == 1 else None


def detect_regulations(text: str) -> list[Regulation]:
    found: list[Regulation] = []
    for rx, reg in _REG_PATTERNS:
        if rx.search(text) and reg not in found:
            found.append(reg)
    return found


def parse_identifiers(text: str, default_regulation: Regulation | None = None) -> ParsedQuery:
    regs = detect_regulations(text)
    reg = regs[0] if len(regs) == 1 else default_regulation
    ids: list[IdentifierFilter] = []
    seen: set[tuple] = set()

    for m in RE_ARTICLE.finditer(text):
        num, letter, para, para_letter, point = m.groups()
        key = ("art", int(num), letter.lower(), para, (para_letter or "").lower())
        if key in seen:
            continue
        seen.add(key)
        ids.append(
            IdentifierFilter(
                label=m.group(0).strip(),
                regulation=reg,
                article=int(num),
                article_letter=letter.lower() or None,
                paragraph=int(para) if para else None,
                paragraph_letter=(para_letter or "").lower() or None,
                point=point.lower() if point else None,
            )
        )
    for m in RE_RECITAL.finditer(text):
        key = ("rec", int(m.group(1)))
        if key in seen:
            continue
        seen.add(key)
        ids.append(IdentifierFilter(label=m.group(0).strip(), regulation=reg, recital=int(m.group(1))))
    for m in RE_ANNEX.finditer(text):
        annex, point, sub = m.group(1).upper(), m.group(2), m.group(3)
        key = ("anx", annex, point)
        if key in seen:
            continue
        seen.add(key)
        ids.append(
            IdentifierFilter(
                label=m.group(0).strip(),
                regulation=reg or "AI_ACT",   # the GDPR has no annexes
                annex=annex,
                point=point,
            )
        )
    return ParsedQuery(regulations=regs, identifiers=ids)
