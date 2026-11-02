"""Write docs/expert_round2.md, the reviewer's pack for the E6 cases A-006 to A-020, from eval/data/assessments.jsonl.

    python scripts/expert_round2.py            # writes docs/expert_round2.md
    python scripts/expert_round2.py --ids A-006 A-007   # a subset

The pack is generated, never edited by hand: when a row changes, run the script again. Fields that are scoring
plumbing (must_not, citation_level, acceptable_alternatives) are left out; what the reviewer sees is the feature as
the product manager wrote it, the expected verdict and flags, the expected findings, and the two lists of points
the author has already classified (merely extra, wrong).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval" / "data" / "assessments.jsonl"
OUT = ROOT / "docs" / "expert_round2.md"

DOMAINS = {
    "D1": "Automated decisions and profiling", "D2": "Data sharing and international transfers",
    "D3": "A new AI component that is high-risk (fintech)", "D4": "A new AI component that is not high-risk",
    "D5": "HR and hiring", "D6": "Special-category data", "D7": "Plainly low-risk features",
    "D8": "Data subject rights and retention",
}

HEAD = """# Compliance Assistant · expert review, round 2

The remaining fifteen end-to-end cases (round 1 had the first five). Same format as before: the feature as the
product manager would write it, then what we expect the assistant to say, and a line `Your view:` per case. Agree /
disagree and one line why is all that is needed; if you disagree, say which finding you would change, add or drop,
and why.

Words used: **Blocker** = the feature as described is unlawful and must change before it can be built;
**Required** = an obligation to fulfil before launch while the design stands (a contract, a notice, a DPIA);
**Covered** = already handled, by the design or by a fact about the organisation. "High-risk AI" and "DPIA" are
yes/no flags the assistant sets. The provisions in brackets are the ones we expect to be cited; the assistant may
cite others for the same point and we list the ones we would accept in the data file. Two lists close each case:
*merely extra* are correct points the assistant may add without penalty, *wrong* are points that count against it
if it makes them. Where a case has a pair, the two sound alike but have different answers; please check that the
difference we expect is the right one.

A reminder of the organisation: an EU fintech of about eighty staff with a named DPO; its US fraud-prevention
vendor is certified under the EU-US Data Privacy Framework (a fact the assistant has in memory).

> **Status (27 Oct).** Reviewed the same day by Gemini 3.1 (Argon 4) acting as the DPO, as a *preliminary* review,
> and applied: A-007's objection finding made Covered; Art. 26(11) (telling people a high-risk system is used on
> them) made its own Required finding in A-004 and A-011 and added to A-013; "sick days" removed from A-015's
> inputs; A-016's Art. 10 finding made a Blocker; A-011 reworked around fine-tuning the vendor's model under the
> organisation's own brand (AI Act Art. 25); A-020 replaced by the "Delete my account" case. Rows carry
> `reviewed_by: "gemini (preliminary, round 2)"` until the human expert has seen them; her answers replace
> Gemini's wherever the two differ. The cases below are the rows as they now stand.

"""

TAIL = """
## Anything missing?

Two or three feature descriptions a fintech product team would actually bring to a DPO that none of the twenty
cases covers, with the answer you would expect, would be the most valuable addition.

Your view:
"""


def render(r: dict) -> str:
    e = r["expected"]
    out = [f"### {r['id']} · {DOMAINS.get(r['domain'], r['domain'])}" + (f" · pair of {r['confusable_with']}" if r.get("confusable_with") else "")]
    out.append("")
    for line in r["text"].split("\n"):
        out.append(f"> {line}")
    out.append("")
    if r.get("assume_memory"):
        out.append("(The assistant's memory holds: " + "; ".join(r["assume_memory"]) + ".)")
        out.append("")
    flags = (f"**{e['verdict']}**, {e['risk_level']} risk, "
             f"{'high-risk AI' if e['high_risk_ai'] else 'not high-risk AI'}, "
             f"{'DPIA required' if e['dpia_required'] else 'no DPIA'}.")
    out.append("Expected: " + flags)
    out.append("")
    for i, k in enumerate(e["key_findings"], 1):
        gist = k["gist"][:1].upper() + k["gist"][1:]
        out.append(f"{i}. **{k['severity']}** — {k['topic']} ({', '.join(k['provisions'])}). {gist}.")
    out.append("")
    if e.get("merely_extra"):
        out.append("Merely extra: " + "; ".join(e["merely_extra"]) + ".")
        out.append("")
    if e.get("known_wrong"):
        out.append("Wrong if the assistant says it: " + "; ".join(e["known_wrong"]) + ".")
        out.append("")
    out.append("Your view:")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", default=[f"A-{i:03d}" for i in range(6, 21)])
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    rows = [json.loads(l) for l in DATA.open(encoding="utf-8") if l.strip()]
    by = {r["id"]: r for r in rows}
    missing = [i for i in a.ids if i not in by]
    if missing:
        raise SystemExit(f"not in {DATA.name}: {', '.join(missing)}")
    body = "\n".join(render(by[i]) for i in a.ids)
    Path(a.out).write_text(HEAD + body + TAIL, encoding="utf-8", newline="\n")
    print(f"wrote {a.out}: {len(a.ids)} cases")


if __name__ == "__main__":
    main()
