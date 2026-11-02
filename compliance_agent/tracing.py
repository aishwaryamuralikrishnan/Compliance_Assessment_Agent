"""LangSmith tagging (step 7).

Tracing itself is switched on by environment variables (LANGSMITH_TRACING=true, LANGSMITH_API_KEY,
LANGSMITH_PROJECT) - LangChain / LangGraph then trace every model call, tool call and node without
any code here. What this module adds is the per-run labelling the project asks for:

  - `graph.run_config` names the root run (`compliance_turn`, `compliance_feedback`), fixes its run id
    (so feedback can be attached later) and tags it with the role and user up front;
  - nodes call `tag_run(...)` for what is only known mid-run: the route and its confidence, the worker
    model actually used, an interrupt, a denied tool, a guardrail regeneration. The tags are added to
    the in-memory root RunTree, which LangSmith receives when the run closes - no extra API call;
  - `graph.send_feedback` posts the thumbs score as `user_score` on that run id.

Everything here is a no-op when tracing is off, and never raises into the graph.
"""
from __future__ import annotations

from typing import Any

from . import config


def _root_run_trees():
    """The root RunTree(s) of the current trace, reached through the LangChain tracer's run map."""
    try:
        from langchain_core.tracers.langchain import LangChainTracer
        from langgraph.config import get_config
        from langsmith import get_current_run_tree

        rt = get_current_run_tree()
        if rt is None:
            return []
        cm = get_config().get("callbacks")
        handlers = list(getattr(cm, "handlers", []) or []) + list(getattr(cm, "inheritable_handlers", []) or [])
        seen, roots = set(), []
        for h in handlers:
            if isinstance(h, LangChainTracer) and id(h) not in seen:
                seen.add(id(h))
                root = h.run_map.get(str(rt.trace_id))
                if root is not None:
                    roots.append(root)
        return roots
    except Exception:
        return []


def tag_run(*tags: str, **metadata: Any) -> bool:
    """Add tags / metadata to the root run of the current turn. Returns True if a run was tagged."""
    if not config.langsmith_enabled():
        return False
    roots = _root_run_trees()
    for root in roots:
        try:
            have = list(root.tags or [])
            root.tags = have + [t for t in tags if t and t not in have]
            if metadata:
                root.extra.setdefault("metadata", {}).update({k: v for k, v in metadata.items() if v is not None})
        except Exception:
            continue
    return bool(roots)


def current_root_run_id() -> str | None:
    try:
        from langsmith import get_current_run_tree

        rt = get_current_run_tree()
        return str(rt.trace_id) if rt is not None else None
    except Exception:
        return None
