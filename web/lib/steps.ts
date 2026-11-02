// The progress stepper shown while a run streams: derived from the view's graph snapshot and stats, so it is
// the same information as the live graph, read left to right.

import type { GraphSnapshot, RunStats, TraceSection, View } from "@/lib/types";

export type StepState = "todo" | "on" | "done" | "bad";
export interface Step { name: string; sub: string; state: StepState }

function routeTier(trace: TraceSection[]): "full" | "quick" | "reject" | null {
  const r = trace.find((s) => s.title === "route");
  const text = r?.items.join(" ") || "";
  if (/<b>full<\/b>/.test(text) || /→ <b>revise/.test(text)) return "full";
  if (/<b>quick<\/b>/.test(text)) return "quick";
  if (/<b>reject<\/b>/.test(text)) return "reject";
  return null;
}

function stripTags(items: string[]): string {
  return items.join(" ").replace(/<[^>]+>/g, "");
}

/** The steps of a resumed run. Nothing before the pause runs again, so Validate / Route / Search / Draft would be
 *  wrong here: the DPO's decision resumes at the interrupt and goes worker → output_guardrail → memory_write (→
 *  pm_revision when changes were requested); the requester's revision runs the reviser (search, draft, verify,
 *  review); feedback only writes memory. Which one it is comes from the trace and the graph, not from the title. */
function resumedSteps(view: View): Step[] {
  const g: GraphSnapshot = view.graph;
  const s: RunStats = view.stats;
  const visited = new Set(g.visited);
  const all = stripTags(view.trace.flatMap((t) => t.items));
  const memSection = view.trace.filter((t) => t.title === "memory_write").pop();
  const memText = memSection ? stripTags(memSection.items) : "";
  const stored = (memText.match(/\bstored\b/g) || []).length - (memText.match(/not stored/g) || []).length;
  const memory: Step = {
    name: "Memory",
    state: g.active === "memory_write" ? "on" : visited.has("memory_write") ? "done" : "todo",
    sub: !memSection ? "lessons from the decision" : /nothing written|nothing to store/.test(memText) ? "nothing written" : stored > 0 ? `${stored} item${stored === 1 ? "" : "s"} stored` : "writing",
  };
  const guard = view.trace.filter((t) => t.title === "output_guardrail").pop();
  const verify: Step = {
    name: "Verify", state: g.active === "output_guardrail" ? "on" : visited.has("output_guardrail") ? "done" : "todo",
    sub: guard ? stripTags(guard.items).slice(0, 60) : "citations against the corpus",
  };

  // feedback: a preference note or "keep as a good example" → memory_write only
  const fb = view.trace.find((t) => t.title === "feedback");
  if (fb) {
    return [{ name: "Feedback", state: "done", sub: stripTags(fb.items).split(" · LangSmith")[0].slice(0, 60) }, memory];
  }

  // the requester's revision: the reviser does the full search → draft → verify, then the DPO reviews v2
  const pmr = view.trace.find((t) => t.title === "pm_revision");
  const revising = g.active === "reviser" || visited.has("reviser") || (pmr ? /received|reviser/.test(stripTags(pmr.items)) : false);
  if (revising) {
    const revision: Step = { name: "Revision", state: "done", sub: "revised description received" };
    const searching = g.substep === "retrieve" || g.substep === "grade" || g.substep === "rewrite";
    const search: Step = {
      name: "Search",
      state: searching && g.active === "reviser" ? "on" : s.searches > 0 || g.substeps_done.includes("retrieve") ? "done" : g.active === "reviser" ? "on" : "todo",
      sub: s.searches ? `${s.searches} search${s.searches === 1 ? "" : "es"} · ${s.rewrites} rewrite${s.rewrites === 1 ? "" : "s"}` : "what changed, against the law",
    };
    const draft: Step = {
      name: "Draft", state: g.substep === "draft" && g.active === "reviser" ? "on" : g.substeps_done.includes("draft") || visited.has("output_guardrail") || g.active === "output_guardrail" ? "done" : "todo",
      sub: "v2 · changes since v1",
    };
    const review: Step = {
      name: "Review", state: g.paused && !g.pm_paused ? "done" : g.gate_state === "pause" ? "on" : "todo",
      sub: g.paused && !g.pm_paused ? "sent to the DPO · paused" : "sent to the DPO",
    };
    return [revision, search, draft, verify, review];
  }

  // the DPO's decision
  const m = /approved by ([^\s·]+)|changes requested by ([^\s·]+)|rejected by ([^\s·]+)/.exec(all);
  const outcome = m ? (m[1] ? "approved" : m[2] ? "changes requested" : "rejected") : null;
  const by = m ? m[1] || m[2] || m[3] : "";
  const recorded = /register entry/.test(all);
  const decision: Step = {
    name: "Decision", state: outcome ? "done" : "on",
    sub: outcome ? `${outcome} by ${by}${recorded ? " · register entry written" : ""}` : "resuming at the interrupt",
  };
  const agentDone = visited.has("output_guardrail") || g.active === "output_guardrail" || visited.has("memory_write") || g.active === "memory_write" || g.active === "__end__";
  const worker: Step = {
    name: "Worker", state: g.active === "worker" ? "on" : agentDone ? "done" : "todo",
    sub: s.searches ? `${s.searches} search${s.searches === 1 ? "" : "es"} · reports the outcome` : "reports the outcome to the requester",
  };
  const steps = [decision, worker, verify, memory];
  if (outcome === "changes requested" || g.pm_paused) {
    steps.push({ name: "Revision", state: g.pm_paused ? "done" : "todo", sub: g.pm_paused ? "waiting for the requester · paused" : "the requester revises the feature" });
  }
  return steps;
}

