"""Middleware that lives on the worker subgraph.

RoleToolsMiddleware  (wrap_model_call)
    Binds only the tools the current role may call and builds the system prompt for this
    call: base instructions + long-term memory (org facts, lessons, this user's prefs).

ToolGateMiddleware   (wrap_tool_call)   -- the "tool_gate" of the architecture
    Re-checks the permission on every call (defence in depth), detects repeated identical
    calls (doom-loop exit), creates the DPO review task and pauses with interrupt() for
    request_dpo_review, and applies the DPO's decision (approve -> record in register, reject)
    when the thread resumes under the DPO's identity. No worker tool writes the register.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_config, get_stream_writer
from langgraph.types import interrupt

from .. import auth, memory, repo, tracing

log = logging.getLogger(__name__)

MAX_IDENTICAL_CALLS = 2


def _cfg() -> dict[str, Any]:
    try:
        return get_config().get("configurable", {}) or {}
    except Exception:
        return {}


def _writer() -> Callable[[dict], None]:
    try:
        return get_stream_writer()
    except Exception:
        return lambda _e: None


SUMMARY_PROMPT = """You condense the older part of a compliance assistant's working thread so the assistant can carry on.
The user's request itself is kept in the thread unchanged; do not repeat it. Write a replacement for the messages
below with exactly these sections:

## DELIVERABLE
What is still owed: for a feature description, the Assessment structured output (verdict, findings with
citations, next steps, flags); for anything else, the StatusReply. State plainly that it has NOT been
produced yet if that is the case.

## FINDINGS SO FAR
The provisions retrieved so far with their exact citation labels (e.g. "GDPR Art. 22(1)"), register lookups
and their results, and conclusions already reached. Keep every citation label exactly as returned.

Respond ONLY with these sections.

<messages>
{messages}
</messages>"""

REQUEST_KIND = "request"           # additional_kwargs["kind"] on the human message that carries the user's request or the revision brief
SUMMARY_INPUT_TOKENS = 12000       # how much of the older part the cheap model reads when it condenses (the stock default is 4000)


def is_request(m: Any) -> bool:
    return isinstance(m, HumanMessage) and (m.additional_kwargs or {}).get("kind") == REQUEST_KIND


STRUCTURED_OUTPUT_NAMES = ("Assessment", "StatusReply")


class ToolBudgetMiddleware(ToolCallLimitMiddleware):
    """The stock per-run tool-call budget, counting real tools only. The structured output (Assessment / StatusReply)
    is delivered as a tool call too, and the stock middleware would count and, on the 15th call, block it with a
    second tool message for the same call id, which strict providers reject in the next request."""

    def _separate_tool_calls(self, tool_calls, thread_count, run_count):
        real = [tc for tc in tool_calls if tc.get("name") not in STRUCTURED_OUTPUT_NAMES]
        return super()._separate_tool_calls(real, thread_count, run_count)


class TracedSummarizationMiddleware(SummarizationMiddleware):
    """The stock summariser, with three changes for this project:

    - the user's request (the feature description, or the revision brief) is never summarised away: when the older
      part of a thread is condensed, the latest request message is pinned in front of the summary, verbatim, so the
      agent always still has the thing it is working on;
    - the cheap model that writes the summary sees that request plus a larger tail of the older part (the stock
      middleware feeds it only the last 4000 tokens, which for a long thread never contain the request);
    - a project summary prompt (deliverable still owed, findings so far with exact citation labels) and one trace
      event when a thread is actually condensed."""

    def __init__(self, *args, agent: str = "worker", **kwargs):
        kwargs.setdefault("summary_prompt", SUMMARY_PROMPT)
        kwargs.setdefault("trim_tokens_to_summarize", SUMMARY_INPUT_TOKENS)
        self.agent = agent
        super().__init__(*args, **kwargs)

    @staticmethod
    def _latest_request(messages: list) -> Any:
        return next((m for m in reversed(messages or []) if is_request(m)), None)

    def _trim_messages_for_summary(self, messages: list) -> list:
        request = self._latest_request(messages)
        tail = super()._trim_messages_for_summary([m for m in messages if m is not request])
        return ([request] if request is not None else []) + list(tail)

    def _report(self, state, result):
        if result and result.get("messages"):
            request = self._latest_request(state["messages"])
            msgs = result["messages"]
            pinned = request is not None and not any(getattr(m, "id", None) == request.id for m in msgs[1:])
            if pinned:
                msgs.insert(1, request)                               # [RemoveMessage, request, summary, *kept]
            kept = max(0, len(msgs) - (3 if pinned else 2))           # minus RemoveMessage, the summary and the pinned request
            older = max(0, len(state["messages"]) - kept - (1 if pinned else 0))
            _writer()({"node": self.agent, "event": "summarised", "older": older, "kept": kept, "request_pinned": pinned})
        return result

    def before_model(self, state, runtime):
        return self._report(state, super().before_model(state, runtime))

    async def abefore_model(self, state, runtime):
        return self._report(state, await super().abefore_model(state, runtime))


# --------------------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------------------

WORKER_PROMPT = """You are the Compliance Assistant of an EU company. Your goal is an assessment of a planned
feature or data-processing activity against the GDPR and the EU AI Act that a Data Protection
Officer can approve and record in the organisation's processing register.

