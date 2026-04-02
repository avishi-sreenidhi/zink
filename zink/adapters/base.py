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
