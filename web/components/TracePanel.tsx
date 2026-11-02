import type { RunView, TraceSection } from "@/lib/types";

/** The text flow: one block per graph node, tool calls in grey boxes (the approved canvas). The items and row
 *  details are HTML snippets the server produced and escaped (trace.TraceBuilder). Several runs on a thread (the
 *  assessment, the DPO's decision, a revision) are stacked, each under a small heading. */
export function Sections({ sections }: { sections: TraceSection[] }) {
  if (sections.length === 0) return <div className="sec muted">waiting for the first event …</div>;
  return (
    <>
      {sections.map((s) => (
        <div key={s.key} className={`sec ${s.cls}`.trim()}>
          <div className="sec-h">
            {s.cls === "tool" ? "⚙ " : ""}{s.title}
            {s.subtitle ? <span className="q" dangerouslySetInnerHTML={{ __html: s.subtitle }} /> : null}
          </div>
          {s.items.length > 0 ? <ul>{s.items.map((it, i) => <li key={i} dangerouslySetInnerHTML={{ __html: it }} />)}</ul> : null}
          {s.rows.map((r, i) => (
            <div key={i} className="tr" title={r.tip || undefined}>
              <span className="lb">{r.label}</span>
              <span className="dt" dangerouslySetInnerHTML={{ __html: r.detail }} />
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

export const RUN_LABEL: Record<RunView["kind"], string> = {
  turn: "the assessment", decision: "the DPO's decision", revision: "the revision", feedback: "feedback",
};

export default function TracePanel({ views }: { views: RunView[] }) {
  if (views.length === 0) return <div className="trace"><div className="sec muted">no run on this thread yet</div></div>;
  return (
    <div className="trace">
      {views.map((v, i) => (
        <div key={v.run_id}>
          {views.length > 1 || i > 0 ? <div className="run-h">{i + 1} · {RUN_LABEL[v.kind]} · {v.user_id}{v.done ? "" : " · running"}</div> : null}
          <Sections sections={v.view.trace} />
          {v.error ? <div className="sec bad">run failed: {v.error}</div> : null}
        </div>
      ))}
    </div>
  );
}
