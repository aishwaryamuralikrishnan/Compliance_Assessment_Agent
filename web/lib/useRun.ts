"use client";

// Follow one run's event stream (docs/web_app_design.md §3): the latest view, the interrupt, the final body.

import { useEffect, useState } from "react";
import { subscribeRun } from "@/lib/api";
import type { FinalEvent, InterruptEvent, View } from "@/lib/types";

export interface RunState {
  runId: string | null;
  view: View | null;
  interrupt: InterruptEvent | null;
  final: FinalEvent | null;
  error: string | null;
  done: boolean;
}

export function useRun(runId: string | null): RunState {
  const [state, setState] = useState<RunState>({ runId: null, view: null, interrupt: null, final: null, error: null, done: false });

  useEffect(() => {
    if (!runId) return;
    setState({ runId, view: null, interrupt: null, final: null, error: null, done: false });
    const off = subscribeRun(runId, {
      view: (v) => setState((s) => ({ ...s, view: v as View })),
      interrupt: (v) => setState((s) => ({ ...s, interrupt: v as InterruptEvent })),
      final: (v) => setState((s) => ({ ...s, final: v as FinalEvent, done: true })),
      error: (message) => setState((s) => ({ ...s, error: message, done: true })),
    });
    return off;
  }, [runId]);

  return state;
}
