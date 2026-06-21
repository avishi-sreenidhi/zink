"""
Demo: Audit Chain Verification & Tamper Detection
"""
import tempfile, json, hashlib
from pathlib import Path
from zink.store.sqlite import ZinkStore
from zink.audit.logger import AuditLogger
from zink.schemas import ValidationRequest, ValidationResult, LayerResult, LayerStatus


def make_request(i=0):
    return ValidationRequest(
        agent="finance_agent",
        action="invoke",
        resource=f"tool_{i}",
        params={"index": i},
        context={},
    )


def make_result(approved=True):
    status = LayerStatus.PASS if approved else LayerStatus.BLOCK
    layer = LayerResult(status=status, layer="scope", reason="" if approved else "blocked")
    return ValidationResult(
        approval=approved,
        reason="" if approved else "blocked",
        layer_trace={"scope": layer.to_trace_entry()},
    )


def print_chain(store):
    rows = store.query("SELECT id, agent, resource, prev_hash, entry_hash FROM audit_log ORDER BY id ASC")
    print(f"\n  {'ID':<4} {'Agent':<15} {'Resource':<10} {'prev_hash[:12]':<16} {'entry_hash[:12]'}")
    print("  " + "-" * 65)
    for row in rows:
        print(f"  {row['id']:<4} {row['agent']:<15} {row['resource']:<10} {row['prev_hash'][:12]:<16} {row['entry_hash'][:12]}")


with tempfile.TemporaryDirectory() as tmp:
    store = ZinkStore(Path(tmp) / "audit.db")
    logger = AuditLogger(store)

    # ── Section 4: Chain Verification ────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SECTION 4 — Audit Chain Verification")
    print("=" * 65)

    print("\n  Writing 5 audit entries...")
    for i in range(5):
        logger.write(make_request(i), make_result(True))

    print_chain(store)

    result = logger.verify_chain()
    print(f"\n  verify_chain() → {result}")
    print(f"  Chain intact: {'YES — all hashes link correctly' if result else 'NO'}")

    # ── Section 5: Tamper Detection ───────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SECTION 5 — Tamper Detection")
    print("=" * 65)

    original = store.query_one("SELECT entry_hash FROM audit_log WHERE id = 3")["entry_hash"]
    forged   = "deadbeef" * 8

    print(f"\n  Tampering with row id=3:")
    print(f"    original entry_hash : {original[:32]}...")
    print(f"    forged   entry_hash : {forged[:32]}...")

    store.execute("UPDATE audit_log SET resource = 'TAMPERED' WHERE id = 3")

    result = logger.verify_chain()
    print(f"\n  verify_chain() → {result}")
    print(f"  Tamper detected: {'YES — hash mismatch at row 3' if not result else 'NO'}")

print("\n" + "=" * 65 + "\n")
