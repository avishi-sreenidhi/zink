# SPDX-License-Identifier: Apache-2.0
"""
zink/adapters/base.py
---------------------
Framework-agnostic governed callable.

Wraps any callable with Zink enforcement.
Returns a plain Python callable — no framework dependency.

Flow:
    1. Build ValidationRequest
    2. engine.validate()          pre-execution gates
    3. If blocked: audit, raise PermissionError
    4. tool fires
    5. engine.post_execute()      stateful write-back
    6. engine.scan_output()       L2 on return value
    7. engine.audit()             always, Merkle-chained
    8. return outcome
"""
from typing import Any, Callable
from zink.schemas import ValidationRequest
from zink.engine import ZinkEngine

def create_governed_callable(
        fn: Callable,
        engine: ZinkEngine,
        agent_name: str,
        resource_name:str,
        context_fn: Callable[[], dict] | None = None,
)-> Callable:
    """
    Closure over: fn, engine, agent_name, resource_name, context_fn.
    These four names are captured at creation time.
    The inner function references them on every call.
    """
    def governed(*args, **kwargs):
        # build context every call
        context = context_fn() if context_fn else {}

        request = ValidationRequest(
            agent= agent_name,
            action= "invoke",
            resource=resource_name,
            params = kwargs,
            context= context,
        )
        #pre execution
        result = engine.validate(request)

        if not result.approval:
            engine.audit(request,result,outcome=None)
            raise PermissionError(result.reason)
        
        #tool fires
        outcome = fn(*args, **kwargs)

        # post-execution write-back
        engine.post_execute_all(request, outcome)

        # output scan
        engine.scan_output(outcome, request)

        # audit — always
        engine.audit(request, result, outcome)

        return outcome

    return governed







