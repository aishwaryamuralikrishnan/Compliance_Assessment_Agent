"""Recount the sentence line of an E5 run with the fixed counter (stdlib only):
    python scripts/recount_e5.py eval/results/E5_<stamp>"""
import json, re, sys

_SENT = re.compile(r"[.!?](?:\s|$)")
_ABBR = re.compile(r"\b(Art|Arts|Rec|Recs|No|e\.g|i\.e|cf|para|paras)\.\s", re.IGNORECASE)


def count_sentences(text):
    return len([s for s in _SENT.split(_ABBR.sub(lambda m: m.group(0).replace(". ", " "), text)) if s.strip()])


folder = sys.argv[1]
rows = [json.loads(l) for l in open(f"{folder}/cases.jsonl", encoding="utf-8")]
quick = [r for r in rows if r.get("quick")]
for r in quick:
    f = r.get("faithfulness") or {}
    print(r["id"], "sentences:", count_sentences(r["answer"]), "| faithfulness:", f.get("score"), "| not supported:",
          [s.get("text", "")[:90] for s in (f.get("statements") or []) if s.get("verdict") == "not_supported"])
print("over three sentences:", sum(1 for r in quick if count_sentences(r["answer"]) > 3), "of", len(quick))
