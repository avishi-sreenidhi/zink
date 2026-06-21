# SPDX-License-Identifier: Apache-2.0
"""
study/run_study.py
------------------
Runs the labelled suite (study/suite.py) through REAL Zink and measures five
things a governance reviewer actually cares about:

  1. Decision correctness   expected PASS/BLOCK vs what Zink did
  2. Layer attribution      which gate was responsible for each block
  3. Audit completeness     every action -> exactly one tamper-evident log row
  4. Tamper-evidence        chain verifies clean; a 1-field edit breaks it,
                            and we can name the row where it breaks
  5. Determinism (replay)   N independent runs from identical state produce a
                            byte-identical decision sequence

Each run uses a FRESH SQLite store so stateful layers (dedup, rate limits)
start from the same state — determinism is "same input + same config + same
state -> same decision", and state is part of that. We hash the DECISION
sequence only (approval + reason + responsible layer), never the wrapped
tool's own return value: Zink governs the control plane, not the tool.

Run:
    python -m study.run_study
Outputs:
    study/out/results.json
"""
import json
import os
import sqlite3
import hashlib
from pathlib import Path

os.environ.setdefault("PYTHONHASHSEED", "0")

from zink import Zink
from zink.audit.logger import AuditLogger
from zink.store.sqlite import ZinkStore
from study.suite import build_suite

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


# ── one execution of the full suite against a fresh store ─────────────────────
def run_once(db_path: str):
    """Execute every case once. Return per-case decisions + the store path."""
    if os.path.exists(db_path):
        os.remove(db_path)

    suite = build_suite()
    # one Zink instance (one shared store) so the audit chain spans the whole run
    zink = Zink(store_path=db_path)

    # cache one governed callable per (agent, resource) so dedup/rate state is shared
    governed = {}
    for c in suite:
        key = (c.agent, c.resource, tuple(sorted(c.context.items())))
        if key not in governed:
            governed[key] = zink.govern(
                c.agent, c.config, (lambda ctx=c.context: ctx),
                resource_name=c.resource,
            )(c.fn)

    decisions = []
    for c in suite:
        key = (c.agent, c.resource, tuple(sorted(c.context.items())))
        tool = governed[key]
        try:
            tool(**c.params)
            decisions.append({"label": c.label, "decision": "PASS", "reason": "—"})
        except PermissionError as e:
            decisions.append({"label": c.label, "decision": "BLOCK", "reason": str(e)})

    # WAL is on; fold the sidecar back into the main file so the db is
    # self-contained for copying (tamper test) and reopening.
    zink._store.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    zink._store.close()
    return suite, decisions, db_path