How to work:
1. Check the register first (lookup_register) so you can say when something is already registered.
2. Retrieve the law with search_regulation, ONE focused topic per call (about 10 words; several calls
   run in parallel) - never bundle topics into one long query. Typical topics for a feature:
   legal basis (GDPR Art. 6), automated decisions and profiling (GDPR Art. 22, Rec. 71), transparency
   (Art. 13/14), data minimisation and retention (Art. 5), special categories (Art. 9), DPIA (Art. 35),
   international transfers (Art. 44-49), and for AI: prohibited practices (AI Act Art. 5), high-risk
   classification (Art. 6, Annex III), provider/deployer obligations (Art. 16, 26, 27), transparency (Art. 50).
   Use get_article when you already know the provision you need to quote.
3. Cite ONLY the citation labels the tools returned, verbatim, e.g. "GDPR Art. 22(1)", "GDPR Rec. 71",
   "AI Act Art. 6(2)", "AI Act Annex III point 5". Never invent article numbers. Every finding needs
   at least one citation. Cite the most specific label the tools returned for the rule you rely on:
   "GDPR Art. 5(1)(c)" rather than "GDPR Art. 5", "GDPR Art. 6(1)(f)" or "6(4)" rather than "Art. 6",
   "AI Act Annex III point 5" rather than "Annex III" - a bare article number does not say which rule
   applies. The output is checked against the corpus and sent back if a citation is unknown.
4. Apply the organisation facts from memory: something the organisation already covers is a
   "Covered" finding that cites the provision and the fact. Lessons from earlier DPO decisions are
   the organisation's standing positions: apply them as requirements, state the concrete limit or
   severity they set (e.g. "retention must not exceed two years"), and do not describe them as
   lessons, memory or DPO notes - the DPO already knows where they come from.
5. Output: a feature description ALWAYS ends in an Assessment (findings tagged Blocker / Required /
   Covered, blockers first; verdict; concrete next steps; DPIA flag; high-risk-AI flag) - never in a
   summary, an acknowledgement or a request for more detail: assess with what you have and put the
   open questions into next_steps. Address every data source the description names (e.g. browsing
   behaviour, device data, purchase history), each as its own finding where the law treats it
   differently - do not fold them into one. A StatusReply is only for a status question, a register
   or review action, or when the activity is already recorded in the register (say which entry).
   Severity means: Blocker = the feature as described is unlawful or prohibited and must change before
   it can be built (a solely automated decision without the Art. 22 safeguards, a prohibited AI practice,
   special-category data without an Art. 9 ground, a transfer with no lawful basis); Required = an
   obligation the team must fulfil before launch while the design stands (a contract, a notice, a DPIA or
   an impact assessment, a legal basis to document, data to minimise) - never raise such paperwork to a
   Blocker; Covered = already handled, by the design or by an organisation fact. One finding carries one
   severity: never put a Covered point and a Required point in the same finding - write two.
6. Never include personal names, e-mail addresses or other personal data of individuals in the output.
   This is an automated first assessment, not legal advice; the DPO decides.

