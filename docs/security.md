# Security Model

This page documents the trust assumptions Zink makes, the guarantees it provides, and the conditions under which those guarantees hold. Understanding this is necessary to use Zink safely.

---

## The context contract

Every `ValidationRequest` carries two dicts: `params` (the agent's tool arguments) and `context` (runtime attributes from your infrastructure). These have different trust levels:

| | `params` | `context` |
|---|---|---|
| **Written by** | The agent (tool kwargs) | Your `context_fn` |
| **Trust level** | Untrusted — assume the LLM chose these | Trusted — you wrote the function that produces them |
| **Used by** | Scope constraints, injection scanner | Identity (caller_id), Policy (hour, role), Scope (value_from) |

**The agent cannot write to `context`.** The governed closure intercepts every tool call, calls `context_fn()` itself, and builds the `ValidationRequest` — the agent only gets to supply tool kwargs. The agent has no reference to the `ValidationRequest` object.

```python
def governed(*args, **kwargs):
    context = context_fn()       # ← your code runs here, not the agent's
    request = ValidationRequest(
        params  = kwargs,        # ← agent supplied these
        context = context,       # ← your context_fn supplied these
        ...
    )
    result = engine.validate(request)
```

**What this means in practice:** Layers that read from `context` — Identity's `caller_id`, Policy's `context.hour`, Scope's `value_from` paths — are structurally insulated from agent influence. They trust `context` as authoritative because only your wiring code can write it.

**Precondition:** This guarantee holds only if `context_fn` reads from sources the agent cannot influence — your auth session, a system clock, a database keyed to the authenticated user. If `context_fn` reads from agent-controlled state (e.g., the agent's own tool call arguments are passed into it), the contract breaks. Keep `context_fn` as a closure over your infrastructure, not over the agent's state.

---

## `value_from` contract

`value_from` in a scope constraint resolves the expected value from `request.context` at runtime, rather than from the config file. This allows per-caller allowlists without duplicating scope entries:

```yaml
# One config entry, different enforcement per caller
constraints:
  - param: patient_id
    operator: in
    value_from: context.allowed_patients   # Doctor A gets [P001], Doctor B gets [P002]
```

**Safety condition:** `value_from` is sound if and only if the path it references is populated by a trusted source upstream of the agent — your PIP (Policy Information Point): an identity provider, auth middleware, or session layer that the agent cannot influence.

If the agent or its orchestrator can write arbitrary values into the resolved context key, `value_from` becomes a bypass vector: the agent could set `context.allowed_patients` to include any patient ID it wants.

**Fail-closed:** If the dot-path in `value_from` does not resolve (key absent, wrong type), the constraint **blocks**. It never passes on a missing value.

**Auditability note:** With `value=`, the YAML is the complete, auditable record of what was enforced — an auditor reads the config and knows exactly what was checked. With `value_from`, the enforced value is a runtime quantity. To close this gap, read the `layer_trace` in the audit log: the scope layer records the `expected` value it actually checked, so the audit row captures what was enforced, not just "something from context."

---

## Fail-closed behaviors

Zink is designed to block when in doubt. The specific fail-closed behaviors:

| Situation | Behavior |
|---|---|
| `value_from` path doesn't exist in context | `BLOCK` |
| Request action+resource not in scope list | `BLOCK` |
| Policy field missing in context (lenient mode) | condition evaluates to `false` — policy does not fire |
| Layer raises an unexpected exception | not caught by default — propagates; do not silently swallow errors in custom layers |
| `post_execute` raises | caught and logged as `RuntimeWarning`, tool outcome is returned normally |
| Output scan detects injection | `PermissionError` raised after tool fires but before result reaches agent |

There is no "allow on error" path for gate decisions. If you add a custom layer, ensure it returns an explicit `PASS` rather than defaulting to pass via a missing return.

---

## Audit chain

Every tool call — approved or blocked — produces an audit row in the `audit_log` SQLite table. The rows form a **SHA-256 hash chain**: each row's `entry_hash` is computed from the previous row's `entry_hash` concatenated with the current row's fingerprint.

```
entry_hash[n] = SHA-256( entry_hash[n-1] + fingerprint[n] )

fingerprint = JSON({ agent, resource, params, ts }, sort_keys=True)
```

The first row uses `"0" * 64` as the genesis hash.

**What this proves:**
- No row was deleted (gap in `prev_hash` chain would be detected)
- No row was modified (hash would no longer match)
- Rows are in the correct insertion order (via `prev_hash` linkage)
- `params` are stored and included in the fingerprint — parameter-level tampering is detectable

**What this does not prove:** That the audit log itself has not been replaced wholesale. The chain is tamper-evident, not tamper-proof. For a stronger guarantee, periodically export and cryptographically sign the chain head, or write the chain head to an append-only external log.

**Verifying the chain:**
```python
from zink.audit.logger import AuditLogger
from zink.store.sqlite import ZinkStore

logger = AuditLogger(ZinkStore("zink.db"))
ok = logger.verify_chain()   # True = intact, False = tampered
```

**Multi-agent shared store:** Multiple `ZinkEngine` instances sharing one `ZinkStore` write audit rows atomically. The store acquires a lock, reads the last `entry_hash`, computes the new hash, and inserts — all in one lock acquisition. There is no TOCTOU window.

---

## What Zink does not do

- **Does not authenticate cryptographic tokens.** `caller_id` is a string you supply in context. Zink trusts it as-is. Verify the actual auth token before calling `context_fn`.
- **Does not sandbox the tool.** If a tool does something destructive, Zink blocked the *call* — but if the call was approved, the tool runs without further restriction.
- **Does not inspect LLM reasoning.** Zink operates on tool call boundaries, not on the agent's internal chain-of-thought.
- **Does not protect against a compromised `context_fn`.** The trust model assumes your wiring code is correct. Zink enforces what context says — it cannot verify context was produced honestly.
