"""
EmailManager: Sends emails on behalf of agents
For v0.1: Mock (doesn't actually send, just logs)
"""

from datetime import datetime


class EmailManager:
    """
    Manages email operations
    
    In production: Use SendGrid, Mailgun, etc.
    For v0.1: Mock email (just log to console + file)
    """
    
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self.sent_emails = []  # Track all emails sent
    
    def send_rejection(self, candidate_email: str, candidate_name: str, reason: str) -> bool:
        """Send rejection email"""
        
        subject = "Application Status Update"
        body = f"""Dear {candidate_name},

Thank you for applying to our position. We appreciate your interest in our company.

After careful review of your application, we have decided not to move forward at this time.

Reason: {reason}

We encourage you to apply again in the future.

Best regards,
Hiring Team"""
        
        return self._send_email(candidate_email, subject, body)
    
    def send_screening_passed(self, candidate_email: str, candidate_name: str, next_steps: str) -> bool:
        """Send screening passed notification"""
        
        subject = "Good News! Your Application Moved Forward"
        body = f"""Dear {candidate_name},

Congratulations! Your application has passed our initial screening.

Next steps: {next_steps}

We'll be in touch soon with interview details.

Best regards,
Hiring Team"""
        
        return self._send_email(candidate_email, subject, body)
    
    def send_interview_scheduled(self, candidate_email: str, candidate_name: str,
                                interview_date: str, interview_time: str, 
                                hiring_manager: str) -> bool:
        """Send interview scheduling email"""
        
        subject = "Interview Scheduled"
        body = f"""Dear {candidate_name},

Your interview has been scheduled!

Date: {interview_date}
Time: {interview_time}
Interviewer: {hiring_manager}

Please confirm your attendance by replying to this email.

Best regards,
Hiring Team"""
        
        return self._send_email(candidate_email, subject, body)
    
    def send_offer(self, candidate_email: str, candidate_name: str,
                  position: str, salary: float, start_date: str) -> bool:
        """Send job offer email"""
        
        subject = f"Job Offer: {position}"
        body = f"""Dear {candidate_name},

We are excited to offer you the position of {position}!

Details:
- Position: {position}
- Salary: ${salary:,.0f}
- Start Date: {start_date}

Please sign and return the attached offer letter within 5 business days.

Welcome to the team!

Best regards,
Hiring Team"""
        
        return self._send_email(candidate_email, subject, body)
    
    def send_welcome(self, candidate_email: str, candidate_name: str, start_date: str) -> bool:
        """Send welcome/onboarding email"""
        
        subject = f"Welcome to the Team, {candidate_name}!"
        body = f"""Dear {candidate_name},

Welcome! We're excited to have you join us on {start_date}.

Your onboarding materials and first-day details will be sent separately.

See you soon!

Best regards,
HR Team"""
        
        return self._send_email(candidate_email, subject, body)
    
    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Actually send email (or mock it)
        """
        
        email_record = {
            "to": to_email,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.use_mock:
            # Just log to console and internal list
            print(f"\n📧 EMAIL SENT (MOCK)")
            print(f"   To: {to_email}")
            print(f"   Subject: {subject}")
            print(f"   Body: {body[:80]}...")
            
            self.sent_emails.append(email_record)
            return True
        else:
            # In production: use SMTP
            # For now, just log
            self.sent_emails.append(email_record)
            return True