Register and approval: an assessment becomes an organisational record only after the DPO approves it.
When asked to request review, call request_dpo_review(assessment_id) with the assessment id shown to the
user (e.g. A-0012); the DPO's approval writes the register. Never state that something is recorded unless
a tool result says so.
"""

ROLE_NOTES = {
    "product_manager": "The current user is a product manager: they can request assessments, which are sent to the "
                       "DPO for review automatically, but cannot write to the register. If they ask for that, "
                       "explain that only the DPO's approval records an assessment.",
    "dpo": "The current user is the Data Protection Officer.",
}


def repair_tool_pairs(messages: list) -> tuple[list, list[str]]:
    """Make the history acceptable to strict providers (Mistral rejects a request unless every assistant tool call is
    answered by exactly one tool message, in order, before any other message). Returns (messages, repairs): a copy
    where an unanswered tool call gets a synthetic tool message saying so, and an orphan tool message is dropped.

    The check counts what the provider will actually see. langchain sends an assistant message's *invalid* tool calls
    (malformed or cut-off JSON, typically an Assessment that hit the output token limit) as ordinary tool calls, so
    they need an answer too; one without an id cannot be answered and is removed from the message. A tool call id
    repeated inside one assistant message is sent once. Nothing is invented about the content: the synthetic message
    states that no result was recorded. Every repair is logged and reported in the trace, because it means something
    upstream left the thread inconsistent."""
    out: list = []
    repairs: list[str] = []
    pending: list[tuple[str, str]] = []          # (tool_call_id, name) awaiting a ToolMessage
    answered: set[str] = set()

    def flush(reason: str) -> None:
        for cid, name in pending:
            out.append(ToolMessage(content="(no result was recorded for this call)", tool_call_id=cid, name=name, status="error"))
            repairs.append(f"unanswered tool call {name}#{cid} {reason}")
        pending.clear()

    for m in messages:
        if isinstance(m, ToolMessage):
            ids = [cid for cid, _ in pending]
            if m.tool_call_id in ids:
                pending.pop(ids.index(m.tool_call_id))
                answered.add(m.tool_call_id)
                out.append(m)
            elif m.tool_call_id in answered:
                repairs.append(f"second tool result for {m.tool_call_id} dropped (the call was already answered)")
            else:
                repairs.append(f"orphan tool message {m.tool_call_id} dropped")
            continue
        calls = list(getattr(m, "tool_calls", None) or [])
        invalid = list(getattr(m, "invalid_tool_calls", None) or [])
        if calls or invalid:
            flush("before the next assistant message")
            seen: set[str] = set()
            kept_calls, kept_invalid = [], []
            for tc in calls:
                cid = tc.get("id") or ""
                if cid in seen:
                    repairs.append(f"duplicate tool call id {cid} sent once")
                    continue
                seen.add(cid)
                kept_calls.append(tc)
            for tc in invalid:
                cid = tc.get("id") or ""
                if not cid:
                    repairs.append(f"malformed tool call {tc.get('name') or '?'} without an id removed")
                    continue
                if cid in seen:
                    repairs.append(f"duplicate tool call id {cid} sent once")
                    continue
                seen.add(cid)
                kept_invalid.append(tc)
            if len(kept_calls) != len(calls) or len(kept_invalid) != len(invalid):
                m = m.model_copy(update={"tool_calls": kept_calls, "invalid_tool_calls": kept_invalid})
            out.append(m)
            pending.extend((tc.get("id") or "", tc.get("name") or "") for tc in kept_calls + kept_invalid)
            continue
        if pending:
            flush("before a non-tool message")
        out.append(m)
    flush("at the end of the history")
    return out, repairs


def describe_history(messages: list) -> str:
    """One line per message with what matters to a provider's order check: role, tool call ids (malformed ones marked
    with !), tool_call_id of tool messages, content length. Used in the log and the trace when a provider rejects
    a request, so the cause can be read off without the full payload."""
    lines = []
    for i, m in enumerate(messages):
        kind = type(m).__name__.replace("Message", "").lower()
        content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
        bits = [f"{i:02d} {kind:<6} len={len(content or '')}"]
        calls = [f"{tc.get('name')}#{tc.get('id')}" for tc in (getattr(m, "tool_calls", None) or [])]
        calls += [f"!{tc.get('name')}#{tc.get('id')}" for tc in (getattr(m, "invalid_tool_calls", None) or [])]
        if calls:
            bits.append("calls=" + ",".join(calls))
        if isinstance(m, ToolMessage):
            bits.append(f"answers={m.tool_call_id}")
        fr = (getattr(m, "response_metadata", None) or {}).get("finish_reason")
        if fr and fr != "stop":
            bits.append(f"finish={fr}")
        lines.append(" ".join(bits))
    return "\n".join(lines)


class RoleToolsMiddleware(AgentMiddleware):
    """Per-role tool binding and dynamic system prompt with long-term memory.

    `base_prompt` is the agent's own instructions (the worker's or the reviser's); `agent` names the node in
    trace events so the two agents are told apart in the text flow and the live graph."""

    def __init__(self, base_prompt: str | None = None, agent: str = "worker") -> None:
        super().__init__()
        self._memory_cache: dict[tuple[str, str], dict] = {}
        self.base_prompt = base_prompt or WORKER_PROMPT
        self.agent = agent

    def _recall(self, request: ModelRequest, user_id: str, thread_id: str) -> dict:
        query = ""
        for m in reversed(request.messages):
            if isinstance(m, HumanMessage):
                query = m.content if isinstance(m.content, str) else str(m.content)
                break
        key = (thread_id, query[:200])
        if key in self._memory_cache:
            return self._memory_cache[key]
        store = request.runtime.store if request.runtime else None
        mem = {"org_facts": [], "lessons": [], "prefs": []}
        if store is None:
            mem["unavailable"] = "no store attached to this run"
        else:
            try:
                mem = memory.recall(store, user_id, query or "compliance assessment")
            except Exception as exc:
                # Never silently run with empty memory: log the real error and say so in the trace.
                log.warning("memory recall failed for user %s: %s: %s", user_id, type(exc).__name__, exc)
                mem["unavailable"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        if mem.get("unavailable"):
            _writer()({"node": self.agent, "event": "memory_unavailable", "error": mem["unavailable"]})
        self._memory_cache[key] = mem
        if len(self._memory_cache) > 200:
            self._memory_cache.pop(next(iter(self._memory_cache)))
        return mem

    def wrap_model_call(self, request: ModelRequest, handler):
        cfg = _cfg()
        role = cfg.get("role", "product_manager")
        user_id = cfg.get("user_id", "unknown")
        thread_id = cfg.get("thread_id", "")
        allowed = auth.allowed_tools(role)
        tools = [t for t in (request.tools or []) if _tool_name(t) in allowed or _tool_name(t) is None]
        mem = self._recall(request, user_id, thread_id)
        system = (
            self.base_prompt
            + "\n" + ROLE_NOTES.get(role, "")
            + "\n\nLong-term memory:\n" + memory.format_for_prompt(mem)
        )
        messages, repairs = repair_tool_pairs(list(request.messages))
        if repairs:
            log.warning("message history repaired before the %s model call (thread %s): %s\nhistory received:\n%s",
                        self.agent, thread_id, "; ".join(repairs), describe_history(list(request.messages)))
            _writer()({"node": self.agent, "event": "history_repaired", "repairs": repairs})
        _writer()({
            "node": self.agent, "event": "model_call", "role": role,
            "tools": sorted(_tool_name(t) for t in tools if _tool_name(t)),
            "memories": {k: len(v) for k, v in mem.items() if isinstance(v, list)},
            "memory_unavailable": mem.get("unavailable"),
        })
        try:
            response = handler(request.override(messages=messages, tools=tools, system_message=SystemMessage(content=system)))
        except Exception as exc:
            # A provider's rejection of the request is about the history we sent: write that history's shape to the
            # log and the trace so the cause is visible, then let the error surface.
            if "400" in str(exc) or "BadRequest" in type(exc).__name__:
                shape = describe_history(messages)
                log.error("the %s model call was rejected (thread %s): %s\nhistory sent:\n%s", self.agent, thread_id, exc, shape)
                _writer()({"node": self.agent, "event": "request_rejected", "error": str(exc)[:300], "history": shape})
                try:
                    exc.add_note("history sent to the model (role, tool calls, answered call id):\n" + shape)
                except Exception:
                    pass
            raise
        return self._settle_output(response)

    def _settle_output(self, response):
        """Keep the thread consistent when the model's structured output could not be used. A tool call whose JSON
        is malformed or cut off at the output token limit (finish_reason "length") never becomes an Assessment;
        langchain keeps it on the message as an *invalid* tool call and still sends it to the provider as a tool
        call. Answer it here, at once, with a tool message that says so: then every later request carries a
        balanced history whatever the provider or the langchain version, and the trace says what happened instead
        of only showing the guardrail sending the draft back."""
        try:
            msgs = list(getattr(response, "result", None) or [])
            ai = next((m for m in msgs if isinstance(m, AIMessage)), None)
            if ai is None:
                return response
            fr = (getattr(ai, "response_metadata", None) or {}).get("finish_reason")
            invalid = list(getattr(ai, "invalid_tool_calls", None) or [])
            if fr != "length" and not invalid:
                return response
            names = [tc.get("name") or "?" for tc in invalid]
            reason = "output cut off at the token limit" if fr == "length" else "malformed tool call JSON"
            log.warning("%s model output unusable: %s (%s)", self.agent, reason, ", ".join(names) or "no tool call")
            _writer()({"node": self.agent, "event": "output_unusable", "reason": reason, "calls": names,
                       "error": (invalid[0].get("error") or "")[:200] if invalid else ""})
            answered = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
            answers = [ToolMessage(content=f"The {tc.get('name') or 'tool'} call could not be used: {reason}. Produce it again.",
                                   tool_call_id=tc["id"], name=tc.get("name") or "tool", status="error")
                       for tc in invalid if tc.get("id") and tc["id"] not in answered]
            if not answers:
                return response
            return ModelResponse(result=msgs + answers, structured_response=getattr(response, "structured_response", None))
        except Exception as exc:                        # never let the bookkeeping break the run
            log.warning("could not settle the %s model output: %s", self.agent, exc)
            return response


def _tool_name(t: Any) -> str | None:
    if isinstance(t, dict):
        return t.get("name") or (t.get("function") or {}).get("name")
    return getattr(t, "name", None)


# --------------------------------------------------------------------------------------
# Tool gate
# --------------------------------------------------------------------------------------

class ToolGateMiddleware(AgentMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self._seen: Counter = Counter()

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        tc = request.tool_call
        name, args, call_id = tc["name"], tc.get("args", {}) or {}, tc["id"]
        cfg = _cfg()
        user_id, role, thread_id = cfg.get("user_id", "unknown"), cfg.get("role", "unknown"), cfg.get("thread_id", "")
        say = _writer()
        kind = auth.tool_kind(name)

        def reply(content: str, status: str = "success") -> ToolMessage:
            return ToolMessage(content=content, tool_call_id=call_id, name=name, status=status)

        # doom-loop exit: the same call with the same arguments, again and again
        sig = (thread_id, name, json.dumps(args, sort_keys=True, default=str))
        self._seen[sig] += 1
        if self._seen[sig] > MAX_IDENTICAL_CALLS:
            say({"node": "tool_gate", "event": "repeat_call", "tool": name, "count": self._seen[sig]})
            tracing.tag_run("gate:doom_loop_exit", f"tool:{name}")
            return reply(
                f"You already called {name} with these exact arguments {self._seen[sig] - 1} times. "
                f"Use the earlier result; do not repeat the call. Finish the answer with what you have.",
                "error",
            )

        # permission (re-checked here even though the model only saw its allowed tools). A resumed
        # request_dpo_review runs under the DPO's identity, so its permission is the requester's, checked
        # when the task was created (see _request_review).
        if name == "request_dpo_review":
            return self._request_review(args, call_id, user_id, role, thread_id, say, reply)
        if not auth.is_allowed(role, name):
            say({"node": "tool_gate", "event": "denied", "tool": name, "role": role, "tool_kind": kind})
            tracing.tag_run("gate:denied", f"tool:{name}", denied_tool=name)
            return reply(auth.denied_message(role, name), "error")

        say({"node": "tool_gate", "event": "allowed", "tool": name, "tool_kind": kind, "role": role})
        tracing.tag_run(f"tool:{name}")
        return handler(request)

    # -- request_dpo_review: create task, pause, apply the DPO decision --------------------

    def _request_review(self, args, call_id, user_id, role, thread_id, say, reply):
        name = "request_dpo_review"
        if repo.review_task_for_thread(thread_id, status="pending") is None and not auth.is_allowed(role, name):
            say({"node": "tool_gate", "event": "denied", "tool": name, "role": role, "tool_kind": "write"})
            tracing.tag_run("gate:denied", f"tool:{name}", denied_tool=name)
            return reply(auth.denied_message(role, name), "error")
        assessment_id = str(args.get("assessment_id", "")).strip().upper()
        a = repo.get_assessment(assessment_id) if assessment_id else None
        if a is None:
            latest = repo.latest_assessment_for_thread(thread_id)
            if latest is None:
                return reply(f"No assessment '{assessment_id}' exists yet. Produce the assessment first, then request review.", "error")
            a, assessment_id = latest, latest["assessment_id"]
        if a["status"] == "recorded":
            return reply(f"{assessment_id} is already recorded in the register; nothing to review.")
        task = repo.create_review_task(thread_id, assessment_id, user_id)
        say({"node": "tool_gate", "event": "pause", "tool": "request_dpo_review", "tool_kind": "write",
             "task_id": task["id"], "assessment_id": assessment_id, "requested_by": task["requested_by"],
             "resumed_by": user_id if user_id != task["requested_by"] else None})
        tracing.tag_run("gate:interrupt", "tool:request_dpo_review", interrupt_type="dpo_review", review_task=task["id"], assessment_id=assessment_id)
        decision = interrupt({
            "type": "dpo_review", "task_id": task["id"], "assessment_id": assessment_id, "title": a["title"],
            "requested_by": task["requested_by"], "thread_id": thread_id, "assessment": a["assessment"],
        }) or {}

        resumer = _cfg()
        r_id, r_role = resumer.get("user_id", "unknown"), resumer.get("role", "unknown")
        if not auth.can_approve(r_role):
            say({"node": "tool_gate", "event": "rejected", "tool": "request_dpo_review", "by": r_id, "reason": "not an approver"})
            return reply(f"Only the DPO can decide on review task #{task['id']}; it stays pending.", "error")

        verdict = str(decision.get("decision", "")).lower()
        comment = decision.get("comment") or ""
        amended = decision.get("assessment")
        memory_items = decision.get("memory_items") or []      # what the DPO ticked; memory_write applies the role gate
        tracing.tag_run(f"decision:{verdict if verdict in ('approve', 'request_changes') else 'reject'}", *(["decision:amended"] if amended else []),
                        decided_by=r_id, review_task=task["id"], assessment_id=assessment_id, amended=bool(amended))
        if verdict == "approve":
            if amended:
                repo.update_assessment(assessment_id, assessment=amended)
            repo.resolve_review_task(task["id"], "approved", r_id, comment, amended, memory_items)
            row = repo.record_in_register(assessment_id, approved_by=r_id, requested_by=task["requested_by"])
            say({"node": "tool_gate", "event": "approved", "tool": "request_dpo_review", "by": r_id,
                 "assessment_id": assessment_id, "amended": bool(amended), "register_id": row["assessment_id"]})
            return reply(
                f"The DPO ({r_id}) approved assessment {assessment_id}"
                + (" with amendments" if amended else "")
                + f" and it has been recorded in the processing register as {row['assessment_id']}."
                + (f" DPO comment: {comment}" if comment else "")
                + " Report this outcome to the user in two sentences."
            )
        if verdict == "request_changes" and comment.strip():
            # The feature itself must change. Nothing is recorded; the requester revises the description and a
            # revision run (the reviser agent) produces v2, which comes back here as a new review request.
            repo.resolve_review_task(task["id"], "changes_requested", r_id, comment, None, memory_items)
            repo.update_assessment(assessment_id, status="changes_requested")
            say({"node": "tool_gate", "event": "changes_requested", "tool": "request_dpo_review", "by": r_id,
                 "assessment_id": assessment_id, "comment": comment})
            return reply(f"The DPO ({r_id}) requested changes to the feature before assessment {assessment_id} can be approved. "
                         f"Requested changes: {comment} Nothing was recorded. Tell the user what must change and that they can "
                         f"revise the feature description and run a revision; keep it to two or three sentences.", "error")
        # Otherwise: reject with a reason. Anything else - including an empty resume payload - is treated as a
        # rejection, never as an approval.
        repo.resolve_review_task(task["id"], "rejected", r_id, comment, None, memory_items)
        repo.update_assessment(assessment_id, status="rejected")
        say({"node": "tool_gate", "event": "rejected", "tool": "request_dpo_review", "by": r_id, "comment": comment})
        return reply(f"The DPO ({r_id}) rejected assessment {assessment_id}. Comment: {comment or 'none'}. "
                     f"Tell the user; do not record anything.", "error")
