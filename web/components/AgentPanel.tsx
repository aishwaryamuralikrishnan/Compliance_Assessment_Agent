"use client";

// "Behind the scenes": the live graph, the stacked traces and the run stats. Opens when a run streams; otherwise
// one click away on the strip.

import { useState } from "react";
import { useAgent, useSession } from "@/lib/context";
import { mergeSnapshots } from "@/lib/graph";
import LiveGraph, { GraphLegend } from "@/components/LiveGraph";
import RunStats, { statsLine } from "@/components/RunStats";
import TracePanel from "@/components/TracePanel";

type Tab = "graph" | "trace" | "stats";

export function AgentStrip() {
  const { agent, panelOpen, setPanelOpen } = useAgent();
  if (!agent || panelOpen) return null;
  const last = agent.views.length ? agent.views[agent.views.length - 1].view : null;
  return (
    <div className="strip">
      <span className={`pill ${agent.kind}`}><span className="dot" />{agent.status}</span>
      <span className="mono">{statsLine(last?.stats || null)}</span>
      <span className="grow" />
      <button type="button" className="btn sm" onClick={() => setPanelOpen(true)}>Behind the scenes ›</button>
    </div>
  );
}

export default function AgentPanel() {
  const { layout, meta } = useSession();
  const { agent, panelOpen, setPanelOpen } = useAgent();
  const [tab, setTab] = useState<Tab>("graph");
  if (!agent || !panelOpen) return null;
  const views = agent.views;
  const merged = mergeSnapshots(views.map((v) => v.view.graph));
  const last = views.length ? views[views.length - 1].view : null;
  return (
    <aside className="panel" aria-label="Behind the scenes">
      <div className="head">
        <div className="title">Behind the scenes</div>
        <button type="button" className={`tab${tab === "graph" ? " on" : ""}`} onClick={() => setTab("graph")}>Graph</button>
        <button type="button" className={`tab${tab === "trace" ? " on" : ""}`} onClick={() => setTab("trace")}>Trace</button>
        <button type="button" className={`tab${tab === "stats" ? " on" : ""}`} onClick={() => setTab("stats")}>Stats</button>
        <button type="button" className="tab icon" aria-label="Collapse the panel" title="Collapse" onClick={() => setPanelOpen(false)}>›</button>
      </div>
      <div className="scroll">
        {tab === "graph" ? (
          <>
            <LiveGraph layout={layout} snapshot={merged} />
            <GraphLegend />
            <div className="small faint">The compiled orchestrator, drawn from its own edges. Dashed-border shapes are what happens inside a node: the tool gate and the DPO&apos;s pause inside the worker and the reviser, the product manager&apos;s pause inside pm_revision, the retrieve / grade / rewrite / draft steps inside the search tool.</div>
          </>
        ) : null}
        {tab === "trace" ? <TracePanel views={views} /> : null}
        {tab === "stats" ? (
          <>
            <RunStats stats={last?.stats || null} />
            <div className="eyebrow" style={{ marginTop: 6 }}>Models per node</div>
            <div className="mono small" style={{ lineHeight: 1.7, color: "var(--ink-2)" }}>
              {meta ? Object.entries(meta.models).map(([node, name]) => <div key={node}><span style={{ color: "var(--accent)" }}>{node}</span> · {name}</div>) : "…"}
            </div>
            <div className="small faint">Display only: models are chosen in config/models.yaml by whoever runs the app, so a user cannot switch a node to an expensive one. {meta?.langsmith.enabled ? `LangSmith tracing on (project ${meta.langsmith.project}).` : "LangSmith tracing off."}</div>
          </>
        ) : null}
      </div>
    </aside>
  );
}
