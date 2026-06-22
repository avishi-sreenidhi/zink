# Layers

Layers are the building blocks of the validation pipeline. Each layer receives a `ValidationRequest` and returns a `LayerResult` with a status of `PASS`, `BLOCK`, or `FLAG`.

Gate layers (phase 1) exit the pipeline immediately on `BLOCK`. Enrichment layers (phase 2) run regardless and can only `FLAG`. All currently implemented layers are phase 1.

---

## Execution model

```
for layer in default_layers:
    result = layer.evaluate(request)
    if result.status == BLOCK:
        return build_result([...so far...])   # early exit
```

The final trace contains only the layers that ran. A layer that didn't run because an earlier one blocked is absent from the trace — this is intentional and tells you exactly where enforcement stopped.

---

## L1 — Identity (`identity`)

**What it does:** Verifies the caller is known and permitted.

**What it reads:** `request.context["caller_id"]`

**Config:**
```yaml
identity:
  require_caller: true
  allowed_callers:
    - finance_portal
    - hr_system
```

**Decision logic:**
1. If `require_caller: true` and `caller_id` is absent → `BLOCK`
2. If `allowed_callers` is non-empty and `caller_id` not in list → `BLOCK`
3. Otherwise → `PASS` with `enrichments: {"caller": "<caller_id>"}`

**Trace reason examples:**
- `"caller_id required but not present in context"`
- `"caller 'rogue_script' not in allowed_callers"`

