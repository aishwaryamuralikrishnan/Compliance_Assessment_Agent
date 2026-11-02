"use client";

// The thread body (GET /api/threads/{id}), polled every 4 s while the thread waits
// for the DPO or a run started elsewhere is finishing; the moment the API reports a run executing on the thread
// (`running_run_id`), the caller attaches to that run's stream, which is how the DPO's decision plays live in the
// product manager's window. A run that never finishes is reported after five minutes.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ThreadBody } from "@/lib/types";

const POLL_MS = 4000;
const STUCK_MS = 5 * 60 * 1000;

export interface ThreadState {
  thread: ThreadBody | null;
  loading: boolean;
  error: string | null;
  stuck: boolean;
  refresh: () => Promise<ThreadBody | null>;
  set: (t: ThreadBody | null) => void;
}

export function useThread(threadId: string | null, { poll, onRunning }: { poll: boolean; onRunning?: (runId: string) => void }): ThreadState {
  const [thread, setThread] = useState<ThreadBody | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stuck, setStuck] = useState(false);
  const since = useRef<number | null>(null);
  const onRunningRef = useRef(onRunning);
  onRunningRef.current = onRunning;

  const refresh = useCallback(async () => {
    if (!threadId) return null;
    try {
      const body = await api.get<ThreadBody>(`/api/threads/${threadId}`);
      setThread(body);
      setError(null);
      if (body.running_run_id) onRunningRef.current?.(body.running_run_id);
      if (body.run_in_progress && !body.running_run_id) {
        since.current = since.current ?? Date.now();
        setStuck(Date.now() - since.current > STUCK_MS);
      } else {
        since.current = null;
        setStuck(false);
      }
      return body;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setThread(null);
      else setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, [threadId]);

  useEffect(() => {
    if (!threadId) {
      setThread(null);
      return;
    }
    setLoading(true);
    refresh().finally(() => setLoading(false));
  }, [threadId, refresh]);

  useEffect(() => {
    if (!threadId || !poll) return;
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [threadId, poll, refresh]);

  return { thread, loading, error, stuck, refresh, set: setThread };
}
