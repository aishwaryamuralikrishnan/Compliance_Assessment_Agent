"use client";

// Contexts the shell provides. The session (user, models, graph layout), and the "agent" state a page publishes
// for the shell's top-bar pill and its Behind-the-scenes panel: the views of the runs on the current thread, whether
// one is streaming.

import { createContext, useContext } from "react";
import type { GraphLayout, Meta, RunView, User } from "@/lib/types";

export interface Session {
  user: User;
  meta: Meta | null;
  layout: GraphLayout | null;
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside the shell");
  return s;
}

export type AgentKind = "idle" | "running" | "paused" | "done" | "error";

export interface AgentState {
  views: RunView[];          // every run of the thread, in order; the streaming one carries its live view
  live: boolean;             // a run is streaming right now
  kind: AgentKind;           // drives the top-bar pill
  status: string;            // the pill's text, e.g. "Agent running · worker · searching the GDPR"
}

export interface AgentContextValue {
  agent: AgentState | null;
  setAgent: (a: AgentState | null) => void;
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
}

export const AgentContext = createContext<AgentContextValue>({ agent: null, setAgent: () => {}, panelOpen: false, setPanelOpen: () => {} });

export function useAgent(): AgentContextValue {
  return useContext(AgentContext);
}
