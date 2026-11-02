# E5 · 2026-10-27T15:26:09+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 15 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E5 quick answers

| metric | result | target |
|---|---|---|
| questions answered on the quick path | 15 of 15 | reported |
| must-cite recall | 13 of 15 | ≥ 0.80 |
| invented citations (before the guardrail; E7 tests that the guardrail catches them) | 0 across 15 answers | reported |
| faithfulness (RAGAs definition, own implementation), mean | 0.873 over 15 | ≥ 0.90 |
| answers over three sentences | 0 of 15 | reported |
| empty answers | 0 of 15 | reported |
| model cost of the run (answers and judge) | $0.0325 | – |
Must-cite misses: K-004: GDPR Art. 46; K-008: AI Act Art. 5
