// The evaluation page's figures, plain inline SVG (no chart library): a scorecard of targets, paired bars, a
// count matrix, stacked bars per case and the cost split. Colours: the Frost accent blue as series 1, a validated
// orange as series 2, and one blue ramp for the ordered matched / partial / missed; text always in the ink tokens.
// Every mark carries a <title> for hover; values are labelled directly where they fit.

import type { ReactNode } from "react";

export const C = {
  s1: "#1D6FE0", s2: "#EB6834", // categorical slots 1 and 2 (validated adjacent pair)
  ramp: ["#1554B3", "#5598E7", "#86B6EF"], // ordinal: matched, partial, missed (one hue, validated)
  seq: ["#E8F0FB", "#B7D3F6", "#86B6EF", "#5598E7", "#2A78D6", "#1C5CAB", "#104281"], // sequential counts
  ink: "#16213A", muted: "#5B6B85", faint: "#7D8AA3", grid: "#E1E6EE", axis: "#C4D0E0", surface: "#FFFFFF",
};

export function Figure({ title, sub, children, wide }: { title: string; sub?: string; children: ReactNode; wide?: boolean }) {
  return (
    <figure className={`fig${wide ? " wide" : ""}`}>
      <figcaption><b>{title}</b>{sub ? <span className="muted"> · {sub}</span> : null}</figcaption>
      {children}
    </figure>
  );
}

export function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span key={it.label}><i style={{ background: it.color }} />{it.label}</span>
      ))}
    </div>
  );
}

/** Horizontal bars, one or two series per category, values labelled at the bar end. */
export function Bars({ cats, series, max = 1, fmt = (v: number) => v.toFixed(2), width = 420 }: {
  cats: string[]; series: { name: string; color: string; values: number[] }[]; max?: number; fmt?: (v: number) => string; width?: number;
}) {
  const labelW = 170, barH = 14, gap = 4, rowH = series.length * (barH + gap) + 10, H = cats.length * rowH + 6, plotW = width - labelW - 56;
  return (
    <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label="bar chart">
      {cats.map((c, i) => (
        <g key={c} transform={`translate(0 ${i * rowH})`}>
          <text x={labelW - 8} y={rowH / 2} textAnchor="end" dominantBaseline="middle" fontSize={12} fill={C.ink}>{c}</text>
          {series.map((s, j) => {
            const v = s.values[i];
            const w = Math.max(2, (plotW * Math.min(v, max)) / max);
            const y = 5 + j * (barH + gap);
            return (
              <g key={s.name}>
                <title>{`${c} · ${s.name}: ${fmt(v)}`}</title>
                <rect x={labelW} y={y} width={w} height={barH} rx={4} fill={s.color} />
                <text x={labelW + w + 6} y={y + barH / 2} dominantBaseline="middle" fontSize={11} fill={C.muted}>{fmt(v)}</text>
              </g>
            );
          })}
        </g>
      ))}
      <line x1={labelW} x2={labelW} y1={0} y2={H} stroke={C.axis} />
    </svg>
  );
}

