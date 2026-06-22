# Configuration Reference

Every agent is governed by a single YAML file. The file is loaded once at startup and parsed into a validated `AgentConfig`. Policy `when:` expressions are compiled to an AST at load time — there is no string evaluation at request time.

---

## Top-level fields

```yaml
agent: my_agent           # required. snake_case identifier.
role: data_assistant      # optional. Free-text label for audit logs.
trust_level: low          # low | medium | high. Default: low.

default_layers:           # ordered list of layers to run on every request.
  - identity
  - injection
  - scope
  - policy
  - memory
```

`default_layers` controls both which layers run and their order. First `BLOCK` wins and the pipeline exits early — layers after the blocking one are not evaluated and do not appear in the trace.

Available layer names: `identity`, `injection`, `scope`, `policy`, `memory`.

---

## `identity`

Controls caller authentication.

```yaml
identity:
  require_caller: true          # if true, block when caller_id absent from context
  allowed_callers:              # if set, block any caller_id not in this list
    - hr_system
    - recruiter_portal
```

`caller_id` is read from `request.context["caller_id"]`. It must be set by your `context_fn` — the agent cannot supply it via tool kwargs. If `allowed_callers` is empty and `require_caller` is false, the layer passes everything.

---

## `denied`

Absolute blocklist evaluated before `scope`. No constraints, no exceptions.

```yaml
denied:
  - action: invoke
    resource: wire_transfer
  - action: invoke
    resource: iam.create_role
```

`action` and `resource` support glob patterns (`*`, `?`). A request matching any denied entry is blocked immediately, even if it would otherwise match a `scope` entry.

---

## `scope`

Allowlist of permitted actions. A request not matching any entry is blocked.

```yaml
scope:
  - action: invoke
    resource: approve_expense
    constraints:
      - param: amount
        operator: lte
        value: 5000
      - param: category
        operator: in
        value: [travel, meals, equipment, software]
    dedup:
      identity_params: [expense_id]
      ttl_seconds: 86400
```

**`param:` is a top-level key lookup.** Constraints address tool kwargs by name at the top level of `params`. A nested value like `params = {"body": {"amount": 500}}` cannot be reached with `param: amount` — you would need `param: body` and then the constraint evaluates against the entire sub-dict. Design tools to expose governed values as top-level kwargs.

### Constraint operators

| Operator | Meaning | Notes |
|---|---|---|
| `eq` | `==` | |
| `neq` | `!=` | |
| `gt` | `>` | numeric |
| `gte` | `>=` | numeric |
| `lt` | `<` | numeric |
| `lte` | `<=` | numeric |
| `in` | `actual in expected` | expected must be a list |
| `not_in` | `actual not in expected` | expected must be a list |
| `contains` | `expected in actual` | actual must be a collection |
| `not_contains` | `expected not in actual` | actual must be a collection |
| `exists` | `actual is not None` | value field is ignored |

### Static vs. context-resolved constraint values

By default, `value:` is a literal written into the config:

```yaml
constraints:
  - param: patient_id
    operator: in
    value: [P001, P002, P003]      # same list for every caller
```

Use `value_from:` to resolve the expected value from `request.context` at runtime:

```yaml
constraints:
  - param: patient_id
    operator: in
    value_from: context.allowed_patients   # resolved per-caller from context
```

`value_from` is a dot-path into `{"context": request.context, "params": request.params}`. If the path does not exist, the constraint **blocks (fail-closed)** — it never passes on a missing value.

**Security note:** `value_from` is safe only when `context` is populated by a trusted layer outside the agent's reach. See [Security — value_from contract](security.md#value_from-contract).

### Deduplication (`dedup`)

```yaml
dedup:
  identity_params: [expense_id]   # params that uniquely identify this logical request
  ttl_seconds: 86400              # how long to remember. Default: 86400 (24h)
```

