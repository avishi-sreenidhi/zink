# Wrapping LangChain Tools with Zink

Zink wraps LangChain tools at the point where your agent calls them.
Every call goes through the engine — scope, injection, policy — before the real tool executes.
The agent code sees no difference: the governed tool has the same `.name`, `.description`, and `.args_schema` as the original.

---

## Prerequisites

Your tools must be LangChain `BaseTool` instances before Zink can wrap them.
There are two ways to get there depending on how your tools are structured.

---

## Pattern 1 — Standalone `@tool` functions

Use this when your tools don't share state (no LLM client, no DB connection on `self`).

```python
from langchain_core.tools import tool

@tool
def schedule_interview(candidate_email: str, manager_email: str, date: str, time: str) -> dict:
    """Schedule interview on calendar and return event_id."""
    ...
```

`@tool` produces a `StructuredTool` (a `BaseTool` subclass) directly.
The function name becomes `tool.name`. The docstring becomes `tool.description`.
Type hints become `tool.args_schema` automatically.

If your agent wraps them in a class for consistency:

```python
class SchedulingTools:
    def __init__(self):
        self.schedule_interview = schedule_interview   # already a BaseTool
        self.send_invite        = send_invite
```

---

## Pattern 2 — Class methods with `StructuredTool.from_function()`

Use this when tools share instance state — an LLM client, an API manager, etc.

```python
from langchain_core.tools import StructuredTool

class ScreeningTools:
    def __init__(self):
        self.llm   = ChatGoogleGenerativeAI(...)
        self.excel = ExcelManager()

        # Private implementation methods
        # Public attributes are the StructuredTool wrappers
        self.extract_resume = StructuredTool.from_function(
            func=self._extract_resume,
            name="extract_resume",
            description="Extract structured data from resume text."
        )
        self.score_candidate = StructuredTool.from_function(
            func=self._score_candidate,
            name="score_candidate",
            description="Score a candidate based on extracted resume data."
        )

    def _extract_resume(self, resume_text: str) -> dict:
        # uses self.llm — that's why it's a method, not a standalone function
        ...

    def _score_candidate(self, name: str, years_experience: int,
                         skills: list[str], education: str) -> dict:
        ...
```

`StructuredTool.from_function()` reads the type hints of `func` to build `args_schema`.
The `name` and `description` you pass override whatever the function has.

> **Rule of thumb:** if the function needs `self`, use `StructuredTool.from_function()`.
> If it doesn't, use `@tool`.

---

## Wiring governance in your agent

Once your tools are `BaseTool` instances, call `zink.govern()` in `__init__` —
**before** `_build_graph()` so every node picks up the governed versions.

```python
from zink import Zink
from datetime import datetime

class ScreeningAgent:
    def __init__(self):
        self.tools = ScreeningTools()

        # 1. Govern
        zink = Zink("configs/")
        governed = zink.govern(
            "screening_agent",
            [
                self.tools.extract_resume,
                self.tools.score_candidate,
                self.tools.log_to_excel_tool,
                self.tools.send_email_tool,
            ],
            context=lambda: {"hour": datetime.now().hour}
        )

        # 2. Replace originals
        self.tools.extract_resume    = governed[0]
        self.tools.score_candidate   = governed[1]
        self.tools.log_to_excel_tool = governed[2]
        self.tools.send_email_tool   = governed[3]

        # 3. Build graph — nodes see governed tools
        self.graph = self._build_graph()
```

`zink.govern()` returns a list of `GovernedTool` instances in the same order you passed them.
Each `GovernedTool` is itself a `BaseTool`, so the rest of LangGraph doesn't notice the swap.

### The `context` parameter

`context` is a zero-argument callable evaluated fresh on every tool call.
Use it for anything that changes at runtime — time of day, user session, request metadata.

```python
context=lambda: {"hour": datetime.now().hour}
```

The returned dict is available as `context.*` in your YAML policy rules:

```yaml
- rule: business_hours
  when: "context.hour < 9 OR context.hour > 18"
  then: block
  reason: "HR actions restricted to business hours"
```

Omit `context` entirely if your policies don't need runtime values.

---

## Calling governed tools in nodes

`GovernedTool` is a `BaseTool`. Call it with `.invoke({...})`.

```python
# extract
result = self.tools.extract_resume.invoke({"resume_text": state["resume_text"]})

# score
result = self.tools.score_candidate.invoke({
    "name": name,
    "years_experience": years_experience,
    "skills": skills,
    "education": education
})

# log / email
self.tools.log_to_excel_tool.invoke({
    "candidate_id": candidate_id,
    "name": name,
    "email": email,
    "score": score,
    "decision": "approve"
})
```

Do not call the tool as a plain function (`self.tools.extract_resume(resume_text=...)`).
`BaseTool.__call__` has a different signature — `.invoke()` is the correct entry point.

---

## What happens at call time

```
node calls .invoke({...})
    └── GovernedTool._run(**kwargs)
            └── ZinkEngine.validate(ValidationRequest)
                    ├── L2  InjectionDetect  — scans params for prompt injection
                    └── L9  ScopeCheck       — checks allowed/denied resources + constraints
                            ├── BLOCK → raises PermissionError(reason)
                            └── PASS  → original StructuredTool.invoke(kwargs)
```

`ValidationRequest` is built automatically from the tool name, the kwargs dict, and the context.
You never construct it manually.

---

## Config files

Zink expects this directory layout:

```
configs/
├── hr.zink.yaml              # domain-level defaults and global denied list
└── agents/
    └── screening_agent.yaml  # per-agent scope, constraints, layers
```

The domain config filename must match `*.zink.yaml`. There can only be one per directory.

**Domain config** (`hr.zink.yaml`) — sets defaults inherited by all agents:

```yaml
domain: "HR"
version: "0.1"

defaults:
  trust_level: low
  default_layers: [l2_injection, l9_scope]
  decision_on_unknowns: block

denied:
  - action: invoke
    resource: payment.*

policies:
  - rule: business_hours
    when: "context.hour < 9 OR context.hour > 18"
    then: block
    reason: "HR actions restricted to business hours"
```

**Agent config** (`agents/screening_agent.yaml`) — declares exactly what this agent may call:

```yaml
agent: screening_agent
extends: ../hr.zink.yaml
role: screener
trust_level: high
default_layers: [l2_injection, l9_scope]

scope:
  - action: invoke
    resource: extract_resume

  - action: invoke
    resource: score_candidate
    constraints:
      - param: years_experience
        operator: gte
        value: 0
      - param: name
        operator: exists
        value: True

  - action: invoke
    resource: log_to_excel_tool

  - action: invoke
    resource: send_email_tool

denied:
  - action: invoke
    resource: schedule_interview
  - action: invoke
    resource: generate_offer
```

The `resource` name in the YAML must match `tool.name` exactly — the string passed to
`@tool` (the function name) or the `name=` argument in `StructuredTool.from_function()`.

---

## Checklist

- [ ] Every tool is a `BaseTool` instance (`@tool` or `StructuredTool.from_function()`)
- [ ] `tool.name` matches the `resource:` value in the agent YAML
- [ ] `zink.govern()` is called before `_build_graph()`
- [ ] All call sites use `.invoke({...})` not direct function calls
- [ ] Domain config (`*.zink.yaml`) exists in the configs directory
- [ ] Agent config exists at `configs/agents/<agent_name>.yaml`
