"use client";

// The evaluation report's sections, drawn from GET /api/eval/report (eval/harness/report.py). Used by the public
// page (/evaluation, one tab at a time) and by its print view (/evaluation/print, every section in sequence).
// Each set states what it tests and on what data, then its metrics with definitions on hover, then its figure.

import type { ReactNode } from "react";
import type { EvalDomain, EvalMetric, EvalReport, EvalSet } from "@/lib/types";
import { Bars, C, CostBar, Figure, JUDGED_COLORS, Legend, Matrix, ScreenFlow, SetsMap, Stacked, Stat } from "@/components/EvalCharts";

const SHORT: Record<string, string> = { "Do not build as described": "Do not build", "Proceed with conditions": "Conditions", Proceed: "Proceed" };
const yes = (v: boolean | null | undefined) => (v === null || v === undefined ? "–" : v ? "yes" : "no");

/** A metric line: the name carries its definition as a tooltip (and prints in the glossary). */
export function MetricRow({ x }: { x: EvalMetric }) {
  return (
    <tr className={x.met === false ? "miss" : ""}>
      <td><abbr title={x.definition}>{x.label}</abbr></td>
      <td className="mono">{x.result}</td>
      <td className="mono muted">{x.target || ""}</td>
      <td>{x.met === null ? "" : x.met ? <span className="chip ok">✓ met</span> : <span className="chip bad">✗ not met</span>}</td>
      <td className="small muted detail">{x.detail.length ? x.detail.join("; ") : ""}</td>
    </tr>
  );
}

export function Metrics({ rows }: { rows: EvalMetric[] }) {
  return (
    <table className="metrics">
      <thead><tr><th>metric</th><th>result</th><th>target</th><th></th><th>detail</th></tr></thead>
      <tbody>{rows.map((x) => <MetricRow key={x.key} x={x} />)}</tbody>
    </table>
  );
}

export function Glossary({ sets }: { sets: EvalSet[] }) {
  const rows = sets.flatMap((s) => s.metrics);
  if (!rows.length) return null;
  return (
    <div className="glossary printonly">
      <div className="eyebrow">Definitions</div>
      <dl>{rows.map((x) => <div key={x.key}><dt>{x.label}</dt><dd>{x.definition}</dd></div>)}</dl>
    </div>
  );
}

export function SetBlock({ s, children, table = true, name }: { s: EvalSet; children?: ReactNode; table?: boolean; name?: string }) {
  return (
    <section className="set card pad" id={s.id}>
      <div className="row" style={{ alignItems: "baseline", gap: 8 }}>
        <span className="chip neutral mono">{s.id}</span>
        <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>{name || s.name}</h3>
      </div>
      <div className="wd">
        <div><span className="wdk">Tests</span><span>{s.what}</span></div>
        <div><span className="wdk">Data</span><span>{s.data}</span></div>
      </div>
      {!s.run ? <div className="band wait"><span className="dot" /><div>This set has not been run.</div></div> : table ? <Metrics rows={s.metrics} /> : null}
      {children}
    </section>
  );
}

function findSet(r: EvalReport, id: string): EvalSet | undefined {
  return r.sections.flatMap((s) => s.sets).find((s) => s.id === id);
}

