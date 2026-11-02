"use client";

// The live graph: the layout from GET /api/meta/graph-layout drawn as SVG, with a run's `graph` snapshot applied by
// the rules UI.md describes (the layout comes from compliance_agent/viz.py through the API). Solid edges: the forward path; dashed: a pause or a
// return into a node that already ran; blue: taken in this run; amber: active or waiting; green: done.

import type { GraphLayout, GraphSnapshot, LayoutNode } from "@/lib/types";

const PSEUDO = new Set(["tool_gate", "interrupt", "interrupt_pm"]);

export const EMPTY_SNAPSHOT: GraphSnapshot = {
  active: null, visited: [], taken: [], paused: false, pm_paused: false, resumed: false, substep: null, substeps_done: [],
  rewrote: false, da_state: null, gate_state: null, finished: false, retrievals: 0, tool_calls: 0, tokens_in: 0, tokens_out: 0,
  tokens_cached: 0, cost: 0,
};

const poly = (pts: [number, number][]) => pts.map(([x, y]) => `${x},${y}`).join(" ");

function nodeState(name: string, t: GraphSnapshot, taken: Set<string>): string {
  const has = (a: string, b: string) => taken.has(`${a}>${b}`);
  if (name === "interrupt") return t.paused && !t.pm_paused ? "paused" : has("tool_gate", "interrupt") ? "visited" : "";
  if (name === "interrupt_pm") return t.paused && t.pm_paused ? "paused" : has("pm_revision", "interrupt_pm") ? "visited" : "";
  if (name === "tool_gate") {
    if ((t.active === "worker" || t.active === "reviser") && t.gate_state && !t.finished && t.gate_state !== "allowed") return "active";
    if (has("worker", "tool_gate") || has("reviser", "tool_gate") || t.visited.includes("tool_gate")) return "visited";
    return "";
  }
  if (name === t.active && !t.paused) return "active";
  if (t.visited.includes(name) || (name === t.active && t.paused)) return "visited";
  return "";
}

