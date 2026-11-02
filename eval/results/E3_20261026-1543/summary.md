# E3 · 2026-10-26T14:43:42+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 20 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E3 retrieval

| metric | result | target |
|---|---|---|
| must-retrieve recall@5, agentic loop | 18 of 20 (0.90) | ≥ 0.85 |
| must-retrieve recall@5, single ungraded pass | 16 of 20 (0.80) | reported (the difference is what the loop buys) |
| nice-to-retrieve recall@5, loop | 22 of 39 (0.56) | reported |
| attempts per query (mean) · rewrites in all · queries ended insufficient | 1.4 · 8 · 1 | reported |
| confusable pairs both right (loop) | 5 of 5 | reported |
| model cost of the run (grader, rewrite; the reranker is not priced here) | $0.009 | – |

Loop misses: Q-012: AI Act Annex III; Q-014: AI Act Art. 5
Single-pass misses: Q-005: GDPR Art. 45; Q-006: GDPR Art. 6; Q-008: AI Act Art. 5; Q-014: AI Act Art. 5

## E4 grader

| grades | said sufficient, must present (right) | said sufficient, must absent (false pass) | said insufficient, must present (false fail) | said insufficient, must absent (right) | precision | recall |
|---|---|---|---|---|---|---|
| 28 | 15 | 2 | 8 | 3 | 0.88 | 0.65 |

Threshold sweep on the same grades (what the loop would have accepted at each `accept_threshold`):

| threshold | accepted | false passes | false fails |
|---|---|---|---|
| 0.5 | 15 of 26 | 0 | 8 |
| 0.6 | 15 of 26 | 0 | 8 |
| 0.7 | 15 of 26 | 0 | 8 |
| 0.8 | 15 of 26 | 0 | 8 |
| 0.9 | 13 of 26 | 0 | 10 |
| 0.95 | 12 of 26 | 0 | 11 |

Grader confidence: min 0.00, median 0.98, max 1.00. The threshold is chosen as the lowest value with the fewest false passes at a tolerable number of false fails (to-do item 8).
