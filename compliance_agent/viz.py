"""Live graph for the UI: the fixed layout of the orchestrator's flowchart (`layout_json`, served once by the
web API) and the tracker that follows a run's stream events (`TraceTracker.snapshot`, streamed with every view):
the active node, the visited nodes, the edges taken, the worker's inner loop (retrieve / grade / rewrite / draft),
the tool gate beside it and the `interrupt() wait DPO` box that lights up while a thread is paused. The React
component draws the picture from these two.

The node set is checked against `graph.get_graph()` (see `layout_matches`) so the picture
cannot drift from the compiled graph without a test failing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------------------
# Layout (viewBox 0 0 490 570)
# --------------------------------------------------------------------------------------

NODES: dict[str, dict[str, Any]] = {
    "__start__":        {"kind": "circle", "cx": 180, "cy": 20, "label": "START", "lpos": "left"},
    "validate_input":   {"kind": "rect", "x": 120, "y": 44, "w": 120, "h": 34, "label": ["validate_input"]},
    "route":            {"kind": "diamond", "cx": 180, "cy": 130, "r": 40, "label": ["route"]},
    "direct_answer":    {"kind": "direct", "x": 10, "y": 176, "w": 100, "h": 52, "label": ["direct_answer"]},
    "reject":           {"kind": "rect", "x": 360, "y": 160, "w": 90, "h": 30, "label": ["reject"]},
    "worker":           {"kind": "worker", "x": 120, "y": 215, "w": 120, "h": 112, "label": ["worker"]},
    "tool_gate":        {"kind": "diamond", "cx": 320, "cy": 252, "r": 30, "label": ["tool", "gate"]},
    "interrupt":        {"kind": "rect", "x": 275, "y": 292, "w": 90, "h": 30, "label": ["interrupt()", "wait DPO"], "small": True},
    "reviser":          {"kind": "rect", "x": 360, "y": 356, "w": 100, "h": 48, "label": ["reviser", "v2 after", "DPO changes"], "small2": True},
    "output_guardrail": {"kind": "rect", "x": 120, "y": 364, "w": 120, "h": 40, "label": ["output_", "guardrail"]},
    "memory_write":     {"kind": "rect", "x": 120, "y": 432, "w": 120, "h": 40, "label": ["memory_", "write"]},
    "pm_revision":      {"kind": "rect", "x": 360, "y": 440, "w": 100, "h": 40, "label": ["pm_", "revision"]},
    "interrupt_pm":     {"kind": "rect", "x": 365, "y": 496, "w": 90, "h": 30, "label": ["interrupt()", "wait PM"], "small": True},
    "__end__":          {"kind": "circle", "cx": 180, "cy": 546, "label": "END", "lpos": "below"},
}
# inner steps of the worker's agentic RAG, drawn as the real control flow:
#   retrieve -> grade -> (stop) draft        or        grade -> rewrite -> retrieve again (max 3 attempts)
SUBSTEPS = {"retrieve": (128, 249, 50, 15), "grade": (128, 276, 50, 15), "rewrite": (190, 276, 44, 15), "draft": (128, 306, 106, 15)}
SUBSTEP_EDGES: list[tuple[str, str, list[tuple[float, float]], str]] = [
    ("retrieve", "grade", [(153, 264), (153, 276)], "solid"),
    ("grade", "rewrite", [(178, 283.5), (190, 283.5)], "dashed"),         # grader not satisfied
    ("rewrite", "retrieve", [(212, 276), (212, 256.5), (178, 256.5)], "dashed"),  # loop back with the rewritten query
    ("grade", "draft", [(153, 291), (153, 306)], "solid"),                 # satisfied, or attempts exhausted
]
SUBSTEP_LABELS = [("retry", 215, 268, "start"), ("stop", 149, 301, "end")]
DA_SUBSTEP = (18, 202, 84, 16)           # direct_answer's single retrieval pass

# edges as (source, target, points, style)   style: solid | dashed
# Solid: the forward path. Dashed: a pause, or a return into a node that already ran (a resume, a regeneration, the
# review request, the retry inside the worker). The two agents share the drawn tool gate and its interrupt box;
# pm_revision has its own interrupt box, and the compiled graph's self-loop pm_revision -> pm_revision (a refused
# resume asks again) is drawn as the round trip through that box.
EDGES: list[tuple[str, str, list[tuple[int, int]], str]] = [
    ("__start__", "validate_input", [(180, 30), (180, 44)], "solid"),
    ("validate_input", "route", [(180, 78), (180, 90)], "solid"),
    ("route", "direct_answer", [(140, 130), (60, 130), (60, 176)], "solid"),
    ("route", "reject", [(220, 130), (405, 130), (405, 160)], "solid"),
    ("route", "worker", [(180, 170), (180, 215)], "solid"),
    ("worker", "tool_gate", [(240, 244), (298, 244)], "solid"),
    ("tool_gate", "worker", [(298, 260), (240, 260)], "solid"),
    ("tool_gate", "interrupt", [(320, 282), (320, 292)], "dashed"),
    ("interrupt", "worker", [(275, 307), (240, 307)], "dashed"),
    ("reviser", "tool_gate", [(400, 356), (400, 266), (336, 266)], "solid"),
    ("tool_gate", "reviser", [(350, 252), (425, 252), (425, 356)], "solid"),
    ("interrupt", "reviser", [(365, 307), (380, 307), (380, 356)], "dashed"),
    ("worker", "output_guardrail", [(170, 327), (170, 364)], "solid"),
    ("output_guardrail", "worker", [(198, 364), (198, 327)], "dashed"),   # regeneration, or "request DPO review" after a verified assessment
    ("direct_answer", "output_guardrail", [(60, 228), (60, 384), (120, 384)], "solid"),
    ("reviser", "output_guardrail", [(360, 374), (240, 374)], "solid"),
    ("output_guardrail", "reviser", [(240, 392), (360, 392)], "dashed"),   # regeneration / review request on the revise route
    ("output_guardrail", "memory_write", [(180, 404), (180, 432)], "solid"),      # after a DPO decision
    ("output_guardrail", "__end__", [(120, 398), (100, 398), (100, 546), (170, 546)], "solid"),   # verified quick answer
    ("memory_write", "pm_revision", [(240, 452), (360, 452)], "solid"),           # the DPO requested changes: pause for the PM
    ("pm_revision", "interrupt_pm", [(410, 480), (410, 496)], "dashed"),         # waits for the product manager
    ("interrupt_pm", "pm_revision", [(455, 511), (470, 511), (470, 460), (460, 460)], "dashed"),   # her resume re-runs the node (asked again if refused)
    ("pm_revision", "reviser", [(410, 440), (410, 404)], "solid"),               # the revised description: v2
    ("reject", "__end__", [(450, 175), (482, 175), (482, 546), (190, 546)], "solid"),
    ("memory_write", "__end__", [(180, 472), (180, 536)], "solid"),
]

# Drawn but not nodes of the compiled graph: the tool gate and the DPO's interrupt() live inside the worker's and the
# reviser's `tools` node (middleware around every tool call); the PM's interrupt() is raised inside pm_revision.
PSEUDO_NODES = ("tool_gate", "interrupt", "interrupt_pm")
OUTER_NODES = {n for n in NODES if n not in PSEUDO_NODES}


def layout_matches(compiled) -> bool:
    """The outer graph's nodes and edges are all drawn (ignores subgraph internals)."""
    g = compiled.get_graph()
    nodes = {str(n) for n in g.nodes if ":" not in str(n)}
    edges = {(str(e.source), str(e.target)) for e in g.edges if ":" not in str(e.source) and ":" not in str(e.target)}
    edges = {(a, b) for a, b in edges if a != b}          # a self-loop is drawn as the round trip through the node's interrupt box
    drawn = {(s, t) for s, t, _, _ in EDGES if s in OUTER_NODES and t in OUTER_NODES}
    return nodes == OUTER_NODES and edges == drawn