export function deriveSteps(view: View | null, finished: boolean): Step[] {
  if (!view) return [];
  const g: GraphSnapshot = view.graph;
  const s: RunStats = view.stats;
  if (g.resumed) return resumedSteps(view);
  const visited = new Set(g.visited);
  const tier = routeTier(view.trace);
  const vi = view.trace.find((t) => t.title === "validate_input");
  const validate: Step = {
    name: "Validate", state: visited.has("validate_input") || g.active !== "validate_input" && g.active !== null && g.active !== "__start__" ? "done" : g.active === "validate_input" ? "on" : "todo",
    sub: vi ? vi.items.join(" ").replace(/<[^>]+>/g, "").slice(0, 60) : "limits · PII · injection",
  };
  if (visited.has("reject") || g.active === "reject") validate.state = "bad";
  const route: Step = { name: "Route", state: visited.has("route") ? "done" : g.active === "route" ? "on" : "todo", sub: tier ? `${tier}` : "classifier" };
  if (tier === "reject" || visited.has("reject") || g.active === "reject") {
    return [validate, route, { name: "Rejected", sub: "nothing else runs", state: "bad" }];
  }
  if (tier === "quick" || visited.has("direct_answer") || g.active === "direct_answer") {
    const answer: Step = { name: "Answer", state: visited.has("direct_answer") ? "done" : g.active === "direct_answer" ? "on" : "todo", sub: g.da_state === "on" ? "one retrieval pass" : "cheap model, no tools" };
    const verify: Step = { name: "Verify", state: visited.has("output_guardrail") || (finished && g.active === "__end__") ? "done" : g.active === "output_guardrail" ? "on" : "todo", sub: "citations against the corpus" };
    return [validate, route, answer, verify];
  }
  const agent = g.active === "reviser" || visited.has("reviser") ? "reviser" : "worker";
  const searching = g.substep === "retrieve" || g.substep === "grade" || g.substep === "rewrite";
  const search: Step = {
    name: "Search",
    state: searching && g.active === agent ? "on" : s.searches > 0 || g.substeps_done.includes("retrieve") ? "done" : g.active === agent ? "on" : "todo",
    sub: s.searches ? `${s.searches} search${s.searches === 1 ? "" : "es"} · ${s.rewrites} rewrite${s.rewrites === 1 ? "" : "s"}` : "agentic RAG · ≤3 attempts",
  };
  const draft: Step = {
    name: "Draft", state: g.substep === "draft" && g.active === agent ? "on" : g.substeps_done.includes("draft") || visited.has("output_guardrail") || g.active === "output_guardrail" ? "done" : "todo",
    sub: "structured output",
  };
  const guard = view.trace.filter((t) => t.title === "output_guardrail").pop();
  const verify: Step = {
    name: "Verify", state: g.active === "output_guardrail" ? "on" : visited.has("output_guardrail") ? "done" : "todo",
    sub: guard ? stripTags(guard.items).slice(0, 60) : "citations against the corpus",
  };
  const review: Step = {
    name: "Review", state: g.paused && !g.pm_paused ? "done" : g.gate_state === "pause" ? "on" : g.visited.includes("memory_write") || g.active === "memory_write" || g.active === "__end__" ? "done" : "todo",
    sub: g.paused && !g.pm_paused ? "sent to the DPO · paused" : g.pm_paused ? "changes requested" : "sent to the DPO",
  };
  return [validate, route, search, draft, verify, review];
}
