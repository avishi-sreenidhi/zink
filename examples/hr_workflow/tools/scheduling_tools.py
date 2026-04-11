"""
Scheduling Tools: Standalone tool definitions
FIXED: Removed 'self' from tool signatures to prevent Pydantic ValidationErrors.
"""

from datetime import datetime
from langchain_core.tools import tool
from integrations import CalendarManager, EmailManager

# Initialize managers globally or inside functions
calendar = CalendarManager()
email = EmailManager()

@tool
def get_availability(manager_email: str) -> list:
    """Get hiring manager's available interview slots."""
    availability = calendar.get_availability(manager_email)
    return list(availability)

@tool
def schedule_interview(candidate_email: str, candidate_name: str, 
                       manager_email: str, date: str, time: str) -> dict:
    """Schedule interview on calendar and return event_id."""
    success, event_id = calendar.schedule_interview(
        candidate_email, candidate_name, manager_email, date, time
    )
    return {
        "success": success,
        "event_id": event_id or "MOCK-ID",
        "date": date,
        "time": time
    }

@tool
def send_interview_invite(candidate_email: str, candidate_name: str,
                         date: str, time: str, manager: str) -> dict:
    """Send interview invitation email."""
    email.send_interview_scheduled(candidate_email, candidate_name, date, time, manager)
    return {"sent": True}

class SchedulingTools:
    """
    Wrapper to keep your Agent's __init__ consistent.
    We map the class attributes to the standalone tool functions.
    """
    def __init__(self):
        self.get_availability = get_availability
        self.schedule_interview = schedule_interview
        self.send_interview_invite = send_interview_invite