# --------------------------------------------------------------------------------------
# Tracker: turns stream events into highlight state + run stats
# --------------------------------------------------------------------------------------

@dataclass
class TraceTracker:
    active: str | None = "__start__"
    visited: list[str] = field(default_factory=list)
    taken: list[tuple[str, str]] = field(default_factory=list)
    paused: bool = False
    pm_paused: bool = False               # paused in pm_revision (for the product manager) rather than at the gate
    resumed: bool = False                 # this tracker follows a resumed run: nothing before the pause is lit (START stays grey)
    substep: str | None = None
    substeps_done: set = field(default_factory=set)
    rewrote: bool = False
    da_state: str | None = None          # None | on | done  (direct_answer's single pass)
    gate_state: str | None = None          # allowed | denied | pause | approved | rejected
    retrievals: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0                # input tokens the provider served from its prompt cache (part of tokens_in)
    cost: float = 0.0
    finished: bool = False

    def _goto(self, node: str) -> None:
        if node == self.active:
            return
        if self.active:
            self.taken.append((self.active, node))
            if self.active not in self.visited:
                self.visited.append(self.active)
        self.active = node

    def observe(self, event: dict[str, Any], pricing: dict[str, dict[str, float]] | None = None) -> None:
        k = event.get("kind")
        ns = event.get("ns") or ()
        node = ns[0] if ns else event.get("node")
        # which agent emitted a subgraph event: the worker or the reviser (they share the drawn tool gate)
        agent = ns[0] if ns and ns[0] in ("worker", "reviser") else ("reviser" if self.active == "reviser" else "worker")
        if k == "interrupt":
            value = event.get("value") if isinstance(event.get("value"), dict) else {}
            if value.get("type") == "pm_revision" or self.active == "pm_revision":
                self.paused = True; self.pm_paused = True
                self._goto("pm_revision")
                self.taken.append(("pm_revision", "interrupt_pm"))
                return
            self.paused = True; self.pm_paused = False
            self.gate_state = "pause"
            self._goto(agent)
            self.taken.append((agent, "tool_gate")); self.taken.append(("tool_gate", "interrupt"))
            return
        if k == "custom":
            ev = event.get("event")
            if event.get("node") == "search_regulation":
                if not ns:                       # quick path: direct_answer's single pass, not the worker
                    self._goto("direct_answer")
                    if ev == "retrieve":
                        self.retrievals += 1; self.da_state = "on"
                    elif ev in ("graded", "done"):
                        self.da_state = "done"
                    return
                self._goto(agent)
                if ev == "retrieve":
                    self.retrievals += 1
                if agent == "worker":            # the inner loop is drawn inside the worker box only
                    if ev == "retrieve":
                        self.substep = "retrieve"
                    elif ev == "graded":
                        self.substeps_done.add("retrieve"); self.substep = "grade"
                    elif ev == "rewrite":
                        self.substeps_done.add("grade"); self.substep = "rewrite"; self.rewrote = True
                    elif ev == "done":
                        self.substeps_done.update({"retrieve", "grade"})
                        if self.rewrote:
                            self.substeps_done.add("rewrite")
                        self.substep = None
                return
            if event.get("node") == "pm_revision":
                self._goto("pm_revision")
                if ev == "pause":
                    self.paused = True; self.pm_paused = True
                    self.taken.append(("pm_revision", "interrupt_pm"))
                elif ev in ("refused", "received"):          # a resume: the node runs again after its interrupt box
                    self.paused = False; self.pm_paused = False
                    self.taken.append(("pm_revision", "interrupt_pm")); self.taken.append(("interrupt_pm", "pm_revision"))
                return
            if event.get("node") == "tool_gate":
                replay = ev == "pause" and (event.get("resumed_by") or (self.resumed and self.gate_state is None))
                self._goto(agent)
                self.gate_state = ev
                self.tool_calls += 1 if ev in ("allowed", "approved") else 0
                if replay:
                    # the resumed call replays its pause: the run is coming out of the interrupt box, not entering it
                    self.paused = False
                    self.taken.append(("tool_gate", "interrupt"))
                    for n in ("tool_gate", "interrupt"):
                        if n not in self.visited:
                            self.visited.append(n)
                    self.gate_state = "resumed"
                elif ev == "pause":
                    self.paused = True
                    self.taken.append((agent, "tool_gate")); self.taken.append(("tool_gate", "interrupt"))
                elif ev in ("approved", "rejected", "changes_requested"):
                    self.paused = False
                    self.taken.append(("interrupt", agent))           # the decision continues from the pause into the agent
                else:
                    self.paused = False
                    self.taken.append((agent, "tool_gate")); self.taken.append(("tool_gate", agent))
                return
            if event.get("node") in ("worker", "reviser") and ev == "model_call":
                self._goto(event["node"])
                self.substep = ("draft" if self.tool_calls or self.retrievals else None) if event["node"] == "worker" else None
                return
            if event.get("node") == "output_guardrail" and ev == "request_review":
                self._goto("output_guardrail")
                self._goto(event.get("agent") or "worker")   # the dashed edge back into the agent: request DPO review
                self.substep = None
                return
            if event.get("node") == "output_guardrail":
                if self.substep == "draft":
                    self.substeps_done.add("draft")
                self.substep = None
            if node in NODES:
                self._goto(node)
            return
        if k == "update":
            if node in NODES:
                self._goto(node)
            self._count_tokens(event, pricing)

    def _count_tokens(self, event: dict[str, Any], pricing: dict[str, dict[str, float]] | None) -> None:
        data = event.get("data")
        if not isinstance(data, dict):
            return
        if not event.get("ns") and event.get("node") in ("worker", "reviser"):
            # The agent node's own update carries the subgraph's whole message list (the entire thread, with the
            # usage of every earlier model call); its model calls were already counted from the subgraph's events.
            return
        slot = "worker_full" if (event.get("ns") or ()) and event["ns"][0] in ("worker", "reviser") else (
            "worker_quick" if event.get("node") == "direct_answer" else "cheap")
        for m in data.get("messages") or []:
            usage = getattr(m, "usage_metadata", None)
            if usage:
                i, o = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
                cached = int((usage.get("input_token_details") or {}).get("cache_read", 0) or 0)
                self.tokens_in += i; self.tokens_out += o; self.tokens_cached += cached
                if pricing and slot in pricing:
                    p_in = pricing[slot].get("input", 0)
                    p_cached = pricing[slot].get("cached_input", p_in)      # providers that cache bill cached tokens at a lower rate
                    self.cost += (i - cached) / 1e6 * p_in + cached / 1e6 * p_cached + o / 1e6 * pricing[slot].get("output", 0)

    def finish(self) -> None:
        if not self.paused and self.active and self.active != "__end__":
            self._goto("__end__")
        if self.substep:
            self.substeps_done.add(self.substep)
        self.substep = None
        self.finished = True

    @property
    def step_label(self) -> str:
        if self.paused:
            return "paused"
        if self.active == "__end__":
            return "END"
        return self.active or "-"

    def snapshot(self) -> dict[str, Any]:
        """The tracker as plain JSON for the web API's event stream, with the edges as two-element lists and the
        substep set as a list. The React live graph applies them to `layout_json`."""
        return {
            "active": self.active, "visited": list(self.visited), "taken": [list(e) for e in self.taken],
            "paused": self.paused, "pm_paused": self.pm_paused, "resumed": self.resumed,
            "substep": self.substep, "substeps_done": sorted(self.substeps_done), "rewrote": self.rewrote,
            "da_state": self.da_state, "gate_state": self.gate_state, "finished": self.finished,
            "retrievals": self.retrievals, "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out, "tokens_cached": self.tokens_cached, "cost": self.cost,
        }


def layout_json() -> dict[str, Any]:
    """The drawn layout as JSON, served by the web API (`GET /api/meta/graph-layout`): one source for the picture."""
    return {
        "viewbox": [0, 0, 490, 570],
        "nodes": NODES,
        "substeps": {k: list(v) for k, v in SUBSTEPS.items()},
        "substep_edges": [{"source": a, "target": b, "points": [list(pt) for pt in pts], "style": st} for a, b, pts, st in SUBSTEP_EDGES],
        "substep_labels": [list(l) for l in SUBSTEP_LABELS],
        "da_substep": list(DA_SUBSTEP),
        "edges": [{"source": a, "target": b, "points": [list(pt) for pt in pts], "style": st} for a, b, pts, st in EDGES],
    }
