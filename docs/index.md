# Zink Documentation

Zink is a governance middleware for autonomous AI agents. It wraps your agent's tools with a validation pipeline that runs before (and after) every tool call, enforcing identity checks, injection detection, deduplication, policy rules, rate limits, and scope constraints — and writing a tamper-evident audit trail regardless of outcome.

## The core idea

Every tool your agent can call is wrapped in a **governed closure**. The agent can't tell the difference — it sees the same function signature. But every invocation passes through the pipeline first:

```
agent calls tool
       │
       ▼
  governed()              ← Zink intercepts here
       │
       ├─► L1 Identity      is the caller allowed?
       ├─► L2 Injection      is input clean?
       ├─► L4 Memory         have we done this before?
       ├─► L6 Policy         do business rules permit this?
       ├─► L9 Scope          is this action in scope? params valid?
       │        │
       │      BLOCK ──────► PermissionError + audit row
       │
       ▼
  tool.invoke(**kwargs)   ← tool fires only if all layers pass
       │
       ├─► post_execute()   stateful write-back (dedup hash, rate counter)
       ├─► scan_output()    L2 on the return value
       └─► audit()          always — approved or blocked
```

If any gate layer returns `BLOCK`, the tool never fires, the reason is audited, and a `PermissionError` is raised to the caller.

## Two channels into every request

Every request carries two separate dicts:

| Channel | Field | Who writes it | What goes here |
|---|---|---|---|
| `params` | `request.params` | The agent (tool kwargs) | Tool arguments the LLM chose |
| `context` | `request.context` | Your `context_fn` | Caller identity, time, auth attributes |

The governed closure builds the `ValidationRequest`. The agent never constructs it directly, so it cannot inject into `context`. See [Security — the context contract](security.md#the-context-contract).

## Navigation

| Doc | What it covers |
|---|---|
| [Quickstart](quickstart.md) | Install and wrap your first tool in under 5 minutes |
| [Configuration](configuration.md) | Complete YAML reference for agent config files |
| [Layers](layers.md) | Each layer in depth — what it checks, what it reads, what it writes |
| [Security](security.md) | Trust model, fail-closed guarantees, audit chain, `value_from` contract |
| [API Reference](api-reference.md) | Python API — `Zink`, `ValidationRequest`, `ZinkStore`, `verify_chain` |
