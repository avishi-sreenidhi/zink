# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/l1_identity.py
--------------------------
L1 Identity — first gate layer.

Extracts caller_id from request context.
Checks against allowed_callers list.
Enriches trace with caller identity for audit log.

Config:
    identity:
      require_caller: true
      allowed_callers:
        - "hr_system"
        - "recruiter_portal"

If no identity config: layer passes everything.
If require_caller and no caller in context: BLOCK.
If allowed_callers set and caller not in list: BLOCK.
Otherwise: PASS with caller enrichment.
"""

from zink.schemas import AgentConfig, ValidationRequest, LayerResult, LayerStatus
from zink.layers.base import Layer


class IdentityCheck(Layer):
    name = "l1_identity"
    phase = 1

    def __init__(self, agent_cfg: AgentConfig) -> None:
        identity = getattr(agent_cfg, "identity", None)
        self._require_caller = getattr(identity, "require_caller", False)
        self._allowed_callers: list[str] = getattr(identity, "allowed_callers", [])

    def evaluate(self, request: ValidationRequest) -> LayerResult:
        caller_id = request.context.get("caller_id")

        if self._require_caller and not caller_id:
            return LayerResult(
                status=LayerStatus.BLOCK,
                layer=self.name,
                reason="caller_id required but not present in context",
            )

        if self._allowed_callers and caller_id not in self._allowed_callers:
            return LayerResult(
                status=LayerStatus.BLOCK,
                layer=self.name,
                reason=(
                    f"caller '{caller_id}' not in allowed_callers"
                    if caller_id
                    else "caller_id missing and allowed_callers is set"
                ),
            )

        return LayerResult(
            status=LayerStatus.PASS,
            layer=self.name,
            enrichments={"caller": caller_id} if caller_id else {},
        )