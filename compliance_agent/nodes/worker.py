"""worker: the create_agent subgraph.

Model: the worker_full slot. Tools: every business tool; RoleToolsMiddleware narrows them
per role at each model call and ToolGateMiddleware re-checks each call. Middleware stack:
PII redaction (input), summarisation of long threads (cheap slot), a per-run tool-call
budget, then the role binding and the gate. Structured output: Assessment | StatusReply.
"""
from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import PIIMiddleware
from langchain.agents.structured_output import ToolStrategy

from .. import models
from ..state import Assessment, StatusReply
from ..tools import ALL_TOOLS
from .middleware import WORKER_PROMPT, RoleToolsMiddleware, ToolBudgetMiddleware, ToolGateMiddleware, TracedSummarizationMiddleware

PHONE_PATTERN = r"(?<![\w/])\+?\d[\d\s().-]{8,}\d(?![\w/])"
TOOL_CALL_RUN_LIMIT = 14          # loop budget per turn; the agent is asked to finish when reached


def _middleware(agent: str, base_prompt: str) -> list:
    cheap = models.chat("cheap")
    return [
        PIIMiddleware("email", strategy="redact"),
        PIIMiddleware("credit_card", strategy="mask"),
        PIIMiddleware("ip", strategy="redact"),
        PIIMiddleware("phone", detector=PHONE_PATTERN, strategy="redact"),
        # Only genuinely long threads are condensed: a single assessment with a handful of searches stays well
        # under this (the heavy model's context is 1M tokens), so the original request is never summarised away.
        TracedSummarizationMiddleware(model=cheap, trigger=("tokens", 60000), keep=("messages", 24), agent=agent),
        ToolBudgetMiddleware(run_limit=TOOL_CALL_RUN_LIMIT, exit_behavior="continue"),   # real tools only, not the structured output
        RoleToolsMiddleware(base_prompt=base_prompt, agent=agent),
        ToolGateMiddleware(),
    ]


def _response_format() -> ToolStrategy:
    """Assessment | StatusReply as a tool call. The tool message that answers the structured-output call is kept
    short: the agent would otherwise echo the whole Assessment back into the history, which doubles what every later
    call (the review request, a regeneration, a revision) has to carry."""
    try:
        return ToolStrategy(Assessment | StatusReply, tool_message_content="Structured output received.")
    except TypeError:                                   # older langchain without the keyword
        return ToolStrategy(Assessment | StatusReply)


@lru_cache(maxsize=1)
def build_worker():
    """The assessing agent: searches broadly and writes the full picture."""
    return create_agent(
        model=models.chat("worker_full"),
        tools=ALL_TOOLS,
        system_prompt=WORKER_PROMPT,
        middleware=_middleware("worker", WORKER_PROMPT),
        response_format=_response_format(),
        name="worker",
    )


@lru_cache(maxsize=1)
def build_reviser():
    """The revising agent: same machinery (model slot, tools, gate, guardrail) with its own instructions. It takes
    v1, the DPO's requested changes and the product manager's revised description, and produces v2: the legal
    consequence of what changed, finding by finding, with everything else carried over unchanged."""
    from .reviser import REVISER_PROMPT

    return create_agent(
        model=models.chat("worker_full"),
        tools=ALL_TOOLS,
        system_prompt=REVISER_PROMPT,
        middleware=_middleware("reviser", REVISER_PROMPT),
        response_format=_response_format(),
        name="reviser",
    )
