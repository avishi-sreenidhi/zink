# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/l6_policy.py
-------------------------
L6 Policy — business rules and rate limiting.

Evaluation order:
    1. Denied list   — absolute, no conditions, first match blocks
    2. Policy rules  — AST-evaluated conditions, first block wins
    3. Rate limits   — stateful SQLite counter, post_execute increments

post_execute increments rate counter only after tool succeeds.
Blocked calls never reach post_execute — governed() contract.
"""

import math
import time
from typing import Any

from zink.layers.base import Layer
from zink.layers.condition_evaluator import check_denied, evaluate_policies
from zink.schemas import AgentConfig, ValidationRequest, LayerResult, LayerStatus
from zink.store.sqlite import ZinkStore


class PolicyEnforcer(Layer):
    name  = "l6_policy"
    phase = 1

    def __init__(self, agent_cfg: AgentConfig, store: ZinkStore) -> None:
        self._agent       = agent_cfg.agent
        self._policies    = agent_cfg.policies         # tuple of parsed AST dicts
        self._denied      = agent_cfg.denied           # list[DeniedEntry]
        self._rate_limits = getattr(agent_cfg, "rate_limits", [])
        self._store       = store

    def evaluate(self, request: ValidationRequest) -> LayerResult:
        # 1. denied list
        hit = check_denied(request.to_eval_dict(), self._denied)
        if hit:
            return LayerResult(
                status=LayerStatus.BLOCK,
                layer=self.name,
                reason=hit["reason"],
            )

        # 2. policy conditions
        verdict = evaluate_policies(
            request=request.to_eval_dict(),
            policies=self._policies,
            strict=False,
        )

        if verdict["verdict"] == "BLOCKED":
            return LayerResult(
                status=LayerStatus.BLOCK,
                layer=self.name,
                reason=verdict["reason"] or f"Policy '{verdict['rule']}' blocked request",
            )

        if verdict["verdict"] == "FLAGGED":
            flags  = verdict.get("flags", [])
            reason = "; ".join(f["reason"] for f in flags if f.get("reason"))
            return LayerResult(
                status=LayerStatus.FLAG,
                layer=self.name,
                reason=reason,
                enrichments={"flags": flags},
            )

        # 3. rate limits
        return self._check_rate_limits(request)

    def _check_rate_limits(self, request: ValidationRequest) -> LayerResult:
        now = time.time()
        for rl in self._rate_limits:
            if rl.resource != request.resource:
                continue
            window_start = math.floor(now / rl.window_seconds) * rl.window_seconds
            row = self._store.query_one(
                """
                SELECT count FROM rate_counters
                WHERE agent = ? AND resource = ? AND window_start = ?
                """,
                (self._agent, request.resource, window_start),
            )
            count = row["count"] if row else 0
            if count >= rl.limit:
                return LayerResult(
                    status=LayerStatus.BLOCK,
                    layer=self.name,
                    reason=(
                        f"Rate limit exceeded for '{request.resource}': "
                        f"{count}/{rl.limit} calls in window"
                    ),
                )
        return LayerResult(status=LayerStatus.PASS, layer=self.name)

    def post_execute(self, request: ValidationRequest, outcome: Any) -> None:
        """Increment rate counter only after tool succeeds."""
        now = time.time()
        for rl in self._rate_limits:
            if rl.resource != request.resource:
                continue
            window_start = math.floor(now / rl.window_seconds) * rl.window_seconds
            self._store.execute(
                """
                INSERT INTO rate_counters (agent, resource, window_start, count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(agent, resource, window_start)
                DO UPDATE SET count = count + 1
                """,
                (self._agent, request.resource, window_start),
            )