export function Overview({ r }: { r: EvalReport }) {
  const n = r.notes || {};
  const e6 = r.e6, e5 = r.e5, e12 = r.e12;
  const bill = r.cost.reduce((a, c) => a + (c.gateway ?? c.harness), 0);
  const caught = e12 ? e12.detection.injection.detected + e12.detection.pii_redacted.detected : null;
  const planted = e12 ? e12.detection.injection.of + e12.detection.pii_redacted.of : null;
  const dataLines: { id: string; text: string }[] = [
    { id: "E1 · E2", text: "45 inputs: 10 questions, 17 feature descriptions, 4 off-topic messages, 7 prompt injections, 7 with personal data" },
    { id: "E7", text: "4 assessments with one planted fault each" },
    { id: "E3 · E4", text: "20 plain-English queries with the provisions that must come back; every grade the loop made" },
    { id: "E5", text: "15 short questions, one per provision" },
    { id: "E6", text: "20 feature descriptions over eight areas, with the expected verdict, flags and findings; eight confusable pairs" },
  ];
  const judged = [
    { color: JUDGED_COLORS.rules, title: "Exact rules against the test data", text: "E1 E2 E7 E3 E4, and the verdict, flags and citations of E5 E6" },
    { color: JUDGED_COLORS.judge, title: "An AI judge with a rubric", text: "faithfulness (E5, E6) and the key findings (E6)" },
    { color: JUDGED_COLORS.human, title: "A human check", text: "five E6 cases scored blind to check the judge" },
  ];
  return (
    <div className="evalpage">
      {n.headline ? <p className="headline">{n.headline}</p> : null}
      <div className="hero-row">
        {caught !== null ? <Stat label="injections and personal data caught" value={`${Math.round((100 * caught) / (planted || 1))} %`} sub={`${caught} of ${planted} planted inputs, none of the clean ones flagged`} tone="ok" /> : null}
        {e6 ? <Stat label="high-risk AI flag right" value={`${e6.flags.high_risk_ai.positives + e6.flags.high_risk_ai.negatives - e6.flags.high_risk_ai.missed - e6.flags.high_risk_ai.false} of ${e6.flags.high_risk_ai.positives + e6.flags.high_risk_ai.negatives}`} sub="full assessments" tone="ok" /> : null}
        {e6 ? <Stat label="dangerous misses" value={String(e6.dangerous_misses.length)} sub="expected Do not build, got Proceed" tone={e6.dangerous_misses.length ? "bad" : "ok"} /> : null}
        {e5 && e6 ? <Stat label="faithfulness, mean" value={`${e5.faithfulness.mean ?? "–"} · ${e6.faithfulness.mean ?? "–"}`} sub="quick answers · full assessments (target 0.80)" /> : null}
        <Stat label="one full run" value={`$${bill.toFixed(2)}`} sub="model cost on the gateway, all seven sets" />
      </div>
      <Figure title="Where the seven sets sit" sub="the path of a request through the app, with the set that evaluates each part; the badge colour says how that set is scored, as in the list below" wide>
        <SetsMap />
      </Figure>
      <div className="figgrid stackprint">
        <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="eyebrow">The test data</div>
          <ul className="datalist">{dataLines.map((d) => <li key={d.id}><span className="chip neutral mono">{d.id}</span> {d.text}</li>)}</ul>
          {n.data_note ? <p className="small" style={{ margin: "4px 0 0 0", color: "var(--ink-2)" }}>{n.data_note}</p> : null}
        </div>
        <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="eyebrow">How the numbers are produced</div>
          {judged.map((j) => (
            <div key={j.title} className="jrow"><i style={{ background: j.color }} /><div><b>{j.title}</b><div className="small muted">{j.text}</div></div></div>
          ))}
          {r.judge_note ? <p className="small muted" style={{ margin: "4px 0 0 0" }}>{r.judge_note}</p> : null}
        </div>
      </div>
      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="eyebrow">Cost of one full run · ${bill.toFixed(2)} on the gateway</div>
        <CostBar rows={r.cost.map((c) => ({ label: c.label, value: c.gateway ?? c.harness }))} />
        {e6 ? <div className="small muted">Full assessments take {Math.round(e6.run.seconds_mean || 0)} s per case on average.</div> : null}
      </div>
      {n.limitations?.length ? (
        <div className="card pad twocol">
          <div><div className="eyebrow">What this run does not show</div><ul className="small" style={{ margin: "6px 0 0 18px", padding: 0 }}>{n.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
          {n.next?.length ? <div><div className="eyebrow">What follows</div><ul className="small" style={{ margin: "6px 0 0 18px", padding: 0 }}>{n.next.map((l, i) => <li key={i}>{l}</li>)}</ul></div> : null}
        </div>
      ) : null}
    </div>
  );
}

const nOf = (c: { right: number; of: number } | undefined) => (c && c.of ? `${c.right} of ${c.of}` : "not run");
const Tick = ({ v }: { v: boolean | null | undefined }) => (v === null || v === undefined ? <span className="r none">–</span> : v ? <span className="r ok">✓</span> : <span className="r bad">✗</span>);

/** The Legal domains tab: the nine areas drawn inside their regulation's band, then the confusable pairs with the run's result. */
export function Domains({ r }: { r: EvalReport }) {
  const d = r.domains || [], p = r.pairs;
  // the picture: GDPR areas in the first two columns, those both laws decide in the third, AI Act areas in the fourth
  const col = (law: EvalDomain["law"]) => d.filter((x) => x.law === law);
  const gdpr = col("gdpr"), both = col("both"), ai = col("ai");
  const rows = Math.max(Math.ceil(gdpr.length / 2), both.length, ai.length);
  const place = (x: EvalDomain, c: number, rw: number) => (
    <div key={x.id} className="dbox" style={{ gridColumn: c, gridRow: rw + 2 }}>
      <b>{x.name}</b>
      <div className="laws">{x.articles.map((a, i) => <span key={i} className={`law ${a.law}`}>{a.text}</span>)}</div>
    </div>
  );
  return (
    <div className="evalpage">
      <Figure title="Legal domains" sub="nine areas of the two regulations, chosen as the situations a fintech product team brings to a DPO; every test case belongs to one" wide>
        <div className="lawmap" style={{ gridTemplateRows: `26px repeat(${rows}, auto)` }}>
          <div className="band g" style={{ gridRow: `1 / ${rows + 2}` }}><b>GDPR</b></div>
          <div className="band a" style={{ gridRow: `1 / ${rows + 2}` }}><b>EU AI Act</b></div>
          {gdpr.map((x, i) => place(x, 1 + (i % 2), Math.floor(i / 2)))}
          {both.map((x, i) => place(x, 3, i))}
          {ai.map((x, i) => place(x, 4, i))}
          <span className="both" style={{ gridRow: rows + 1 }}>both laws decide</span>
        </div>
        <div className="lg"><span><i style={{ background: C.s1 }} />GDPR article</span><span><i style={{ background: "#6250D6" }} />EU AI Act article</span></div>
      </Figure>
      {p ? (
        <div className="fig wide pairs" style={{ gap: 14 }}>
          <div><b style={{ fontSize: 13.5 }}>Confusable pairs</b><span className="muted"> · situations that sound alike but where the law answers differently, written in pairs to check that the assistant tells them apart rather than pattern-matching on words.</span></div>
          <div className="psec">
            <h4>In the full assessments · {nOf(p.full_right)} both right</h4>
            <p>Two feature descriptions that sound alike; the assistant should give each its own verdict and flags.</p>
            <table className="pt">
              <thead><tr><th style={{ width: "25%" }}>Case</th><th style={{ width: "15%" }}>Expected</th><th style={{ width: "25%" }}>Its twin</th><th style={{ width: "15%" }}>Expected</th><th style={{ textAlign: "right" }}>E6 result</th></tr></thead>
              <tbody>
                {p.full.map((x) => (
                  <tr key={x.a.id + x.b.id}>
                    <td className="case"><span className="id">{x.a.id}</span>{x.a.text}</td><td className="expc"><span className="exp">{x.a.expected}</span> <span className="art">{x.a.article}</span></td>
                    <td className="case"><span className="id">{x.b.id}</span>{x.b.text}</td><td className="expc"><span className="exp">{x.b.expected}</span> <span className="art">{x.b.article}</span></td>
                    <td className="res"><div>{x.ok === null ? <span className="r none">not run</span> : x.ok ? <span className="r ok">both right ✓</span>
                      : [x.a, x.b].filter((h) => h.ok === false).map((h) => <span key={h.id} className="r bad">{h.id} ✗ {h.why}</span>)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="ptwo">
            <div className="psec">
              <h4>In the direct answers · retrieval {nOf(p.quick_e3)} · answers {nOf(p.quick_e5)}</h4>
              <p>Two provisions often mixed up; the search should find the right one (E3) and the quick answer cite it (E5).</p>
              <table className="pt">
                <thead><tr><th>Provision</th><th>Its twin</th><th className="c">E3</th><th className="c">E5</th></tr></thead>
                <tbody>
                  {p.quick.map((x) => (
                    <tr key={x.a.e3_id}>
                      <td>{x.a.text} <span className="art">{x.a.article}</span></td><td>{x.b.text} <span className="art">{x.b.article}</span></td>
                      <td className="c"><Tick v={x.e3} /></td><td className="c"><Tick v={x.e5} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="psec">
              <h4>In routing · {nOf(p.routing_right)}</h4>
              <p>Two inputs with similar words that must take different paths (E1).</p>
              <table className="pt">
                <thead><tr><th>Input</th><th>Its twin</th><th className="c">E1</th></tr></thead>
                <tbody>
                  {p.routing.map((x) => (
                    <tr key={x.a.id}>
                      <td>{x.a.text}<br /><span className="art">→ {x.a.route}</span></td><td>{x.b.text}<br /><span className="art">→ {x.b.route}</span></td>
                      <td className="c"><Tick v={x.ok} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function Shortfalls({ r }: { r: EvalReport }) {
  const n = r.notes || {};
  return (
    <div className="evalpage">
      {n.shortfalls_intro ? <p className="what">{n.shortfalls_intro}</p> : null}
      {r.not_met.length ? (
        <Figure title="Targets not met" sub="the targets fixed before the run that the result stayed under; the bar is the result, the mark the target" wide>
          <div className="gaps">
            {r.not_met.map((x) => {
              const target = parseFloat((x.target || "").replace(/[^0-9.]/g, "")) || 0;
              return (
                <div key={`${x.set}-${x.key}`} className="gap">
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                    <span><span className="chip neutral mono">{x.set}</span> <abbr title={x.definition}><b>{x.label}</b></abbr></span>
                    <span className="mono muted small">{x.result} · {x.target}</span>
                  </div>
                  <div className="track"><div className="f" style={{ width: `${100 * (x.value ?? 0)}%` }} />{target ? <div className="t" style={{ left: `${100 * target}%` }} /> : null}</div>
                  <div className="row" style={{ justifyContent: "space-between" }}><span className="small bad-ink">{(x.value ?? 0).toFixed(2)} against {x.target}</span><span className="small muted">{target ? `${(100 * (target - (x.value ?? 0))).toFixed(0)} points short` : ""}</span></div>
                  {x.detail.length ? <div className="small muted">{x.detail.join("; ")}</div> : null}
                </div>
              );
            })}
          </div>
        </Figure>
      ) : <div className="band ok"><span className="dot" /><div>Every target was met.</div></div>}
      {n.failure_modes?.length ? (
        <>
          <div className="eyebrow">Failure modes, one example each</div>
          <div className="cards">
            {n.failure_modes.map((f) => (
              <div key={f.title} className="card pad fm">
                <b>{f.title}</b>
                <p>{f.text}</p>
                {f.example ? <p className="small ex">{f.example}</p> : null}
                {f.response ? <p className={`small resp ${f.response_kind === "proposed fix" ? "fix" : ""}`}><span className="wdk">{f.response_kind || "the way out"}</span> {f.response}</p> : null}
                {f.cases?.length ? <div className="small mono muted">{f.cases.join(" · ")}</div> : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

export function Guardrails({ r }: { r: EvalReport }) {
  const e1 = findSet(r, "E1"), e2 = findSet(r, "E2"), e7 = findSet(r, "E7");
  const x = r.e12, g = r.e7;
  const routeNames: Record<string, string> = { quick: "question → quick", full: "feature → full", reject: "must be rejected" };
  const screenRows = x ? [
    { title: `${x.detection.injection.of} injections`, sub: x.detection.injection.detected === x.detection.injection.of ? "all flagged and stopped" : `${x.detection.injection.detected} flagged, missed ${x.detection.injection.missed.join(", ")}`, result: `${x.detection.injection.detected} of ${x.detection.injection.of}`, ok: x.detection.injection.detected === x.detection.injection.of },
    { title: `${x.detection.pii_redacted.of} with personal data`, sub: x.redactions_exact.right === x.redactions_exact.of ? "all flagged, every item redacted" : `${x.detection.pii_redacted.detected} flagged, ${x.redactions_exact.right} with the exact count`, result: `${x.detection.pii_redacted.detected} of ${x.detection.pii_redacted.of}`, ok: x.detection.pii_redacted.detected === x.detection.pii_redacted.of && x.redactions_exact.right === x.redactions_exact.of },
    { title: `${x.detection.off_topic.of} off-topic`, sub: x.detection.off_topic.detected === x.detection.off_topic.of ? "all flagged and stopped" : `${x.detection.off_topic.detected} flagged`, result: `${x.detection.off_topic.detected} of ${x.detection.off_topic.of}`, ok: x.detection.off_topic.detected === x.detection.off_topic.of },
    { title: `${x.false_positives.of} clean inputs`, sub: x.false_positives.count === 0 ? "all passed, none wrongly flagged" : `${x.false_positives.count} wrongly flagged: ${x.false_positives.ids.join(", ")}`, result: `${x.false_positives.of - x.false_positives.count} of ${x.false_positives.of}`, ok: x.false_positives.count === 0 },
  ] : [];
  const misrouted = (id: string, kind: string, expected: string, got: string, screen: string[]) => {
    const what = kind === "pii" ? "an input with personal data" : kind === "feature" ? "a feature description" : kind === "question" ? "a question" : kind === "injection" ? "a prompt injection" : "an off-topic input";
    const flags = screen.filter((f) => f !== "pii_redacted").map((f) => f.replace("_", "-"));
    return `${id}, ${what}: sent to ${got} instead of ${expected}${flags.length ? `, after the screen flagged it as ${flags.join(" and ")}` : ""}${kind === "pii" ? ", where it should have been assessed with the personal data redacted" : ""}.`;
  };
  return (
    <div className="evalpage">
      {e1 ? (
        <SetBlock s={e1} table={false}>
          {x ? (
            <>
              <div className="esplit">
                <div className="stack">
                  <Stat label="routed right" value={`${x.route_accuracy.right} of ${x.route_accuracy.of}`} sub={`${Math.round((1000 * x.route_accuracy.right) / x.route_accuracy.of) / 10} %`} tone="ok" />
                  <Stat label="fallback decided" value={`${x.fallback.count} of ${x.fallback.of}`} sub={x.fallback.count === 0 ? "the classifier answered every time" : "the classifier did not answer"} />
                  <Stat label="misrouted" value={String(x.route_accuracy.of - x.route_accuracy.right)} sub={x.misrouted.length ? x.misrouted.map((m) => m.id).join(", ") + ", see below" : "none"} />
                </div>
                <Figure title="Expected route against the route given" sub="the diagonal is right; a red edge marks a miss">
                  <Matrix order={x.route_matrix.order} counts={x.route_matrix.counts} rowLabel="expected" colLabel="the router sent it to" rowNames={routeNames} markOff />
                </Figure>
              </div>
              {x.misrouted.length ? <div className="small muted">{x.misrouted.length === 1 ? "The one misrouted input: " : "Misrouted: "}{x.misrouted.map((m) => misrouted(m.id, m.kind || "", m.expected || "", m.got || "", m.screen)).join(" ")}</div> : null}
            </>
          ) : null}
        </SetBlock>
      ) : null}
      {e2 ? (
        <SetBlock s={e2} table={false} name="Input screening">
          {x ? (
            <Figure title={`What the screen did with the ${x.route_accuracy.of} inputs`} sub="each outcome with its count; a tick when every input of that kind was handled right">
              <ScreenFlow rows={screenRows} total={`${x.route_accuracy.of} inputs`} />
            </Figure>
          ) : null}
        </SetBlock>
      ) : null}
      {e7 ? (
        <SetBlock s={e7} table={false}>
          {g ? (
            <div className="fgrid">
              {g.faults.map((f) => (
                <div key={f.id} className="fcard">
                  <div className="eyebrow">planted fault</div>
                  <b>{f.name}</b>
                  <div className="small muted">{f.planted}</div>
                  <div className="small muted">expected: <span className="chip neutral">{f.expected?.startsWith("redact") ? `redact ${f.expected.split(":")[1] || ""} items` : f.expected}</span></div>
                  <div className={`chip ${f.ok ? "ok" : "bad"}`}>{f.ok ? (f.expected?.startsWith("redact") ? `${f.why?.split(" ")[0]} items redacted ✓` : "regenerated ✓") : `missed ✗ ${f.why || ""}`}</div>
                </div>
              ))}
            </div>
          ) : null}
        </SetBlock>
      ) : null}
    </div>
  );
}

export function Retrieval({ r }: { r: EvalReport }) {
  const e3 = findSet(r, "E3"), e4 = findSet(r, "E4");
  const x = r.e3;
  const pct = (f: { found: number; of: number }) => Math.round((100 * f.found) / f.of);
  const g = x?.grader;
  const conf = g?.confidence_min_median_max;
  const said = g ? g.tp + g.fp : 0, present = g ? g.tp + g.fn : 0;
  const wrongPass = g?.false_pass?.length ? g.false_pass : [];
  return (
    <div className="evalpage">
      {e3 ? (
        <SetBlock s={e3} table={false}>
          {x ? (
            <>
              <div className="hero3">
                <Stat label="recall with the loop" value={`${x.recall_loop.found} of ${x.recall_loop.of}`} sub={`the must-retrieve provision among the five passages · target ≥ 0.85 ${x.recall_loop.found / x.recall_loop.of >= 0.85 ? "met" : "not met"}`} tone={x.recall_loop.found / x.recall_loop.of >= 0.85 ? "ok" : "bad"} />
                <Stat label="single search" value={`${x.recall_single.found} of ${x.recall_single.of}`} sub="the same queries, one search and no grader" />
                <Stat label="searches per query" value={String(x.attempts_mean ?? "–")} sub={`${g?.grades_logged ?? g?.grades ?? "–"} searches, ${x.rewrites_total} rewrites`} />
              </div>
              <Figure title="Recall@5, with and without the loop" sub="the must-retrieve provision among the five passages returned" wide>
                <Legend items={[{ color: C.s1, label: "with the loop (grade, rewrite, search again)" }, { color: C.s2, label: "single search, no grader" }]} />
                <Bars cats={["must-retrieve recall@5"]}
                  series={[{ name: "with the loop", color: C.s1, values: [x.recall_loop.found / x.recall_loop.of] }, { name: "single search", color: C.s2, values: [x.recall_single.found / x.recall_single.of] }]}
                  fmt={(v) => v.toFixed(2)} width={440} />
                <div className="gain">The agentic loop raised retrieval recall from <b>{pct(x.recall_single)} %</b> to <b>{pct(x.recall_loop)} %</b>{x.gain.relative_pct !== null ? <>, an improvement of <b>{x.gain.relative_pct} %</b></> : null}.</div>
              </Figure>
              {x.hard?.length ? (
                <Figure title={`The ${x.hard.length === 1 ? "one query" : `${x.hard.length} queries`} a single search missed`} sub="what the loop did with each" wide>
                  <div className="fgrid">
                    {x.hard.map((h) => (
                      <div key={h.id} className="fcard">
                        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", gap: 8 }}><b className="mono" style={{ fontSize: 12 }}>{h.id} · {h.provision}</b><span className={`chip ${h.recovered ? "ok" : "bad"}`}>{h.recovered ? "recovered" : "missed"}</span></div>
                        <div className="small muted">{h.domain} · {h.domain_name}</div>
                        <div>{h.text}</div>
                      </div>
                    ))}
                  </div>
                </Figure>
              ) : null}
            </>
          ) : null}
        </SetBlock>
      ) : null}
      {e4 ? (
        <SetBlock s={e4} table={false}>
          {x && g ? (
            <>
              <div className="hero3">
                <Stat label="precision of ‘enough’" value={g.precision === null ? "–" : g.precision.toFixed(2)} sub={`${g.tp} of the ${said} times it said enough, the right provision was there${wrongPass.length ? `; the wrong ‘enough’ ${wrongPass.length === 1 ? "is" : "are"} the ${wrongPass.map((w) => w.id).join(", ")} miss${wrongPass.length === 1 ? "" : "es"}` : ""}`} />
                <Stat label="recall of ‘enough’" value={g.recall === null ? "–" : g.recall.toFixed(2)} sub={`the right provision was there ${present} times; it said enough ${g.tp} times and asked for an unneeded extra search ${g.fn} times`} />
                <Stat label="unneeded extra searches" value={`${g.fn} of ${g.grades}`} sub="a wrong ‘not enough’ costs one more search, not the answer" tone={g.fn === 0 ? "ok" : undefined} />
              </div>
              <Figure title="The grader’s decisions" sub={`${g.grades} grades: rows are the truth, columns what it said; a red edge marks a wrong call`} wide>
                <Matrix order={["enough", "not enough"]} counts={{ enough: { enough: g.tp, "not enough": g.fn }, "not enough": { enough: g.fp, "not enough": g.tn } }} rowLabel="truth: the right provision was there" colLabel="the grader said" rowNames={{ enough: "yes", "not enough": "no" }} markOff />
                {conf ? (
                  <div className="small muted">The grader was between {conf[0]} and {conf[2]} confident in all {g.grades} grades, so the floor of 0.6 below which the loop ignores an ‘enough’ never came into play; raising it to 0.9 would only have added rewrites{wrongPass.length ? ` and would not have caught the wrong ‘enough’ (confidence ${wrongPass.map((w) => w.confidence).join(", ")})` : ""}.</div>
                ) : null}
              </Figure>
            </>
          ) : null}
        </SetBlock>
      ) : null}
    </div>
  );
}

/** What a key finding is and how the judge scores one against the expected finding: the picture above the findings numbers. */
function FindingAnatomy() {
  const part = (k: string, v: string, color: string) => (
    <div className="fa-part"><span className="fa-k" style={{ color }}>{k}</span><span>{v}</span></div>
  );
  return (
    <div className="fa">
      <div className="fa-card">
        <div className="fa-title">One key finding has three parts</div>
        <div className="fa-example">
          <span className="chip sev" style={{ background: "var(--bad-bg)", color: "var(--bad-ink)", display: "inline-block", padding: "2px 8px" }}>Blocker</span>
          <span> automated declines must offer human review and a way to challenge the outcome </span>
          <span className="mono" style={{ color: "var(--accent-ink)" }}>(GDPR Art. 22(3))</span>
        </div>
        {part("the point", "the obligation or risk it names, in any wording", "var(--ink)")}
        {part("the severity", "Blocker: unlawful as described, stop and redesign · Required: an obligation to fulfil before launch · Covered: already handled", "var(--bad-ink)")}
        {part("the citation", "the provision, at the level the expected finding asks for (the article, or the paragraph where the article is an umbrella of unrelated rules)", "var(--accent-ink)")}
      </div>
      <div className="fa-card">
        <div className="fa-title">The judge compares it with the finding a reviewer expects</div>
        <div className="fa-out"><span className="fa-dot" style={{ background: C.ramp[0] }} /><div><b>matched</b> · the same point, the right provision and the same severity</div></div>
        <div className="fa-out"><span className="fa-dot" style={{ background: C.ramp[1] }} /><div><b>partial</b> · the same point and severity, but the provision is missing, at the wrong level or a different article</div></div>
        <div className="fa-out"><span className="fa-dot" style={{ background: C.ramp[2] }} /><div><b>missed</b> · the point is absent, or it is there with the wrong severity (counted separately as <i>severity miscalibrated</i>)</div></div>
        <div className="small muted">Findings the reviewer did not expect are extras: wrong when they misstate the law or demand what the facts say is done, otherwise merely extra and not counted.</div>
      </div>
    </div>
  );
}

export function EndToEnd({ r, print }: { r: EvalReport; print?: boolean }) {
  const e5 = findSet(r, "E5"), e6 = findSet(r, "E6");
  const q = r.e5, a = r.e6;
  const kfRows = a ? a.per_case.map((c) => ({ label: c.id, values: [c.key_findings.matched || 0, c.key_findings.partial || 0, c.key_findings.missed || 0], note: c.key_findings.severity_miscalibrated ? `${c.key_findings.severity_miscalibrated} severity only` : undefined })) : [];
  const met = (v: number, t: number) => (v >= t ? "met" : "not met");
  const flagCard = (name: string, f: { missed: number; positives: number; false: number; negatives: number }) => {
    const total = f.positives + f.negatives, right = total - f.missed - f.false;
    const dots = [...Array(f.positives - f.missed).fill("y"), ...Array(f.missed).fill("x"), ...Array(f.negatives - f.false).fill("n"), ...Array(f.false).fill("x")];
    return (
      <div className="flagcard">
        <div className="row" style={{ justifyContent: "space-between" }}><b>{name}</b><span className={`chip ${right === total ? "ok" : "warn"}`}>{right} of {total}</span></div>
        <div className="dots">{dots.map((d, i) => <i key={i} className={d} />)}</div>
        <div className="small muted">{f.positives} cases expected the flag{f.missed ? `, ${f.missed} missed` : ", none missed"} · {f.negatives} did not{f.false ? `, ${f.false} wrongly set` : ", none wrongly set"}</div>
      </div>
    );
  };
  const kf = a?.key_findings;
  return (
    <div className="evalpage">
      {e5 ? (
        <SetBlock s={e5} table={false}>
          {q ? (
            <>
              <div className="hero-row">
                <Stat label="on the quick path" value={`${q.quick_answers.count} of ${q.quick_answers.of}`} sub={q.quick_answers.not_quick.length ? `took the full path: ${q.quick_answers.not_quick.join(", ")}` : "every question answered without the full path"} tone={q.quick_answers.not_quick.length ? undefined : "ok"} />
                <Stat label="cited the right article" value={`${q.must_cite.found} of ${q.must_cite.of}`} sub={`target ≥ 0.80 ${met(q.must_cite.found / Math.max(1, q.must_cite.of), 0.8)}${q.must_cite.misses.length ? ` · missed ${q.must_cite.misses.join(", ")}` : ""}`} tone={q.must_cite.found / Math.max(1, q.must_cite.of) >= 0.8 ? "ok" : "bad"} />
                <Stat label="faithfulness" value={q.faithfulness.mean === null ? "–" : q.faithfulness.mean.toFixed(2)} sub={`mean over ${q.faithfulness.over} answers · target ≥ 0.80 ${met(q.faithfulness.mean ?? 0, 0.8)}`} tone={(q.faithfulness.mean ?? 0) >= 0.8 ? "ok" : "bad"} />
                <Stat label="invented citations" value={String(q.invented.count)} sub={q.invented.count ? q.invented.rows.join(", ") : "every cited label exists in the corpus"} tone={q.invented.count ? "bad" : "ok"} />
                <Stat label="within three sentences" value={`${q.quick_answers.count - q.over_three_sentences.length} of ${q.quick_answers.count}`} sub={q.over_three_sentences.length ? `over: ${q.over_three_sentences.join(", ")}` : "the length rule of the quick path"} tone={q.over_three_sentences.length ? undefined : "ok"} />
              </div>
              <Figure title={`The ${q.per_case.length} questions`} sub="what each cited and how faithful the answer was" wide>
                <div className="qgrid">
                  {q.per_case.map((c) => {
                    const miss = (c.missing || []).length > 0;
                    return (
                      <div key={c.id} className={`q${miss ? " miss" : ""}${c.quick ? "" : " full"}`}>
                        <b>{c.id}</b><span>{!c.quick ? "full path" : miss ? `✗ ${c.missing![0]}` : `✓ ${(c.found || c.must || [])[0]}`}</span><span className="f">{c.faithfulness === null || c.faithfulness === undefined ? "–" : c.faithfulness.toFixed(2)}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="small muted">each question: the provision it must cite, ✓ cited or ✗ not, and its faithfulness score</div>
              </Figure>
            </>
          ) : null}
        </SetBlock>
      ) : null}
      {e6 && a && kf ? (
        <SetBlock s={e6} table={false}>
          <div className="theme">
            <div className="eyebrow">The verdict</div>
            <p className="small" style={{ margin: 0, color: "var(--ink-2)" }}>The verdict is the assessment’s bottom line, one of three: <b>Proceed</b> (nothing stands in the way), <b>Proceed with conditions</b> (obligations to fulfil before launch) or <b>Do not build as described</b> (the design is unlawful as it stands). It is right when it equals the one the reviewer expected; a dangerous miss is a Do not build answered with Proceed.</p>
            <div className="esplit">
              <div className="stack">
                <Stat label="verdict right" value={`${a.verdict.right} of ${a.verdict.of}`} sub={`target ≥ 0.80 ${met(a.verdict.right / a.verdict.of, 0.8)}`} tone={a.verdict.right / a.verdict.of >= 0.8 ? "ok" : "bad"} />
                <Stat label="dangerous misses" value={String(a.dangerous_misses.length)} sub={a.dangerous_misses.length ? a.dangerous_misses.join(", ") : "expected Do not build, got Proceed · target 0 met"} tone={a.dangerous_misses.length ? "bad" : "ok"} />
                <Stat label="risk level right" value={`${a.risk_level.right} of ${a.risk_level.of}`} sub="low · medium · high" />
              </div>
              <Figure title="Expected verdict against the verdict given" sub="the diagonal is right; a red edge marks a miss">
                <Matrix order={a.verdict_matrix.order} counts={a.verdict_matrix.counts} rowLabel="expected" colLabel="given" short={(s) => SHORT[s] || s} markOff />
              </Figure>
            </div>
          </div>
          <div className="theme">
            <div className="eyebrow">The two flags</div>
            <div className="flagrow">{flagCard("High-risk AI flag", a.flags.high_risk_ai)}{flagCard("DPIA required flag", a.flags.dpia_required)}</div>
            <Legend items={[{ color: C.ramp[0], label: "flag expected and set" }, { color: "#C9D9F0", label: "no flag expected, none set" }, { color: "#D23B3B", label: "wrong" }]} />
          </div>
          <div className="theme">
            <div className="eyebrow">Citations and key findings</div>
            <FindingAnatomy />
            <div className="hero-row">
              <Stat label="cited the required articles" value={`${a.must_cite.found} of ${a.must_cite.of}`} sub={`target ≥ 0.80 ${met(a.must_cite.found / Math.max(1, a.must_cite.of), 0.8)}${a.must_cite.misses.length ? ` · missed ${a.must_cite.misses.join(", ")}` : ""}`} tone={a.must_cite.found / Math.max(1, a.must_cite.of) >= 0.8 ? "ok" : "bad"} />
              <Stat label="key findings matched" value={`${kf.matched} of ${kf.of}`} sub={`target ≥ 0.75 ${met(kf.matched / Math.max(1, kf.of), 0.75)} (${(kf.matched / Math.max(1, kf.of)).toFixed(2)})`} tone={kf.matched / Math.max(1, kf.of) >= 0.75 ? "ok" : "bad"} />
              <Stat label="wrong extra findings" value={String(a.wrong_extras.length)} sub={a.wrong_extras.length ? `${a.wrong_extras.map((w) => w.split(":")[0]).join(", ")}: a finding the law or the facts rule out` : "none"} tone={a.wrong_extras.length ? undefined : "ok"} />
              <Stat label="red lines crossed" value={String(a.must_not_violations.length)} sub="a recommendation the rubric forbids" tone={a.must_not_violations.length ? "bad" : "ok"} />
            </div>
            <Figure title={`The ${kf.of} expected findings`} sub="as the judge scored them" wide>
              <div className="stackbar">
                <div style={{ width: `${(100 * kf.matched) / kf.of}%`, background: C.ramp[0] }}>{kf.matched} matched</div>
                <div style={{ width: `${(100 * kf.partial) / kf.of}%`, background: C.ramp[1] }}>{kf.partial} partial</div>
                <div style={{ width: `${(100 * kf.missed) / kf.of}%`, background: C.ramp[2], color: "var(--ink)" }}>{kf.missed} missed</div>
              </div>
              <div className="small muted">over {a.per_case.length} cases · {kf.severity_miscalibrated} of the {kf.missed} missed make the right point with the wrong severity, {kf.missed_absent} are absent</div>
            </Figure>
            <div className="figgrid">
              <Figure title="Severity of the miscalibrated findings" sub="right point and provision, wrong label: expected (rows) against given (columns)">
                <Matrix order={a.severity_matrix.order} counts={a.severity_matrix.counts} rowLabel="expected" colLabel="given" markOff />
              </Figure>
              <Figure title="Key findings per case" sub="matched · partial · missed, of the findings expected for that case">
                <Legend items={[{ color: C.ramp[0], label: "matched" }, { color: C.ramp[1], label: "partial" }, { color: C.ramp[2], label: "missed" }]} />
                <Stacked rows={kfRows} keys={["matched", "partial", "missed"]} colors={C.ramp} width={460} />
              </Figure>
            </div>
          </div>
          <div className="theme">
            <div className="eyebrow">Checks on the scoring</div>
            <div className="hero-row">
              <Stat label="faithfulness of the findings" value={a.faithfulness.mean === null ? "–" : a.faithfulness.mean.toFixed(2)} sub={`mean over ${a.faithfulness.over} · target ≥ 0.80 ${met(a.faithfulness.mean ?? 0, 0.8)}`} tone={(a.faithfulness.mean ?? 0) >= 0.8 ? "ok" : "bad"} />
              <Stat label="confusable pairs both right" value={`${a.pairs.right} of ${a.pairs.total}`} sub="see Legal domains" />
              {a.judge_vs_human ? <Stat label="judge agrees with a human" value={`${a.judge_vs_human.agreed} of ${a.judge_vs_human.of}`} sub={`findings scored by both${a.judge_vs_human.unsure.length ? ` · ${a.judge_vs_human.unsure.length} unsure left out` : ""} · target ≥ 0.85 ${met(a.judge_vs_human.agreed / Math.max(1, a.judge_vs_human.of), 0.85)}`} tone={a.judge_vs_human.agreed / Math.max(1, a.judge_vs_human.of) >= 0.85 ? "ok" : "bad"} /> : null}
              <Stat label="one assessment" value={`${Math.round(a.run.seconds_mean || 0)} s · $${((r.cost.find((c) => c.set === "E6")?.gateway ?? (a.cost || 0) + (a.judge_cost || 0)) / Math.max(1, a.per_case.length)).toFixed(2)}`} sub="mean per case on the gateway, judge included" />
            </div>
            {a.judge_vs_human && r.notes?.judge_note ? <div className="small muted">{r.notes.judge_note}</div> : null}
          </div>
          <details className="plain appendix" open={print}>
            <summary><b>Per case</b> · the {a.per_case.length} assessments one by one</summary>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
              <div className="tblwrap">
                  <table className="tbl small">
                    <thead><tr><th>id</th><th>domain</th><th>expected</th><th>given</th><th>risk</th><th>high-risk AI</th><th>DPIA</th><th>key findings m / p / x</th><th>wrong extras</th><th>faithful</th><th>searches</th><th>s</th><th>$</th></tr></thead>
                    <tbody>
                      {a.per_case.map((c) => (
                        <tr key={c.id} className={c.verdict_ok ? "" : "miss"}>
                          <td className="mono">{c.id}</td><td className="mono">{c.domain}</td><td>{SHORT[c.expected_verdict || ""] || c.expected_verdict}</td><td>{SHORT[c.verdict || ""] || c.verdict}{c.dangerous ? " !" : ""}</td>
                          <td>{c.risk_level}{c.risk_ok ? "" : " ·"}</td><td>{yes(c.high_risk_ai.got)}{c.high_risk_ai.got === c.high_risk_ai.expected ? "" : ` (exp. ${yes(c.high_risk_ai.expected)})`}</td>
                          <td>{yes(c.dpia_required.got)}{c.dpia_required.got === c.dpia_required.expected ? "" : ` (exp. ${yes(c.dpia_required.expected)})`}</td>
                          <td className="mono">{c.key_findings.matched} / {c.key_findings.partial} / {c.key_findings.missed} of {c.key_findings.of}{c.key_findings.severity_miscalibrated ? ` (${c.key_findings.severity_miscalibrated} sev.)` : ""}</td>
                          <td className="mono">{c.wrong_extras || ""}</td><td className="mono">{c.faithfulness ?? "–"}</td><td className="mono">{c.searches ?? "–"}</td><td className="mono">{c.seconds ? Math.round(c.seconds) : "–"}</td><td className="mono">{c.cost.toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              <div className="small faint">Shaded rows: a verdict other than the expected one. A dot after the risk level: not the expected level. Domains: D1 automated decisions, D2 data sharing and transfers, D3 high-risk AI, D4 AI that is not high-risk, D5 HR and hiring, D6 special-category data, D7 plainly low-risk, D8 rights and retention.</div>
            </div>
          </details>
        </SetBlock>
      ) : e6 ? <SetBlock s={e6} table={false} /> : null}
    </div>
  );
}

export const TABS = [
  { id: "overview", label: "Overview", render: (r: EvalReport) => <Overview r={r} /> },
  { id: "domains", label: "Legal domains", render: (r: EvalReport) => <Domains r={r} /> },
  { id: "guardrails", label: "Guardrails · E1 E2 E7", render: (r: EvalReport) => <Guardrails r={r} /> },
  { id: "retrieval", label: "Retrieval · E3 E4", render: (r: EvalReport) => <Retrieval r={r} /> },
  { id: "end-to-end", label: "End to end · E5 E6", render: (r: EvalReport, print?: boolean) => <EndToEnd r={r} print={print} /> },
  { id: "shortfalls", label: "What fell short", render: (r: EvalReport) => <Shortfalls r={r} /> },
];

export function ReportHeader({ r }: { r: EvalReport }) {
  const dates = Array.from(new Set(Object.values(r.runs).map((x) => x.timestamp.slice(0, 10)))).sort();
  const when = dates.length > 1 ? `runs of ${dates.join(", ")}` : `run of ${r.run_date}`;
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>{r.notes?.title || "Evaluation report"}</h2>
      <p className="muted" style={{ margin: "4px 0 0 0" }}>Compliance Assistant · {when} · build <span className="mono">{r.commit}</span>{r.missing_sets.length ? ` · not run: ${r.missing_sets.join(", ")}` : ""}</p>
    </div>
  );
}
