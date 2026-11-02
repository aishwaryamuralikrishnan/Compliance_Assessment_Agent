# E6 · 2026-10-26T15:27:52+00:00

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
| must-cite recall (verified citations, article level) | 2 of 3 | ≥ 0.80 |
| key findings matched (judge + rubric) | 4 of 5 · partial 0 | matched ≥ 0.75 |
| must_not violations | 0 | 0 |
| faithfulness of findings (RAGAs definition, own implementation), mean | 0.739 over 1 | ≥ 0.85 |
| confusable pairs both right (verdict and flags) | – | reported |
| per case: searches · rewrites · regenerations · seconds (mean) | 9.0 · 1.0 · 0.0 · 70.68 | reported |
| model cost of the run: assessments · judge | $0.0062 · $0.0114 | – |
Must-cite misses: A-003: GDPR Art. 35

### Key findings, per case

**A-003** (Do not build as described):
- KF1 matched: Finding 1 (Blocker) says fully automated refusals need human intervention and the ability to contest, citing GDPR Art. 22 and Rec. 71, which matches the gist, provisions and Blocker severity.
- KF2 missed: No assistant finding addresses a DPIA with the systematic-profiling basis. The DPIA is only mentioned in the summary and next steps, with no Art. 35 citation and no severity, so the expected Required finding is absent.
- KF3 matched: Finding 4 (Required) says creditworthiness AI is high-risk, that the fraud exception does not apply, and that high-risk deployer obligations must be met, citing AI Act Annex III point 5 and Art. 26(2), which matches the gist, provision and Required severity.
- KF4 matched: Finding 3 (Blocker) requires browsing behaviour to be justified for necessity and proportionality, or not included, citing GDPR Art. 5 and Art. 6(1). Art. 5 is an acceptable alternative and Blocker is one step from Required, which is within the one-level tolerance.
- KF5 matched: Finding 8 (Covered) states the US vendor transfer is covered by its EU-US Data Privacy Framework certification, subject to confirmation, citing GDPR Art. 45(1), which matches the gist, provision and Covered severity.

