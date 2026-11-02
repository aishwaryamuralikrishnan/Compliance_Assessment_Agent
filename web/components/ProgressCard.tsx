import { deriveSteps } from "@/lib/steps";
import type { Meta, View } from "@/lib/types";

/** The progress card while a run streams (the approved canvas): a horizontal stepper read off the view, three facts
 *  (memory read, tools bound, model and tokens), and a placeholder for the card that is coming. */
export default function ProgressCard({ view, title, meta, finished }: { view: View | null; title: string; meta: Meta | null; finished: boolean }) {
  const steps = deriveSteps(view, finished);
  // the agent's opening line ("reading memory: … · tools bound: …"): in a resumed run it is not the first item of the
  // first agent section (the gate's decision line comes before it), so every agent section is searched
  const agentText = (view?.trace || []).filter((s) => s.title === "worker" || s.title === "reviser" || s.title === "direct_answer")
    .flatMap((s) => s.items).map((i) => i.replace(/<[^>]+>/g, "")).join("\n");
  const mem = /reading memory: ([^·\n]+)/.exec(agentText)?.[1]?.trim() || (agentText.includes("memory unavailable") ? "memory unavailable" : "—");
  const tools = /tools bound: ([^\n]+)/.exec(agentText)?.[1]?.trim() || "—";
  const model = meta?.models.worker || "—";
  const s = view?.stats;
  return (
    <section className="card pad" aria-label="Progress" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div style={{ fontSize: 17, fontWeight: 600 }}>{title}</div>
        <div className="mono small muted">{s ? `${s.elapsed.toFixed(1)} s · ${s.searches} searches · ${s.rewrites} rewrites · $${s.cost.toFixed(4)}` : "starting…"}</div>
      </div>
      <ol className="steps" style={{ gridTemplateColumns: `repeat(${Math.max(steps.length, 3)}, minmax(0, 1fr))` }}>
        {steps.map((st) => (
          <li key={st.name} className={st.state === "todo" ? "" : st.state}>
            <span className="bar" />
            <span className="name">{st.name}</span>
            <span className="sub" title={st.sub}>{st.sub}</span>
          </li>
        ))}
        {steps.length === 0 ? <li className="on"><span className="bar" /><span className="name">Starting</span><span className="sub">waiting for the first event</span></li> : null}
      </ol>
      <div className="facts">
        <div className="inset"><div className="k">Memory read</div><div className="v">{mem}</div></div>
        <div className="inset"><div className="k">Tools bound</div><div className="v mono small">{tools}</div></div>
        <div className="inset"><div className="k">Model</div><div className="v">{model}{s ? ` · ${s.tokens_in} in / ${s.tokens_out} out${s.cached ? ` · ${s.cached} cached` : ""}` : ""}</div></div>
      </div>
    </section>
  );
}

export function ResultSkeleton({ text }: { text: string }) {
  return (
    <section className="skeleton" aria-label="Result placeholder">
      <div className="ln h" style={{ width: "46%" }} />
      <div className="ln" style={{ width: "82%" }} />
      <div className="ln" style={{ width: "70%" }} />
      <div className="small" style={{ marginTop: 6 }}>{text}</div>
    </section>
  );
}
