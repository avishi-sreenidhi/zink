# Zink Roadmap

## Shipped

Core governance pipeline working end-to-end.

- **L1 Identity** — caller validation, allowed-caller lists, trace enrichment
- **L2 Injection** — regex-based prompt injection detection on inputs and outputs
- **L4 Memory** — deduplication with TTL, idempotency enforcement
- **L6 Policy** — business rules via AST condition evaluator, rate limiting with stateful counters
- **L7 Audit** — SHA-256 chained tamper-evident log, SQLite-backed
- **L9 Scope** — tool-level permissions + param constraints
- YAML-driven config with domain → agent inheritance
- LangChain / LangGraph adapter — zero agent code changes
- SQLite backing store — shared by all stateful layers
- `post_execute()` hook — governance after tool success, not just before
- Output scanner — L2 injection detection on tool return values

---

## Next — v0.3

Behavioral intelligence and the research contribution.

- **L3 Intent** — semantic coherence of params (score vs decision contradictions)
- **L5 Data** — field-level ACL, PII stripping, egress control
- **L8 Anomaly** — behavioral drift detection across sessions, FLAG only
- **Fingerprint Engine** — multi-dimensional threat scoring across behavioral dimensions for statistical anomaly detection
- Dashboard — real-time visibility into governance decisions

Production hardening and multi-process deployment.

- L1 upgrade to JWT / HMAC for cryptographic agent identity
- Multi-process backing store (Redis / Postgres)
- Async support throughout (`_arun` on GovernedTool)
- Plain callable adapter — govern any Python function, not just LangChain tools
- PyPI publish under a unique package name

---

## Layer numbering

Zink uses a fixed nine-position taxonomy. Not all positions are implemented yet.

| Layer | Name      | Status        |
|-------|-----------|---------------|
| L1    | Identity  | ✓ shipped     |
| L2    | Injection | ✓ shipped     |
| L3    | Intent    | v0.3          |
| L4    | Memory    | ✓ shipped     |
| L5    | Data      | v0.3          |
| L6    | Policy    | ✓ shipped     |
| L7    | Audit     | ✓ shipped     |
| L8    | Anomaly   | v0.3          |
| L9    | Scope     | ✓ shipped     |

Gaps are intentional. The numbering reflects the governance taxonomy, not implementation order.
