import type { Assessment, ChangeNote } from "@/lib/types";

export const SEV_CLASS: Record<string, string> = { Blocker: "bad", Required: "warn", Covered: "ok" };
export const VERDICT_CLASS: Record<string, string> = { "Do not build as described": "bad", "Proceed with conditions": "warn", Proceed: "ok" };

export function Cites({ cites }: { cites: string[] }) {
  if (!cites.length) return <i className="muted">no citation</i>;
  return <>{cites.map((c, i) => <span key={i}>{i ? " · " : ""}<span className="cite" style={{ color: "var(--accent)" }}>{c}</span></span>)}</>;
}

export function Flags({ a }: { a: Assessment }) {
  const risk = (a.risk_level || "").replace(/^\w/, (c) => c.toUpperCase());
  return (
    <div className="row" style={{ gap: 8 }}>
      {a.assessment_id ? <span className="mono small muted">{a.assessment_id}</span> : null}
      <span className={`chip ${VERDICT_CLASS[a.verdict] || "neutral"}`}>{risk || "unknown"} risk</span>
      {a.high_risk_ai ? <span className="chip ai">High-risk AI · Annex III</span> : null}
      {a.dpia_required ? <span className="chip dpia">DPIA required · Art. 35</span> : null}
    </div>
  );
}

function Changes({ a }: { a: Assessment }) {
  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: 10 }}>Changes since {a.revises}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {(a.changes_since_v1 || []).map((c: ChangeNote, i) => (
          <div key={i} className="change">
            <span className={`chip sev ${c.outcome}`}>{c.outcome}</span>
            <div>
              <b>DPO:</b> {c.request} &nbsp;·&nbsp; <b>PM:</b> {c.pm_response}
              <div className="muted">{c.explanation}{c.finding && c.finding !== "none" ? <i> ({c.finding})</i> : null}</div>
            </div>
          </div>
        ))}
      </div>
      {a.revision_rule_violation ? (
        <div className="band wait" style={{ marginTop: 10 }}><span className="dot" /><div>Revision rule not met by the reviser, even after one retry: {a.revision_rule_violation} The DPO should treat this version with care.</div></div>
      ) : null}
    </div>
  );
}

/** The assessment as the hero (the approved canvas): verdict headline, flags, findings, next steps and sources,
 *  disclaimer and the Markdown download. `compact` drops the download row (the panel's previous-version view). */
export default function VerdictCard({ a, compact, status }: { a: Assessment; compact?: boolean; status?: React.ReactNode }) {
  if (!a) return <div className="band bad"><span className="dot" /><div>No assessment stored for this entry.</div></div>;
  const tone = VERDICT_CLASS[a.verdict] || "neutral";
  return (
    <article className={`card verdict ${tone}`} aria-label={`Assessment ${a.assessment_id || ""}`}>
      <div className="hero">
        <Flags a={a} />
        <h1>{a.verdict}</h1>
        <div className="summary"><b>{a.title}.</b> {a.summary}</div>
      </div>
      <div className="rest">
        {a.revises ? <Changes a={a} /> : null}
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Findings</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(a.findings || []).length === 0 ? <span className="muted small">no findings stored</span> : null}
            {(a.findings || []).map((f, i) => (
              <div key={i} className="finding">
                <span className={`chip sev ${SEV_CLASS[f.severity] || "neutral"}`}>{f.severity}</span>
                <div>{f.text} <Cites cites={f.citations || []} /></div>
              </div>
            ))}
          </div>
        </div>
        <div className="two">
          <div className="inset">
            <div className="eyebrow" style={{ marginBottom: 8 }}>Next steps</div>
            {a.next_steps?.length ? (
              <ol style={{ margin: 0, paddingLeft: 18, color: "var(--ink-2)", display: "flex", flexDirection: "column", gap: 4 }}>
                {a.next_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            ) : <span className="muted">none</span>}
          </div>
          <div className="inset">
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              Sources · {a.verified_citations?.length || 0} verified{a.unverified_citations?.length ? ` · ${a.unverified_citations.length} not checked` : ""}
            </div>
            <div className="mono small" style={{ color: "var(--ink-2)", lineHeight: 1.7 }}>{a.sources?.join(" · ") || "-"}</div>
            {a.unverified_citations?.length ? (
              <div className="band wait" style={{ marginTop: 8 }}><span className="dot" /><div>The corpus could not be queried for {a.unverified_citations.join(", ")}: kept but not verified; see the server log.</div></div>
            ) : null}
          </div>
        </div>
        {!compact ? (
          <div className="foot">
            <span className="small muted">{a.disclaimer || "Automated first assessment, not legal advice."}{status ? <> {status}</> : null}</span>
            <span className="grow" />
            {a.assessment_id ? <a className="btn" href={`/api/assessments/${a.assessment_id}.md`} download>Download .md</a> : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