export default function LiveGraph({ layout, snapshot }: { layout: GraphLayout | null; snapshot: GraphSnapshot | null }) {
  if (!layout) return <div className="lg-wrap" style={{ minHeight: 200 }} />;
  const t = snapshot || EMPTY_SNAPSHOT;
  const taken = new Set(t.taken.map(([a, b]) => `${a}>${b}`));
  const [vx, vy, vw, vh] = layout.viewbox;
  const done = new Set<string>([...t.substeps_done, ...(t.substep ? [t.substep] : [])]);
  const innerTaken: Record<string, boolean> = {
    "retrieve>grade": done.has("grade"),
    "grade>rewrite": t.rewrote,
    "rewrite>retrieve": t.rewrote,
    "grade>draft": done.has("draft") && t.retrievals > 0,
  };

  const renderNode = (name: string, n: LayoutNode) => {
    const state = nodeState(name, t, taken);
    const cls = `node ${state}`.trim() + (PSEUDO.has(name) ? " pseudo" : "");
    const parts: React.ReactNode[] = [];
    if (n.kind === "circle") {
      const cx = n.cx!, cy = n.cy!;
      parts.push(<circle key="c" className={cls} cx={cx} cy={cy} r={9} />);
      if (name === "__end__") parts.push(<circle key="c2" cx={cx} cy={cy} r={5} fill="none" stroke="#3A4760" strokeWidth={1.2} />);
      parts.push(
        n.lpos === "left" ? (
          <text key="l" className="lbl-small" x={cx - 14} y={cy + 3} textAnchor="end">{n.label as string}</text>
        ) : (
          <text key="l" className="lbl-small" x={cx} y={cy + 20} textAnchor="middle">{n.label as string}</text>
        ),
      );
    } else if (n.kind === "diamond") {
      const cx = n.cx!, cy = n.cy!, r = n.r!;
      const label = n.label as string[];
      parts.push(<polygon key="p" className={cls} points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`} />);
      label.forEach((line, i) => {
        const dy = (i - (label.length - 1) / 2) * 11 + 3.5;
        parts.push(<text key={`t${i}`} x={cx} y={cy + dy} textAnchor="middle" fontWeight={600}>{line}</text>);
      });
    } else {
      const x = n.x!, y = n.y!, w = n.w!, h = n.h!;
      const lines = n.label as string[];
      parts.push(<rect key="r" className={cls} x={x} y={y} width={w} height={h} rx={5} />);
      const top = n.kind === "worker" || n.kind === "direct" || n.small2 ? y + 16 : y + h / 2 - (lines.length - 1) * 5.5 + 3.5;
      lines.forEach((line, i) => {
        const tiny = !!n.small2 && i > 0;
        parts.push(
          <text key={`t${i}`} className={n.small || tiny ? "lbl-small" : undefined} x={x + w / 2} y={top + i * 11} textAnchor="middle" fontWeight={tiny ? 400 : 600}>
            {line}
          </text>,
        );
      });
      if (n.kind === "direct") {
        const [sx, sy, sw, sh] = layout.da_substep;
        const st = t.da_state === "on" ? " on" : t.da_state === "done" ? " done" : "";
        parts.push(<rect key="da" className={`sub${st}`} x={sx} y={sy} width={sw} height={sh} rx={3} />);
        parts.push(<text key="dat" className="lbl-small" x={sx + sw / 2} y={sy + 11} textAnchor="middle">retrieve · 1 pass</text>);
      }
      if (n.kind === "worker") {
        parts.push(<text key="w0" className="lbl-small" x={x + w / 2} y={y + 29} textAnchor="middle">agentic RAG · ≤3 attempts</text>);
        layout.substep_edges.forEach((e, i) => {
          const on = innerTaken[`${e.source}>${e.target}`] || false;
          const ecls = "sedge" + (e.style === "dashed" ? " dashed" : "") + (on ? " taken" : "");
          parts.push(<polyline key={`se${i}`} className={ecls} points={poly(e.points)} markerEnd={`url(#${on ? "arrsb" : "arrs"})`} />);
        });
        layout.substep_labels.forEach(([text, lx, ly, anchor], i) => {
          parts.push(<text key={`sl${i}`} className="lbl-tiny" x={lx} y={ly} textAnchor={anchor as "start" | "end"}>{text}</text>);
        });
        Object.entries(layout.substeps).forEach(([sname, [sx, sy, sw, sh]]) => {
          const st = t.substep === sname && t.active === "worker" && !t.finished ? " on" : t.substeps_done.includes(sname) ? " done" : "";
          parts.push(<rect key={`s${sname}`} className={`sub${st}`} x={sx} y={sy} width={sw} height={sh} rx={3} />);
          parts.push(<text key={`st${sname}`} className="lbl-small" x={sx + sw / 2} y={sy + 11} textAnchor="middle">{sname}</text>);
        });
      }
    }
    return <g key={name}>{parts}</g>;
  };

  return (
    <div className="lg-wrap">
      <svg className="lg-svg" viewBox={`${vx} ${vy} ${vw} ${vh}`} width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Live graph of the orchestrator">
        <defs>
          <marker id="arr" markerWidth={6} markerHeight={6} refX={5} refY={3} orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L6,3 L0,6 z" fill="#B9C6D8" /></marker>
          <marker id="arrb" markerWidth={7} markerHeight={7} refX={6} refY={3.5} orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L7,3.5 L0,7 z" fill="#1D6FE0" /></marker>
          <marker id="arrs" markerWidth={4.5} markerHeight={4.5} refX={4} refY={2.25} orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L4.5,2.25 L0,4.5 z" fill="#B9C6D8" /></marker>
          <marker id="arrsb" markerWidth={4.5} markerHeight={4.5} refX={4} refY={2.25} orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L4.5,2.25 L0,4.5 z" fill="#1D6FE0" /></marker>
        </defs>
        {layout.edges.map((e, i) => {
          const on = taken.has(`${e.source}>${e.target}`);
          const cls = "edge" + (e.style === "dashed" ? " dashed" : "") + (on ? " taken" : "");
          return <polyline key={i} className={cls} points={poly(e.points)} markerEnd={`url(#${on ? "arrb" : "arr"})`} />;
        })}
        {Object.entries(layout.nodes).map(([name, n]) => renderNode(name, n))}
      </svg>
    </div>
  );
}

export function GraphLegend() {
  return (
    <div className="legend">
      <span><span className="sw" style={{ background: "#1E9E5F" }} />done</span>
      <span><span className="sw" style={{ background: "#D98A0C" }} />running / waiting</span>
      <span><span className="sw" style={{ background: "#1D6FE0" }} />path taken</span>
      <span>dashed: a pause or a return into a node that already ran</span>
    </div>
  );
}
