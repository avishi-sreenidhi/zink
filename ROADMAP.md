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
