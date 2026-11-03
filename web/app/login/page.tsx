"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { landing } from "@/lib/nav";
import type { User } from "@/lib/types";

const OIDC_ERRORS: Record<string, string> = {
  "state-expired": "The sign-in took too long or the browser lost its place; please try again.",
  "state-mismatch": "The sign-in did not come back the way it left; please try again.",
  "token-invalid": "The identity provider's answer could not be verified.",
  "email-unverified": "The account has no verified e-mail address; a verified address is needed.",
  "not-invited": "This account is not on the list of users for this installation.",
  "exchange-failed": "The identity provider refused the sign-in; please try again.",
  "provider-unreachable": "The identity provider could not be reached; please try again in a moment.",
};

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState<{ oidc: boolean; name: string | null } | null>(null);
  useEffect(() => {
    api.get<{ oidc: boolean; name: string | null }>("/api/auth/providers").then(setProvider).catch(() => setProvider({ oidc: false, name: null }));
    const e = new URLSearchParams(window.location.search).get("error");   // the OIDC callback redirects here on failure
    if (e) setError(OIDC_ERRORS[e] || `Sign-in with the identity provider failed (${e}).`);
  }, []);

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
        <div className="small" style={{ color: "var(--rail-text)", display: "flex", flexDirection: "column", gap: 6 }}>
          <span>This is an AI system in a demo: what you type is redacted and then sent to AI model providers through OpenRouter under zero data retention. Please enter no real personal data. <a href="/privacy" style={{ color: "#DCE8FA" }}>Privacy notice</a></span>
          <span>Turing College capstone · Aishwarya Muralikrishnan · <a href="/evaluation" style={{ color: "#DCE8FA" }}>How well does it work? The evaluation report</a></span>
        </div>
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
          {provider?.oidc ? (
            <>
              <div className="or"><span />or<span /></div>
              <a className="btn" href="/api/auth/oidc/start" style={{ height: 42, justifyContent: "center", textDecoration: "none" }}>Sign in with {provider.name || "your identity provider"}</a>
              <div className="small muted" style={{ marginTop: 6 }}>A first sign-in creates a product manager account from your verified e-mail address; the DPO role is given by the administrator. Two seeded accounts remain for the demo: <code>lena.k</code> (product manager) and <code>m.weber</code> (DPO).</div>
            </>
          ) : (
            <div className="small muted" style={{ marginTop: 6 }}>Two seeded accounts for the demo: <code>lena.k</code> is a product manager, <code>m.weber</code> the data protection officer. The DPO lands on the review queue and has no assistant page.</div>
          )}
        </form>
      </div>
    </main>
  );
}
