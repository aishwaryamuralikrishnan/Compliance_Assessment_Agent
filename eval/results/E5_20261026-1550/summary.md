# E5 · 2026-10-26T14:50:38+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 1 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E5 quick answers

| metric | result | target |
|---|---|---|
| questions answered on the quick path | 1 of 1 | reported |
| must-cite recall | 1 of 1 | ≥ 0.80 |
| invented citations (before the guardrail) | 0 across 1 answers | ≤ 1 |
| faithfulness (RAGAs definition, own implementation), mean | 1.0 over 1 | ≥ 0.90 |
| answers over three sentences | 1 of 1 | reported |
| empty answers | 0 of 1 | reported |
| confusable pairs both right | – | reported |
| model cost of the run (answers and judge) | $0.0021 | – |
