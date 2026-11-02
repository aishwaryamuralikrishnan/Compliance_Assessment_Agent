"""Turn stream events into the trace panel.

One section per graph block (heading + bullet points describing what happened inside it),
and one boxed section per tool call. Inside a `search_regulation` box the agentic RAG loop
is shown the way the run-view mock does it - short rows:

    ⚙ search_regulation   query="credit scoring browsing behaviour"
      retrieve 1      2 weak hits · grade: insufficient · certainty 0.31
      rewrite_query   → "automated individual decision-making profiling"
      retrieve 2      Art. 22 · Art. 35(3) · Rec. 71 · grade: sufficient · certainty 0.88 · stop

Rows of one tool call stay together even when several calls run in parallel (keyed by the
`call` id the tool attaches to its events); the grader's reason for an "insufficient"
verdict is a hover tooltip. UI-agnostic: the items are small HTML snippets (escaped here), served as JSON by
the web API (`sections_json`) and placed by the React trace panel with its own CSS.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any

SHORT_REG = {"GDPR ": "", "AI Act ": "AIA "}


def esc(s: Any) -> str:
    return html.escape(str(s))


def short_cite(c: str) -> str:
    """'GDPR Art. 22(1)' -> 'Art. 22(1)'; 'AI Act Annex III point 5' -> 'AIA Annex III 5'."""
    for k, v in SHORT_REG.items():
        if c.startswith(k):
            c = v + c[len(k):]
    return c.replace(" point ", " ")


@dataclass
class Row:
    label: str
    detail: str
    attempt: int | None = None
    tip: str = ""


@dataclass
class Section:
    key: str
    title: str
    cls: str = ""
    subtitle: str = ""
    items: list[str] = field(default_factory=list)      # bullets (node sections)
    rows: list[Row] = field(default_factory=list)       # label | detail rows (search boxes)


@dataclass
class TraceBuilder:
    worker_model: str = ""
    sections: list[Section] = field(default_factory=list)
    _calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    _model_calls: int = 0
    _tools_used: int = 0

    # ---------------------------------------------------------------------------------
    def _section(self, key: str, title: str, cls: str = "", subtitle: str = "") -> Section:
        for s in self.sections:
            if s.key == key:
                return s
        s = Section(key, title, cls, subtitle)
        self.sections.append(s)
        return s

    _agent: str = "worker"

    def _worker(self) -> Section:
        """The current agent section (worker or reviser): a new one per model call keeps the order chronological."""
        if self._model_calls == 0:
            self._model_calls = 1
        return self._section(f"{self._agent}:{self._model_calls}", self._agent)

    def add(self, e: dict[str, Any]) -> bool:
        """Consume one event; returns True if the panel changed."""
        if e.get("kind") != "custom":
            return False
        node, ev = e.get("node"), e.get("event")

        if node == "validate_input":
            flags = e.get("flags") or []
            bits = [f"{e.get('chars')} chars", "injection detected" if "injection" in flags else "no injection",
                    f"{e.get('redactions')} PII item(s) redacted" if e.get("redactions") else "no PII to redact",
                    '<span class="ok">ok</span>' if e.get("ok") else f'<span class="bad">rejected ({", ".join(flags)})</span>']
            self._section("validate_input", "validate_input").items.append(" · ".join(bits))
            return True

        if node == "route":
            self._section("route", "route").items.append(
                f"{esc(e.get('impl'))} → <b>{esc(e.get('tier'))}</b> (confidence {e.get('confidence')}) · {esc(e.get('reason', ''))}")
            return True

        if node in ("worker", "reviser") and ev == "summarised":
            self._worker().items.append(f"thread summarised ({e.get('older')} older messages → summary on the cheap model, last {e.get('kept')} kept"
                                        + (", the request itself kept verbatim)" if e.get("request_pinned") else ")"))
            return True

        if node in ("worker", "reviser") and ev == "history_repaired":
            self._worker().items.append('<span class="warn">message history repaired before the model call</span> · ' + esc("; ".join(e.get("repairs") or []))
                                        + " · a strict provider would otherwise reject the request (see the log)")
            return True
        if node in ("worker", "reviser") and ev == "output_unusable":
            calls = ", ".join(e.get("calls") or []) or "no tool call"
            self._worker().items.append(f'<span class="warn">model output unusable: {esc(e.get("reason"))}</span> ({esc(calls)})'
                                        + (f" · {esc(e.get('error'))}" if e.get("error") else "") + " · the guardrail asks for it again, shorter")
            return True
        if node in ("worker", "reviser") and ev == "request_rejected":
            self._worker().items.append(f'<span class="bad">the provider rejected the request</span> · {esc(e.get("error"))}'
                                        f'<pre class="small">{esc(e.get("history"))}</pre>')
            return True
        if node in ("worker", "reviser") and ev == "memory_unavailable":
            self._worker().items.append(f'<span class="bad">long-term memory unavailable</span> · {esc(e.get("error"))} · the model runs without it')
            return True
        if node in ("worker", "reviser") and ev == "model_call":
            self._agent = node
            m = e.get("memories") or {}
            self._model_calls += 1
            s = self._worker()
            if self._model_calls == 1:
                mem_txt = (f"reading memory: {m.get('org_facts', 0)} org facts, {m.get('lessons', 0)} lessons, {m.get('prefs', 0)} user pref(s)"
                           if not e.get("memory_unavailable") else "memory unavailable (see above)")
                s.items.append(f"model call 1 as {esc(e.get('role'))} · {mem_txt} · tools bound: {esc(', '.join(e.get('tools', [])))}")
            elif self._tools_used:
                s.items.append(f"model call {self._model_calls} · reading tool results · drafting the structured output"
                               + (f" ({esc(self.worker_model)})" if self.worker_model else ""))
            else:
                s.items.append(f"model call {self._model_calls} as {esc(e.get('role'))}")
            return True

        if node == "search_regulation":
            if not e.get("call"):                 # quick path: one retrieval pass inside direct_answer
                return self._quick_search(e)
            return self._search(e)

        if node == "tool_gate":
            tool, role, kind = e.get("tool"), e.get("role"), e.get("tool_kind")
            s = self._worker()
            if ev == "allowed":
                self._tools_used += 1
                s.items.append(f"tool_gate: {esc(tool)} · {esc(kind)} · <span class=\"ok\">allowed for {esc(role)}</span>")
                if tool == "lookup_register":
                    self._section(f"lookup:{self._tools_used}", "lookup_register", "tool").items.append("checking the processing register for an existing entry")
            elif ev == "denied":
                s.items.append(f"tool_gate: {esc(tool)} · {esc(kind)} · <span class=\"bad\">not permitted for {esc(role)}</span>")
            elif ev == "pause":
                if tool == "request_dpo_review":
                    t = self._section(f"gate:{e.get('task_id')}", "request_dpo_review", "tool", f"assessment {esc(e.get('assessment_id'))}")
                    t.items.append(f"review task #{e.get('task_id')} created for the DPO (requested by {esc(e.get('requested_by'))})")
                    t.items.append('<span class="warn">interrupt()</span> · thread paused, state checkpointed in Postgres')
                else:
                    s.items.append(f"tool_gate: {esc(tool)} · {esc(kind)} · <span class=\"warn\">interrupt()</span> waiting for approval")
            elif ev == "approved":
                extra = f" → register entry <b>{esc(e.get('register_id'))}</b> written" if e.get("register_id") else " → executing"
                tgt = self._section(f"gate:{e.get('task_id')}", "request_dpo_review", "tool") if e.get("task_id") else s
                tgt.items.append(f"<span class=\"ok\">approved by {esc(e.get('by'))}</span>{' with amendments' if e.get('amended') else ''}{extra}")
            elif ev == "rejected":
                s.items.append(f"tool_gate: {esc(tool)} · <span class=\"warn\">{esc(ev.replace('_', ' '))} by {esc(e.get('by'))}</span> · {esc(e.get('comment') or e.get('reason') or '')}")
            elif ev == "changes_requested":
                tgt = self._section(f"gate:{e.get('task_id')}", "request_dpo_review", "tool") if e.get("task_id") else s
                tgt.items.append(f"<span class=\"warn\">changes requested by {esc(e.get('by'))}</span> · {esc(e.get('comment') or '')} · nothing recorded; the requester can revise the feature")
            elif ev == "repeat_call":
                s.items.append(f"<span class=\"warn\">repeated call to {esc(tool)} stopped (doom-loop exit)</span>")
            return True

        if node == "direct_answer" and ev == "memory_unavailable":
            self._section("direct_answer", "direct_answer").items.append(
                f'<span class="bad">long-term memory unavailable</span> · {esc(e.get("error"))} · answering without it')
            return True
        if node == "direct_answer" and ev == "empty_answer":
            self._section("direct_answer", "direct_answer").items.append(
                f'<span class="bad">the model returned no text</span> · {e.get("tokens_out")} output tokens of max_tokens '
                f'{e.get("max_tokens")} · a reasoning model may spend the whole budget before the answer; raise max_tokens '
                f'for worker_quick or ask again')
            return True
        if node == "direct_answer":
            self._section("direct_answer", "direct_answer").items.append(
                f"quick model, no tools: answering with {esc(e.get('model'))} from the {len(e.get('sources') or [])} passages above")
            return True

        if node == "output_guardrail" and ev == "source_unreachable":
            self._section("output_guardrail", "output_guardrail").items.append(
                f'<span class="bad">corpus unreachable</span> for {esc(", ".join(e.get("labels") or []))} · citations kept, not verified, no regeneration (see the log)')
            return True
        if node == "output_guardrail" and ev == "request_review":
            self._section("output_guardrail", "output_guardrail").items.append(
                f"assessment {esc(e.get('assessment_id'))}" + (f" (revises {esc(e.get('revises'))})" if e.get("revises") else "")
                + f" verified and shown · {esc(e.get('agent') or 'worker')} sent to request DPO review (tool call through the gate)")
            return True

        if node == "output_guardrail":
            s = self._section("output_guardrail", "output_guardrail")
            if ev == "regenerate":
                if e.get("invalid"):
                    why = f"unknown citations {esc(e.get('invalid'))}"
                elif e.get("schema_error"):
                    why = f"schema error: {esc(e.get('schema_error'))}"
                else:
                    why = esc(e.get("reason") or "output rejected")
                s.items.append(f'<span class="warn">{why} → sent back to the {self._agent} (one regeneration)</span>')
                return True
            n, inv, unr = e.get("citations_checked", 0), e.get("invalid") or [], e.get("unreachable") or []
            bits = [f"verify_citations {n - len(inv) - len(unr)}/{n} in corpus" + (f" ({len(unr)} not checked)" if unr else ""),
                    "PII scan clean" if not e.get("pii_redactions") else f"{e.get('pii_redactions')} PII item(s) redacted"]
            if e.get("assessment_id"):
                bits += ["disclaimer added", f"draft stored as <b>{esc(e.get('assessment_id'))}</b>"]
            bits.append('<span class="ok">pass</span>' if not inv else f'<span class="warn">{len(inv)} unverified citation(s) removed</span>')
            s.items.append(" · ".join(bits))
            return True

        if node == "feedback" and ev == "deferred":
            self._section("feedback", "feedback").items.append(f'<span class="warn">not recorded</span> · {esc(e.get("reason"))}')
            return True
        if node == "feedback":
            s = self._section("feedback", "feedback")
            bits = (["keep as a good example"] if e.get("example") else []) + ([f"note: “{esc(e.get('comment'))}”"] if e.get("comment") else [])
            s.items.append(" · ".join(bits or ["feedback"]) + f" · LangSmith: {esc(e.get('langsmith') or '-')}")
            return True
        if node == "memory_write":
            s = self._section("memory_write", "memory_write")
            trig = ", ".join(e.get("triggers") or []) or "none"
            if ev == "skipped":
                s.items.append("no DPO decision or feedback in this run · nothing written")
            elif ev == "reflecting":
                s.items.append(f"triggers: {esc(trig)} · {e.get('candidates', 0)} candidate(s)"
                               + (f" · {e.get('to_reflect')} rephrased by the cheap model" if e.get("to_reflect") else ""))
            elif ev == "written":
                s.items.append(f"role gate: <b>{esc(e.get('role'))}</b> ({esc(e.get('by'))}) may write "
                               f"{esc(', '.join(sorted({w['ns'].rsplit('/', 1)[0] for w in (e.get('written') or [])})) or 'nothing new')}")
                for w in e.get("written") or []:
                    s.items.append(f'<span class="ok">stored</span> {esc(w["ns"])} · {esc(w["text"])}')
                for d in e.get("dropped") or []:
                    s.items.append(f'<span class="warn">not stored</span> {esc(d.get("ns") or d.get("type"))} · {esc(d.get("why"))} · {esc(d.get("text"))}')
                if not (e.get("written") or e.get("dropped")):
                    s.items.append("nothing to store from this event")
            else:
                s.items.append(f"{esc(ev)} · triggers: {esc(trig)}")
            return True
        if node == "pm_revision":
            s = self._section("pm_revision", "pm_revision")
            if ev == "pause":
                why = f' · previous attempt refused: {esc(e.get("error"))}' if e.get("error") else ""
                s.items.append(f'<span class="warn">interrupt()</span> · waiting for the product manager ({esc(e.get("requester"))}) to revise '
                               f'{esc(e.get("revises"))}: {e.get("requests")} requested change(s){why}')
            elif ev == "refused":
                s.items.append(f'<span class="bad">resume refused</span> (attempt {e.get("attempt")}, by {esc(e.get("by"))}) · {esc(e.get("reason"))} · asked again')
            elif ev == "received":
                self._agent = "reviser"
                self._model_calls = 0
                flags = e.get("flags") or []
                answers = ", ".join(e.get("responses") or []) or "none"
                s.items.append(f'revised description received from {esc(e.get("by"))} · {e.get("chars")} chars · deterministic screen: '
                               + ("PII redacted · " if "pii_redacted" in flags else "no PII · ") + "no injection"
                               + f' · answers: {esc(answers)} · <b>revise</b> → the reviser agent (v2 of {esc(e.get("revises"))})')
            return True
        return False

    def _quick_search(self, e: dict[str, Any]) -> bool:
        """direct_answer's retrieval: a plain function call, one pass, no grader, no loop."""
        ev = e.get("event")
        box = self._section("quick:call", "search_regulation", "tool",
                            f'called by direct_answer · single pass, no loop · query="{esc(e.get("query", ""))}"' if ev == "retrieve" else "")
        if ev == "retrieve":
            self._calls.setdefault("quick", {"attempts": 1, "rewrites": 0})
            box.rows.append(Row("retrieve 1", '<span class="muted">hybrid search → rerank …</span>', attempt=1))
            return True
        if ev == "graded":
            cites = " · ".join(short_cite(c) for c in (e.get("relevant") or e.get("top") or [])[:6])
            for r in box.rows:
                if r.attempt == 1:
                    r.detail = f"{esc(cites) or 'no passages'} · no grading, no rewrite"
            return True
        return False

    # ---------------------------------------------------------------------------------
    def _search(self, e: dict[str, Any]) -> bool:
        cid, ev, n = e["call"], e.get("event"), e.get("attempt")
        info = self._calls.setdefault(cid, {"attempts": 0, "rewrites": 0})
        if ev == "retrieve":
            s = self._section(f"call:{cid}", "search_regulation", "tool", f'query="{esc(e.get("query"))}"' if n == 1 else "")
            info["attempts"] = max(info["attempts"], n or 0)
            s.rows.append(Row(f"retrieve {n}", '<span class="muted">hybrid search → rerank → grade …</span>', attempt=n))
            return True
        s = self._section(f"call:{cid}", "search_regulation", "tool")
        if ev == "graded":
            ok = e.get("sufficient")
            cites = e.get("relevant") or []
            shown = " · ".join(short_cite(c) for c in cites[:4]) if cites else f"{len(e.get('top') or [])} weak hits"
            verdict = f'grade: <span class="ok">sufficient</span> · certainty {e.get("confidence")}' if ok else f'grade: <span class="warn">insufficient</span> · certainty {e.get("confidence")}'
            detail = f"{esc(shown)} · {verdict}" + (" · <b>stop</b>" if ok else "")
            tip = "" if ok else str(e.get("reason", ""))
            for r in s.rows:
                if r.attempt == n and r.label.startswith("retrieve"):
                    r.detail, r.tip = detail, tip
                    return True
            s.rows.append(Row(f"retrieve {n}", detail, attempt=n, tip=tip))
            return True
        if ev == "rewrite":
            info["rewrites"] += 1
            s.rows.append(Row("rewrite_query", f'→ "{esc(e.get("new_query"))}"', tip=e.get("why", "")))
            return True
        if ev == "done":
            if not e.get("sufficient"):
                s.rows.append(Row("retrieval", f'<span class="warn">grader never satisfied after {e.get("attempts")} attempts · best effort</span>'))
                return True
            return False
        return False

    # ---------------------------------------------------------------------------------
    @property
    def retrieval_stats(self) -> dict[str, int]:
        return {"calls": len(self._calls),
                "attempts": sum(c["attempts"] for c in self._calls.values()),
                "rewrites": sum(c["rewrites"] for c in self._calls.values())}

    def sections_json(self) -> list[dict[str, Any]]:
        """The sections as plain data for the web API's event stream. `items` and `rows[].detail` are the HTML
        snippets this builder produces (escaped here, with the small ok / warn / bad spans); the front end renders
        them as HTML with the trace panel's CSS."""
        return [{"key": s.key, "title": s.title, "cls": s.cls, "subtitle": s.subtitle, "items": list(s.items),
                 "rows": [{"label": r.label, "detail": r.detail, "attempt": r.attempt, "tip": r.tip} for r in s.rows]}
                for s in self.sections]

