"""
ApprovalAgent: Human-in-the-loop with interrupts
FIXED: Resume logic now returns full state for Onboarding; nodes use direct tool calls.
might have to fix defensive manual checks and use pydantic instead
"""

import uuid
from datetime import datetime
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from tools.approval_tools import ApprovalTools
from models import ToolCall


class ApprovalState(TypedDict):
    """State for approval agent"""
    candidate_id: str
    candidate_name: str
    candidate_email: str
    interview_date: str
    job_offer: dict
    human_approval: str
    approval_complete: bool
    tool_calls: list


class ApprovalAgent:
    """Approval agent with human interrupt"""
    
    def __init__(self):
        self.tools = ApprovalTools()
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build approval workflow with interrupt"""
        workflow = StateGraph(ApprovalState)
        
        workflow.add_node("decide_action", self._decide_action_node)
        workflow.add_node("generate_offer", self._generate_offer_node)
        workflow.add_node("wait_for_human", self._wait_for_human_node)
        workflow.add_node("log_offer", self._log_offer_node)
        workflow.add_node("send_offer", self._send_offer_node)
        workflow.add_node("send_rejection", self._send_rejection_node)
        workflow.add_node("finish", self._finish_node)
        
        workflow.add_edge(START, "decide_action")
        
        workflow.add_conditional_edges(
            "decide_action",
            self._choose_next_tool,
            {
                "generate_offer": "generate_offer",
                "wait_for_human": "wait_for_human",
                "log_offer": "log_offer",
                "send_offer": "send_offer",
                "send_rejection": "send_rejection",
                "finish": "finish"
            }
        )
        
        workflow.add_edge("generate_offer", "decide_action")
        workflow.add_edge("wait_for_human", "decide_action")
        workflow.add_edge("log_offer", "decide_action")
        workflow.add_edge("send_offer", "finish")
        workflow.add_edge("send_rejection", "finish")
        workflow.add_edge("finish", END)
        
        return workflow.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["wait_for_human"]
        )
    
    def _decide_action_node(self, state: ApprovalState) -> ApprovalState:
        if not state.get("job_offer"): return state
        if not state.get("human_approval"): return state
        return state
    
    def _choose_next_tool(self, state: ApprovalState) -> str:
        if not state.get("job_offer"): return "generate_offer"
        if not state.get("human_approval"): return "wait_for_human"
        
        approval = state.get("human_approval")
        if approval == "approved":
            return "log_offer" if not state.get("approval_complete") else "send_offer"
        return "send_rejection"
    
    def _generate_offer_node(self, state: ApprovalState) -> ApprovalState:
        # Direct call to tools (No .invoke)
        result = self.tools.generate_offer(
            candidate_name=state.get("candidate_name"),
            candidate_email=state.get("candidate_email"),
            position="Senior Engineer",
            salary=150000
        )
        state["job_offer"] = result
        print(f"✓ Generated offer: ${result.get('salary', 0):,.0f}")
        return state
    
    def _wait_for_human_node(self, state: ApprovalState) -> ApprovalState:
        # This node is hit right before the interrupt
        print(f"\n⏸️  PAUSED - WAITING FOR HUMAN APPROVAL: {state['candidate_name']}")
        return state
    
    def _log_offer_node(self, state: ApprovalState) -> ApprovalState:
        self.tools.log_offer_to_excel(
            candidate_id=state.get("candidate_id"),
            candidate_name=state.get("candidate_name"),
            position=state.get("job_offer", {}).get("position"),
            salary=state.get("job_offer", {}).get("salary")
        )
        state["approval_complete"] = True
        print(f"✓ Logged offer to database")
        return state
    
    def _send_offer_node(self, state: ApprovalState) -> ApprovalState:
        self.tools.send_offer_email(
            candidate_email=state.get("candidate_email"),
            candidate_name=state.get("candidate_name"),
            position=state.get("job_offer", {}).get("position"),
            salary=state.get("job_offer", {}).get("salary"),
            start_date=state.get("job_offer", {}).get("start_date")
        )
        print(f"✓ Offer email sent")
        return state
    
    def _send_rejection_node(self, state: ApprovalState) -> ApprovalState:
        self.tools.send_rejection_email(
            candidate_email=state.get("candidate_email"),
            candidate_name=state.get("candidate_name")
        )
        return state
    
    def _finish_node(self, state: ApprovalState) -> ApprovalState:
        return state

    def process(self, scheduling_result: dict, thread_id: str) -> dict:
        """Starts the graph and triggers the interrupt"""
        # Ensure we have a candidate_id to avoid KeyErrors downstream
        c_id = scheduling_result.get("candidate_id") or f"CAND-{uuid.uuid4().hex[:4].upper()}"
        
        initial_state = {
            "candidate_id": c_id,
            "candidate_name": scheduling_result.get("candidate_name", "Unknown"),
            "candidate_email": scheduling_result.get("candidate_email", "unknown@example.com"),
            "interview_date": scheduling_result.get("interview_date", ""),
            "job_offer": {},
            "human_approval": "",
            "approval_complete": False,
            "tool_calls": []
        }
        
        self.graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})
        
        # We know it interrupts, so return the current progress
        return {
            "status": "paused",
            "candidate_id": c_id,
            "candidate_name": initial_state["candidate_name"],
            "thread_id": thread_id
        }
    
    def resume_with_human_input(self, thread_id: str, approval: str) -> dict:
        """RESUMES the graph and returns the FINAL data for Onboarding"""
        print(f"\n▶️  RESUMING - Continuing with {approval.upper()}...")
        
        # 1. Inject the human decision
        self.graph.update_state(
            config={"configurable": {"thread_id": thread_id}},
            values={"human_approval": approval.lower()}
        )
        
        # 2. Run until the end (None as input means 'resume')
        final_state = self.graph.invoke(None, config={"configurable": {"thread_id": thread_id}})
        
        # 3. Return the COMPLETE Passport for Onboarding
        return {
            "candidate_id": final_state.get("candidate_id"),
            "candidate_name": final_state.get("candidate_name"),
            "candidate_email": final_state.get("candidate_email"),
            "decision": final_state.get("human_approval"),
            "status": "complete",
            "thread_id": thread_id
        }