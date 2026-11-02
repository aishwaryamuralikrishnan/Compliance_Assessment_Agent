"use client";

// The product manager's feedback on a completed thread: one note, stored as that user's own preference.

import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";

export default function PreferenceNote({ threadId, saved, onSaved, onStarted }: { threadId: string; saved: string | null; onSaved: (note: string) => void; onStarted: (runId: string) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    setProblem(null);
    try {
      const r = await api.post<{ run_id: string }>(`/api/threads/${threadId}/feedback`, { comment: note.trim() });
      onSaved(note.trim());
      onStarted(r.run_id);
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (saved) return <div className="small muted">Saved as your preference: “{saved}” (memory_write ran under your identity; see the Memory page).</div>;
  return (
    <form onSubmit={submit} className="row" aria-label="Preference note">
      <input type="text" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 260 }}
             placeholder="What should the assistant do differently next time? Stored as your preference (e.g. 'shorter findings, cite the recital too')" />
      <button type="submit" className="btn" disabled={busy || !note.trim()}>Save preference</button>
      {problem ? <span className="error">{problem}</span> : null}
    </form>
  );
}
