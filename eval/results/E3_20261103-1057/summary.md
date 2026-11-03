# E3 · 2026-11-03T09:57:22+00:00

commit `68ee851` · database `localhost/compliance_eval` · 20 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E3 retrieval

| metric | result | target |
|---|---|---|
| must-retrieve recall@5, agentic loop | 20 of 20 (1.00) | ≥ 0.85 |
| must-retrieve recall@5, single ungraded pass | 15 of 20 (0.75) | reported (the difference is what the loop buys) |
| nice-to-retrieve recall@5, loop | 20 of 39 (0.51) | reported |
| attempts per query (mean) · rewrites in all · queries ended insufficient | 1.65 · 13 · 2 | reported |
| model cost of the run (grader, rewrite; the reranker is not priced here) | $0.0215 | – |
Single-pass misses: Q-005: GDPR Art. 45; Q-006: GDPR Art. 6; Q-013: GDPR Art. 9; Q-014: AI Act Art. 5; Q-019: GDPR Art. 5

## E4 grader

| grades | said sufficient, must present (right) | said sufficient, must absent (false pass) | said insufficient, must present (false fail) | said insufficient, must absent (right) | precision | recall |
|---|---|---|---|---|---|---|
| 33 | 16 | 0 | 11 | 6 | 1.0 | 0.59 |

Threshold sweep on the same grades (what the loop would have accepted at each `accept_threshold`):

| threshold | accepted | false passes | false fails |
|---|---|---|---|
| 0.5 | 16 of 33 | 0 | 11 |
| 0.6 | 16 of 33 | 0 | 11 |
| 0.7 | 16 of 33 | 0 | 11 |
| 0.8 | 16 of 33 | 0 | 11 |
| 0.9 | 16 of 33 | 0 | 11 |
| 0.95 | 14 of 33 | 0 | 13 |

Grader confidence: min 0.88, median 0.98, max 1.00. The threshold is chosen as the lowest value with the fewest false passes at a tolerable number of false fails (to-do item 8).
