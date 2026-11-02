# E5 · 2026-10-27T14:36:05+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 20 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E5 quick answers

| metric | result | target |
|---|---|---|
| questions answered on the quick path | 13 of 20 (0.65) | reported |
| must-cite recall | 11 of 13 | ≥ 0.80 |
| invented citations (before the guardrail; E7 tests that the guardrail catches them) | 0 across 13 answers | reported |
| faithfulness (RAGAs definition, own implementation), mean | 0.838 over 13 | ≥ 0.90 |
| answers over three sentences | 12 of 13 | reported |
| empty answers | 0 of 13 | reported |
| model cost of the run (answers and judge) | $0.0679 | – |

Not routed quick: Q-001 (full), Q-004 (full), Q-006 (full), Q-009 (full), Q-011 (full), Q-012 (full), Q-013 (full)
Must-cite misses: Q-008: AI Act Art. 5; Q-014: AI Act Art. 5
