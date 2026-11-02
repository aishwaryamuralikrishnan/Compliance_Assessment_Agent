"""Find the exact ids of the embedding and rerank models, which /models does not list.

    python scripts/probe_models.py

Sends one tiny request per candidate id to the gateway's /embeddings and /rerank
endpoints and reports which ids answer. Costs a fraction of a cent in total.
Paste the output back; the winning ids go into config/models.yaml.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from compliance_agent import config  # noqa: E402

EMBEDDING_CANDIDATES = [
    "openai/text-embedding-3-small",
    "openai/text-embedding-3-large",
    "text-embedding-3-small",
    "qwen/qwen3-embedding-8b",
]
RERANK_CANDIDATES = [
    "cohere/rerank-4-fast",
    "cohere/rerank-v4-fast",
    "cohere/rerank-v4.0-fast",
    "cohere/rerank-4.0-fast",
    "cohere/rerank-fast-4",
    "cohere/rerank-4-pro",
    "cohere/rerank-v4.0-pro",
    "cohere/rerank-v3.5",
]
RERANK_PATHS = ["/rerank", "/v1/rerank", "/rerankers"]


def main() -> None:
    base = config.openrouter_base_url()
    headers = {"Authorization": f"Bearer {config.openrouter_api_key()}", "Content-Type": "application/json"}

    print(f"gateway: {base}\n")
    print("== embeddings (POST /embeddings) ==")
    for mid in EMBEDDING_CANDIDATES:
        try:
            r = requests.post(f"{base}/embeddings", headers=headers, timeout=30,
                              json={"model": mid, "input": ["automated decision-making"]})
            if r.ok:
                dims = len(r.json()["data"][0]["embedding"])
                print(f"  OK    {mid:<40} {dims} dims")
            else:
                print(f"  {r.status_code:<5} {mid:<40} {r.text[:90].replace(chr(10), ' ')}")
        except Exception as exc:
            print(f"  ERR   {mid:<40} {exc}")

    print("\n== rerank ==")
    docs = ["The data subject shall have the right not to be subject to a decision based solely on automated processing.",
            "This Regulation applies to the processing of personal data wholly or partly by automated means.",
            "Member States shall provide for one or more independent public authorities."]
    for path in RERANK_PATHS:
        print(f"-- POST {path}")
        any_ok = False
        for mid in RERANK_CANDIDATES:
            try:
                r = requests.post(f"{base}{path}", headers=headers, timeout=30,
                                  json={"model": mid, "query": "automated decision making", "documents": docs, "top_n": 2})
                if r.ok:
                    body = r.json()
                    results = body.get("results") or body.get("data") or body
                    print(f"  OK    {mid:<40} -> {str(results)[:120]}")
                    any_ok = True
                elif r.status_code == 404 and "model" not in r.text.lower():
                    print(f"  404   path not served ({r.text[:60].replace(chr(10), ' ')}); trying next path")
                    break
                else:
                    print(f"  {r.status_code:<5} {mid:<40} {r.text[:90].replace(chr(10), ' ')}")
            except Exception as exc:
                print(f"  ERR   {mid:<40} {exc}")
        if any_ok:
            break


if __name__ == "__main__":
    main()
