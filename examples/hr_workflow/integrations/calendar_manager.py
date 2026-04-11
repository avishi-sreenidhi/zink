"""
CalendarManager: Manages calendar operations
For v0.1: Mock (simulated availability)
"""

import uuid
from datetime import datetime


class CalendarManager:
    """
    Manages interview scheduling on hiring manager calendars
    
    In production: Google Calendar API, Outlook, etc.
    For v0.1: Mock with simulated availability
    """
    
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self.scheduled_events = []
        
        # Mock availability: hiring managers + their free slots
        self.mock_availability = {
            "alice@company.com": [
                {"date": "2026-03-05", "times": ["14:00", "15:00", "16:00"]},
                {"date": "2026-03-07", "times": ["14:00", "15:00", "16:00"]},
                {"date": "2026-03-12", "times": ["10:00", "11:00", "14:00"]},
            ],
            "bob@company.com": [
                {"date": "2026-03-04", "times": ["10:00", "11:00"]},
                {"date": "2026-03-06", "times": ["10:00", "11:00", "15:00"]},
                {"date": "2026-03-11", "times": ["09:00", "10:00"]},
            ]
        }
    
    def get_availability(self, hiring_manager_email: str) -> list[dict]:
        """Get hiring manager's available slots"""
        
        if hiring_manager_email in self.mock_availability:
            availability = self.mock_availability[hiring_manager_email]
            print(f"✓ Got availability for {hiring_manager_email}: {len(availability)} dates")
            return availability
        
        # If not in mock data, return empty list
        print(f"✗ No availability for {hiring_manager_email}")
        return []
    
    def schedule_interview(self, candidate_email: str, candidate_name: str,
                          hiring_manager_email: str, date: str, time: str) -> tuple[bool, str]:
        """Schedule interview on calendar"""
        
        event_id = f"EVENT-{uuid.uuid4().hex[:8].upper()}"
        
        event = {
            "event_id": event_id,
            "candidate_email": candidate_email,
            "candidate_name": candidate_name,
            "hiring_manager": hiring_manager_email,
            "date": date,
            "time": time,
            "timestamp": datetime.now().isoformat()
        }
        
        self.scheduled_events.append(event)
        
        print(f"\n📅 INTERVIEW SCHEDULED (MOCK)")
        print(f"   Candidate: {candidate_name}")
        print(f"   Date: {date} {time}")
        print(f"   Manager: {hiring_manager_email}")
        print(f"   Event ID: {event_id}")
        
        return (True, event_id)
    
    def get_scheduled_events(self) -> list[dict]:
        """Return all scheduled interviews"""
        return self.scheduled_events