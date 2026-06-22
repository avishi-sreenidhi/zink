# Quickstart

## Install

```bash
pip install zink
# or from source:
pip install -e .
```

Zink depends on `pydantic`, `pyparsing`, and `pyyaml`. LangChain support requires `langchain-core` but is imported lazily — it's not a hard dependency.

---

## 1. Write a config file

Create `configs/my_agent.yaml`:

```yaml
agent: my_agent
role: data_assistant
trust_level: low

default_layers:
  - injection
  - scope

scope:
  - action: invoke
    resource: fetch_records
    constraints:
      - param: limit
        operator: lte
        value: 100
```

This config allows `fetch_records` calls where `limit ≤ 100`, and blocks anything that looks like a prompt injection.

---

## 2. Wrap a plain Python tool

```python
from zink import Zink

zink = Zink(store_path="zink.db")

@zink.govern("my_agent", "configs/my_agent.yaml")
def fetch_records(query: str, limit: int) -> list:
    ...

# Or equivalently:
fetch_records = zink.govern("my_agent", "configs/my_agent.yaml")(original_fn)
```

Calling `fetch_records(query="SELECT *", limit=50)` now passes through the pipeline. Calling it with `limit=200` raises `PermissionError`.

---

## 3. Wrap multiple tools at once

When you have several tools under the same agent config, pass a list:

```python
zink = Zink("configs/")   # config_dir: resolves my_agent.yaml from agent name

governed = zink.govern("my_agent", [tool_a, tool_b, tool_c])
tool_a, tool_b, tool_c = governed
```

All three share one `ZinkEngine` and one SQLite store — dedup hashes and rate counters are shared across tools as you'd expect.

---

## 4. Supply runtime context

Context carries information your `context_fn` knows but the agent doesn't: caller identity, current time, session attributes. It's called fresh on every tool invocation.

```python
import datetime

context_fn = lambda: {
    "caller_id": session.user_id,        # from your auth layer
    "hour":      datetime.now().hour,
    "role":      session.role,
}

governed = zink.govern("my_agent", [tool_a, tool_b], context=context_fn)
```

**The agent cannot influence context.** The closure captures `context_fn` at wrap time and calls it itself — the agent only supplies tool kwargs (which become `params`). See [Security](security.md#the-context-contract).

---

## 5. LangChain / LangGraph

```python
from langchain_core.tools import tool as lc_tool

@lc_tool
def fetch_records(query: str, limit: int) -> list:
    """Fetch database records."""
    ...

# Option A — single tool, explicit config path
governed_tool = zink.govern_langchain("my_agent", "configs/my_agent.yaml", fetch_records)

# Option B — list of LangChain tools via govern()
governed = zink.govern("my_agent", [fetch_records, other_tool], context=context_fn)
```

`GovernedTool` preserves `.name`, `.description`, and `.args_schema` exactly. The agent graph sees no structural difference. On a block, instead of raising (which would crash the graph), `GovernedTool._run` returns `{"zink_blocked": True, "reason": "..."}` — you must check for this in your node logic. If you don't, the agent receives the block dict as a normal tool result and will continue acting on it.

```python
def my_node(state):
    result = tools.fetch_records.invoke({"query": "...", "limit": 50})
    if isinstance(result, dict) and result.get("zink_blocked"):
        # handle the block — log it, return an error state, stop the graph
        return {**state, "error": result["reason"]}
    # normal path
    ...
```

---

## What happens on a block

For plain callables:
```
PermissionError: Param 'limit' failed constraint: lte 100 (got 200)
```

For LangChain tools:
```python
{"zink_blocked": True, "reason": "Param 'limit' failed constraint: lte 100 (got 200)"}
```

Either way, an audit row is written to the SQLite store before the error propagates.

---

## Verify the audit chain

```python
engine = zink._store   # or ZinkStore("zink.db") directly

from zink.audit.logger import AuditLogger
logger = AuditLogger(engine)
ok = logger.verify_chain()   # True if unbroken, False if any row was tampered
```

See [Security — audit chain](security.md#audit-chain).