/** A count matrix (expected rows × given columns), cells filled on a sequential ramp, counts printed. */
export function Matrix({ order, counts, rowLabel, colLabel, short, rowNames, markOff }: {
  order: string[]; counts: Record<string, Record<string, number>>; rowLabel: string; colLabel: string; short?: (s: string) => string;
  rowNames?: Record<string, string>; markOff?: boolean;
}) {
  const cell = 88, labelW = rowNames ? 170 : 150, top = 44, n = order.length;
  const W = labelW + n * cell + 8, H = top + n * cell + 8;
  const vals = order.flatMap((r) => order.map((c) => counts[r]?.[c] ?? 0));
  const max = Math.max(1, ...vals);
  const sh = short || ((s: string) => s);
  const fill = (v: number) => (v === 0 ? C.surface : C.seq[Math.min(C.seq.length - 1, 1 + Math.round(((C.seq.length - 2) * v) / max))]);
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${rowLabel} against ${colLabel}`}>
      <text x={labelW + (n * cell) / 2} y={12} textAnchor="middle" fontSize={11} fill={C.muted}>{colLabel}</text>
      {order.map((c, j) => (
        <text key={c} x={labelW + j * cell + cell / 2} y={32} textAnchor="middle" fontSize={11} fill={C.ink}>{sh(c)}</text>
      ))}
      <text transform={`translate(12 ${top + (n * cell) / 2}) rotate(-90)`} textAnchor="middle" fontSize={11} fill={C.muted}>{rowLabel}</text>
      {order.map((r, i) => (
        <g key={r}>
          <text x={labelW - 8} y={top + i * cell + cell / 2} textAnchor="end" dominantBaseline="middle" fontSize={11} fill={C.ink}>{rowNames ? rowNames[r] || r : sh(r)}</text>
          {order.map((c, j) => {
            const v = counts[r]?.[c] ?? 0;
            const dark = v > 0 && v >= max * 0.6;
            const off = markOff && i !== j && v > 0;
            return (
              <g key={c}>
                <title>{`expected ${r}, given ${c}: ${v}`}</title>
                <rect x={labelW + j * cell + 1} y={top + i * cell + 1} width={cell - 2} height={cell - 2} rx={6} fill={fill(v)} stroke={off ? "#D23B3B" : i === j ? C.ink : C.grid} strokeWidth={i === j || off ? 1.5 : 1} />
                <text x={labelW + j * cell + cell / 2} y={top + i * cell + cell / 2} textAnchor="middle" dominantBaseline="middle" fontSize={16} fontWeight={600} fill={dark ? "#fff" : C.ink}>{v}</text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

/** Stacked horizontal bars, one per case, segments in the ordinal ramp with a 2px surface gap and the count inside. */
export function Stacked({ rows, keys, colors, width = 460, total }: {
  rows: { label: string; values: number[]; note?: string }[]; keys: string[]; colors: string[]; width?: number; total?: (r: { values: number[] }) => number;
}) {
  const labelW = 64, barH = 14, rowH = 20, plotW = width - labelW - 40;
  const max = Math.max(1, ...rows.map((r) => (total ? total(r) : r.values.reduce((a, b) => a + b, 0))));
  const H = rows.length * rowH + 4;
  return (
    <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label="stacked bars per case">
      {rows.map((r, i) => {
        let x = labelW;
        const sum = r.values.reduce((a, b) => a + b, 0);
        return (
          <g key={r.label} transform={`translate(0 ${i * rowH})`}>
            <text x={labelW - 8} y={rowH / 2} textAnchor="end" dominantBaseline="middle" fontSize={11} fill={C.ink} fontFamily="JetBrains Mono, ui-monospace, monospace">{r.label}</text>
            {r.values.map((v, j) => {
              const w = (plotW * v) / max;
              const el = v > 0 ? (
                <g key={keys[j]}>
                  <title>{`${r.label} · ${keys[j]}: ${v}${r.note ? ` · ${r.note}` : ""}`}</title>
                  <rect x={x + 1} y={3} width={Math.max(0, w - 2)} height={barH} rx={3} fill={colors[j]} />
                  {w > 14 ? <text x={x + w / 2} y={3 + barH / 2} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill={j === 2 ? C.ink : "#fff"}>{v}</text> : null}
                </g>
              ) : null;
              x += w;
              return el;
            })}
            <text x={x + 6} y={rowH / 2} dominantBaseline="middle" fontSize={10} fill={C.muted}>{sum}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "ok" | "bad" | "neutral" }) {
  return (
    <div className={`tile${tone ? ` ${tone}` : ""}`}>
      <div className="k">{label}</div>
      <div className="v">{value}</div>
      {sub ? <div className="s">{sub}</div> : null}
    </div>
  );
}

/** Where the seven sets sit in the app: the request's path from the input screen to the DPO, with a set badge on
 *  every part that was evaluated. Plain SVG; the badges carry the set id and a short name. */
/** The colour of a set's badge says how its numbers are produced, as the Overview's "how the numbers are produced" list
 *  does: rules (blue) for E1 E2 E7 E3 E4, the AI judge (orange) for E5, and E6 half judge, half human check (green). */
export const JUDGED_COLORS = { rules: C.s1, judge: C.s2, human: "#1E9E5F" };
const BADGE: Record<string, (keyof typeof JUDGED_COLORS)[]> = { E1: ["rules"], E2: ["rules"], E7: ["rules"], E3: ["rules"], E4: ["rules"], E5: ["judge"], E6: ["judge", "human"] };

function Badge({ x, y, id }: { x: number; y: number; id: string }) {
  const kinds = BADGE[id] || ["rules"];
  const w = 40, h = 20;
  return (
    <g>
      {kinds.length === 1 ? (
        <rect x={x} y={y} width={w} height={h} rx={10} fill={JUDGED_COLORS[kinds[0]]} stroke="#fff" strokeWidth={2} />
      ) : (
        <g>
          <clipPath id={`badge-${id}`}><rect x={x} y={y} width={w} height={h} rx={10} /></clipPath>
          <rect x={x} y={y} width={w / 2} height={h} fill={JUDGED_COLORS[kinds[0]]} clipPath={`url(#badge-${id})`} />
          <rect x={x + w / 2} y={y} width={w / 2} height={h} fill={JUDGED_COLORS[kinds[1]]} clipPath={`url(#badge-${id})`} />
          <rect x={x} y={y} width={w} height={h} rx={10} fill="none" stroke="#fff" strokeWidth={2} />
        </g>
      )}
      <text x={x + w / 2} y={y + 14} textAnchor="middle" fontSize={11} fontWeight={700} fill="#fff">{id}</text>
    </g>
  );
}

