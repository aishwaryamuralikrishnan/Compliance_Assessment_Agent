# E6 · 2026-10-26T15:20:33+00:00

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
| faithfulness of findings (RAGAs definition, own implementation), mean | 0.714 over 1 | ≥ 0.85 |
| confusable pairs both right (verdict and flags) | – | reported |
| per case: searches · rewrites · regenerations · seconds (mean) | 8.0 · 1.0 · 0.0 · 52.37 | reported |
| model cost of the run: assessments · judge | $0.0064 · $0.0104 | – |

### Key findings, per case

**A-003** (Do not build as described):
- KF1 matched: Finding 1 covers the Art. 22 point with 'provide meaningful human review, a way to contest' at Blocker, citing GDPR Art. 22 and Rec. 71, which matches the expected Blocker with no tolerance.
- KF2 matched: Finding 6 states 'decisions with legal or similarly significant effects are based on systematic, extensive automated evaluation' at Required and cites GDPR Art. 35(3), matching the DPIA point.
- KF3 matched: Finding 2 says 'This is high-risk AI for evaluating creditworthiness' and cites AI Act Annex III point 5 with provider/deployer-style oversight duties; its Blocker is one step from the expected Required, which is within the one-level tolerance.
- KF4 matched: Finding 5 covers browsing behaviour with 'demonstrate a lawful basis, purpose compatibility, and necessity for credit scoring; otherwise exclude it' at Required, citing GDPR Art. 5 (an acceptable alternative) and Art. 6.
- KF5 matched: Finding 8 marks the US vendor transfer as Covered by 'the organisation's Data Privacy Framework certification fact' and cites GDPR Art. 45(1), matching the expected Covered finding.

