"""Shared pieces of the evaluation harness (eval/README.md): the golden files, the evaluation database guard, the
citation matching at article level, the usage counter that prices every model call of a case, the captured stream
writer for calling a graph node directly, and the results writer (cases.jsonl, summary.json, summary.md)."""
from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
PROMPTS = ROOT / "eval" / "prompts"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------------------------
# the evaluation database
# --------------------------------------------------------------------------------------

class EvalError(RuntimeError):
    pass


def require_eval_db(needed: bool = True) -> str | None:
    """Point the app at EVAL_DATABASE_URL for this process. Refuses to run against the demo database: the sets that
    run the app (E5, E6, and E7's stored drafts) write assessments, review tasks and paused threads exactly as the
    app does (README section 2). Must be called before the first database connection."""
    import compliance_agent.config  # noqa: F401  (loads .env)

    url = os.environ.get("EVAL_DATABASE_URL")
    if not needed:
        return url
    if not url:
        raise EvalError("EVAL_DATABASE_URL is not set. Create the evaluation database once "
                        "(CREATE DATABASE compliance_eval TEMPLATE compliance;) and set EVAL_DATABASE_URL to it.")
    if url == os.environ.get("DATABASE_URL"):
        raise EvalError("EVAL_DATABASE_URL equals DATABASE_URL: the harness never runs against the demo database.")
    os.environ["DATABASE_URL"] = url
    return url


def db_host() -> str:
    url = os.environ.get("DATABASE_URL") or ""
    try:
        p = urlsplit(url)
        return f"{p.hostname}/{p.path.lstrip('/')}"
    except Exception:
        return "?"


# --------------------------------------------------------------------------------------
# golden rows
# --------------------------------------------------------------------------------------

REQUIRED = ("id", "source", "author", "reviewed_by", "notes")


def load_rows(name: str, ids: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    path = DATA / name
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvalError(f"{name} line {n}: not valid JSON ({exc})") from exc
            missing = [k for k in REQUIRED if k not in row]
            if missing:
                raise EvalError(f"{name} line {n}: missing {missing}")
            rows.append(row)
    seen = set()
    for r in rows:
        if r["id"] in seen:
            raise EvalError(f"{name}: duplicate id {r['id']}")
        seen.add(r["id"])
    if ids:
        want = set(ids)
        rows = [r for r in rows if r["id"] in want]
    if limit:
        rows = rows[:limit]
    return rows


def pairs(rows: list[dict[str, Any]], ok: dict[str, bool]) -> dict[str, Any]:
    """The confusable-pairs line: pairs where both rows were right, of the pairs present in this run."""
    done = set()
    total, right, failed = 0, 0, []
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        other = r.get("confusable_with")
        if not other or other not in by_id:
            continue
        key = tuple(sorted((r["id"], other)))
        if key in done:
            continue
        done.add(key)
        total += 1
        if ok.get(key[0]) and ok.get(key[1]):
            right += 1
        else:
            failed.append(f"{key[0]}+{key[1]}")
    return {"pairs_right": right, "pairs_total": total, "pairs_failed": failed}


# --------------------------------------------------------------------------------------
# citations
# --------------------------------------------------------------------------------------

def article_key(label: str) -> str:
    """'GDPR Art. 22(1)' -> 'GDPR Art. 22'; 'AI Act Annex III point 5' -> 'AI Act Annex III'; recitals unchanged."""
    s = " ".join(str(label).split())
    if " point " in s:
        s = s.split(" point ")[0]
    if "(" in s:
        s = s.split("(")[0].rstrip()
    return s


def satisfied(must: list[str], labels: list[str]) -> tuple[list[str], list[str]]:
    """(found, missing) of the must list against the labels, at article level."""
    have = {article_key(l) for l in labels}
    found = [m for m in must if article_key(m) in have]
    missing = [m for m in must if article_key(m) not in have]
    return found, missing


# --------------------------------------------------------------------------------------
# model usage and cost
# --------------------------------------------------------------------------------------

@contextlib.contextmanager
def usage_counter() -> Iterator[dict[str, Any]]:
    """Collects the token usage of every chat-model call made inside the block (the grader and the rewrite inside
    the search tool included) and prices it with config/models.yaml. Yields a dict filled on exit:
    {"calls": n, "tokens_in", "tokens_out", "cached", "cost", "by_model": {...}}."""
    from langchain_core.callbacks import get_usage_metadata_callback

    from compliance_agent import config as C

    out: dict[str, Any] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cached": 0, "cost": 0.0, "by_model": {}}
    price_by_model: dict[str, dict[str, float]] = {}
    for slot, spec in (C.models_config().get("slots") or {}).items():
        if isinstance(spec.get("price"), dict) and spec.get("model"):
            price_by_model[spec["model"]] = {k: float(v) for k, v in spec["price"].items()}
    t0 = time.time()
    with get_usage_metadata_callback() as cb:
        yield out
    for model, u in (cb.usage_metadata or {}).items():
        i, o = int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))
        cached = int(((u.get("input_token_details") or {}).get("cache_read")) or 0)
        p = price_by_model.get(model) or price_by_model.get(model.split("/")[-1]) or {}
        cost = ((i - cached) * p.get("input", 0) + cached * p.get("cached_input", p.get("input", 0)) + o * p.get("output", 0)) / 1e6
        out["by_model"][model] = {"tokens_in": i, "tokens_out": o, "cached": cached, "cost": round(cost, 6), "priced": bool(p)}
        out["tokens_in"] += i; out["tokens_out"] += o; out["cached"] += cached; out["cost"] += cost
    out["cost"] = round(out["cost"], 6)
    out["seconds"] = round(time.time() - t0, 2)


