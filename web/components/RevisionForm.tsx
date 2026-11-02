"use client";

// The product manager's revision (design v2 §6): the DPO's requested changes with done / not possible and a note
// each, the description pre-filled with the previous one, the reason when a resume was refused, Run revision.

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PendingPm } from "@/lib/types";

export default function RevisionForm({ threadId, pending, onStarted }: { threadId: string; pending: PendingPm; onStarted: (runId: string) => void }) {
  const [responses, setResponses] = useState(pending.requests.map(() => ({ status: "done" as "done" | "not_possible", note: "" })));
  const [text, setText] = useState(pending.previous_description || "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function setResp(i: number, patch: Partial<{ status: "done" | "not_possible"; note: string }>) {
    setResponses((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      const r = await api.post<{ run_id: string }>(`/api/threads/${threadId}/resume`, { description: text.trim(), responses: responses.map((x) => ({ status: x.status, note: x.note.trim() })) });
      onStarted(r.run_id);
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <section className="card pad" aria-label="Revise the feature" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="band wait">
        <span className="dot" />
        <div>
          <b>Changes requested by the DPO ({pending.requested_by || "DPO"})</b> before {pending.revises} can be approved. The thread is paused for you: answer each request, revise the description, then run the revision.
          {pending.comment ? <div className="small" style={{ marginTop: 4 }}>“{pending.comment}”</div> : null}
        </div>
      </div>
      {pending.error ? <div className="band bad"><span className="dot" /><div>Your previous revision was not accepted: {pending.error}</div></div> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {pending.requests.map((req, i) => (
          <div key={i} className="inset" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div><b>{i + 1}.</b> {req}</div>
            <div className="row">
              <span className="radio">
                <label><input type="radio" name={`r${i}`} checked={responses[i].status === "done"} onChange={() => setResp(i, { status: "done" })} /> done</label>
                <label><input type="radio" name={`r${i}`} checked={responses[i].status === "not_possible"} onChange={() => setResp(i, { status: "not_possible" })} /> not possible</label>
              </span>
              <input type="text" value={responses[i].note} onChange={(e) => setResp(i, { note: e.target.value })} placeholder="done: what you changed · not possible: why" style={{ flex: 1, minWidth: 240 }} />
            </div>
          </div>
        ))}
      </div>
      <label className="field">Revised feature description
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} />
      </label>
      {problem ? <div className="error">{problem}</div> : null}
      <div className="row">
        <button type="button" className="btn primary" onClick={submit} disabled={busy || !text.trim()}>Run revision</button>
        <span className="small muted">The reviser produces v2 linked to {pending.revises}; it goes to the DPO like any assessment.</span>
      </div>
    </section>
  );
}
