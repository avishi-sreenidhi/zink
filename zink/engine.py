# SPDX-License-Identifier: Apache-2.0
"""
zink/engine.py
--------------
Orchestrates the validation pipeline.

Holds:
    agent_cfg       resolved AgentConfig
    store           ZinkStore, shared by all stateful layers
    layers          ordered list of instantiated Layer objects
    output_scanner  InjectionDetector instance, reused for output scanning
    audit_logger    AuditLogger, independent of pipeline
"""

import json
from typing import Any

from zink.schemas import AgentConfig, ValidationRequest, ValidationResult, build_result
from zink.store.sqlite import ZinkStore
from zink.audit.logger import AuditLogger
from zink.layers.base import Layer
from zink.layers.l2_injection import InjectionDetect
from zink.layers.l9_scope import ScopeCheck


class ZinkEngine:

    def __init__(self, agent_cfg: AgentConfig, store: ZinkStore) -> None:
        self._cfg = agent_cfg
        self._store = store
        self._layers: list[Layer] = self._build_layers()
        self._output_scanner = InjectionDetect()
        self._audit_logger = AuditLogger(store)

    def _build_layers(self) -> list[Layer]:
        registry = {
            "l2_injection": lambda: InjectionDetect(),
            "l9_scope":     lambda: ScopeCheck(self._cfg),
            # uncomment as you build them:
            # "l1_identity": lambda: IdentityCheck(self._cfg),
            # "l6_policy":   lambda: PolicyEnforcer(self._cfg, self._store),
            # "l4_memory":   lambda: MemoryGuard(self._cfg, self._store),
        }
        from zink.config.parser import ConfigError
        layers = []
        for name in self._cfg.default_layers:
            if name not in registry:
                raise ConfigError(
                    f"Layer '{name}' not implemented. "
                    f"Available: {list(registry.keys())}"
                )
            layers.append(registry[name]())
        return layers

    def validate(self, request: ValidationRequest) -> ValidationResult:
        """
        Run all layers in order.
        Phase 1 (gate): first BLOCK exits immediately.
        Phase 2 (enrichment): all run, FLAG only.
        """
        results = []
        for layer in self._layers:
            layer_result = layer.evaluate(request)
            results.append(layer_result)

            if getattr(layer, "phase", 1) == 2:
                # enrichment layers cannot hard-block
                pass
            elif layer_result.blocked:
                return build_result(results)

        return build_result(results)

    def post_execute_all(
        self,
        request: ValidationRequest,
        outcome: Any,
    ) -> None:
        """
        Call post_execute on every layer after tool succeeds.
        Exceptions are caught and logged — post_execute must never
        crash a successful tool call.
        """
        for layer in self._layers:
            try:
                layer.post_execute(request, outcome)
            except Exception as e:
                # log and continue — don't surface post_execute failures
                import warnings
                warnings.warn(
                    f"post_execute failed on {layer.name}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def scan_output(self, outcome: Any, request: ValidationRequest) -> None:
        """
        Run L2 injection detection on tool return value.
        Raises PermissionError if injection pattern found.
        """
        if outcome is None:
            return

        if isinstance(outcome, str):
            text = outcome
        elif isinstance(outcome, dict):
            text = json.dumps(outcome)
        else:
            text = str(outcome)

        if not text.strip():
            return

        scan_request = ValidationRequest(
            agent=request.agent,
            action="output_scan",
            resource=request.resource,
            params={},
            context={"prompt_text": text},
        )
        result = self._output_scanner.evaluate(scan_request)
        if result.blocked:
            raise PermissionError(
                f"Output injection detected on '{request.resource}': {result.reason}"
            )

    def audit(
        self,
        request: ValidationRequest,
        result: ValidationResult,
        outcome: Any = None,
    ) -> None:
        self._audit_logger.write(request, result, outcome)