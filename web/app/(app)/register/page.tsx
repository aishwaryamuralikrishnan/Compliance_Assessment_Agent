"use client";

// The processing register (UI.md): every entry the DPO approved and recorded, the full assessment under each, the
// v1 → v2 history for revisions, and the PDF export for the DPO.

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAgent } from "@/lib/context";
import type { RegisterEntry } from "@/lib/types";
import VerdictCard from "@/components/VerdictCard";

function when(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${d.toTimeString().slice(0, 5)}`;
}

export default function RegisterPage() {
  const { setAgent } = useAgent();
  const [entries, setEntries] = useState<RegisterEntry[] | null>(null);
  const [canExport, setCanExport] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => { setAgent(null); }, [setAgent]);
  useEffect(() => {
    api.get<{ entries: RegisterEntry[]; can_export: boolean }>("/api/register")
      .then((r) => { setEntries(r.entries); setCanExport(r.can_export); })
      .catch((e) => setProblem(e instanceof ApiError ? e.message : String(e)));
  }, []);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700 }}>Processing register</h2>
          <p className="muted" style={{ margin: "4px 0 0 0" }}>{entries ? `${entries.length} entries` : "…"} · every assessment the DPO approved and recorded, the agent&apos;s goal state. Rejected or revised requests are not here; see the decision history on the review queue.</p>
        </div>
        {canExport ? <a className="btn" href="/api/register.pdf" download title="The overview table and every recorded assessment in full, for audits.">Export register (PDF)</a> : <span className="small muted">Export is available to the DPO.</span>}
      </div>
      {problem ? <div className="error">{problem}</div> : null}
      {entries && entries.length === 0 ? <div className="band wait"><span className="dot" /><div>The register is empty. Entries appear here once the DPO approves an assessment.</div></div> : null}
      {entries && entries.length > 0 ? (
        <div className="tblwrap">
          <table className="tbl">
            <thead><tr><th>id</th><th>title</th><th>verdict</th><th>risk</th><th>high-risk AI</th><th>DPIA required</th><th>requested by</th><th>approved by</th><th>approved at</th></tr></thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.assessment_id}>
                  <td className="mono">{e.assessment_id}</td><td>{e.title}</td><td>{e.verdict}</td><td>{e.risk_level}</td>
                  <td>{e.high_risk_ai ? "yes" : "no"}</td><td>{e.dpia_required ? "yes" : "no"}</td><td>{e.requested_by}</td><td>{e.approved_by}</td><td className="mono">{when(e.approved_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {entries && entries.length > 0 ? <div className="small faint">A yes under <i>high-risk AI</i> means the assessment classified the activity as a high-risk AI system under the AI Act (Annex III); a yes under <i>DPIA required</i> means it concluded a data protection impact assessment must be done before processing (GDPR Art. 35).</div> : null}
      {entries?.map((e) => (
        <details key={e.assessment_id} className="plain">
          <summary>{e.assessment_id} · {e.title}{e.revises ? ` · revises ${e.revises}` : ""}</summary>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 12 }}>
            <VerdictCard a={e.assessment} compact />
            {e.history.length ? (
              <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="eyebrow">History</div>
                {e.history.map((h) => (
                  <div key={h.assessment_id} className="small">
                    <b>v{h.version} · {h.assessment_id}</b> · {when(h.created_at)} · {h.assessment?.verdict}
                    {h.decision ? <> → <b>{h.decision.status.replace("_", " ")}</b> by {h.decision.resolved_by}{h.decision.dpo_comment ? `: ${h.decision.dpo_comment}` : ""}</> : null}
                    {h.description ? <div className="muted">Feature as described: {h.description}</div> : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </details>
      ))}
    </>
  );
}