# ── read the audit log back and attribute the responsible layer per row ───────
def read_audit(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id ASC").fetchall()
    out = []
    for r in rows:
        trace = json.loads(r["layer_trace"]) if r["layer_trace"] else {}
        responsible = None
        # first layer in the trace whose status is 'block'
        for layer, entry in trace.items():
            if entry.get("status") == "block":
                responsible = layer
                break
        out.append({
            "id": r["id"], "resource": r["resource"],
            "approved": bool(r["approved"]), "responsible_layer": responsible,
            "params": r["params"],
        })
    conn.close()
    return out


def decision_signature(decisions):
    """Stable hash over the control-plane decision sequence (not tool output)."""
    payload = json.dumps(
        [(d["label"], d["decision"], d["reason"]) for d in decisions],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# ── metric 4: tamper-evidence demonstration ───────────────────────────────────
def tamper_test(db_path: str):
    store = ZinkStore(db_path)
    logger = AuditLogger(store)
    clean = logger.verify_chain()

    # pick a real blocked row and silently rewrite its stored params
    target = store.query(
        "SELECT id, params FROM audit_log WHERE approved = 0 ORDER BY id ASC LIMIT 1"
    )[0]
    tampered_id = target["id"]
    store.execute(
        "UPDATE audit_log SET params = ? WHERE id = ?",
        (json.dumps({"amount": 0.01, "category": "travel"}), tampered_id),
    )
    after = logger.verify_chain()

    # locate the first row where recomputed hash diverges (should be tampered_id)
    break_at = _first_broken_row(store)
    store.close()
    return {
        "verify_before_tamper": clean,
        "tampered_row_id": tampered_id,
        "verify_after_tamper": after,
        "chain_breaks_at_row": break_at,
    }


def _first_broken_row(store: ZinkStore):
    rows = store.query("SELECT * FROM audit_log ORDER BY id ASC")
    prev = "0" * 64
    for row in rows:
        fp = json.dumps({
            "agent": row["agent"], "resource": row["resource"],
            "params": json.loads(row["params"]) if row["params"] else {},
            "ts": row["ts"],
        }, sort_keys=True)
        expected = hashlib.sha256((prev + fp).encode()).hexdigest()
        if row["prev_hash"] != prev or expected != row["entry_hash"]:
            return row["id"]
        prev = row["entry_hash"]
    return None


# ── orchestration ─────────────────────────────────────────────────────────────
def main(n_runs: int = 10):
    # canonical run (used for correctness + attribution + audit + tamper)
    suite, decisions, db = run_once(str(OUT / "canonical.db"))
    audit = read_audit(db)

    # 1. correctness  +  2. attribution
    per_case, correct, layer_hits = [], 0, {}
    audit_by_resource_order = audit  # same order as suite execution
    for c, d, a in zip(suite, decisions, audit_by_resource_order):
        decision_ok = (d["decision"] == c.expected)
        layer_ok = (c.expected != "BLOCK") or (a["responsible_layer"] == c.expected_layer)
        ok = decision_ok and layer_ok
        correct += int(ok)
        if d["decision"] == "BLOCK" and a["responsible_layer"]:
            layer_hits[a["responsible_layer"]] = layer_hits.get(a["responsible_layer"], 0) + 1
        per_case.append({
            "label": c.label, "expected": c.expected, "got": d["decision"],
            "expected_layer": c.expected_layer,
            "responsible_layer": a["responsible_layer"],
            "match": ok,
        })

    # 3. audit completeness
    completeness = {
        "actions_executed": len(suite),
        "audit_rows_written": len(audit),
        "complete": len(suite) == len(audit),
    }

    # 4. tamper-evidence (mutates a COPY of the canonical db)
    import shutil
    tamper_db = str(OUT / "tamper.db")
    shutil.copy(db, tamper_db)
    tamper = tamper_test(tamper_db)

    # 5. determinism across N independent runs from identical fresh state
    signatures = []
    for i in range(n_runs):
        _, d_i, _ = run_once(str(OUT / f"run_{i}.db"))
        signatures.append(decision_signature(d_i))
    deterministic = len(set(signatures)) == 1

    results = {
        "n_cases": len(suite),
        "correctness": {
            "cases_correct": correct,
            "total": len(suite),
            "accuracy": round(correct / len(suite), 4),
        },
        "layer_attribution": layer_hits,
        "audit_completeness": completeness,
        "tamper_evidence": tamper,
        "determinism": {
            "runs": n_runs,
            "unique_decision_signatures": len(set(signatures)),
            "deterministic": deterministic,
            "signature": signatures[0],
        },
        "per_case": per_case,
    }

    (OUT / "results.json").write_text(json.dumps(results, indent=2))

    # cleanup transient run dbs
    for i in range(n_runs):
        p = OUT / f"run_{i}.db"
        if p.exists():
            p.unlink()

    _print_summary(results)
    return results


def _print_summary(r):
    c = r["correctness"]
    print("=" * 64)
    print("ZINK EMPIRICAL STUDY — SUMMARY")
    print("=" * 64)
    print(f"Cases:                 {r['n_cases']}")
    print(f"Decision correctness:  {c['cases_correct']}/{c['total']}  ({c['accuracy']*100:.1f}%)")
    print(f"Layer attribution:     {r['layer_attribution']}")
    ac = r["audit_completeness"]
    print(f"Audit completeness:    {ac['audit_rows_written']}/{ac['actions_executed']} rows  -> {ac['complete']}")
    t = r["tamper_evidence"]
    print(f"Tamper-evidence:       clean={t['verify_before_tamper']}  "
          f"after 1-field edit on row {t['tampered_row_id']}={t['verify_after_tamper']}  "
          f"(breaks at row {t['chain_breaks_at_row']})")
    d = r["determinism"]
    print(f"Determinism:           {d['runs']} runs, {d['unique_decision_signatures']} unique "
          f"signature -> deterministic={d['deterministic']}")
    print("=" * 64)


if __name__ == "__main__":
    main()