The memory layer hashes `(agent, resource, identity_params values)` and blocks if the same hash was seen within the TTL. The hash is written **after** the tool succeeds — if the tool raises, no hash is written and the request is safe to retry.

---

## `policies`

Business rules evaluated as an AST. Parsed at config load, not at request time.

```yaml
policies:
  - rule: business_hours
    when: "context.hour < 8 OR context.hour > 18"
    then: block
    reason: "Expense approvals only permitted 8am–6pm"

  - rule: flag_large_amount
    when: "params.amount > 2000"
    then: flag
    reason: "Large expense flagged for review"

  - rule: vip_always_allowed
    when: "context.role == 'vip'"
    then: allow
    reason: "VIP callers bypass business-hours restriction"
```

`then` values:
- `block` — first matching block wins, pipeline exits
- `flag` — logged in the trace, pipeline continues
- `allow` — short-circuit pass, no further policies evaluated

Policies run in order. All `flag` conditions accumulate before any verdict.

### Policy expression grammar

Fields use dot notation to traverse the request: `context.hour`, `params.amount`, `agent`, `action`, `resource`.

Operators: `== != < > <= >= in not_in contains not_contains matches not_matches`

Logic: `AND`, `OR`, `NOT` (case-insensitive). Precedence: `NOT` > `AND` > `OR`.

```
context.hour < 8 OR context.hour > 18
params.amount > 1000 AND context.weekday >= 5
NOT context.role == "admin"
context.region in [us-east-1, us-west-2]
```

Missing fields evaluate to `false` (lenient mode) — a missing `context.hour` means the business-hours condition is not met, not an error.

---

## `rate_limits`

Sliding-window call limits per resource.

```yaml
rate_limits:
  - resource: approve_expense
    limit: 20
    window_seconds: 3600     # default: 3600
```

The counter increments in `post_execute` — only after the tool succeeds. Blocked calls do not count toward the limit. Window boundaries are fixed to `floor(now / window_seconds) * window_seconds`, so all agents share the same window ticks.

---

## Config inheritance (`extends`)

An agent config can inherit from a parent:

```yaml
# agents/junior_analyst.yaml
agent: junior_analyst
extends: ../base_analyst.yaml

scope:
  - action: invoke
    resource: read_report     # only this scope; parent's scope is replaced
```

Merge rules:
- `scope` — child's list completely replaces parent's
- `denied` — union (deduped by action+resource pair)
- `policies` — parent policies first, then child policies appended. A parent policy with `final: true` prevents a child from adding a policy with the same `rule` name
- `default_layers` — child wins if set, otherwise parent's
- `identity` — child wins if explicitly set, otherwise parent's
- `rate_limits` — child wins if set, otherwise parent's
- `role`, `trust_level` — child wins if set

Maximum extends depth: 5. Circular extends are detected and rejected at load time.

---

## Full example

```yaml
agent: expense_agent
role: expense_approver
trust_level: medium

default_layers:
  - identity
  - injection
  - scope
  - policy
  - memory

identity:
  require_caller: true
  allowed_callers:
    - expense_system
    - hr_portal

denied:
  - action: invoke
    resource: wire_transfer
  - action: invoke
    resource: access_payroll

scope:
  - action: invoke
    resource: approve_expense
    constraints:
      - param: amount
        operator: lte
        value: 5000
      - param: category
        operator: in
        value: [travel, meals, equipment, software, training]
    dedup:
      identity_params: [expense_id]
      ttl_seconds: 86400

  - action: invoke
    resource: reject_expense
    constraints:
      - param: expense_id
        operator: exists
        value: ~

policies:
  - rule: business_hours
    when: "context.hour < 8 OR context.hour > 18"
    then: block
    reason: "Expense approvals only permitted 8am–6pm"

  - rule: weekend_block
    when: "context.weekday >= 5"
    then: block
    reason: "Expense approvals not permitted on weekends"

rate_limits:
  - resource: approve_expense
    limit: 20
    window_seconds: 3600
```
