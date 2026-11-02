import type { GraphSnapshot } from "@/lib/types";

/** The accumulated picture of several runs on one thread (the assessment, then the DPO's decision, then a revision …):
 *  the union of the nodes visited and the edges taken, the newest run's current state. A resumed run's tracker starts
 *  grey before its pause (viz.TraceTracker resumed=True), so the earlier runs supply the first half of the path, and
 *  the node an earlier run stopped at (the agent paused at the gate) counts as visited. The same accumulation the first
 *  UI did by walking its own tracker forward after the DPO decided. */
export function mergeSnapshots(list: GraphSnapshot[]): GraphSnapshot | null {
  if (list.length === 0) return null;
  const last = list[list.length - 1];
  const visited: string[] = [];
  const taken: [string, string][] = [];
  const seen = new Set<string>();
  const substeps = new Set<string>();
  list.forEach((s, i) => {
    for (const v of s.visited) if (!visited.includes(v)) visited.push(v);
    if (i < list.length - 1 && s.active && !visited.includes(s.active)) visited.push(s.active);
    for (const e of s.taken) {
      const k = `${e[0]}>${e[1]}`;
      if (!seen.has(k)) {
        seen.add(k);
        taken.push(e);
      }
    }
    for (const d of s.substeps_done) substeps.add(d);
  });
  return {
    ...last,
    visited,
    taken,
    substeps_done: [...substeps],
    rewrote: list.some((s) => s.rewrote),
    retrievals: list.reduce((n, s) => n + s.retrievals, 0),
    tool_calls: list.reduce((n, s) => n + s.tool_calls, 0),
  };
}
