# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/l4_memory.py
------------------------
L4 Memory — deduplication and idempotency enforcement.

Hashes (agent + resource + identity_params) to produce a stable
fingerprint for a logical request. Blocks if the same fingerprint
was seen within the TTL window.

Hash is written AFTER tool succeeds via post_execute.
If tool raises, no hash is written — safe to retry.

Config (on scope entry):
    scope:
      - action: invoke
        resource: score_candidate
        dedup:
          identity_params: ["candidate_id"]
          ttl_seconds: 86400
"""

import hashlib
import json
import time
from typing import Any

from zink.schemas import AgentConfig, ValidationRequest, LayerResult, LayerStatus
from zink.store.sqlite import ZinkStore
from zink.layers.base import Layer


class MemoryGuard(Layer):
    name = "l4_memory"
    phase = 1

    def __init__(self, agent_cfg: AgentConfig, store: ZinkStore) -> None:
        self._scope = agent_cfg.scope
        self._store = store
        self._agent = agent_cfg.agent

    def evaluate(self, request: ValidationRequest) -> LayerResult:
        entry = self._find_scope_entry(request)
        if entry is None or entry.dedup is None:
            return LayerResult(status=LayerStatus.PASS, layer=self.name)

        h = self._compute_hash(request, entry.dedup.identity_params)
        now = time.time()

        row = self._store.query_one(
            """
            SELECT hash FROM dedup_hashes
            WHERE hash = ? AND expires_at > ?
            """,
            (h, now),
        )

        if row:
            return LayerResult(
                status=LayerStatus.BLOCK,
                layer=self.name,
                reason=(
                    f"Duplicate request detected for '{request.resource}' — "
                    f"already processed within TTL window"
                ),
            )

        return LayerResult(status=LayerStatus.PASS, layer=self.name)

    def post_execute(
        self,
        request: ValidationRequest,
        outcome: Any,
    ) -> None:
        """Write dedup hash after tool succeeds."""
        entry = self._find_scope_entry(request)
        if entry is None or entry.dedup is None:
            return

        h = self._compute_hash(request, entry.dedup.identity_params)
        now = time.time()
        expires_at = now + entry.dedup.ttl_seconds

        self._store.execute(
            """
            INSERT OR IGNORE INTO dedup_hashes
                (hash, agent, resource, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (h, self._agent, request.resource, now, expires_at),
        )

    def _find_scope_entry(self, request: ValidationRequest):
        for entry in self._scope:
            from fnmatch import fnmatch
            if fnmatch(request.action, entry.action) and \
               fnmatch(request.resource, entry.resource):
                return entry
        return None

    def _compute_hash(
        self,
        request: ValidationRequest,
        identity_params: list[str],
    ) -> str:
        identity = {k: request.params.get(k) for k in identity_params}
        payload = json.dumps({
            "agent":    self._agent,
            "resource": request.resource,
            **identity,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()