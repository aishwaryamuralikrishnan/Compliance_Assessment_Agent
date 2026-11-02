# E7 · 2026-10-27T14:29:55+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 4 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E7 output guardrail

| fault | expected | caught | detail |
|---|---|---|---|
| unknown_citation | regenerate | yes | regenerate: ['GDPR Art. 99(9)'] |
| pii_in_text | redact:2 | yes | 2 redactions; finding ends: '22(3) safeguards. Contact Lena Kowalski at [REDACTED_EMAIL] or [REDACTED_PHONE].' |
| schema_violation | regenerate | yes | regenerate: 1 validation error for Assessment |
| status_reply | regenerate | yes | regenerate: status reply instead of an assessment |

caught 4 of 4 · target: all (a miss is a bug, not a model result)