export function SetsMap() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, badge?: string, dim?: boolean) => (
    <g key={title}>
      <rect x={x} y={y} width={w} height={h} rx={10} fill={dim ? "#F5F8FC" : "#fff"} stroke={dim ? C.grid : C.axis} strokeWidth={1.2} />
      <text x={x + 12} y={y + 24} fontSize={13} fontWeight={600} fill={C.ink}>{title}</text>
      <text x={x + 12} y={y + 42} fontSize={11} fill={C.muted}>{sub}</text>
      {badge ? <Badge x={x + w - 48} y={y - 10} id={badge} /> : null}
    </g>
  );
  const arrow = (x1: number, y1: number, x2: number, y2: number) => (
    <path key={`${x1}-${y1}-${x2}-${y2}`} d={`M${x1} ${y1} L${x2} ${y2}`} stroke={C.axis} strokeWidth={1.6} markerEnd="url(#arr)" fill="none" />
  );
  return (
    <svg width={930} height={300} viewBox="0 0 930 300" role="img" aria-label="Where the seven evaluation sets sit in the app">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill={C.axis} /></marker></defs>
      {box(10, 130, 120, 58, "Request", "question or feature", undefined, true)}
      {arrow(130, 159, 160, 159)}
      {box(160, 130, 175, 58, "Input screen", "injection · PII · off-topic", "E2")}
      {arrow(335, 159, 365, 159)}
      {box(365, 130, 130, 58, "Router", "quick or full path", "E1")}
      {arrow(495, 148, 535, 64)}
      {arrow(495, 170, 535, 254)}
      {box(535, 36, 215, 58, "Quick answer", "one search, three sentences", "E5")}
      {box(535, 130, 215, 58, "Search tool + loop", "grade · rewrite · search again", "E3")}
      <Badge x={656} y={120} id="E4" />
      <text x={642} y={210} textAnchor="middle" fontSize={10} fill={C.muted}>used by the agent · E4 tests the loop&apos;s grader</text>
      {box(535, 226, 215, 58, "Agent · full assessment", "tools, findings, verdict", "E6")}
      {arrow(750, 65, 790, 140)}
      {arrow(750, 255, 790, 178)}
      {box(790, 130, 130, 58, "Output guardrail", "citations · PII · shape", "E7")}
      <text x={855} y={215} textAnchor="middle" fontSize={11} fill={C.muted}>→ the person, or the DPO</text>
    </svg>
  );
}

