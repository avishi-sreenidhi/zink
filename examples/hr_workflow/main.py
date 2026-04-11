"""
Main workflow orchestrator
Wires all 4 agents together
"""

import uuid
import time
from agents.screening_agent import ScreeningAgent
from agents.scheduling_agent import SchedulingAgent
from agents.approval_agent import ApprovalAgent
from agents.onboarding_agent import OnboardingAgent


def run_hiring_workflow(resume_text: str, thread_id: str | None = None) -> dict:
    """
    Complete hiring workflow
    All agents use same thread_id for state persistence
    """
    
    if thread_id is None:
        thread_id = f"hiring_{uuid.uuid4().hex[:8]}"
    
    print("=" * 70)
    print("HIRING WORKFLOW START")
    print("=" * 70)
    
    # STEP 1: SCREENING
    
    print("\n SCREENING AGENT")
    print("-" * 70)
    
    screening = ScreeningAgent()
    screening_result = screening.process(resume_text, thread_id=thread_id)
    
    print(f"\nDecision: {screening_result['decision'].upper()}")
    print(f"Score: {screening_result['score']:.2f}")
    print(f"Candidate ID: {screening_result['candidate_id']}")
    
    if screening_result["decision"] == "reject":
        print("\n❌ REJECTED AT SCREENING")
        return {
            "final_decision": "rejected",
            "stage": "screening",
            "candidate": screening_result["candidate_name"],
            "thread_id": thread_id,
            "screening": screening_result,
            "scheduling": {},
            "approval": {},
            "onboarding": {}
        }
    
    # ====================================================================
    # STEP 2: SCHEDULING
    # ====================================================================
    
    print("\n2️⃣  SCHEDULING AGENT")
    print("-" * 70)
    
    scheduling = SchedulingAgent()
    scheduling_result = scheduling.process(screening_result, thread_id=thread_id)
    
    print(f"\nInterview Scheduled: {scheduling_result['interview_date']} @ {scheduling_result['interview_time']}")
    print(f"Event ID: {scheduling_result['event_id']}")

    
    # ====================================================================
    # STEP 3: APPROVAL (With human interrupt)
    # ====================================================================
    
    print("\n3️⃣  APPROVAL AGENT")
    print("-" * 70)
    
    approval = ApprovalAgent()
    approval_result = approval.process(scheduling_result, thread_id=thread_id)
    
    # In LangGraph, if it returns after an interrupt, status will be captured here
    if approval_result.get("status") in ["paused", "paused_waiting_for_human"]:
        print("\n⏸️  PAUSED - WAITING FOR HUMAN APPROVAL")
        print(f"Candidate: {approval_result['candidate_name']}")
        
        # Simulate human review time
        print("\n👤 MANAGER REVIEWS (Simulated)")
        print("-" * 70)
        time.sleep(2) # Just for UI feel
        print("Interview Feedback: Excellent technical skills")
        print("Recommendation: Strong hire")
        print("Decision: APPROVED")
        
        human_decision = "approved"
        
        # Resume from interrupt
        approval_result = approval.resume_with_human_input(
            thread_id=thread_id,
            approval=human_decision
        )
        
        if human_decision == "rejected":
            print("\n❌ REJECTED BY HUMAN")
            return {
                "final_decision": "rejected",
                "stage": "approval",
                "candidate": screening_result["candidate_name"],
                "thread_id": thread_id
            }
    
    # ====================================================================
    # STEP 4: ONBOARDING
    # ====================================================================
    
    print("\n4️⃣  ONBOARDING AGENT")
    print("-" * 70)
    
    # Last API cooldown
    time.sleep(10)
    
    onboarding = OnboardingAgent()
    onboarding_result = onboarding.process(approval_result, thread_id=thread_id)
    
    print(f"\nOnboarding Complete: {onboarding_result.get('onboarding_complete', 'SUCCESS')}")
    
    # ====================================================================
    # FINAL RESULT
    # ====================================================================
    
    print("\n" + "=" * 70)
    print("✅ HIRING WORKFLOW COMPLETE")
    print("=" * 70)
    
    print(f"\nCandidate: {screening_result['candidate_name']}")
    print(f"Email: {screening_result['candidate_email']}")
    print(f"Final Decision: HIRED")
    print(f"Thread ID: {thread_id}")
    print(f"Start Date: 2026-04-01")
    
    return {
        "final_decision": "hired",
        "candidate_name": screening_result["candidate_name"],
        "candidate_email": screening_result["candidate_email"],
        "candidate_id": screening_result["candidate_id"],
        "thread_id": thread_id,
        "screening": screening_result,
        "scheduling": scheduling_result,
        "approval": approval_result,
        "onboarding": onboarding_result
    }


if __name__ == "__main__":
    sample_resume = """
    Jane Smith
    jane@test.com | 555-1234
    
    EXPERIENCE:
    - Senior Engineer at TechCorp (4 years)
    - Developer at StartupXYZ (2 years)
    
    SKILLS: Python, Go, AWS, Docker, Kubernetes
    
    EDUCATION: BS Computer Science, Stanford
    """
    
    result = run_hiring_workflow(sample_resume)
    print(f"\n\nFinal Result: {result['final_decision'].upper()}")