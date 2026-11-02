"use client";

// Every section of the evaluation report in sequence, for printing (scripts/eval_pdf.py) or reading top to bottom.

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { EvalReport } from "@/lib/types";
import { Glossary, ReportHeader, TABS } from "@/components/EvalReport";

export default function EvaluationPrintPage() {
  const [r, setR] = useState<EvalReport | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  useEffect(() => {
    api.get<EvalReport>("/api/eval/report").then(setR).catch((e) => setProblem(e instanceof ApiError ? e.message : String(e)));
  }, []);
  return (
    <main className="evalshell print">
      <div className="evalbody">
        {problem ? <div className="band wait"><span className="dot" /><div><b>No report to show.</b> {problem}</div></div> : null}
        {r ? (
          <>
            <ReportHeader r={r} />
            {TABS.map((t) => (
              <section key={t.id} className="printsection">
                <h2 className="sectitle">{t.label}</h2>
                {t.render(r, true)}
              </section>
            ))}
            <section className="printsection">
              <h2 className="sectitle">Definitions</h2>
              <Glossary sets={r.sections.flatMap((s) => s.sets)} />
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}
