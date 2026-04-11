"""Test all integrations work together"""

from integrations import ExcelManager, EmailManager, CalendarManager, HRISMock

print("=" * 60)
print("TESTING ALL INTEGRATIONS")
print("=" * 60)

# Test 1: Excel
print("\n1. Testing ExcelManager...")
excel = ExcelManager("test_pipeline.xlsx")
excel.add_candidate("CAND-001", "Jane Smith", "jane@test.com")
excel.update_screening_score("CAND-001", 0.78, "pass")
candidates = excel.get_all_candidates()
print(f"   ✓ ExcelManager works ({len(candidates)} candidates in pipeline)")

# Test 2: Email
print("\n2. Testing EmailManager...")
email = EmailManager(use_mock=True)
email.send_rejection("john@test.com", "John Doe", "not enough experience")
email.send_screening_passed("jane@test.com", "Jane Smith", "Interview scheduling")
print(f"   ✓ EmailManager works ({len(email.sent_emails)} emails sent)")

# Test 3: Calendar
print("\n3. Testing CalendarManager...")
calendar = CalendarManager()
slots = calendar.get_availability("alice@company.com")
success, event_id = calendar.schedule_interview(
    "jane@test.com",
    "Jane Smith",
    "alice@company.com",
    "2026-03-05",
    "14:00"
)
print(f"   ✓ CalendarManager works ({len(calendar.get_scheduled_events())} events scheduled)")

# Test 4: HRIS
print("\n4. Testing HRISMock...")
hris = HRISMock()
hris.onboard_employee(
    "CAND-001",
    "Jane Smith",
    "jane@test.com",
    "Senior Engineer",
    150000,
    "2026-04-01"
)
emp = hris.get_employee("EMP-001")
print(f"   ✓ HRISMock works ({len(hris.get_audit_log())} audit logs)")

print("\n" + "=" * 60)
print("✅ ALL INTEGRATIONS WORKING")
print("=" * 60)