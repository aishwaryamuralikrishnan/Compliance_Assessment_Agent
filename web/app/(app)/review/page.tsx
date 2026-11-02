"use client";

// The DPO's review queue (UI.md, on the approved canvas): the pending requests on the left, the selected request's
// review form in the middle, the decision's run in Behind the scenes, the outcome below with "Keep as a good
// example" after an approval, and the decision history. For a revision (v2), the previous version and what was asked
// for sit above the form, collapsed, so the comparison is on the main display and not in the panel.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAgent, useSession } from "@/lib/context";
import { agentStateOf, useThreadRuns } from "@/lib/useThreadRuns";
import type { PendingPm, ReviewDetail, ReviewTask } from "@/lib/types";
import ProgressCard from "@/components/ProgressCard";
import ReviewForm from "@/components/ReviewForm";
import VerdictCard from "@/components/VerdictCard";

function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()} ${d.toLocaleString("en-GB", { month: "short" })} ${d.toTimeString().slice(0, 5)}`;
}

export default function ReviewPage() {
  const { user, meta } = useSession();
  const { setAgent } = useAgent();
  const [pending, setPending] = useState<ReviewTask[]>([]);
  const [decided, setDecided] = useState<ReviewTask[]>([]);
  const [taskId, setTaskId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [decision, setDecision] = useState<string | null>(null);
  const [kept, setKept] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const r = useThreadRuns(detail?.task.thread_id || null, user.user_id);
  const t = r.thread;

  const loadQueue = useCallback(async () => {
    try {
      const q = await api.get<{ pending: ReviewTask[]; decided: ReviewTask[] }>("/api/reviews");
      setPending(q.pending);
      setDecided(q.decided);
      setTaskId((cur) => cur ?? (q.pending.length ? q.pending[0].id : null));
      return q;
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e));
      return null;
    }
  }, []);
  // the queue is polled: a product manager's new request or revision lands here without a reload
  useEffect(() => {
    loadQueue();
    const id = setInterval(loadQueue, 5000);
    return () => clearInterval(id);
  }, [loadQueue]);

  useEffect(() => {
    if (taskId === null) { setDetail(null); return; }
    setDecision(null);
    setKept(false);
    api.get<ReviewDetail>(`/api/reviews/${taskId}`).then(setDetail).catch((e) => setProblem(e instanceof ApiError ? e.message : String(e)));
  }, [taskId]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const agent = useMemo(() => (detail ? agentStateOf(r, user.user_id) : null), [r.views, r.live, r.liveView, r.thread, r.runError, detail, user.user_id]);
  useEffect(() => { setAgent(agent); }, [agent, setAgent]);

  // the decision's run finished: the queue moves on
  useEffect(() => {
    if (decision && r.runDone) loadQueue();
  }, [decision, r.runDone, loadQueue]);

  async function onDecision(payload: Record<string, unknown>) {
    if (!detail) return;
    const res = await api.post<{ run_id: string }>(`/api/threads/${detail.task.thread_id}/resume`, payload);
    setDecision(String(payload.decision));
    r.startRun(res.run_id, "decision");
  }

  async function keepExample() {
    if (!detail) return;
    try {
      const res = await api.post<{ run_id: string }>(`/api/threads/${detail.task.thread_id}/feedback`, { keep_example: true });
      setKept(true);
      r.startRun(res.run_id, "feedback");
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function next() {
    const q = await loadQueue();
    setDecision(null);
    setTaskId(q && q.pending.length ? q.pending[0].id : null);
  }

  const outcome = t?.values.answer || null;
  const pm = t?.pending.kind === "pm" ? (t.pending.value as PendingPm) : null;
  const recorded = t?.review_task || null;
  const lastKind = r.views.length ? r.views[r.views.length - 1].kind : "decision";

  return (
    <div className="split" style={{ margin: "-28px -32px -56px -32px" }}>
      <aside className="side" aria-label="Pending requests">
        <div className="eyebrow">Pending · {pending.length}</div>
        <div className="list">
          {pending.map((p) => (
            <button key={p.id} type="button" className={`item${p.id === taskId ? " current" : ""}`} onClick={() => { setDecision(null); setTaskId(p.id); }}>
              <div className="row" style={{ justifyContent: "space-between" }}><span className="mono small" style={{ color: "var(--accent)" }}>#{p.id} · {p.assessment_id}</span><span className="small muted">{when(p.created_at)}</span></div>
              <div style={{ fontWeight: 600, marginTop: 4 }}>{p.title}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{p.requested_by}</div>
            </button>
          ))}
          {pending.length === 0 ? <div className="small muted">No assessments are waiting for review.</div> : null}
        </div>
        <div className="eyebrow" style={{ marginTop: 12 }}>Decided · {decided.length}</div>
        <div className="small muted" style={{ lineHeight: 1.7 }}>
          {decided.map((d) => (
            <div key={d.id}><span className="mono">#{d.id} {d.assessment_id}</span> · {d.status.replace("_", " ")} · {when(d.resolved_at)}{d.dpo_comment ? <span className="faint"> · “{d.dpo_comment}”</span> : null}</div>
          ))}
        </div>
      </aside>

      <main className="page narrow" style={{ flex: "999 1 560px" }}>
        {problem ? <div className="error">{problem}</div> : null}
        {!detail ? <div className="muted">Select a request on the left.</div> : null}

        {detail && !decision ? (
          <>
            <div className="strip">
              <span className="pill paused"><span className="dot" />thread {detail.task.thread_id.slice(0, 8)} · paused at interrupt()</span>
              <span className="mono">state restored from the checkpointer · your decision resumes it under your identity</span>
            </div>
            {detail.previous ? (
              <details className="plain previous">
                <summary>Previous version {detail.previous.assessment.assessment_id} and what you asked for</summary>
                <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
                  {detail.requested_changes ? (
                    <div className="band wait"><span className="dot" /><div><b>What you asked for:</b><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{detail.requested_changes.split("\n").filter((l) => l.trim()).map((l, i) => <li key={i}>{l}</li>)}</ul></div></div>
                  ) : null}
                  <VerdictCard a={detail.previous.assessment} compact />
                </div>
              </details>
            ) : null}
            <ReviewForm key={detail.task.id} task={detail.task} assessment={detail.assessment.assessment} onDecision={onDecision} />
          </>
        ) : null}

        {detail && decision ? (
          <>
            {r.live ? <ProgressCard view={r.liveView} title={lastKind === "feedback" ? "Updating memory" : "Applying your decision"} meta={meta} finished={false} /> : null}
            {r.runError ? <div className="band bad"><span className="dot" /><div>The run failed: {r.runError}</div></div> : null}
            {!r.live && recorded && recorded.status !== "pending" ? (
              <div className={`band ${recorded.status === "approved" ? "ok" : recorded.status === "rejected" ? "bad" : "wait"}`}>
                <span className="dot" />
                <div>
                  <b>{recorded.status.replace("_", " ")}</b> · {detail.task.assessment_id} · {outcome || "Decision applied."}
                  {pm ? <div className="small" style={{ marginTop: 4 }}>The thread is now paused for {pm.requester} to revise the feature (pm_revision · interrupt()); v2 comes back to this queue.</div> : null}
                </div>
              </div>
            ) : null}
            {!r.live && recorded && recorded.status !== "pending" ? (
              <div className="row">
                {recorded.status === "approved" ? (
                  kept ? <span className="small muted">Kept as a good example (org/lessons).</span> : (
                    <button type="button" className="btn" onClick={keepExample} title="Stores this approved assessment as a lesson the assistant uses as an example in future assessments.">Keep as a good example</button>
                  )
                ) : null}
                <button type="button" className="btn" onClick={next}>Next request</button>
              </div>
            ) : null}
            {t?.values.assessment ? (
              <details className="plain" open={recorded?.status === "approved"}>
                <summary>{recorded?.status === "approved" ? "Assessment as recorded" : "Assessment"}</summary>
                <div style={{ marginTop: 10 }}><VerdictCard a={t.values.assessment} compact /></div>
              </details>
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}
