"""Scripted stand-ins for the model-backed parts, so the graph can be tested offline.

ScriptedChatModel  returns pre-written AIMessages in order (tool calls included)
fake_retrieval()   replaces query embeddings / reranker / grader with deterministic stubs
fake_screens()     replaces the validate_input classifier and the router
"""
from __future__ import annotations

import random
from typing import Any, Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChatModel(BaseChatModel):
    script: list[AIMessage]
    calls: int = 0
    last_prompt: str = ""                      # the text of the last request, for tests that check what a model was shown

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):          # the agent binds tools; we ignore them
        return self

    def with_structured_output(self, schema, **kwargs):
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.last_prompt = "\n".join(m.content if isinstance(m.content, str) else str(m.content) for m in messages)
        if self.calls >= len(self.script):
            msg = AIMessage(content="(script exhausted)")
        else:
            msg = self.script[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def fake_retrieval(monkeypatch, *, relevant_first_n: int = 3) -> None:
    import compliance_agent.retrieval.loop as L
    import compliance_agent.retrieval.search as S
    from compliance_agent.retrieval.grader import GradeResult

    class FakeEmb:
        def embed_query(self, t):
            return [random.random() for _ in range(1536)]

        def embed_documents(self, ts):
            return [self.embed_query(t) for t in ts]

    monkeypatch.setattr(S, "embeddings", lambda: FakeEmb())
    import compliance_agent.models as M
    monkeypatch.setattr(M, "embeddings", lambda: FakeEmb())     # also the Store index (memory writes / recall)

    def fake_rerank(q, chunks, top_n=5):
        for i, c in enumerate(chunks[:top_n]):
            c.rerank_score = round(1 - i / 10, 2)
        return chunks[:top_n], {"method": "stub", "top": [(c.citation, c.rerank_score) for c in chunks[:top_n]]}

    def fake_grade(q, chunks):
        ids = [c.id for c in chunks[:relevant_first_n]]
        return GradeResult(True, 0.9, ids, "stub", "stub")

    monkeypatch.setattr(L, "rerank", fake_rerank)
    monkeypatch.setattr(L, "grade", fake_grade)


def fake_screens(monkeypatch, tier: str = "full") -> None:
    import compliance_agent.nodes.route as R
    import compliance_agent.nodes.validate_input as V

    monkeypatch.setattr(V, "_screen", lambda text: V._Screen(on_topic=True, injection=False, reason="stub"))
    monkeypatch.setattr(R, "decide", lambda text: (R.RouteDecision(tier=tier, confidence=0.95, reason="stub"), "stub"))
    import compliance_agent.memory as Mem

    def fake_reflect(items, **kw):            # the cheap-model rephrase, deterministic: prefix the stored text
        out = []
        for it in items:
            it = dict(it)
            if it.get("reflect"):
                it["text"], it["reflected"] = "Lesson: " + it["text"], True
            out.append(it)
        return out

    monkeypatch.setattr(Mem, "reflect", fake_reflect)


def iter_events(gen: Iterator[dict]) -> tuple[list[dict], dict]:
    events = list(gen)
    final = next(e for e in events if e["kind"] == "final")
    return events, final["state"]


# --------------------------------------------------------------------------------------
# A corpus-free retrieval: canned GDPR / AI Act chunks, no database, no models
# --------------------------------------------------------------------------------------

KNOWN_CITATIONS = {
    "GDPR Art. 22", "GDPR Art. 22(1)", "GDPR Art. 22(3)", "GDPR Art. 35", "GDPR Art. 35(3)(a)", "GDPR Art. 45",
    "GDPR Art. 6(1)(f)", "GDPR Art. 13(2)(f)", "GDPR Rec. 71", "GDPR Art. 5(1)(e)",
    "AI Act Art. 6(2)", "AI Act Annex III point 5", "AI Act Annex III point 5(b)", "AI Act Art. 26", "AI Act Art. 27",
}


def _chunk(i, reg, article=None, paragraph=None, recital=None, annex=None, point=None, text=""):
    from compliance_agent.retrieval.search import RetrievedChunk

    c = RetrievedChunk(id=i, chunk_key=f"fake-{i}", regulation=reg, unit_type="article" if article else ("recital" if recital else "annex"),
                       heading=f"{reg} fake {i}", text=text, article=article, paragraph=paragraph, recital=recital, annex=annex, point=point,
                       word_count=len(text.split()))
    c.rerank_score = round(1 - i / 20, 2)
    c.grader_relevant = True
    return c


def fake_corpus(monkeypatch) -> None:
    """search_with_loop -> canned chunks (events included); citation_exists -> membership in KNOWN_CITATIONS."""
    import compliance_agent.nodes.direct_answer as DA
    import compliance_agent.nodes.guardrail as GR
    import compliance_agent.tools.regulation as TR
    from compliance_agent.retrieval.grader import GradeResult
    from compliance_agent.retrieval.loop import Attempt, RetrievalResult

    chunks = [
        _chunk(1, "GDPR", article=22, paragraph=1, text="1. The data subject shall have the right not to be subject to a decision based solely on automated processing ..."),
        _chunk(2, "GDPR", article=22, paragraph=3, text="3. ... suitable measures ... the right to obtain human intervention ... to contest the decision."),
        _chunk(3, "GDPR", article=35, paragraph=3, text="3. A data protection impact assessment ... (a) a systematic and extensive evaluation ... automated processing, including profiling"),
        _chunk(4, "GDPR", recital=71, text="The data subject should have the right not to be subject to a decision ... such as automatic refusal of an online credit application"),
        _chunk(5, "AI Act", annex="III", point="5", text="5. Access to and enjoyment of essential private services ... (b) AI systems intended to be used to evaluate the creditworthiness of natural persons"),
        _chunk(6, "GDPR", article=45, paragraph=1, text="1. A transfer ... may take place where the Commission has decided that the third country ... ensures an adequate level of protection."),
    ]

    def fake_loop(query, regulation=None, k=5, max_attempts=3, emit=None, use_grader=True):
        def say(ev):
            if emit:
                emit({"node": "search_regulation", **ev})
        sel = [c for c in chunks if regulation in (None, c.regulation)][:k] or chunks[:k]
        say({"event": "retrieve", "attempt": 1, "query": query})
        verdict = GradeResult(True, 0.9 if use_grader else 1.0, [c.id for c in sel], "stub", "stub")
        say({"event": "graded", "attempt": 1, "sufficient": True, "confidence": verdict.confidence,
             "relevant": [c.citation for c in sel], "top": [c.citation for c in sel], "reason": "stub"})
        say({"event": "done", "attempts": 1, "sufficient": True, "chunks": [c.citation for c in sel]})
        return RetrievalResult(query, sel, True, [Attempt(1, query, {"method": "stub"}, {"method": "stub"}, verdict)])

    monkeypatch.setattr(TR, "search_with_loop", fake_loop)
    monkeypatch.setattr(DA, "search_with_loop", fake_loop)
    monkeypatch.setattr(GR, "verify_citation", lambda label: GR.VERIFIED if label in KNOWN_CITATIONS else GR.UNKNOWN)