**Note:** `caller_id` must come from your `context_fn`. The agent cannot set it via tool kwargs. An agent that can write its own `caller_id` into context defeats this layer entirely — see [Security](security.md#the-context-contract).

---

## L2 — Injection (`injection`)

**What it does:** Scans all string values in `params` and a nominated context field for prompt injection patterns.

**What it reads:** All `str` values in `request.params` + `request.context[context_field]` (default: `prompt_text`)

**Config:** No YAML config. Custom patterns can be passed at engine construction if building directly; the default set covers the most common injection forms.

**Default patterns (regex, case-insensitive):**
```
ignore (all )?(previous|prior|above) instructions
you (are|'re) now
disregard your | forget your
new persona | act as
pretend you have no | pretend you are
from now on you
your previous instructions
```

**Decision logic:** First pattern match in any scanned string → `BLOCK`. All strings are scanned before deciding.

**Coverage limits:** Only top-level `str` values in `params` are scanned. Non-string values (lists, dicts, integers) are not traversed. An injection string nested inside `params = {"messages": [{"role": "user", "content": "ignore all..."}]}` is invisible to this layer — the outer list is not a string and is skipped. If your tools receive structured inputs with user-controlled strings at any depth, consider flattening those strings into top-level params or scanning them explicitly before the tool call.

**Output scanning:** `engine.scan_output(outcome, request)` runs the same layer against the tool's return value after it fires. On a match, raises `PermissionError` with `"Output injection detected on '<resource>': ..."`.

**Trace reason example:**
- `"Injection pattern detected: 'ignore\\s+(all\\s+)?previous\\s+instructions'"`

---

## L4 — Memory (`memory`)

**What it does:** Deduplicates requests by a stable hash of the request's identity parameters. Blocks re-runs of the same logical operation within a TTL window.

**What it reads:** `request.params` (the fields named in `identity_params`), `request.resource`, `request.agent`

**Config:** Defined per scope entry, not at the top level:
```yaml
scope:
  - action: invoke
    resource: approve_expense
    dedup:
      identity_params: [expense_id]
      ttl_seconds: 86400
```

**Decision logic:**
1. Find the matching scope entry for this request.
2. If no `dedup` config on that entry → `PASS`.
3. Hash `{agent, resource, identity_params values}` with SHA-256.
4. Query the store for that hash with `expires_at > now`.
5. If found → `BLOCK`.
6. If not found → `PASS`. Hash is written in `post_execute` after the tool succeeds.

**Hash is written only on success.** If the tool raises, no hash is written and the request is safe to retry. This means the dedup window starts at tool completion, not at request time.

**Atomicity assumption:** This model assumes the tool is atomic — it either fully succeeds or the operation didn't happen. If a tool partially completes and then raises (e.g., sends an email then fails writing to the database), Zink treats it as "never ran" and will not block a retry. For non-atomic tools, do not rely on the memory layer alone to prevent double-execution.

**Persistence:** Hashes are stored in SQLite and survive process restarts. A new engine instance connected to the same database file will see hashes written by a previous instance.

**Trace reason example:**
- `"Duplicate request detected for 'approve_expense' — already processed within TTL window"`

---

## L6 — Policy (`policy`)

**What it does:** Evaluates business rules expressed as AST conditions, then checks rate limits.

**What it reads:** `request.to_eval_dict()` — the full request as `{agent, action, resource, params, context}`, traversable by dot-path in policy expressions.

**Config:**
```yaml
policies:
  - rule: business_hours
    when: "context.hour < 8 OR context.hour > 18"
    then: block
    reason: "Only permitted 8am–6pm"

rate_limits:
  - resource: approve_expense
    limit: 20
    window_seconds: 3600
```

**Decision logic:**
1. Walk policies in order. For each:
   - Evaluate the `when` AST condition against the request dict.
   - If condition met and `then: block` → `BLOCK` immediately.
   - If condition met and `then: flag` → accumulate flag, continue.
   - If condition met and `then: allow` → `PASS` immediately (short-circuit).
2. If any flags accumulated → `FLAG` with `enrichments: {"flags": [...]}`.
3. Check rate limits. For each matching resource limit, count calls in the current window. If `count >= limit` → `BLOCK`.

**Rate counter increments in `post_execute`** — only after tool success. Blocked calls do not increment the counter.

**Missing context fields** evaluate to `false` (lenient). A policy checking `context.hour` when hour is absent simply doesn't fire — it does not block or error.

**Field-vs-field comparison is not supported.** The right-hand side of a `when:` expression is always a literal frozen at config-parse time. Writing `params.patient_id in context.assigned_patients` stores the string `"context.assigned_patients"` as the expected value rather than resolving it at runtime. For runtime-resolved right-hand values, use scope `value_from:` constraints instead.

**Trace reason examples:**
- `"Expense approvals only permitted 8am–6pm"` (from policy `reason:`)
- `"Rate limit exceeded for 'approve_expense': 20/20 calls in window"`

---

## L9 — Scope (`scope`)

**What it does:** Verifies the requested action+resource pair is in the allowed list, then checks parameter constraints.

**What it reads:** `request.action`, `request.resource`, `request.params`, `request.context`

**Config:**
```yaml
denied:
  - action: invoke
    resource: wire_transfer

scope:
  - action: invoke
    resource: approve_expense
    constraints:
      - param: amount
        operator: lte
        value: 5000
```

**Decision logic:**
1. Check `denied` list. First matching entry → `BLOCK`. Glob patterns apply.
2. Find the first matching scope entry (by action + resource glob). If no match → `BLOCK`.
3. Evaluate constraints in order. First failure → `BLOCK`.

**Constraint value resolution:**
- `value:` — literal value from config.
- `value_from:` — dot-path resolved against `{"context": request.context, "params": request.params}` at runtime. If the path doesn't exist → `BLOCK` (fail-closed). Cannot be set alongside `value:`.

**Trace reason examples:**
- `"invoke on wire_transfer not in scope for expense_agent"` (not in scope)
- `"invoke for wire_transfer not within scope for expense_agent."` (denied)
- `"Param 'amount' failed constraint: lte 5000 (got 9999)"`
- `"Param 'patient_id': value_from 'context.allowed_patients' not resolvable (fail-closed)"`

---

## Layer trace

Every `ValidationResult` carries a `layer_trace` dict:

```python
{
  "identity": {"status": "pass",  "reason": "",        "enrichments": {"caller": "finance_portal"}},
  "injection": {"status": "pass", "reason": ""},
  "scope":     {"status": "block", "reason": "Param 'amount' failed constraint: lte 5000 (got 9999)"}
}
```

Only layers that ran appear in the trace. The blocking layer's reason is also surfaced as `result.reason` on the top-level `ValidationResult`.

---

## Adding a custom layer

Subclass `Layer` from `zink.layers.base`:

```python
from zink.layers.base import Layer
from zink.schemas import ValidationRequest, LayerResult, LayerStatus

class MyLayer(Layer):
    name = "my_layer"

    def evaluate(self, request: ValidationRequest) -> LayerResult:
        if some_condition(request):
            return LayerResult(status=LayerStatus.BLOCK, layer=self.name,
                               reason="blocked by my_layer")
        return LayerResult(status=LayerStatus.PASS, layer=self.name)
```

Custom layers are not yet loadable from YAML `default_layers` — you'd wire them directly into `ZinkEngine._layers` or extend the engine's `_build_layers` registry.
