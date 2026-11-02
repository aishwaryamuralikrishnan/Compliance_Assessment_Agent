"use client";

// One hook for a page that works on a thread: the thread body (polled while it waits), the run being streamed, the
// views of every run on the thread (the streaming one carrying its live view), and the agent state the shell shows.
// Used by the Assistant page and the review queue.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AgentKind, AgentState } from "@/lib/context";
import { useRun } from "@/lib/useRun";
import { useThread } from "@/lib/useThread";
import type { RunView, ThreadBody, View } from "@/lib/types";

export interface ThreadRuns {
  thread: ThreadBody | null;
  setThread: (t: ThreadBody | null) => void;
  refresh: () => Promise<ThreadBody | null>;
  threadError: string | null;
  stuck: boolean;
  views: RunView[];
  live: boolean;
  liveView: View | null;
  runError: string | null;
  runDone: boolean;
  startRun: (runId: string, kind: RunView["kind"]) => void;
  reset: () => void;
}

export function statusOf(t: ThreadBody | null, live: boolean, liveView: View | null, me: string, runError: string | null): { kind: AgentKind; status: string } {
  if (runError) return { kind: "error", status: "The run failed" };
  if (live) {
    const g = liveView?.graph;
    const node = g?.active ? g.active.replace("__start__", "start").replace("__end__", "end") : "starting";
    const sub = g?.substep ? ` · ${g.substep}` : g?.gate_state === "pause" ? " · tool gate" : "";
    return { kind: "running", status: `Agent running · ${node}${sub}` };
  }
  if (!t) return { kind: "idle", status: "No run yet" };
  if (t.pending.kind === "dpo") return { kind: "paused", status: "Paused · waiting for the DPO" };
  if (t.pending.kind === "pm") {
    const v = t.pending.value as { requester?: string } | null;
    return { kind: "paused", status: v?.requester === me ? "Paused · waiting for your revision" : `Paused · waiting for ${v?.requester || "the requester"}` };
  }
  if (t.run_in_progress || t.running_run_id) return { kind: "running", status: "The DPO's run is finishing" };
  if (t.review_task && t.review_task.status !== "pending") return { kind: "done", status: `Run complete · ${t.review_task.status.replace("_", " ")}` };
  if (t.values.answer || t.values.assessment) return { kind: "done", status: "Run complete" };
  return { kind: "idle", status: "No run yet" };
}

export function useThreadRuns(threadId: string | null, me: string): ThreadRuns {
  const [runId, setRunId] = useState<string | null>(null);
  const runKind = useRef<RunView["kind"]>("turn");
  const run = useRun(runId);
  const [serverDone, setServerDone] = useState(false);
  const live = !!runId && !run.done && !serverDone;

  const attach = useCallback((id: string) => {
    runKind.current = "decision";
    setRunId((cur) => (cur === id ? cur : id));
  }, []);
  // polled while the thread waits and, as a watchdog, while a run streams: the server's thread body says when a run
  // is done even if the stream's last message never reached the browser
  const thread = useThread(threadId, { poll: !!threadId, onRunning: attach });
  useEffect(() => {
    const v = thread.thread?.views?.find((x) => x.run_id === runId);
    setServerDone(!!v && v.done);
  }, [thread.thread, runId]);

  // the run finished: its final body is the thread
  const finalSeen = useRef<string | null>(null);
  useEffect(() => {
    if (run.final && finalSeen.current !== run.final.run_id) {
      finalSeen.current = run.final.run_id;
      thread.set(run.final.thread);
    }
  }, [run.final, thread]);

  const views = useMemo<RunView[]>(() => {
    const base: RunView[] = (thread.thread?.views || []).map((v) => (v.run_id === runId && run.view ? { ...v, view: run.view, done: run.done } : v));
    if (runId && run.view && !base.some((v) => v.run_id === runId)) {
      base.push({ run_id: runId, kind: runKind.current, user_id: me, done: run.done, error: run.error, view: run.view });
    }
    return base;
  }, [thread.thread, runId, run.view, run.done, run.error, me]);

  const startRun = useCallback((id: string, kind: RunView["kind"]) => {
    runKind.current = kind;
    setServerDone(false);
    setRunId(id);
  }, []);
  const reset = useCallback(() => {
    setRunId(null);
    thread.set(null);
  }, [thread]);

  return {
    thread: thread.thread, setThread: thread.set, refresh: thread.refresh, threadError: thread.error, stuck: thread.stuck,
    views, live, liveView: live ? run.view : null, runError: run.error, runDone: run.done || serverDone, startRun, reset,
  };
}

export function agentStateOf(r: ThreadRuns, me: string): AgentState {
  const { kind, status } = statusOf(r.thread, r.live, r.liveView, me, r.runError);
  return { views: r.views, live: r.live, kind, status };
}
