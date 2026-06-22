# API Reference

---

## `Zink`

The top-level entry point. Holds one `ZinkStore` shared across all engines created from this instance.

```python
from zink import Zink

zink = Zink(config_dir=None, *, store_path=None)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `config_dir` | `str \| None` | `None` | Root directory for YAML configs. When set, `govern()` resolves `<agent_name>.yaml` automatically from `agents/<name>.yaml` or `<name>.yaml`. |
| `store_path` | `str \| None` | `$ZINK_STORE_PATH` or `"zink_store.db"` | Path to the SQLite file. Created if absent. |

---

### `Zink.govern()`

```python
zink.govern(
    agent_name: str,
    tools_or_config,
    context_fn: Callable[[], dict] | None = None,
    *,
    context: Callable[[], dict] | None = None,
    resource_name: str | None = None,
)
```

Two calling conventions:

**Decorator style** — `tools_or_config` is a config file path string. Returns a decorator.

```python
@zink.govern("my_agent", "configs/my_agent.yaml")
def my_tool(**kwargs): ...

# or with explicit resource name:
my_tool = zink.govern("my_agent", "configs/my_agent.yaml",
                       resource_name="ec2.launch_instance")(fn)
```

**List style** — `tools_or_config` is a list of callables or `BaseTool` objects. Requires `config_dir` to be set on the `Zink` instance. Returns a list of governed tools in the same order.

```python
governed = zink.govern("my_agent", [tool_a, tool_b], context=context_fn)
tool_a, tool_b = governed
```

| Parameter | Description |
|---|---|
| `agent_name` | Identifies the agent. Must match the `agent:` field in the YAML config. |
| `tools_or_config` | Config path string (decorator style) or list of tools (list style). |
| `context_fn` / `context` | Callable returning a `dict`. Called on every tool invocation. Either name is accepted; `context_fn` takes precedence. |
| `resource_name` | Override the resource name in the `ValidationRequest`. Defaults to `fn.__name__`. |

**Resource name collisions:** If two different tools share the same Python function name (e.g. both are called `run` or `invoke`), they map to the same resource identity and match the same scope entry. When wrapping a list of tools, prefer explicit `resource_name` or ensure function names are unique and match the `resource:` fields in your config.

**Kwargs only:** The governed closure captures `**kwargs` as `params`. Positional arguments (`*args`) are forwarded to the tool but are not inspected by any layer — scope constraints, injection scanning, and dedup hashing are blind to them. Tools governed by Zink should be called with keyword arguments only.

**`context_fn` must be synchronous.** It is called inline on every tool invocation. Async context builders (e.g. looking up session data from an async store) are not supported in the current closure. Run async setup before wrapping tools and close over the results.

---

### `Zink.govern_langchain()`

```python
zink.govern_langchain(
    agent_name: str,
    config_path: str,
    tool: BaseTool,
    context_fn: Callable[[], dict] | None = None,
) -> GovernedTool
```

Wraps a single LangChain `BaseTool`. Returns a `GovernedTool` that preserves `.name`, `.description`, and `.args_schema`. On a block, returns `{"zink_blocked": True, "reason": "..."}` instead of raising.

---

## `ValidationRequest`

```python
from zink.schemas import ValidationRequest

request = ValidationRequest(
    agent    = "my_agent",
    action   = "invoke",
    resource = "approve_expense",
    params   = {"amount": 500, "category": "travel"},
    context  = {"caller_id": "finance_portal", "hour": 10},
)
```

A frozen dataclass. Produced by the governed closure — you rarely construct it manually.

| Field | Type | Description |
|---|---|---|
| `agent` | `str` | Agent identifier. |
| `action` | `str` | Action type. Always `"invoke"` for tool calls; `"output_scan"` for output scanning. |
| `resource` | `str` | Tool/resource name. |
| `params` | `dict[str, Any]` | Tool call arguments. Written by the agent. |
| `context` | `dict[str, Any]` | Runtime attributes. Written by `context_fn`. |

`.to_eval_dict()` returns a flat dict for use in policy condition evaluation:
```python
{"agent": ..., "action": ..., "resource": ..., "params": {...}, "context": {...}}
```

---

## `ValidationResult`

```python
from zink.schemas import ValidationResult

