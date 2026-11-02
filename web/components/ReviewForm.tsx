"use client";

// The DPO's review form (UI.md "Review queue", on the approved canvas): the findings with editable severity and
// wording, the comment, "What the assistant will remember" (the deterministic candidates, re-fetched as she types),
// and the three decisions. Returns nothing itself: the decision is a resume of the thread started by the page.

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Assessment, MemoryCandidatesOut, ReviewTask } from "@/lib/types";
import { Cites, Flags, SEV_CLASS, VERDICT_CLASS } from "@/components/VerdictCard";

const SEVERITIES = ["Blocker", "Required", "Covered"] as const;

export default function ReviewForm({ task, assessment, onDecision }: { task: ReviewTask; assessment: Assessment; onDecision: (payload: Record<string, unknown>) => Promise<void> }) {
  const [findings, setFindings] = useState(assessment.findings.map((f) => ({ ...f })));
  const [comment, setComment] = useState("");
  const [cands, setCands] = useState<MemoryCandidatesOut | null>(null);
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const [need, setNeed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const amended = useMemo<Assessment | null>(() => {
    const changed = findings.some((f, i) => f.severity !== assessment.findings[i].severity || f.text !== assessment.findings[i].text);
    return changed ? { ...assessment, findings } : null;
  }, [findings, assessment]);

  // the memory candidates follow the amendments and the comment (debounced)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.post<MemoryCandidatesOut>(`/api/reviews/${task.id}/memory-candidates`, { amended, comment })
        .then((c) => {
          setCands(c);
          setTicked((old) => {
            const next: Record<string, boolean> = {};
            [...c.amendments, ...c.note].forEach((x, i) => { const k = `${x.item.source}:${i}`; next[k] = old[k] ?? x.allowed; });
            return next;
          });
        })
        .catch(() => setCands(null));
    }, 350);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [amended, comment, task.id]);

  function chosen(decision: "approve" | "request_changes" | "reject") {
    if (!cands) return [];
    const picked = [...cands.amendments, ...cands.note].filter((x, i) => ticked[`${x.item.source}:${i}`]).map((x) => x.item);
    if (decision === "approve") return picked;
    const fixed = (decision === "reject" ? cands.on_reject : cands.on_changes).map((x) => x.item);
    return [...picked.filter((it) => it.source === "dpo_amendment"), ...fixed];
  }

  async function decide(decision: "approve" | "request_changes" | "reject") {
    if (decision !== "approve" && !comment.trim()) {
      setNeed(decision);
      return;
    }
    setNeed(null);
    setBusy(true);
    setProblem(null);
    try {
      const payload: Record<string, unknown> = { decision, comment, memory_items: chosen(decision) };
      if (decision === "approve") payload.assessment = amended;
      await onDecision(payload);
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }

  const tone = VERDICT_CLASS[assessment.verdict] || "neutral";
  return (
    <>
      <div>
        <div className="row" style={{ gap: 10 }}>
          <span className="mono small muted">#{task.id} · requested by {task.requested_by}</span>
          <Flags a={assessment} />
        </div>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: "8px 0 4px 0" }}>{assessment.title}</h1>
        <div style={{ color: "var(--ink-2)", maxWidth: "72ch" }}><b className={`chip ${tone}`} style={{ marginRight: 6 }}>{assessment.verdict}</b> {assessment.summary}</div>
        <div className="small muted" style={{ marginTop: 6 }}>
          Register entry to be written on approval: title, verdict, findings with citations, DPIA required = {assessment.dpia_required ? "yes" : "no"}, AI Act class = {assessment.high_risk_ai ? "high-risk" : "not high-risk"}.
          {assessment.revises ? <> This is a revision of {assessment.revises}; the previous version and what you asked for are folded above this card.</> : null}
        </div>
      </div>

      <section className="card pad" aria-label="Review and amend the assessment" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="eyebrow">Findings · edit severity or wording, then approve</div>
          <span className="small muted">citations are verified by the guardrail and not editable</span>
        </div>
        <div className="editor-grid">
          {findings.map((f, i) => {
            const orig = assessment.findings[i];
            const changed = f.severity !== orig.severity || f.text !== orig.text;
            return (
              <div key={i} style={{ display: "contents" }}>
                <label className="field">Severity
                  <select className={changed ? "amended" : undefined} value={f.severity} onChange={(e) => setFindings((fs) => fs.map((x, j) => (j === i ? { ...x, severity: e.target.value as typeof f.severity } : x)))}
                          style={{ color: `var(--${SEV_CLASS[f.severity] || "ink"}-ink)`, fontWeight: 600, width: "100%" }}>
                    {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Finding{changed ? <span style={{ color: "var(--warn-ink)" }}> · amended{f.severity !== orig.severity ? `: ${orig.severity} → ${f.severity}` : ""}</span> : null}</span>
                  <textarea className={changed ? "amended" : undefined} rows={2} value={f.text} onChange={(e) => setFindings((fs) => fs.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
                  <span><Cites cites={f.citations} /></span>
                </label>
              </div>
            );
          })}
        </div>
        {assessment.next_steps?.length ? <div className="small muted"><b>Next steps:</b> {assessment.next_steps.map((s, i) => `${i + 1}. ${s}`).join(" ")}</div> : null}
      </section>

      <section className="two" aria-label="Decision">
        <label className="field"><span className="eyebrow">Comment to the product manager</span>
          <textarea rows={7} value={comment} onChange={(e) => setComment(e.target.value)}
                    placeholder="Approve: optional note. Request changes: what must change in the feature, one per line (required). Reject: the reason (required). To correct the assessment's wording or severity, edit the findings above and approve." />
        </label>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="eyebrow">What the assistant will remember</div>
          <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
            {cands && [...cands.amendments, ...cands.note].length === 0 ? <div className="small muted">No amendment or comment yet: edit a finding or write a comment and a lesson appears here.</div> : null}
            {cands ? [...cands.amendments, ...cands.note].map((x, i) => {
              const k = `${x.item.source}:${i}`;
              return (
                <label key={k} className="check">
                  <input type="checkbox" checked={!!ticked[k]} disabled={!x.allowed} onChange={(e) => setTicked((o) => ({ ...o, [k]: e.target.checked }))} />
                  <span><span className="mono small" style={{ color: "var(--accent)" }}>{x.label}</span> ← {String(x.item.text)}{x.item.source === "dpo_comment" ? <span className="muted"> (on approve · rephrased by the cheap model)</span> : null}</span>
                </label>
              );
            }) : <div className="small muted">…</div>}
            {cands?.on_changes.map((x, i) => (
              <label key={`c${i}`} className="check"><input type="checkbox" checked disabled /><span><span className="mono small" style={{ color: "var(--accent)" }}>{x.label}</span> ← {String(x.item.text)} <span className="muted">(on request changes · rephrased)</span></span></label>
            ))}
            {cands?.on_reject.map((x, i) => (
              <label key={`r${i}`} className="check"><input type="checkbox" checked disabled /><span><span className="mono small" style={{ color: "var(--accent)" }}>{x.label}</span> ← {String(x.item.text)} <span className="muted">(on reject · rephrased)</span></span></label>
            ))}
            <div className="small faint">Written by memory_write when the thread resumes, under your role; org facts and lessons are DPO-only. Nothing from the feature description itself is stored.</div>
          </div>
        </div>
      </section>

      <div className="row">
        <button type="button" className="btn approve" onClick={() => decide("approve")} disabled={busy}>Approve and record</button>
        <button type="button" className="btn changes" onClick={() => decide("request_changes")} disabled={busy}>Request changes</button>
        <button type="button" className="btn reject" onClick={() => decide("reject")} disabled={busy}>Reject</button>
        <span className="small muted">Approval writes the register under your identity; the other two record nothing and need a reason.</span>
      </div>
      {need === "request_changes" ? <div className="band wait"><span className="dot" /><div>Write the requested changes in the comment box, one per line; they go to the requester and to the reviser.</div></div> : null}
      {need === "reject" ? <div className="band wait"><span className="dot" /><div>A rejection needs a reason in the comment box; it goes to the requester and into the decision history.</div></div> : null}
      {problem ? <div className="error">{problem}</div> : null}
    </>
  );
}
