"""Does every model call still get answered with the provider policy of config/models.yaml, and do the two
calls that bypass the chat client (rerank, embeddings) accept the same `provider` block?  (to-do item 24)

    python scripts/probe_provider.py

Reads the `openrouter.provider` block from config/models.yaml (for example data_collection: deny, zdr: true) and:
  1. sends one tiny chat request per chat slot through the app's own client (compliance_agent.models.chat), so
     the request carries exactly what the app sends, and prints which provider answered or the gateway's refusal;
  2. sends one rerank request and one embeddings request WITH the same `provider` block added to the body, and
     reports whether the endpoint accepted it (200), ignored it, or rejected it (4xx) -- the answer decides
     whether the policy can be enforced on those two calls or must be written down as a known gap.
Each call is one short request; the whole probe costs well under a cent.  Reads OPENROUTER_API_KEY and
OPENROUTER_BASE_URL from the environment / .env.  Nothing in the app is changed by running it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from compliance_agent import config, models  # noqa: E402


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.openrouter_api_key()}", "Content-Type": "application/json"}


def probe_chat() -> None:
    routing = models._provider_routing()
    print(f"provider block sent with every chat request: {json.dumps(routing) or '(none)'}\n")
    for slot in models.CHAT_SLOTS:
        spec = models.slot_spec(slot)
        try:
            r = models.chat(slot).invoke("Reply with the single word: ok")
            meta = r.response_metadata or {}
            served = meta.get("model_provider") or meta.get("provider") or meta.get("model_name") or "?"
            text = (r.content if isinstance(r.content, str) else str(r.content)).strip()[:30]
            print(f"  {slot:<13} {spec['model']:<40} answered ({served}): {text!r}")
        except Exception as e:  # noqa: BLE001  -- the gateway's refusal is the result we want to see
            print(f"  {slot:<13} {spec['model']:<40} REFUSED: {str(e)[:160]}")


def _post(path: str, body: dict) -> tuple[int, str]:
    resp = requests.post(f"{config.openrouter_base_url()}{path}", headers=_headers(), json=body, timeout=30)
    return resp.status_code, resp.text[:200].replace("\n", " ")


def probe_rerank(routing: dict) -> None:
    spec = models.slot_spec("reranker")
    body = {"model": spec["model"], "query": "data protection impact assessment", "documents": ["Article 35 DPIA", "Article 6 lawful basis"], "top_n": 1}
    path = spec.get("endpoint", "/rerank")
    plain = _post(path, body)
    with_policy = _post(path, {**body, "provider": routing})
    print(f"\nrerank  {spec['model']}\n  without provider block: {plain[0]}\n  with provider block:    {with_policy[0]}  {with_policy[1] if with_policy[0] != 200 else ''}")
    _verdict(plain[0], with_policy[0])
    if "zdr" in routing and with_policy[0] != 200:
        without_zdr = {k: v for k, v in routing.items() if k != "zdr"}
        r = _post(path, {**body, "provider": without_zdr})
        print(f"  with the block minus zdr ({json.dumps(without_zdr)}): {r[0]}  {r[1] if r[0] != 200 else ''}")
        print("  -> " + ("the reranker accepts the policy without zero data retention: send that reduced block on the rerank call and record that the reranker has no ZDR endpoint." if r[0] == 200
                       else "the reranker refuses even the reduced block: rely on the account settings and record it as a known gap."))


def probe_embeddings(routing: dict) -> None:
    spec = models.slot_spec("embeddings")
    body = {"model": spec["model"], "input": "data protection impact assessment", "dimensions": spec.get("dims")}
    plain = _post("/embeddings", body)
    with_policy = _post("/embeddings", {**body, "provider": routing})
    print(f"\nembeddings  {spec['model']}\n  without provider block: {plain[0]}\n  with provider block:    {with_policy[0]}  {with_policy[1] if with_policy[0] != 200 else ''}")
    _verdict(plain[0], with_policy[0])


def _verdict(plain: int, with_policy: int) -> None:
    if plain == 200 and with_policy == 200:
        print("  -> the endpoint accepts the block: send it on this call too (item 24).")
    elif plain == 200 and with_policy == 404:
        print("  -> the endpoint understood the block but no provider of this model meets the policy (the model has no endpoint with that data policy).")
    elif plain == 200 and with_policy >= 400:
        print("  -> the endpoint rejects the block itself: the policy cannot be sent here; record it as a known gap and rely on the account settings.")
    else:
        print("  -> the call itself fails; check the key, the base URL and the model id first.")


def main() -> int:
    probe_chat()
    routing = models._provider_routing()
    probe_rerank(routing)
    probe_embeddings(routing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
