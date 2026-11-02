# Evaluation report · run of 27 October 2026

The first full run of the evaluation harness (`eval/README.md`) against the app at commit `6fc8bad`, with the
fixed models of `config/models.yaml`: GPT-6 Luna in the worker and grader slots, Gemini 3.1 Flash Lite as the
cheap model, Claude Haiku 5.5 as the judge, OpenAI `text-embedding-3-small`, Cohere `rerank-4-fast`, the Jev
router. Evaluation database `compliance_eval`, reset to the seeded state before the run; LangSmith off; one run
per case. Result folders: `E12_…-1524`, `E7_…-1529`, `E3_…-1530`, `E5_…-1626` (the rerun on E5's own set),
`E6_…-1635` under `eval/results/`. Total model bill on the gateway: $1.28 (E12 $0.02, E7 $0.01, E3 $0.10, E5
$0.07 for the 15-question rerun, E6 $0.76, plus the first E5 run on the shared set, $0.32, superseded).

## 1. Results against the targets

Targets are those fixed before the run (README section 6; EVALUATION.md §7 step 5 with the additions of 26 and
27 October). None was changed after seeing a number.

| Set | Metric | Result | Target | Met |
|---|---|---|---|---|
| E1 | route accuracy | 44 of 45 (0.98); fallback 0 of 45 | ≥ 0.90 | yes |
| E2 | injection · PII · off-topic detected | 7 of 7 · 7 of 7 · 4 of 4 | ≥ 6 · ≥ 6 · 4 | yes |
| E2 | false positives on clean rows | 0 of 27 | ≤ 3 | yes |
| E2 | redaction counts exact | 7 of 7 | 7 | yes |
| E7 | faults caught | 4 of 4 | 4 | yes |
| E3 | must-retrieve recall@5, agentic loop | 19 of 20 (0.95) | ≥ 0.85 | yes |
| E3 | recall@5, single ungraded pass | 16 of 20 (0.80) | reported | – |
| E4 | grader precision · recall | 0.94 · 0.71 (29 grades) | reported; threshold set | 0.6 kept |
| E5 | questions on the quick path | 15 of 15 | reported | – |
| E5 | must-cite recall | 13 of 15 (0.87) | ≥ 0.80 | yes |
| E5 | invented citations (before the guardrail) | 0 of 15 answers | reported | – |
| E5 | faithfulness, mean | 0.873 | ≥ 0.90 | **no** |
| E5 | answers over three sentences · empty | 0 · 0 | reported | – |
| E6 | cases that produced an assessment | 20 of 20 | all | yes |
| E6 | verdict accuracy · of which dangerous | 13 of 20 (0.65) · 0 | ≥ 0.80 · 0 | **no** · yes |
| E6 | risk level accuracy | 13 of 20 | reported | – |
| E6 | high-risk AI flag: missed · false | 0 of 7 · 0 of 13 | ≤ 1 · ≤ 1 | yes |
| E6 | DPIA flag: missed · false | 2 of 14 · 0 of 6 | ≤ 1 · ≤ 1 | **no** · yes |
| E6 | must-cite recall (verified citations) | 37 of 39 (0.95) | ≥ 0.80 | yes |
| E6 | key findings matched · partial · missed | 59 · 10 · 12 of 81 (0.73 matched) | ≥ 0.75 | **no** (by two findings) |
| E6 | of the missed, wrong severity only | 7 | reported | – |
| E6 | wrong extras | 2 in 20 cases | reported | – |
| E6 | must_not violations | 0 | 0 | yes |
| E6 | faithfulness of findings, mean | 0.851 | ≥ 0.85 | yes |
| E6 | confusable pairs both right | 5 of 8 | reported | – |
| E6 | judge vs human reader | agreed on 13 of 15 findings (4 unsure left out) | ≥ 17 of 20 | yes, as a share (0.87 ≥ 0.85) |

Fourteen targets met, four not, one reported line that needs a word (the judge gate, section 4). The misses
share one cause, severity calibration, described in section 3.

## 2. What each set says

**Routing and screens (E1, E2).** The classifier router sends 44 of 45 inputs the expected way with no fallback;
the one wrong row, R-042, is a plain feature description the router rejects as off-topic, a classifier false
positive recorded in the row's notes before the run. The input screen caught every planted injection, every PII
row with the exact redaction count, every off-topic input, and flagged none of the 27 clean inputs. The output
guardrail (E7) caught all four planted faults: an unknown citation, a personal name with contact details, a
schema violation, a status reply instead of an assessment.

**Retrieval (E3, E4).** The agentic loop finds a must-retrieve provision among the five passages for 19 of 20
queries; the same search without grader and rewrite finds 16 of 20, so the loop buys three queries (Art. 45 for
"DPF-certified vendor", Art. 6 for "reuse delivery data for a credit product", AI Act Art. 5 for "social
scoring") at 1.45 attempts per query, 9 rewrites in all. The one loop miss is AI Act Art. 5 for "guess ethnicity
from faces at the entrance", the same article behind both E5 misses: the prohibited-practices article is the
corpus's weak spot for plain-English phrasing, because its chunks are long and the recitals that paraphrase it
(Rec. 30, Rec. 31) outrank it. The grader accepts with precision 0.94 (one false pass) and recall 0.71 (seven
false fails, which cost a rewrite each, not a wrong answer); its confidence is 0.88–1.00 and the threshold sweep
is flat from 0.5 to 0.8, so `accept_threshold: 0.6` stays. The grader model returned no structured output on two
first calls (A-011, A-013 in E6); the retry succeeded both times.

**Quick answers (E5).** On its own set of 15 questions (section 4 of the README: the first run on the shared
retrieval set sent seven plan-phrased rows down the full route, correctly), every question took the quick path,
every answer stayed within three sentences, none invented a citation, and 13 of 15 cite the expected article. The
two misses are retrieval, not reasoning: K-004 ("US vendor with no certification of any kind") retrieved the
certification articles (Art. 42, Rec. 81) instead of Art. 46 and said so ("the supplied sources do not establish
which alternative applies"); K-008 (social scoring) answered correctly from Rec. 31 without the Art. 5 chunk.
Faithfulness, 0.873 against a target of 0.90, is examined in section 3.

**Assessments (E6).** All 20 cases reached the DPO pause with an assessment. The flags are reliable: the
high-risk AI flag was right in all 20 cases, the DPIA flag in 18. Must-cite recall is 0.95; the two misses are
A-007 (Art. 22 discussed in the summary but not cited in a finding) and A-010 (the fraud carve-out stated
without the Annex III citation). Of 81 expected key findings the judge matched 59 and found 10 partial; of the 12
missed, 7 make the right point with the right provision and only the wrong severity, 5 are absent. Two wrong
extras in 20 cases (A-001: a notice update marked Required although the facts say the notice already covers it;
A-010: a Blocker under Art. 22 for a hold that an analyst reviews within two hours). No assistant output
violated a must_not rule. Faithfulness of the findings to the retrieved passages and memory items is 0.851,
the target. The worker ran 4 to 13 searches per case (mean 8.4), 32 rewrites in all, no regeneration; 76 seconds
per case.

## 3. The failure modes, one example each

**Severity one step off (the main finding).** All seven wrong verdicts are one step away from the expected one,
never two, and never in the dangerous direction; 7 of the 12 missed findings are right on the law and wrong on
the label. Three patterns:

- *Too cautious on plainly low-risk features.* A-001, A-008 and A-019 expected "Proceed" and got "Proceed with
  conditions", each because the assistant added a Required obligation the design already met. A-001, finding 1:
  "Required: document a lawful basis for recording and displaying viewed products … assess and document the
  balance before launch (GDPR Art. 6(1), Rec. 47)" for a recently-viewed strip inside the customer's own
  account.
- *Special-category data as a Blocker where a consent route exists.* A-012 (selfie verification with a video-call
  alternative) and A-017 (doctor's note for a payment holiday) expected "Proceed with conditions" with a Required
  Art. 9(2)(a) finding and got "Do not build as described": "Blocker: do not run it unless customers give valid,
  informed, specific and freely given explicit consent (GDPR Art. 9(1), 9(2))". The point is right; the
  assistant treats a consent that the description does not yet establish as a design fault rather than a
  condition. A reasonable DPO could read it either way, and this is a row for the human expert.
- *The verdict field milder than the text.* A-009 and A-020 expected "Do not build as described" and got "Proceed
  with conditions", yet both summaries open with a stop: A-009 "Do not provide transaction data under the current
  clause until the reuse is separately justified"; A-020 "Do not implement an unconditional, immediate wipe".
  The findings carry the substance (A-009 finding 2 makes the Art. 6(4) point as Required, not Blocker; A-020
  finding 2 makes the AML records a Required point because "an internal policy alone does not establish the
  erasure exception", a careful reading of a text that said "policy", not "law"). The structured verdict lags
  the prose.

**Point present, provision missing or at the wrong level (10 partials).** The typical case cites the umbrella
article where the rubric asks for the paragraph: A-012 finding 6 and A-017 findings 3 and 4 cite "GDPR Art. 5"
for minimisation and storage limitation (5(1)(c), 5(1)(e) expected); A-010 states the fraud carve-out without
"Annex III point 5"; A-006 and A-018 state "not high-risk" in the summary or the flag without a finding that cites
Annex III. The worker prompt's rule "cite the most specific label the tools returned" did not reach these.

**Point absent (5 missed).** Two DPIAs the assistant judged not required (A-007 profiling for promotions, A-009
disclosure for a vendor's model training), both cases where the expectation rests on the EDPB's criteria under
Art. 35(1) rather than on Art. 35(3); one Art. 26(11) duty to tell customers a high-risk system is used (A-011);
one Covered Art. 22 point not stated when a human decides (A-017); one Art. 22 point made in the summary rather
than in a numbered finding (A-007).

**Faithfulness below 0.90 in E5 (0.873).** The 15 unsupported statements fall into three kinds. Citing a
provision the model knows but did not retrieve (K-005: "Art. 45" named only by the memory item, no Art. 45 passage;
K-018: "Rec. 67" cited for rectification, which the retrieved recital does not cover); over-generalising a
conditional rule (K-007: "profiling of natural persons is always high-risk", where Art. 6(3) says so only for
Annex III systems); and recommendations phrased as rules ("requires a full assessment", K-001, K-004). Two
verdicts are the judge's own misreading (K-018: "during restriction only storage is allowed, with exceptions" is
what Art. 18(2) says), which is why the judge-versus-human line exists. In E6, at 0.851, the lowest cases (A-009
0.67, A-012 0.67, A-008 0.72) are the ones with the most recommendations, which the judge was told to leave out
but sometimes checks.

**Retrieval of AI Act Art. 5.** Missed by the single pass in E3 (two queries), by the loop once, and by both E5
questions that needed it. The article's chunks are long and the recitals paraphrasing it rank higher; the loop
recovers one of the two through a rewrite. A corpus-side fix (shorter chunks for Art. 5, or a heading that names
the practices) is the obvious next step, and belongs to the embedding and chunking study after the capstone.

## 4. The judge

The key-finding numbers come from a model (Claude Haiku 5.5) reading another model's output with the rubric of
`eval/prompts/judge_findings.md`. Five cases (A-001 to A-005, 19 findings) were also scored blind by the author
with the same sheet: 4 rows marked unsure and left out, the judge agreed on 13 of the remaining 15, and in both
disagreements (A-003 KF1 and KF5: human partial, judge matched) the judge was the more generous reader. The
target was written as "≥ 17 of 20" on the assumption of 20 scorable rows; with 15 scorable, 13 is 0.87 against
0.85. The report therefore keeps the judge's numbers as they are, with the caveat that where the judge erred it
erred towards the assistant, so 0.73 matched is if anything slightly generous, and that the judge was strict in
one systematic way: a point made only in the summary, not in a numbered finding, counts as absent (A-007 KF1).
The four unsure rows (A-002 KF1, A-004 KF2 and KF5, A-005 KF1) and the two disagreements go to the human expert
in round 3; her verdict replaces the author's for those rows.

## 5. Cost and time

| Set | Gateway bill | Harness token cost | Note |
|---|---|---|---|
| E12 | $0.02 | $0.007 | 45 router and screen calls on Flash Lite |
| E7 | $0.01 | $0 | no model calls; the figure is the gateway's rounding |
| E3 + E4 | $0.10 | $0.009 | the difference is the reranker, 29 calls, unpriced in the harness |
| E5 (15 questions) | $0.07 | $0.033 | answers $0.006, judge $0.027; the rest is 15 rerank calls |
| E6 | $0.76 | $0.13 assessments + $0.18 judge | ≈ 170 rerank calls (about $0.34) make up most of the gap |
| **One full run** | **$0.96** | | against the $4.20 estimated in EVALUATION.md §7 for Mistral Large 4 |

Per E6 case: $0.003–0.010 of worker tokens, 35–126 seconds (mean 76), 4–13 searches. The reranker, at about
$0.002 a call, is close to half the bill of a full run; the harness prices tokens only, so the gateway's figures
are the ones to quote for the bill and the harness's for comparisons between cases.

## 6. What this run does not show

One run per case, 20 cases, 15 questions: the numbers locate failure modes, they do not give confidence
intervals, and a second run would move the verdict count by one or two (A-003 varied 4–5 of 5 across four
rehearsal runs on 26 October). The golden set was reviewed by a model acting as the domain expert (two rounds,
`docs/expert_round1.md`, `docs/expert_round2.md`); the human expert's review is pending, and the four DPIA and
Art. 9 expectations above are the ones most likely to move. The reviser (E9) and the memory's effect on later
assessments are not measured here (pytest and the demo cover the mechanics). The model-dependence run on Mistral
Large 4 (to-do item 10) was not made.

## 7. What follows

Nothing in the app was changed in response to these numbers, by the rule set before the run. The main finding,
severity one step off while the law is right, points at one principled change for the next iteration: a short
calibration passage in the worker prompt with one example per severity, written from the definitions in the
rubric rather than from these cases, and tested on a fresh set. The second is corpus-side: the chunking of AI
Act Art. 5. The third is procedural: the human expert's round 3 on the unsure rows, the two disagreements and the
contested expectations (A-007, A-009 DPIA; A-012, A-017 Art. 9 severity; A-010 Art. 22 on an automated hold).

### Corrections to EVALUATION.md implied by the run (applied on 29 Oct)

§3: E5 has its own set of 15 questions (`quick.jsonl`), not the retrieval set. §4: no RAGAs library; faithfulness
is an own implementation on the judge slot (README section 1). §5: the key-finding rule has no severity
tolerance, a citation level per finding, and matching by atomic point; wrong extras are counted. §7: the targets
as in section 1 above; the cost of one run is about $1 on the current models, not $4.20 (that figure assumed
Mistral Large 4 in the worker slots). §8: the judge gate is stated as a share; LangSmith was not used for the
run.
