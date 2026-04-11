"""
Approval Tools: Structured tools for offer generation and approval
"""

from datetime import datetime
from langchain_core.tools import tool

from models import JobOffer
from integrations import ExcelManager, EmailManager


class ApprovalTools:
    """Tools for offer approval"""
    
    def __init__(self):
        self.excel = ExcelManager()
        self.email = EmailManager()
    
    def generate_offer(self,
                      candidate_name: str,
                      candidate_email: str,
                      position: str = "Senior Engineer",
                      salary: float = 150000) -> dict:
        """
        Generate job offer
        
        Args:
            candidate_name: Candidate name
            candidate_email: Candidate email
            position: Job position
            salary: Annual salary
        
        Returns:
            Job offer details
        """
        
        offer = JobOffer(
            candidate_id="",  # Will be filled later
            position=position,
            salary=salary,
            start_date="2026-04-01",
            benefits=["Health Insurance", "401k", "Remote"],
            offer_expires="2026-03-15"
        )
        
        return offer.model_dump()
    
    def log_offer_to_excel(self,
                          candidate_id: str,
                          candidate_name: str,
                          position: str,
                          salary: float) -> dict:
        """
        Log offer to Excel
        
        Args:
            candidate_id: Candidate ID
            candidate_name: Candidate name
            position: Position offered
            salary: Salary offered
        
        Returns:
            Confirmation
        """
        
        self.excel.update_approval(candidate_id, "offer_generated", salary)
        
        return {
            "logged": True,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "position": position,
            "salary": salary,
            "timestamp": datetime.now().isoformat()
        }
    
    def send_offer_email(self,
                        candidate_email: str,
                        candidate_name: str,
                        position: str,
                        salary: float,
                        start_date: str) -> dict:
        """
        Send offer email to candidate
        
        Args:
            candidate_email: Email address
            candidate_name: Candidate name
            position: Position
            salary: Salary
            start_date: Start date
        
        Returns:
            Email sent confirmation
        """
        
        self.email.send_offer(
            candidate_email,
            candidate_name,
            position,
            salary,
            start_date
        )
        
        return {
            "sent": True,
            "recipient": candidate_email,
            "timestamp": datetime.now().isoformat()
        }
    
    def send_rejection_email(self,
                            candidate_email: str,
                            candidate_name: str) -> dict:
        """
        Send rejection email
        
        Args:
            candidate_email: Email address
            candidate_name: Candidate name
        
        Returns:
            Email sent confirmation
        """
        
        self.email.send_rejection(
            candidate_email,
            candidate_name,
            "Unfortunately, we've decided not to move forward"
        )
        
        return {
            "sent": True,
            "recipient": candidate_email,
            "timestamp": datetime.now().isoformat()
        }