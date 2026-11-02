"use client";

// The Assistant page (UI.md, on the approved canvas): the request, the progress card while the agent works, then
// the assessment as the hero or the short answer; the waiting band while the DPO decides, her decision when it
// comes (a second run on the same thread, shown in Behind the scenes), the revision form when she requested
// changes, and the preference note once the thread has completed. One request per conversation.

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAgent, useSession } from "@/lib/context";
import { agentStateOf, useThreadRuns } from "@/lib/useThreadRuns";
import type { PendingDpo, PendingPm } from "@/lib/types";
import PreferenceNote from "@/components/PreferenceNote";
import ProgressCard, { ResultSkeleton } from "@/components/ProgressCard";
import RevisionForm from "@/components/RevisionForm";
import VerdictCard from "@/components/VerdictCard";

const STORAGE_KEY = "compliance.thread_id"; // per browser tab: two tabs are two conversations

function readStored(): string | null {
  try { return sessionStorage.getItem(STORAGE_KEY); } catch { return null; }
}
function store(id: string | null) {
  try { id ? sessionStorage.setItem(STORAGE_KEY, id) : sessionStorage.removeItem(STORAGE_KEY); } catch { /* no storage */ }
}

export default function AssistantPage() {
  const { user, meta } = useSession();
  const { setAgent } = useAgent();
  const [threadId, setThreadId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [prefSaved, setPrefSaved] = useState<string | null>(null);
  const r = useThreadRuns(threadId, user.user_id);
  const t = r.thread;

  useEffect(() => { setThreadId(readStored()); }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const agent = useMemo(() => (threadId ? agentStateOf(r, user.user_id) : null), [r.views, r.live, r.liveView, r.thread, r.runError, threadId, user.user_id]);
  useEffect(() => { setAgent(agent); }, [agent, setAgent]);

  async function submit() {
    const message = text.trim();
    if (!message) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await api.post<{ run_id: string; thread_id: string }>("/api/threads", { message });
      store(res.thread_id);
      setThreadId(res.thread_id);
      r.startRun(res.run_id, "turn");
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function newConversation() {
    store(null);
    setThreadId(null);
    r.reset();
    setText("");
    setProblem(null);
    setPrefSaved(null);
    setAgent(null);
  }

  const a = t?.values.assessment || null;
  const answer = t?.values.answer || null;
  const pendingDpo = t?.pending.kind === "dpo" ? (t.pending.value as PendingDpo) : null;
  const pendingPm = t?.pending.kind === "pm" ? (t.pending.value as PendingPm) : null;
  const decided = t?.review_task && t.review_task.status !== "pending" ? t.review_task : null;
  const completed = !!t && !t.pending.kind && !r.live && !t.run_in_progress && !t.running_run_id;
  const rejectedInput = !!t && !a && !!answer && t.values.route === "reject";
  const lastKind = r.views.length ? r.views[r.views.length - 1].kind : "turn";
  const liveTitle = lastKind === "revision" ? "Running the revision" : lastKind === "decision" ? "Applying the DPO's decision" : lastKind === "feedback" ? "Updating memory" : "Drafting the assessment";

  if (!threadId) {
    return (
      <>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700 }}>Describe the feature or ask a question</h2>
          <p className="muted" style={{ margin: "4px 0 0 0" }}>A full assessment goes to the DPO automatically; only her approval writes the register. One request per conversation.</p>
        </div>
        <section className="card pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} disabled={busy} autoFocus
                    placeholder="e.g. We're adding automated credit scoring to our checkout using transaction history and browsing behaviour …" />
          {problem ? <div className="error">{problem}</div> : null}
          <div className="row">
            <button type="button" className="btn primary" onClick={submit} disabled={busy || !text.trim()}>Run assessment</button>
            <span className="small muted">Your text is screened first (limits, PII redaction, injection check), then routed: a quick answer, a full assessment, or a refusal.</span>
          </div>
        </section>
      </>
    );
  }

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <div className="eyebrow">Request · thread {threadId.slice(0, 8)}</div>
          <div style={{ fontSize: 15, marginTop: 4, color: "var(--ink-2)" }}>{t?.values.input || text}</div>
        </div>
        <button type="button" className="btn" onClick={newConversation}>New conversation</button>
      </div>
      {r.threadError ? <div className="error">{r.threadError}</div> : null}

      {r.live ? (
        <>
          <ProgressCard view={r.liveView} title={liveTitle} meta={meta} finished={false} />
          {!a && !answer ? <ResultSkeleton text="The assessment card appears here when the guardrail has verified every citation; a question gets a short cited answer instead." /> : null}
        </>
      ) : null}
      {r.runError ? <div className="band bad"><span className="dot" /><div>The run failed: {r.runError}. The thread's state is whatever the checkpointer holds; see the API log.</div></div> : null}

      {pendingPm && pendingPm.requester === user.user_id && !r.live ? (
        <RevisionForm threadId={threadId} pending={pendingPm} onStarted={(id) => r.startRun(id, "revision")} />
      ) : null}
      {pendingPm && pendingPm.requester !== user.user_id ? (
        <div className="band wait"><span className="dot" /><div>This thread waits for {pendingPm.requester} to revise {pendingPm.revises}; only the requester can.</div></div>
      ) : null}

      {a ? (
        <VerdictCard a={a} status={<>{t?.status_text}{t?.status === "pending_review" || t?.status === "draft" ? " Sent to the DPO automatically; only the DPO's approval writes the register." : ""}</>} />
      ) : null}

      {completed && !a && !answer && t?.values.route === "quick" ? (
        <div className="band bad"><span className="dot" /><div><b>The model returned no text.</b> The quick path ran to the end but the answer is empty: a reasoning model can use its whole output budget before writing the answer. The trace says how many tokens it spent; raise <code>max_tokens</code> for the <code>worker_quick</code> slot in <code>config/models.yaml</code> and start a new conversation.</div></div>
      ) : null}
      {answer && !a ? (
        rejectedInput ? (
          <div className="band bad"><span className="dot" /><div><b>Not assessed.</b> {answer}</div></div>
        ) : (
          <section className="card pad" aria-label="Answer" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="eyebrow">Answer · quick path</div>
            <div style={{ fontSize: 15, lineHeight: 1.6 }}>{answer}</div>
            {t?.values.sources?.length ? <div className="mono small muted">Sources: {t.values.sources.map((s) => s.citation).filter(Boolean).join(" · ")}</div> : null}
            <div className="small faint">Quick model over one retrieval pass; citations verified by the guardrail. Not legal advice.</div>
          </section>
        )
      ) : null}

      {pendingDpo && !r.live ? (
        <div className="band wait">
          <span className="dot" />
          <div><b>Waiting for the DPO</b> · request #{pendingDpo.task_id} is in the DPO&apos;s queue. This page updates by itself when she decides; her run appears in Behind the scenes.</div>
        </div>
      ) : null}
      {r.stuck ? <div className="band bad"><span className="dot" /><div>The DPO&apos;s run did not finish within five minutes; showing the thread as it is. Ask the DPO to check her window.</div></div> : null}

      {decided && !r.live && !pendingPm ? (
        <div className={`band ${decided.status === "approved" ? "ok" : decided.status === "rejected" ? "bad" : "wait"}`}>
          <span className="dot" />
          <div>
            <b>{decided.status.replace("_", " ")}</b> by {decided.resolved_by}{decided.dpo_comment ? <>: “{decided.dpo_comment}”</> : null}
            {t?.values.answer && a ? <div className="small" style={{ marginTop: 4 }}>{t.values.answer}</div> : null}
          </div>
        </div>
      ) : null}

      {completed || (r.live && lastKind === "feedback") || prefSaved ? (
        <section className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="eyebrow">Your preference</div>
          <PreferenceNote threadId={threadId} saved={prefSaved} onSaved={setPrefSaved} onStarted={(id) => r.startRun(id, "feedback")} />
        </section>
      ) : null}
    </>
  );
}
