# E6 · 2026-10-26T15:03:15+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 1 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E6 full assessments

| metric | result | target |
|---|---|---|
| cases that produced an assessment | 1 of 1 | all |
| verdict accuracy | 1 of 1 | ≥ 0.80 |
| dangerous misses (expected Do not build, got Proceed) | 0 | 0 |
| risk level accuracy | 1 of 1 | reported |
| high-risk AI flag: missed of positives · false of negatives | 0 of 1 · 0 of 0 | ≤ 1 · ≤ 1 |
| DPIA flag: missed of positives · false of negatives | 0 of 1 · 0 of 0 | ≤ 1 · ≤ 1 |
| must-cite recall (verified citations, article level) | 3 of 3 | ≥ 0.80 |
| key findings matched (judge + rubric) | 4 of 5 · partial 0 | matched ≥ 0.75 |
| must_not violations | 0 | 0 |
| faithfulness of findings (RAGAs definition, own implementation), mean | 0.846 over 1 | ≥ 0.85 |
| confusable pairs both right (verdict and flags) | – | reported |
| per case: searches · rewrites · regenerations · seconds (mean) | 11.0 · 7.0 · 0.0 · 107.89 | reported |
| model cost of the run: assessments · judge | $0.0102 · $0.016 | – |

### Key findings, per case

**A-003** (Do not build as described):
- KF1 matched: Finding 2 is Blocker and states that a person must intervene and the customer must be able to contest ("human intervention and a way to contest the decision"), citing GDPR Art. 22 and Rec. 71, which matches the expected Art. 22 finding.
- KF2 matched: Finding 6 is Required and says the system "systematically evaluates people through automated processing", requiring a DPIA before processing; it cites Art. 35(3), which covers the expected Art. 35(3)(a).
- KF3 matched: Finding 5 is Required, states that the creditworthiness system is high-risk AI, and cites AI Act Annex III point 5 with the applicable obligations (Art. 26(2), Art. 27(1)).
- KF4 matched: Finding 1 is Blocker (one step from the expected Required, within one-level tolerance) and says to exclude browsing behaviour from scoring entirely, citing GDPR Art. 5, which is an acceptable alternative for the expected Art. 5(1)(c)/Art. 6 provisions.
- KF5 missed: Finding 8 says the US transfer is "covered by the organisation's Data Privacy Framework certification fact" (the right point and Art. 45(1)), but labels it Required; the expected severity is Covered with tolerance none, so the severity is outside tolerance and the finding is missed.

