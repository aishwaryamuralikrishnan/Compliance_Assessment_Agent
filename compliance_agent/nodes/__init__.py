"""Nodes of the orchestrator graph.

    validate_input   length / injection / topic checks, PII redaction        (fixed utilities)
    route            quick | full | reject with a confidence                  (Jev, LLM fallback)
    direct_answer    quick path: one retrieval, cheap model, no tools
    worker           create_agent subgraph: tools, PII + summarisation middleware,
                     per-role tool binding and the tool gate (interrupt for the DPO)
    output_guardrail citation verification, PII scan, schema check, disclaimer
    memory_write     reflect + role-gated Store writes                         (step 6)
"""
