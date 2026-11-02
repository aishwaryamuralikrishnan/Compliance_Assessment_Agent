# E6 · 2026-10-26T14:53:25+00:00

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
| key findings matched (judge + rubric) | 5 of 5 · partial 0 | matched ≥ 0.75 |
| must_not violations | 0 | 0 |
| faithfulness of findings (RAGAs definition, own implementation), mean | – | ≥ 0.85 |
| confusable pairs both right (verdict and flags) | – | reported |
| per case: searches · rewrites · regenerations · seconds (mean) | 8.0 · 1.0 · 0.0 · 51.49 | reported |
| model cost of the run: assessments · judge | $0.006 · $0.0049 | – |

### Key findings, per case

**A-003** (Do not build as described):
- KF1 matched: Finding 2 covers the Art. 22 point: a fully automated refusal needs safeguards including human intervention and a way to contest, citing GDPR Art. 22 and Rec. 71. Severity is Blocker, matching the expected Blocker.
- KF2 matched: Finding 6 says a DPIA is required because of the 'systematic automated evaluation that determines checkout outcomes', citing GDPR Art. 35(3), which covers the expected Art. 35(3)(a). Severity is Required, matching the expected Required.
- KF3 matched: Finding 5 states the credit-scoring AI is high-risk and that provider or deployer obligations apply, citing AI Act Art. 6(2) and Annex III point 5. Severity is Required, matching the expected Required.
- KF4 matched: Finding 1 says to 'Exclude browsing behaviour from automated credit scoring', which is the drop-it gist. It cites GDPR Art. 5, an acceptable alternative. Its severity is Blocker against an expected Required, which is within the one-level tolerance.
- KF5 matched: Finding 8 marks the transfer as Covered because the US vendor is certified under the EU-US Data Privacy Framework, citing GDPR Art. 45(1). Severity Covered matches the expected Covered.
- extras noted: Finding 1 calls browsing-behaviour use 'prohibited for this feature', but no cited GDPR provision prohibits it outright; the restriction is a necessity and minimisation judgment, so the wording overstates the law.

