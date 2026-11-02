"""Model registry: slot name -> client, resolved from config/models.yaml.

Every chat model goes through init_chat_model(model=<id>, model_provider="openai",
base_url=<OpenRouter>, api_key=OPENROUTER_API_KEY). The provider is passed explicitly
because OpenRouter ids contain a slash. Clients are cached per slot (lru_cache).

Nodes never name a model; they call `chat("cheap")`, `embeddings()` or
`structured("cheap", MySchema)`. Resolved ids are exposed through `resolved_model_ids()`
so they can be written into LangSmith run metadata (build step 7).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Type

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

from . import config

CHAT_SLOTS = ("worker_full", "worker_quick", "cheap", "grader", "judge")


def _slot(name: str) -> dict[str, Any]:
    slots = config.models_config().get("slots", {})
    if name not in slots:
        raise config.ConfigError(f"Unknown model slot '{name}'. Known: {sorted(slots)}")
    return slots[name]


def _provider_routing() -> dict[str, Any]:
    routing = dict(config.models_config().get("openrouter", {}).get("provider", {}) or {})
    if not routing.get("only"):
        routing.pop("only", None)
    return routing


def _default_headers() -> dict[str, str]:
    title = config.models_config().get("openrouter", {}).get("app_title", "compliance-assistant")
    return {"HTTP-Referer": "http://localhost:8501", "X-Title": title}


@lru_cache(maxsize=None)
def chat(slot: str) -> BaseChatModel:
    """Chat model for a slot: worker_full | worker_quick | cheap | grader | judge (evaluation only)."""
    if slot not in CHAT_SLOTS:
        raise config.ConfigError(f"'{slot}' is not a chat slot; chat slots are {CHAT_SLOTS}")
    spec = _slot(slot)
    extra_body: dict[str, Any] = {}
    routing = _provider_routing()
    if routing:
        extra_body["provider"] = routing
    return init_chat_model(
        model=spec["model"],
        model_provider="openai",
        base_url=config.openrouter_base_url(),
        api_key=config.openrouter_api_key(),
        temperature=spec.get("temperature", 0.0),
        max_tokens=spec.get("max_tokens"),
        default_headers=_default_headers(),
        extra_body=extra_body or None,
    )


def structured(slot: str, schema: Type[BaseModel]):
    """`chat(slot).with_structured_output(schema)` (json_schema mode)."""
    return chat(slot).with_structured_output(schema)


def invoke_structured(slot: str, schema: Type[BaseModel], messages: Any) -> BaseModel:
    """Invoke with structured output; if the model rejects json_schema mode, retry with
    the configured fallback method (function_calling). Raises if both fail."""
    fallback = config.models_config().get("structured_output", {}).get("fallback_method")
    try:
        result = structured(slot, schema).invoke(messages)
        if result is not None:
            return result
        raise ValueError("structured output returned None")
    except Exception:
        if not fallback:
            raise
        result = chat(slot).with_structured_output(schema, method=fallback).invoke(messages)
        if result is None:
            raise ValueError(f"model for slot '{slot}' returned no structured output")
        return result


@lru_cache(maxsize=1)
def embeddings() -> OpenAIEmbeddings:
    spec = _slot("embeddings")
    routing = _provider_routing()   # the same provider policy as the chat calls; the gateway accepts it on /embeddings (probe 2 Nov)
    return OpenAIEmbeddings(
        model=spec["model"],
        base_url=config.openrouter_base_url(),
        api_key=config.openrouter_api_key(),
        dimensions=spec.get("dims"),
        default_headers=_default_headers(),
        check_embedding_ctx_length=False,  # OpenRouter does not accept token-array input
        model_kwargs={"provider": routing} if routing else {},
    )


def embedding_dims() -> int:
    return int(_slot("embeddings")["dims"])


def embedding_model_id() -> str:
    return str(_slot("embeddings")["model"])


def slot_spec(name: str) -> dict[str, Any]:
    """Raw YAML spec for a slot (reranker, router and grader read their own sub-keys)."""
    return _slot(name)


def pricing() -> dict[str, dict[str, float]]:
    """slot -> {input, output} USD per 1M tokens, for the run-stats estimate (slots without a price are skipped)."""
    out: dict[str, dict[str, float]] = {}
    for name, spec in config.models_config().get("slots", {}).items():
        if isinstance(spec.get("price"), dict):
            out[name] = {k: float(v) for k, v in spec["price"].items()}
    return out


def resolved_model_ids() -> dict[str, str]:
    """slot -> model id, for LangSmith run metadata."""
    slots = config.models_config().get("slots", {})
    out: dict[str, str] = {}
    for name, spec in slots.items():
        if "model" in spec:
            out[name] = spec["model"]
        elif "implementation" in spec:
            impl = spec["implementation"]
            sub = spec.get(impl, {})
            out[name] = sub.get("model") or f"{impl}:{sub.get('slot', '?')}"
    return out


# Which graph node (or step inside a node) uses which slot: for the UI's "Models per node" list and the README table.
NODE_SLOTS: list[tuple[str, str]] = [
    ("validate_input", "cheap"),
    ("route", "router"),
    ("direct_answer", "worker_quick"),
    ("direct_answer · embeddings", "embeddings"),
    ("direct_answer · reranker", "reranker"),
    ("worker", "worker_full"),
    ("worker · search_regulation · embeddings", "embeddings"),
    ("worker · search_regulation · reranker", "reranker"),
    ("worker · search_regulation · grader", "grader"),
    ("worker · search_regulation · rewrite", "cheap"),
    ("worker · summariser", "cheap"),
    ("reviser", "worker_full"),
    ("memory_write · reflect", "cheap"),
]


def node_models() -> dict[str, str]:
    """node -> model name, e.g. 'worker': 'GPT-6 Luna'. The slot each node uses is NODE_SLOTS (README 3.2)."""
    slots = config.models_config().get("slots", {})
    ids = resolved_model_ids()
    out: dict[str, str] = {}
    for node, slot in NODE_SLOTS:
        spec = slots.get(slot, {})
        if "implementation" in spec:
            impl = spec["implementation"]
            sub = spec.get(impl, {})
            name = sub.get("name") or (slots.get(sub.get("slot", ""), {}).get("name") if sub.get("slot") else None) or ids.get(slot, "?")
        else:
            name = spec.get("name") or ids.get(slot, "?")
        out[node] = name
    return out
