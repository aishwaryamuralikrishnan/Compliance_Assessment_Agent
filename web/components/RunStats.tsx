import type { RunStats as Stats } from "@/lib/types";

/** The run-stats tiles (UI.md "Run stats"): the estimate covers the calls the graph streams back; the gateway's
 *  activity page is the figure to quote. */
export default function RunStats({ stats }: { stats: Stats | null }) {
  if (!stats) return <div className="muted small">no run yet</div>;
  const tiles: [string, string | number][] = [
    ["step", stats.step], ["searches", stats.searches], ["retrieve passes", stats.retrieve_passes], ["rewrites", stats.rewrites],
    ["tool calls", stats.tool_calls], ["tokens in / out", `${stats.tokens_in} / ${stats.tokens_out}`], ["cached", stats.cached],
    ["est. cost (worker)", `$${stats.cost.toFixed(4)}`], ["elapsed", `${stats.elapsed.toFixed(1)} s`], ["thread", stats.thread],
  ];
  return (
    <>
      <div className="stats">
        {tiles.map(([k, v]) => <div key={k} className="tile"><span>{k}</span><b>{v}</b></div>)}
      </div>
      <div className="small faint">Searches: calls of the search tool; retrieve passes: every retrieval inside them, so passes minus searches is the number of retries after a rewrite. The cost covers the worker&apos;s, the reviser&apos;s and the quick answer&apos;s model calls; the helper models are not in it, so the gateway shows more.</div>
    </>
  );
}

/** One line of the same figures, for the collapsed panel's strip. */
export function statsLine(stats: Stats | null): string {
  if (!stats) return "";
  return `${stats.searches} search${stats.searches === 1 ? "" : "es"} · ${stats.rewrites} rewrite${stats.rewrites === 1 ? "" : "s"} · ${stats.tool_calls} tool call${stats.tool_calls === 1 ? "" : "s"} · ${stats.elapsed.toFixed(1)} s · $${stats.cost.toFixed(4)} est.`;
}
