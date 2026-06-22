from zink.schemas import AgentConfig, ValidationRequest, LayerResult, LayerStatus
from zink.layers.base import Layer
from fnmatch import fnmatch

class ScopeCheck(Layer):
    name = "scope"

    def __init__(self, agent_cfg: AgentConfig):
        self._scope = agent_cfg.scope
        self._denied = agent_cfg.denied

    def evaluate(self, request: ValidationRequest)-> LayerResult:
        """
        1. check if action in denied -> block (DENY FIRST)
        2. check scope
        """

        for entry in self._denied:
            if fnmatch(request.action, entry.action) and fnmatch(request.resource, entry.resource):
                return LayerResult(
                    status= LayerStatus.BLOCK,
                    layer= self.name,
                    reason= f"{request.action} for {request.resource} not within scope for {request.agent}."
                )
            
        for entry in self._scope:
            if fnmatch(request.action, entry.action) and fnmatch(request.resource, entry.resource):
                return self._check_constraints(request.params, request.context, entry.constraints)
            
        # rest not in scope

        return LayerResult(
            status= LayerStatus.BLOCK,
            layer = self.name,
            reason= f"{request.action} on {request.resource} not in scope for {request.agent}"
        )


    def _apply_operator(self, actual, operator: str, expected)-> bool:
        if operator == "eq":          return actual == expected
        if operator == "neq":         return actual != expected
        if operator == "gte":         return actual >= expected
        if operator == "gt":          return actual > expected
        if operator == "lte":         return actual <= expected
        if operator == "lt":          return actual < expected
        if operator == "contains":    return expected in actual
        if operator == "not_contains":return expected not in actual
        if operator == "in":          return actual in expected
        if operator == "not_in":      return actual not in expected
        if operator == "exists":      return actual is not None
        return False

    def _resolve_expected(self, c, root: dict):
        vf = getattr(c, "value_from", None)
        if not vf:
            return c.value
        cur = root
        for part in vf.split("."):
            cur = cur[part]
        return cur

    def _check_constraints(self, params: dict, context: dict, constraints: list)-> LayerResult:
        root = {"context": context or {}, "params": params or {}}
        for c in constraints:
            actual = params.get(c.param)
            try:
                expected = self._resolve_expected(c, root)
            except (KeyError, TypeError):
                return LayerResult(
                    status=LayerStatus.BLOCK,
                    layer=self.name,
                    reason=f"Param '{c.param}': value_from '{c.value_from}' not resolvable (fail-closed)"
                )
            if not self._apply_operator(actual, c.operator, expected):
                return LayerResult(
                    status=LayerStatus.BLOCK,
                    layer=self.name,
                    reason=f"Param '{c.param}' failed constraint: {c.operator} {expected!r} (got {actual!r})"
                )
        return LayerResult(status=LayerStatus.PASS, layer=self.name)