/** How each set's numbers are produced: a grid of sets against three ways of judging. */
export function JudgedGrid({ sets }: { sets: { id: string; name: string; judged: { rules: string | null; judge: string | null; human: string | null } }[] }) {
  const cols: { key: "rules" | "judge" | "human"; label: string; color: string }[] = [
    { key: "rules", label: "exact rules against the test data", color: C.s1 },
    { key: "judge", label: "an AI judge with a rubric", color: C.s2 },
    { key: "human", label: "a human check", color: "#1E9E5F" },
  ];
  return (
    <table className="judged">
      <thead><tr><th></th>{cols.map((c) => <th key={c.key}><i style={{ background: c.color }} />{c.label}</th>)}</tr></thead>
      <tbody>
        {sets.map((s) => (
          <tr key={s.id}>
            <td><span className="chip neutral mono">{s.id}</span> {s.name}</td>
            {cols.map((c) => {
              const v = s.judged[c.key];
              return <td key={c.key} className={v ? "on" : ""}>{v ? <><span className="dot" style={{ background: c.color }} />{v}</> : <span className="faint">–</span>}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** One stacked bar: the sets as segments in proportion, each labelled with its dollars; the total in the caption. */
export const COST_COLORS = ["#1554B3", "#2A78D6", "#5598E7", "#86B6EF", "#EB6834"];

/** Cost per set as one stacked bar, no text on the bar: the legend under it names each colour with its dollars. */
export function CostBar({ rows }: { rows: { label: string; value: number }[] }) {
  const W = 1000, H = 28;
  const total = rows.reduce((a, r) => a + r.value, 0) || 1;
  let x = 0;
  return (
    <>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="cost per set, one stacked bar">
        {rows.map((r, i) => {
          const w = (W * r.value) / total;
          const el = (
            <g key={r.label}>
              <title>{`${r.label}: $${r.value.toFixed(2)}`}</title>
              <rect x={x} y={0} width={Math.max(0, w - 2)} height={H} rx={4} fill={COST_COLORS[i % COST_COLORS.length]} />
            </g>
          );
          x += w;
          return el;
        })}
      </svg>
      <Legend items={rows.map((r, i) => ({ color: COST_COLORS[i % COST_COLORS.length], label: `${r.label} · $${r.value.toFixed(2)}` }))} />
    </>
  );
}

/** What the input screen did with the inputs: one box per outcome with its count and a tick when every one was right. */
export function ScreenFlow({ rows, total }: { rows: { title: string; sub: string; result: string; ok: boolean }[]; total: string }) {
  const W = 860, H = 20 + rows.length * 54;
  const mid = H / 2;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="what the input screen did">
      <defs><marker id="sf" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill={C.axis} /></marker></defs>
      <rect x={10} y={mid - 28} width={130} height={56} rx={10} fill="#F5F8FC" stroke={C.grid} />
      <text x={22} y={mid - 6} fontSize={13} fontWeight={600} fill={C.ink}>{total}</text>
      <text x={22} y={mid + 12} fontSize={11} fill={C.muted}>from E1</text>
      <path d={`M140 ${mid} L190 ${mid}`} stroke={C.axis} strokeWidth={1.6} fill="none" markerEnd="url(#sf)" />
      <rect x={190} y={mid - 28} width={170} height={56} rx={10} fill="#fff" stroke={C.axis} strokeWidth={1.2} />
      <text x={202} y={mid - 6} fontSize={13} fontWeight={600} fill={C.ink}>Input screening</text>
      <text x={202} y={mid + 12} fontSize={11} fill={C.muted}>injection · PII · off-topic</text>
      {rows.map((r, i) => {
        const y = 10 + i * 54;
        return (
          <g key={r.title}>
            <path d={`M360 ${mid} L430 ${y + 24}`} stroke={C.axis} strokeWidth={1.6} fill="none" markerEnd="url(#sf)" />
            <rect x={430} y={y} width={300} height={48} rx={10} fill="#fff" stroke={C.axis} strokeWidth={1.2} />
            <text x={442} y={y + 20} fontSize={13} fontWeight={600} fill={C.ink}>{r.title}</text>
            <text x={442} y={y + 38} fontSize={11} fill={C.muted}>{r.sub}</text>
            <text x={718} y={y + 26} textAnchor="end" fontSize={20} fontWeight={700} fill={r.ok ? "#116B3E" : "#A51F1F"}>{r.result}</text>
            <circle cx={760} cy={y + 24} r={11} fill={r.ok ? "#D8F1E3" : "#FBE4E4"} />
            <text x={760} y={y + 28} textAnchor="middle" fontSize={12} fontWeight={700} fill={r.ok ? "#116B3E" : "#A51F1F"}>{r.ok ? "✓" : "✗"}</text>
          </g>
        );
      })}
    </svg>
  );
}
