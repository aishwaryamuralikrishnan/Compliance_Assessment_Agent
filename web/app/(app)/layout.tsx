"use client";

// The shell (the approved canvas): the navy icon rail, the top bar with the agent's status pill, the page, and
// the Behind-the-scenes panel on the right. Loads the session once; a missing session goes to /login.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { AgentContext, SessionContext, type AgentState } from "@/lib/context";
import { landing, pagesFor } from "@/lib/nav";
import type { GraphLayout, Meta, User } from "@/lib/types";
import AgentPanel, { AgentStrip } from "@/components/AgentPanel";
import { IconAssistant, IconLogout, IconMemory, IconRegister, IconReview } from "@/components/Icons";

const ICONS: Record<string, () => React.JSX.Element> = { "/assistant": IconAssistant, "/review": IconReview, "/register": IconRegister, "/memory": IconMemory };
const TITLES: Record<string, string> = { "/assistant": "Assistant", "/review": "Review queue", "/register": "Processing register", "/memory": "Long-term memory" };

export default function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [layout, setLayout] = useState<GraphLayout | null>(null);
  const [agent, setAgent] = useState<AgentState | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    api.get<User>("/api/auth/me")
      .then((u) => {
        setUser(u);
        api.get<Meta>("/api/meta").then(setMeta).catch((e) => setProblem(String(e)));
        api.get<GraphLayout>("/api/meta/graph-layout").then(setLayout).catch((e) => setProblem(String(e)));
        if (u.role === "dpo") api.get<{ pending: unknown[] }>("/api/reviews").then((r) => setPendingCount(r.pending.length)).catch(() => {});
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setProblem(e instanceof Error ? e.message : String(e));
      });
  }, [router, pathname]);

  // the DPO has no Assistant page; a product manager has no review queue
  useEffect(() => {
    if (!user) return;
    if ((user.role === "dpo" && pathname === "/assistant") || (user.role !== "dpo" && pathname === "/review")) router.replace(landing(user));
  }, [user, pathname, router]);

  // the panel opens by itself when a run starts streaming; closing it is the person's choice (the strip's button opens it again)
  const live = agent?.live || false;
  useEffect(() => {
    if (live) setPanelOpen(true);
  }, [live]);
  // pages publish their own agent state on mount (register and memory publish null)

  const session = useMemo(() => (user ? { user, meta, layout } : null), [user, meta, layout]);
  const agentCtx = useMemo(() => ({ agent, setAgent, panelOpen, setPanelOpen }), [agent, panelOpen]);

  async function logout() {
    await api.post("/api/auth/logout");
    router.replace("/login");
  }

  if (problem) return <main className="login"><div className="formside"><div><div className="error">{problem}</div><p className="small muted">Is the API running on port 8000?</p></div></div></main>;
  if (!session) return null;

  const initials = session.user.display_name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() || session.user.user_id.slice(0, 2).toUpperCase();

  return (
    <SessionContext.Provider value={session}>
      <AgentContext.Provider value={agentCtx}>
        <div className="app">
          <nav className="rail" aria-label="Primary">
            <div className="logo" aria-hidden="true">C</div>
            {pagesFor(session.user).map((p) => {
              const Icon = ICONS[p.href];
              return (
                <Link key={p.href} href={p.href} className={`item${pathname === p.href ? " current" : ""}`} aria-label={p.label}>
                  <Icon />
                  {p.href === "/review" && pendingCount ? <span className="badge-n">{pendingCount}</span> : null}
                  <span className="tip">{p.label}</span>
                </Link>
              );
            })}
            <div className="spacer" />
            <button type="button" className={`avatar${session.user.role === "dpo" ? " dpo" : ""}`} onClick={logout} aria-label={`${session.user.display_name}, ${session.user.role.replace("_", " ")} · log out`} style={{ position: "relative" }}>
              {initials}
              <span className="tip"><IconLogout /> {session.user.display_name} · log out</span>
            </button>
          </nav>
          <div className="frame">
            <header className="topbar">
              <span className="brand">Compliance Assistant</span>
              <span className="sep">/</span>
              <span className="crumb">{TITLES[pathname] || ""}</span>
              <span className="grow" />
              {agent ? <span className={`pill ${agent.kind}`}><span className="dot" />{agent.status}</span> : null}
              <span className="small muted" style={{ marginLeft: 6 }}>{session.user.display_name} · {session.user.role.replace("_", " ")}</span>
            </header>
            <div className="body">
              <main className="page narrow">
                <AgentStrip />
                {children}
              </main>
              <AgentPanel />
            </div>
          </div>
        </div>
      </AgentContext.Provider>
    </SessionContext.Provider>
  );
}
