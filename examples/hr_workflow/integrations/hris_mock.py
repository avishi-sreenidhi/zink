"""
HRISMock: Simulates HRIS database
Stores final hire decisions
"""

from datetime import datetime
from typing import Optional


class HRISMock:
    """
    Simulates HRIS database (Workday, BambooHR, etc.)
    Stores employee records and audit trail
    """
    
    def __init__(self):
        self.employees = {}  # employee_id → employee_data
        self.audit_log = []  # All changes logged
    
    def onboard_employee(self, candidate_id: str, name: str, email: str,
                        position: str, salary: float, start_date: str) -> bool:
        """Add new hire to HRIS"""
        
        employee_id = f"EMP-{candidate_id.replace('CAND-', '')}"
        
        employee_record = {
            "employee_id": employee_id,
            "name": name,
            "email": email,
            "position": position,
            "salary": salary,
            "start_date": start_date,
            "hire_date": datetime.now().isoformat(),
            "status": "pending_onboarding"
        }
        
        # Store employee
        self.employees[employee_id] = employee_record
        
        # Log in audit trail
        self.audit_log.append({
            "action": "onboard_employee",
            "employee_id": employee_id,
            "timestamp": datetime.now().isoformat(),
            "data": employee_record
        })
        
        print(f"\n✅ ONBOARDED TO HRIS")
        print(f"   Employee ID: {employee_id}")
        print(f"   Name: {name}")
        print(f"   Position: {position}")
        print(f"   Salary: ${salary:,.0f}")
        print(f"   Start Date: {start_date}")
        
        return True
    
    def get_employee(self, employee_id: str) -> Optional[dict]:
        """Retrieve employee data"""
        return self.employees.get(employee_id)
    
    def get_audit_log(self) -> list[dict]:
        """Get all recorded changes"""
        return self.audit_log