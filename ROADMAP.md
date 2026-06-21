# Zink Roadmap

## Shipped

Core governance pipeline working end-to-end.

- **Identity** — caller validation, allowed-caller lists, trace enrichment
- **Injection** — regex-based prompt injection detection on inputs and outputs
- **Scope** — tool-level permissions + param constraints
- **Policy** — business rules via AST condition evaluator, rate limiting with stateful counters
- **Memory** — deduplication with TTL, idempotency enforcement
- **Audit** — SHA-256 chained tamper-evident log, SQLite-backed
- YAML-driven config with domain → agent inheritance
- LangChain / LangGraph adapter — zero agent code changes
- SQLite backing store — shared by all stateful layers
- `post_execute()` hook — governance after tool success, not just before
- Output scanner — injection detection on tool return values

---

## Next — v0.3

Behavioral intelligence and the research contribution.

- **Intent** — semantic coherence of params (score vs decision contradictions)
- **Data** — field-level ACL, PII stripping, egress control
- **Anomaly** — behavioral drift detection across sessions, FLAG only
- **Fingerprint Engine** — multi-dimensional threat scoring across behavioral dimensions for statistical anomaly detection
- Dashboard — real-time visibility into governance decisions

Production hardening and multi-process deployment.

- Identity upgrade to JWT / HMAC for cryptographic agent identity
- Multi-process backing store (Redis / Postgres)
- Async support throughout (`_arun` on GovernedTool)
- Plain callable adapter — govern any Python function, not just LangChain tools
- PyPI publish under a unique package name

---

## Layers

Execution order matches `default_layers` in the config.

| Layer     | Status    |
|-----------|-----------|
| Identity  | ✓ shipped |
| Injection | ✓ shipped |
| Scope     | ✓ shipped |
| Policy    | ✓ shipped |
| Memory    | ✓ shipped |
| Audit     | ✓ shipped |
| Intent    | v0.3      |
| Data      | v0.3      |
| Anomaly   | v0.3      |