# --------------------------------------------------------------------------------------
# calling a graph node directly
# --------------------------------------------------------------------------------------

@contextlib.contextmanager
def node_context(module, *, user_id: str = "lena.k", role: str = "product_manager", thread_id: str = "eval") -> Iterator[list[dict[str, Any]]]:
    """Replace the module's get_stream_writer / get_config (imported by name in every node) with a capture of the
    events and a fixed configurable, for the sets that call one node without the graph (E1/E2, E7)."""
    events: list[dict[str, Any]] = []
    saved = {}
    if hasattr(module, "get_stream_writer"):
        saved["get_stream_writer"] = module.get_stream_writer
        module.get_stream_writer = lambda: events.append
    if hasattr(module, "get_config"):
        saved["get_config"] = module.get_config
        module.get_config = lambda: {"configurable": {"thread_id": thread_id, "user_id": user_id, "role": role, "run_id": "eval"}}
    try:
        yield events
    finally:
        for k, v in saved.items():
            setattr(module, k, v)


# --------------------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------------------

def header(set_name: str) -> dict[str, Any]:
    from compliance_agent.models import resolved_model_ids

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip() or "?"
    except Exception:
        commit = "?"
    return {"set": set_name, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": commit,
            "models": resolved_model_ids(), "database": db_host(), "host": socket.gethostname()}


class ResultWriter:
    def __init__(self, set_name: str):
        self.set_name = set_name
        self.folder = RESULTS / f"{set_name}_{datetime.now().strftime('%Y%m%d-%H%M')}"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._cases = (self.folder / "cases.jsonl").open("w", encoding="utf-8")
        self.header = header(set_name)
        self.n = 0

    def case(self, record: dict[str, Any]) -> None:
        self._cases.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._cases.flush()
        self.n += 1

    def finish(self, summary: dict[str, Any], markdown: str) -> Path:
        self._cases.close()
        (self.folder / "summary.json").write_text(json.dumps({"header": self.header, "cases": self.n, **summary}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        head = (f"# {self.set_name} · {self.header['timestamp']}\n\n"
                f"commit `{self.header['commit']}` · database `{self.header['database']}` · {self.n} cases\n\n"
                f"models: " + " · ".join(f"`{k}` = {v}" for k, v in self.header["models"].items()) + "\n\n")
        (self.folder / "summary.md").write_text(head + markdown, encoding="utf-8")
        return self.folder


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def ratio(n: int, d: int) -> str:
    """'17 of 20 (0.85)' with the decimal only from a denominator of 20 (README section 6)."""
    if d == 0:
        return "–"
    return f"{n} of {d}" + (f" ({n / d:.2f})" if d >= 20 else "")
