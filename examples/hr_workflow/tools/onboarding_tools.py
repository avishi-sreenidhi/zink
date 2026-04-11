"""
Onboarding Tools: Structured tools for employee onboarding
"""

from datetime import datetime
from langchain_core.tools import tool

from models import OnboardingTask, EmployeeRecord
from integrations import EmailManager, HRISMock


class OnboardingTools:
    """Tools for onboarding"""
    
    def __init__(self):
        self.email = EmailManager()
        self.hris = HRISMock()
    
    def create_onboarding_tasks(self,
                               employee_id: str,
                               employee_name: str) -> list[dict]:
        """
        Create onboarding task list
        
        Args:
            employee_id: Employee ID
            employee_name: Employee name
        
        Returns:
            List of onboarding tasks
        """
        
        tasks = [
            OnboardingTask(
                task_id="task_1",
                task_name="Set up laptop and equipment",
                due_date="2026-03-31",
                assigned_to="IT Team",
                status="pending"
            ),
            OnboardingTask(
                task_id="task_2",
                task_name="Add to Slack and communication tools",
                due_date="2026-03-31",
                assigned_to="Admin",
                status="pending"
            ),
            OnboardingTask(
                task_id="task_3",
                task_name="Assign mentor/buddy",
                due_date="2026-03-31",
                assigned_to="Engineering Manager",
                status="pending"
            ),
            OnboardingTask(
                task_id="task_4",
                task_name="Schedule training sessions",
                due_date="2026-04-07",
                assigned_to="HR",
                status="pending"
            )
        ]
        
        return [task.model_dump() for task in tasks]
    
    def send_welcome_email(self,
                          candidate_email: str,
                          candidate_name: str,
                          start_date: str) -> dict:
        """
        Send welcome email
        
        Args:
            candidate_email: Email address
            candidate_name: Employee name
            start_date: Start date
        
        Returns:
            Email sent confirmation
        """
        
        self.email.send_welcome(candidate_email, candidate_name, start_date)
        
        return {
            "sent": True,
            "recipient": candidate_email,
            "timestamp": datetime.now().isoformat()
        }
    
    def add_to_hris(self,
                   candidate_id: str,
                   candidate_name: str,
                   candidate_email: str,
                   position: str = "Senior Engineer",
                   salary: float = 150000,
                   start_date: str = "2026-04-01") -> dict:
        """
        Add employee to HRIS
        
        Args:
            candidate_id: Candidate ID
            candidate_name: Employee name
            candidate_email: Email
            position: Position
            salary: Salary
            start_date: Start date
        
        Returns:
            Employee record created
        """
        
        self.hris.onboard_employee(
            candidate_id,
            candidate_name,
            candidate_email,
            position,
            salary,
            start_date
        )
        
        return {
            "added": True,
            "employee_id": f"EMP-{candidate_id.replace('CAND-', '')}",
            "timestamp": datetime.now().isoformat()
        }