# Zink

Deterministic runtime governance for AI agents.

---

## What is this

Zink is a middleware library that sits between an AI agent and the tools it can call. Every time an agent tries to do something, Zink checks whether that action is allowed before it executes. If it's allowed, the tool fires. If it isn't, it's blocked with a clear reason and logged.

No changes to your agent code. No retraining. One integration point.

```python
from zink import Zink

zink = Zink()

# your existing tool, completely unchanged
def approve_expense(expense_id: str, amount: float, category: str) -> dict:
    return db.approve(expense_id, amount)

# wrap it
approve_expense = zink.govern(
    "expense_agent",
    "configs/expense_agent.yaml",
    context_fn=lambda: {"caller_id": "expense_system", "hour": datetime.now().hour}
)(approve_expense)

# now governed. scope enforced. audit logged. that's it.
```

---

## Why it exists

Zink is pre-execution: the agent decides what to do, Zink decides if it's allowed before anything touches a real system. Same input, same config, same result.

---

## How it works

You define what each agent can do in a YAML config file. Zink loads that config, wraps your tools, and enforces the rules on every call.

```yaml
agent: expense_agent
trust_level: medium

default_layers:
  - l1_identity
  - l2_injection
  - l4_memory
  - l6_policy
  - l9_scope

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

denied:
  - action: invoke
    resource: wire_transfer

policies:
  - rule: business_hours
    when: "context.hour < 8 OR context.hour > 18"
    then: block
    reason: "Expense approvals only permitted 8am to 6pm"

rate_limits:
  - resource: approve_expense
    limit: 20
    window_seconds: 3600
```

Every tool call goes through a configurable pipeline of layers. Each layer can block the call immediately or pass it to the next one.

```
L1  Identity      is the caller known and permitted?
L2  Injection     does the input contain attack patterns?
L4  Memory        has this exact request been processed before?
L6  Policy        do business rules and rate limits allow this?
L9  Scope         is this action within the agent's declared permissions?
                  with param constraint validation
        approved
tool fires
        done
post_execute      L4 writes dedup hash, L6 increments rate counter
output scanner    L2 on the return value too
audit             cryptographic hash-chained entry written to SQLite
```

Every decision, blocked or approved, is written to a hash-chained audit log. Tamper with any entry and the chain breaks at that point forward.

---

## Install

```bash
pip install zink
```

With LangChain support:

```bash
pip install "zink[langchain]"
```

For running the examples:

```bash
pip install "zink[examples]"
```

---

## Layers

| Layer | What it does |
|-------|-------------|
| L1 Identity | Verifies caller identity against an allowlist |
| L2 Injection | Detects prompt injection patterns in inputs and outputs |
| L4 Memory | Blocks duplicate requests within a configurable TTL |
| L6 Policy | Enforces business rules via a condition evaluator and rate limits |
| L9 Scope | Enforces the agent's declared permissions and param constraints |

Every layer is opt-in. Start with two. Add more when you need them.

---

## Audit log

Every call writes to a SQLite-backed audit log. Entries are hash-chained so any tampering is detectable.

```python
from zink.audit.logger import AuditLogger
from zink.store.sqlite import ZinkStore

store = ZinkStore("zink_store.db")
logger = AuditLogger(store)

print(logger.verify_chain())  # True if untampered
```

The log persists across process restarts. Rate counters and dedup hashes do too.

---

## Examples

Two fully worked examples are in `examples/`:

**Expense approval agent** covers approval limits, duplicate submissions, out-of-scope payroll access, prompt injection in description fields, business hours enforcement, and rate limiting.

**AWS infrastructure agent** covers production environment blocks, oversized instance types, denied IAM operations, duplicate launches, and prompt injection in resource names.

Run either from the project root:

```bash
python -m examples.expense_agent.agent
python -m examples.infra_agent.agent
```

Or try the interactive demo at [https://zink-demo-ixc1ndfk6-avishi-sreenidhis-projects.vercel.app/]

---

## Design decisions

**Deterministic.** No ML in the governance pipeline. Same input, same config, same result. Reproducible and auditable.

**Framework agnostic.** Works with LangGraph or raw Python. Zink governs tool calls, not frameworks. CrewAI and AutoGen implementations are planned.

**Domain agnostic.** Same engine governs HR workflows, cloud infrastructure, financial transactions, and healthcare systems. Only the config changes.

**Zero agent changes.** Tools are wrapped at setup time and look identical to the original. The agent never knows Zink is there.

**Opt-in complexity.** Start with scope enforcement only. Add identity, memory, policy as you need them.

---

## License

Apache-2.0

---

Built by Avishi. Contributions welcome.