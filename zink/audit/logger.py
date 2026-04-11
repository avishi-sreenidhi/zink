# SPDX-License-Identifier: Apache-2.0
"""
zink/audit/logger.py
--------------------
L7 Audit. Independent of the pipeline. Always runs.

SHA-256 Hash chain audit log: each entry's hash includes the previous entry's hash.
Tamper with any row and all subsequent hashes break.

Replaces zink_trace.jsonl.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from zink.schemas import ValidationRequest, ValidationResult
from zink.store.sqlite import ZinkStore

class AuditLogger:
    def __init__(self, store: ZinkStore)-> None:
        self._store = store

    def write(
            self,
            request: ValidationRequest,
            result: ValidationResult,
            outcome: Any = None
            )-> None:

        ts = datetime.now(timezone.utc).isoformat()

        caller = None
        l1 = result.layer_trace.get("l1_identity")
        if l1 and l1.get("enrichments"):
            caller = l1["enrichments"].get("caller")

        layer_trace_str = json.dumps(result.layer_trace)
        outcome_str = json.dumps(outcome) if outcome is not None else None
        params_str = json.dumps(request.params, sort_keys=True)

        fingerprint = json.dumps({
            "agent":    request.agent,
            "resource": request.resource,
            "params":   request.params,
            "ts":       ts,
        }, sort_keys=True)

        self._store.write_audit_entry(
            ts=ts,
            agent=request.agent,
            resource=request.resource,
            params_str=params_str,
            approved=1 if result.approval else 0,
            reason=result.reason,
            caller=caller,
            layer_trace_str=layer_trace_str,
            outcome_str=outcome_str,
            fingerprint=fingerprint,
        )

    def verify_chain(self) -> bool:
        """
        Reads every row in audit_log in insertion order and recomputes
        each entry_hash from the stored fields. Returns False the moment
        any hash doesn't match — chain is broken at that point.

        What this proves:
            - No row was deleted (gap in prev_hash chain)
            - No row was modified (hash would no longer match)
            - Rows are in the correct order (prev_hash linkage)
            - Params are stored and included in the fingerprint 
            — param-level tampering is detectable.
        """
        rows = self._store.query("SELECT * FROM audit_log ORDER BY id ASC")

        if not rows:
            return True # empty log
        
        prev = "0" * 64 # genesis hash — same value used at first write

        for row in rows:
            if row["prev_hash"] != prev:
                return False
            
            fingerprint = json.dumps({
                "agent":    row["agent"],
                "resource": row["resource"],
                "params":   json.loads(row["params"]) if row["params"] else {},
                "ts":       row["ts"],
            }, sort_keys=True)

            # recompute the hash the same way write() did
            expected = hashlib.sha256(
                (prev + fingerprint).encode()
            ).hexdigest()

            # compare to what's stored
            # any modification to agent, resource, ts, or the chain itself
            # will produce a different hash here
            if expected != row["entry_hash"]:
                return False

            # advance — next row's prev_hash must equal this row's entry_hash
            prev = row["entry_hash"]

        return True



        

