"use client";

// The public evaluation report (no login; linked from the login page): one tab at a time. The print view at
// /evaluation/print lays every tab out in sequence for scripts/eval_pdf.py.

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { EvalReport } from "@/lib/types";
import { ReportHeader, TABS } from "@/components/EvalReport";

export default function EvaluationPage() {
  const [r, setR] = useState<EvalReport | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("overview");

  useEffect(() => {
    const h = typeof window !== "undefined" ? window.location.hash.replace("#", "") : "";
    if (TABS.some((t) => t.id === h)) setTab(h);
    api.get<EvalReport>("/api/eval/report").then(setR).catch((e) => setProblem(e instanceof ApiError ? e.message : String(e)));
  }, []);

  function pick(id: string) {
    setTab(id);
    if (typeof window !== "undefined") window.history.replaceState(null, "", `#${id}`);
  }

  const current = TABS.find((t) => t.id === tab) || TABS[0];
  return (
    <main className="evalshell">
      <header className="evalbar">
        <Link href="/login" className="row" style={{ gap: 10, color: "inherit", textDecoration: "none" }}>
          <span className="logo-sm" aria-hidden="true">C</span><b>Compliance Assistant</b><span className="sep">/</span><span className="muted">Evaluation</span>
        </Link>
        <span className="grow" />
        <a className="btn sm" href="/api/eval/report" target="_blank" rel="noreferrer" title="The report as JSON, what these pages draw.">JSON</a>
        <Link className="btn sm" href="/evaluation/print" title="Every section on one page, for printing.">Print view</Link>
      </header>
      <div className="evalbody">
        {problem ? <div className="band wait"><span className="dot" /><div><b>No report to show.</b> {problem}</div></div> : null}
        {!r && !problem ? <div className="skeleton"><div className="ln h" /><div className="ln" /><div className="ln" /></div> : null}
        {r ? (
          <>
            <ReportHeader r={r} />
            <nav className="tabs" aria-label="Report sections">
              {TABS.map((t) => <button key={t.id} type="button" className={`tab${t.id === tab ? " on" : ""}`} onClick={() => pick(t.id)}>{t.label}</button>)}
            </nav>
            {current.render(r)}
          </>
        ) : null}
      </div>
    </main>
  );
}
