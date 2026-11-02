"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { landing } from "@/lib/nav";
import type { User } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await api.post<User>("/api/auth/login", { username, password });
      router.replace(landing(u));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <section className="about" aria-label="About">
        <div className="row"><span className="rail-logo" style={{ width: 36, height: 36, borderRadius: 10, background: "var(--accent)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }} aria-hidden="true">C</span><b style={{ fontSize: 15 }}>Compliance Assistant</b></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <h1>Describe the feature. Get an article-cited first assessment. The DPO decides what goes on record.</h1>
          <p>GDPR and the EU AI Act, searched by an agent that verifies every citation against the law&apos;s text before you see it. Not legal advice; a record only once the DPO approves.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginTop: 8 }}>
            <div className="stat"><b>2</b><span>regulations in the corpus: GDPR, EU AI Act</span></div>
            <div className="stat"><b>every</b><span>citation checked against the law&apos;s text</span></div>
            <div className="stat"><b>DPO</b><span>approval before anything is recorded</span></div>
          </div>
        </div>
        <div className="small" style={{ color: "var(--rail-text)" }}>Turing College capstone · Aishwarya Muralikrishnan · <a href="/evaluation" style={{ color: "#DCE8FA" }}>How well does it work? The evaluation report</a></div>
      </section>
      <div className="formside">
        <form onSubmit={submit}>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Sign in</h2>
          <label className="field">Username
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="lena.k or m.weber" autoFocus autoComplete="username" />
          </label>
          <label className="field">Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error ? <div className="error">{error}</div> : null}
          <button className="btn primary" type="submit" disabled={busy || !username || !password} style={{ height: 44, justifyContent: "center", marginTop: 4 }}>Sign in</button>
          <div className="or"><span />later<span /></div>
          <button type="button" className="btn" disabled style={{ height: 42, justifyContent: "center" }}>Continue with your organisation (OIDC)</button>
          <div className="small muted" style={{ marginTop: 6 }}>Two seeded accounts for the demo: <code>lena.k</code> is a product manager, <code>m.weber</code> the data protection officer. The DPO lands on the review queue and has no assistant page.</div>
        </form>
      </div>
    </main>
  );
}
