"""
Pydantic models for all payloads
Zink sees these, not f-strings
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ========================================================================
# RESUME & CANDIDATE DATA
# ========================================================================

class ResumeExtraction(BaseModel):
    """Extracted resume data"""
    name: str
    email: str
    phone: Optional[str] = None
    years_experience: int
    skills: List[str]
    education: str
    previous_companies: List[str]


class CandidateScore(BaseModel):
    """Candidate scoring result"""
    candidate_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    strengths: List[str]
    weaknesses: List[str]


class ScreeningDecision(BaseModel):
    """Screening decision payload"""
    candidate_id: str
    decision: str = Field(pattern="^(reject|escalate|approve)$")
    reasoning: str
    score: float
    threshold: float = 0.6


# ========================================================================
# SCHEDULING PAYLOADS
# ========================================================================

class AvailabilitySlot(BaseModel):
    """Interview availability slot"""
    date: str
    time: str
    duration_minutes: int = 60
    manager_email: str


class InterviewScheduling(BaseModel):
    """Scheduled interview"""
    event_id: str
    candidate_id: str
    candidate_email: str
    date: str
    time: str
    manager_email: str
    location: str = "Virtual"


# ========================================================================
# APPROVAL PAYLOADS
# ========================================================================

class JobOffer(BaseModel):
    """Job offer details"""
    candidate_id: str
    position: str
    salary: float = Field(gt=0)
    start_date: str
    benefits: List[str]
    offer_expires: str


class ApprovalDecision(BaseModel):
    """Human approval decision"""
    candidate_id: str
    approval: str = Field(pattern="^(approved|rejected)$")
    approver: str
    feedback: str
    timestamp: str


# ========================================================================
# ONBOARDING PAYLOADS
# ========================================================================

class OnboardingTask(BaseModel):
    """Single onboarding task"""
    task_id: str
    task_name: str
    due_date: str
    assigned_to: str
    status: str = "pending"


class EmployeeRecord(BaseModel):
    """Employee HRIS record"""
    employee_id: str
    name: str
    email: str
    position: str
    salary: float
    start_date: str
    manager: str


# ========================================================================
# TOOL CALL PAYLOADS (What Zink sees)
# ========================================================================

class ToolCall(BaseModel):
    """Generic tool call payload (Zink intercepts this)"""
    tool_name: str
    agent_id: str
    tool_input: dict  # Actual input to tool
    timestamp: str
    reasoning: str  # Why agent called this tool


# ========================================================================
# STATE PAYLOADS
# ========================================================================

class ScreeningStatePayload(BaseModel):
    """Data flowing through screening agent"""
    resume_text: Optional[str] = None
    extracted_resume: Optional[ResumeExtraction] = None
    candidate_score: Optional[CandidateScore] = None
    screening_decision: Optional[ScreeningDecision] = None
    tool_calls: List[ToolCall] = []


class SchedulingStatePayload(BaseModel):
    """Data flowing through scheduling agent"""
    candidate_id: str
    candidate_email: str
    available_slots: List[AvailabilitySlot] = []
    scheduled_interview: Optional[InterviewScheduling] = None
    tool_calls: List[ToolCall] = []


class ApprovalStatePayload(BaseModel):
    """Data flowing through approval agent"""
    candidate_id: str
    candidate_name: str
    job_offer: Optional[JobOffer] = None
    human_approval: Optional[ApprovalDecision] = None
    tool_calls: List[ToolCall] = []


class OnboardingStatePayload(BaseModel):
    """Data flowing through onboarding agent"""
    employee_id: str
    employee_name: str
    onboarding_tasks: List[OnboardingTask] = []
    employee_record: Optional[EmployeeRecord] = None
    tool_calls: List[ToolCall] = []