"use client";

// Long-term memory (UI.md): the Store's three namespaces with provenance; seeded items grey, learned items blue.

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAgent, useSession } from "@/lib/context";
import type { MemoryOut } from "@/lib/types";

export default function MemoryPage() {
  const { user } = useSession();
  const { setAgent } = useAgent();
  const [mem, setMem] = useState<MemoryOut | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => { setAgent(null); }, [setAgent]);
  useEffect(() => {
    api.get<MemoryOut>("/api/memory").then(setMem).catch((e) => setProblem(e instanceof ApiError ? e.message : String(e)));
  }, []);

  return (
    <>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>Long-term memory</h2>
        <p className="muted" style={{ margin: "4px 0 0 0" }}>
          What the assistant remembers between conversations, with where each item came from. Grey items were seeded; blue items were learned from a DPO decision or from feedback.
          As {user.role.replace("_", " ")} you can add: {mem ? (mem.can_add.length ? mem.can_add.join(", ") : "nothing") : "…"}.
        </p>
      </div>
      {problem ? <div className="error">{problem}</div> : null}
      {mem?.sections.map((s) => (
        <section key={s.namespace} className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><b>{s.what}</b> <span className="muted">({s.who})</span></div>
            <span className="mono small muted">{s.namespace} · {s.items.length} item{s.items.length === 1 ? "" : "s"}</span>
          </div>
          {s.error ? <div className="band bad"><span className="dot" /><div>{s.error}</div></div> : null}
          {s.items.length === 0 && !s.error ? <div className="small muted">empty</div> : null}
          {s.items.map((it, i) => {
            const prov = [it.source, it.author, (it.created_at || "").slice(0, 16).replace("T", " "), it.assessment_id ? `assessment ${it.assessment_id}` : "", it.reflected ? "rephrased" : ""].filter(Boolean).join(" · ");
            return (
              <div key={i} className={`mem${it.source === "seed" ? "" : " learned"}`}>
                <div>{it.text}</div>
                <div className="prov">{prov}{it.detail ? ` · ${it.detail}` : ""}</div>
              </div>
            );
          })}
        </section>
      ))}
    </>
  );
}
