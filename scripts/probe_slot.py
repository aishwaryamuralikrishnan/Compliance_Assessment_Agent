"""Can this model serve a slot of the app? Price from the gateway, then the three calls a slot has to answer.

    python scripts/probe_slot.py openai/gpt-5.4-mini openai/gpt-6-luna

For each model id: the list price (USD per 1M tokens, prompt / completion), a plain reply, a tool call
(the worker binds tools and must call them), and a structured output (every slot: the input screen, the grader,
the Assessment itself), first in json_schema mode, then with the fallback method from config/models.yaml.
Each call is one short request; the whole probe costs a fraction of a cent per model.
Reads OPENROUTER_API_KEY and OPENROUTER_BASE_URL from the environment / .env.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
from langchain.chat_models import init_chat_model  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from compliance_agent import config  # noqa: E402


class Verdict(BaseModel):
    """A tiny structured output, shaped like the app's screens and graders."""

    on_topic: bool = Field(description="True if the text is about data protection law.")
    severity: Literal["Blocker", "Required", "Covered"]
    reason: str


@tool
def lookup_article(regulation: str, article: int) -> str:
    """Return the text of an article of the GDPR or the AI Act."""
    return f"{regulation} Art. {article}: (stub)"


def price_of(model_id: str) -> str:
    url = f"{config.openrouter_base_url()}/models"
    resp = requests.get(url, headers={"Authorization": f"Bearer {config.openrouter_api_key()}"}, timeout=30)
    resp.raise_for_status()
    for m in resp.json().get("data", []):
        if m.get("id") == model_id:
            p = m.get("pricing") or {}
            try:
                inp, out = float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
            except (TypeError, ValueError):
                return "price: not given"
            cached = p.get("input_cache_read")
            extra = f", cached input ${float(cached) * 1e6:.2f}" if cached not in (None, "", "0") else ""
            ctx = m.get("context_length")
            return f"price: ${inp:.2f} in / ${out:.2f} out per 1M tokens{extra} · context {ctx}"
    return "price: model id not in the gateway's list"


def llm(model_id: str, max_tokens: int = 512):
    return init_chat_model(model=model_id, model_provider="openai", base_url=config.openrouter_base_url(),
                           api_key=config.openrouter_api_key(), temperature=0.0, max_tokens=max_tokens)


def usage(msg) -> str:
    u = getattr(msg, "usage_metadata", None) or {}
    return f"{u.get('input_tokens', '?')} in / {u.get('output_tokens', '?')} out"


def probe(model_id: str) -> None:
    print(f"\n== {model_id}")
    try:
        print("  " + price_of(model_id))
    except Exception as exc:
        print(f"  price: lookup failed: {type(exc).__name__}: {exc}")

    t0 = time.time()
    try:
        reply = llm(model_id).invoke([("human", "In one sentence: what is GDPR Article 17 about?")])
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        ok = bool(text.strip())
        print(f"  {'OK  ' if ok else 'FAIL'} plain reply · {usage(reply)} · {time.time() - t0:.1f}s · {text.strip()[:90]!r}")
    except Exception as exc:
        print(f"  FAIL plain reply · {type(exc).__name__}: {str(exc)[:160]}")

    t0 = time.time()
    try:
        reply = llm(model_id).bind_tools([lookup_article]).invoke([("human", "Use the tool to fetch GDPR Article 22.")])
        calls = getattr(reply, "tool_calls", None) or []
        ok = any(c.get("name") == "lookup_article" for c in calls)
        print(f"  {'OK  ' if ok else 'FAIL'} tool call · {usage(reply)} · {time.time() - t0:.1f}s · {[(c.get('name'), c.get('args')) for c in calls] or 'no tool call made'}")
    except Exception as exc:
        print(f"  FAIL tool call · {type(exc).__name__}: {str(exc)[:160]}")

    prompt = [("human", "Classify: 'We log the customer's IP address for fraud checks.' Is it on topic for data protection law, "
                        "what severity would a reviewer give the missing legal basis, and why?")]
    t0 = time.time()
    try:
        out = llm(model_id).with_structured_output(Verdict).invoke(prompt)
        print(f"  {'OK  ' if isinstance(out, Verdict) else 'FAIL'} structured output (json_schema) · {time.time() - t0:.1f}s · {out!r}"[:220])
    except Exception as exc:
        print(f"  FAIL structured output (json_schema) · {type(exc).__name__}: {str(exc)[:160]}")
        fallback = config.models_config().get("structured_output", {}).get("fallback_method")
        if fallback:
            t0 = time.time()
            try:
                out = llm(model_id).with_structured_output(Verdict, method=fallback).invoke(prompt)
                print(f"  {'OK  ' if isinstance(out, Verdict) else 'FAIL'} structured output ({fallback}) · {time.time() - t0:.1f}s · {out!r}"[:220])
            except Exception as exc2:
                print(f"  FAIL structured output ({fallback}) · {type(exc2).__name__}: {str(exc2)[:160]}")


def main() -> None:
    ids = sys.argv[1:]
    if not ids:
        print(__doc__)
        sys.exit(2)
    print(f"gateway: {config.openrouter_base_url()}")
    for mid in ids:
        probe(mid)


if __name__ == "__main__":
    main()
