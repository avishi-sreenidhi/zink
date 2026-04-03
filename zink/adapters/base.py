# SPDX-License-Identifier: Apache-2.0
"""
zink/adapters/base.py
---------------------
Framework-agnostic governed callable.
Wraps any tool with Zink enforcement.

Flow:
    1. Build ValidationRequest from params + context
    2. engine.validate(request)         — pre-execution gates
    3. tool.invoke(params)              — tool fires if approved
    4. engine.post_execute(request, outcome)  — stateful write-back
    5. output_scanner.scan(outcome)     — L2 on return value
    6. audit_logger.write(...)          — always, Merkle-chained
    7. return outcome to agent
"""
import json
import os
from datetime import datetime
from zink.engine import ZinkEngine
from zink.schemas import ValidationRequest

_TRACE_LOG = os.getenv("ZINK_TRACE_LOG", "zink_trace.jsonl")

def _append_trace(agent: str, resource: str, result) -> None:
    entry = {
        "ts":       datetime.now().isoformat(),
        "agent":    agent,
        "resource": resource,
        "approved": result.approval,
        "reason":   result.reason,
        "layers":   result.layer_trace,
    }
    with open(_TRACE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def create_governed_callable(tool, engine: ZinkEngine, agent_name: str, context_fn=None):
    """
    Wraps any callable with Zink enforcement.
    Built once in __init__, called many times.
    Returns a closure.
    """

    def governed(**kwargs):
        context = context_fn() if context_fn else {}
        request = ValidationRequest(
            agent = agent_name,
            action= "invoke",
            resource= tool.name,
            params= kwargs,
            context= context
        )

        result = engine.validate(request)
        _append_trace(agent_name, tool.name, result)
        if result.approval:
            return tool.invoke(kwargs)
        raise PermissionError(result.reason)

    #return a function that remembers its context.
    return governed

def create_governed_fn(fn, engine:ZinkEngine, agent_name:str, context_fn = None):
    """Wraps a plain python callable with Zink"""
    def governed(**kwargs):
        context = context_fn() if context_fn else {}
        request = ValidationRequest(
            agent = agent_name,
            action="invoke",
            resource= fn.__name__,
            params=kwargs,
            context= context
        )

        result = engine.validate(request)
        _append_trace(agent_name, fn.__name__, result)
        if result.approval:
            return fn(**kwargs)
        raise PermissionError(result.reason)
    
    governed.__name__ = fn.__name__
    return governed