result.approval      # bool — True = approved, False = blocked
result.reason        # str  — human-readable reason (from the blocking layer)
result.layer_trace   # dict — {layer_name: {"status": ..., "reason": ..., "enrichments": ...}}
```

Produced by `engine.validate()`. The `layer_trace` contains one entry per layer that ran. Layers after the first `BLOCK` are absent.

---

## `LayerResult`

```python
from zink.schemas import LayerResult, LayerStatus

result = LayerResult(
    status      = LayerStatus.BLOCK,
    layer       = "scope",
    reason      = "Param 'amount' failed constraint: lte 5000 (got 9999)",
    enrichments = {},
)

result.blocked   # True if status == BLOCK
result.flagged   # True if status == FLAG
```

---

## `ZinkEngine`

Low-level engine. Instantiated internally by `Zink.govern()`. You can use it directly when you don't want the `Zink` convenience wrapper.

```python
from zink.engine import ZinkEngine
from zink.store.sqlite import ZinkStore
from zink.config.loader import load_agent_config

cfg    = load_agent_config("configs/my_agent.yaml")
store  = ZinkStore("zink.db")
engine = ZinkEngine(cfg, store)

result = engine.validate(request)           # run pipeline
engine.post_execute_all(request, outcome)   # write-back after tool fires
engine.scan_output(outcome, request)        # L2 on return value
engine.audit(request, result, outcome)      # always write audit row
```

`post_execute_all` catches exceptions from individual layers and emits `RuntimeWarning` — it will not crash a successful tool call.

---

## `ZinkStore`

SQLite backing store. Thread-safe via a write lock. WAL mode for concurrent reads.

```python
from zink.store.sqlite import ZinkStore

store = ZinkStore("zink.db")   # path created if absent
store = ZinkStore()            # uses $ZINK_STORE_PATH or "zink_store.db"
```

You rarely call store methods directly. The exception is raw queries for testing or tooling:

```python
rows = store.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 10")
row  = store.query_one("SELECT count FROM rate_counters WHERE agent = ?", ("my_agent",))
store.execute("INSERT INTO ...", (values,))
```

### Schema

| Table | Purpose |
|---|---|
| `audit_log` | Hash-chained record of every validation (approved and blocked). |
| `dedup_hashes` | SHA-256 fingerprints written by MemoryGuard after tool success. |
| `rate_counters` | Per-agent, per-resource call counts in fixed-width time windows. |
| `behavioral` | Reserved for future behavioral baseline tracking. |

---

## `AuditLogger`

```python
from zink.audit.logger import AuditLogger

logger = AuditLogger(store)

# Write a row (called automatically by engine.audit()):
logger.write(request, result, outcome)

# Verify the chain is intact:
ok = logger.verify_chain()   # True = no tampering detected
```

`verify_chain()` reads every row in insertion order, recomputes each `entry_hash` from stored fields, and returns `False` the moment any hash doesn't match. It detects row modification, row deletion, and reordering.

**Params must be JSON-serializable.** `AuditLogger.write` calls `json.dumps(request.params)`. Tool arguments containing non-serializable types (numpy arrays, dataclasses, `datetime` objects, custom classes) will cause the audit write to raise `TypeError` — after the tool has already fired. If your tools receive non-serializable arguments, convert them to serializable forms (strings, dicts, lists) before the governed call, or provide a custom JSON encoder.

---

## `load_agent_config()`

```python
from zink.config.loader import load_agent_config

cfg = load_agent_config("path/to/config.yaml")
# returns: AgentConfig (validated Pydantic model)
```

Handles `extends` resolution (up to depth 5, circular detection), policy `when:` string parsing, and full Pydantic validation. Raises `ConfigError` on invalid YAML structure or schema violations; `SyntaxError` on invalid `when:` expressions.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ZINK_STORE_PATH` | `"zink_store.db"` | Path to the SQLite store when not passed explicitly. |
