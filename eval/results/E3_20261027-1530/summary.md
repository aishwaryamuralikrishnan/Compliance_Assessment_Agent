# E3 · 2026-10-27T14:30:49+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 20 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E3 retrieval

| metric | result | target |
|---|---|---|
| must-retrieve recall@5, agentic loop | 19 of 20 (0.95) | ≥ 0.85 |
| must-retrieve recall@5, single ungraded pass | 16 of 20 (0.80) | reported (the difference is what the loop buys) |
| nice-to-retrieve recall@5, loop | 24 of 39 (0.62) | reported |
| attempts per query (mean) · rewrites in all · queries ended insufficient | 1.45 · 9 · 1 | reported |
| model cost of the run (grader, rewrite; the reranker is not priced here) | $0.0088 | – |

Loop misses: Q-014: AI Act Art. 5
Single-pass misses: Q-005: GDPR Art. 45; Q-006: GDPR Art. 6; Q-008: AI Act Art. 5; Q-014: AI Act Art. 5

## E4 grader

| grades | said sufficient, must present (right) | said sufficient, must absent (false pass) | said insufficient, must present (false fail) | said insufficient, must absent (right) | precision | recall |
|---|---|---|---|---|---|---|
| 29 | 17 | 1 | 7 | 4 | 0.94 | 0.71 |

Threshold sweep on the same grades (what the loop would have accepted at each `accept_threshold`):

| threshold | accepted | false passes | false fails |
|---|---|---|---|
| 0.5 | 18 of 29 | 1 | 7 |
| 0.6 | 18 of 29 | 1 | 7 |
| 0.7 | 18 of 29 | 1 | 7 |
| 0.8 | 18 of 29 | 1 | 7 |
| 0.9 | 16 of 29 | 1 | 9 |
| 0.95 | 13 of 29 | 1 | 12 |

Grader confidence: min 0.88, median 0.98, max 1.00. The threshold is chosen as the lowest value with the fewest false passes at a tolerable number of false fails (to-do item 8).
