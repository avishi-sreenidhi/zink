"""
OnboardingAgent: Final agent to complete hiring process
"""

from datetime import datetime
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from tools.onboarding_tools import OnboardingTools
from models import ToolCall


class OnboardingState(TypedDict):
    """State for onboarding agent"""
    candidate_id: str
    candidate_name: str
    candidate_email: str
    tasks_created: bool
    welcome_sent: bool
    hris_updated: bool
    onboarding_complete: bool
    tool_calls: list


class OnboardingAgent:
    """Onboard approved candidates"""
    
    def __init__(self):
        self.tools = OnboardingTools()
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build onboarding workflow"""
        
        workflow = StateGraph(OnboardingState)
        
        workflow.add_node("decide_action", self._decide_action_node)
        workflow.add_node("create_tasks", self._create_tasks_node)
        workflow.add_node("send_welcome", self._send_welcome_node)
        workflow.add_node("update_hris", self._update_hris_node)
        workflow.add_node("finish", self._finish_node)
        
        workflow.add_edge(START, "decide_action")
        
        workflow.add_conditional_edges(
            "decide_action",
            self._choose_next_tool,
            {
                "create_tasks": "create_tasks",
                "send_welcome": "send_welcome",
                "update_hris": "update_hris",
                "finish": "finish"
            }
        )
        
        workflow.add_edge("create_tasks", "decide_action")
        workflow.add_edge("send_welcome", "decide_action")
        workflow.add_edge("update_hris", "decide_action")
        workflow.add_edge("finish", END)
        
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    
    def _decide_action_node(self, state: OnboardingState) -> OnboardingState:
        """Decide next action"""
        
        if not state.get("tasks_created"):
            return state
        
        if not state.get("welcome_sent"):
            return state
        
        if not state.get("hris_updated"):
            return state
        
        state["onboarding_complete"] = True
        return state
    
    def _choose_next_tool(self, state: OnboardingState) -> str:
        """Route to next tool"""
        
        if not state.get("tasks_created"):
            return "create_tasks"
        
        if not state.get("welcome_sent"):
            return "send_welcome"
        
        if not state.get("hris_updated"):
            return "update_hris"
        
        return "finish"
    
    def _create_tasks_node(self, state: OnboardingState) -> OnboardingState:
        """Create onboarding tasks"""
        
        tool_call = ToolCall(
            tool_name="create_onboarding_tasks",
            agent_id="onboarding_agent",
            tool_input={
                "employee_id": state["candidate_id"],
                "employee_name": state["candidate_name"]
            },
            timestamp=datetime.now().isoformat(),
            reasoning="Create onboarding task checklist"
        )
        
        result = self.tools.create_onboarding_tasks(**{
            "employee_id": state["candidate_id"],
            "employee_name": state["candidate_name"]
        })
        
        state["tasks_created"] = True
        state["tool_calls"].append(tool_call.model_dump())
        
        print(f"✓ Created {len(result)} onboarding tasks")
        
        return state
    
    def _send_welcome_node(self, state: OnboardingState) -> OnboardingState:
        """Send welcome email"""
        
        tool_call = ToolCall(
            tool_name="send_welcome_email",
            agent_id="onboarding_agent",
            tool_input={
                "candidate_email": state["candidate_email"],
                "candidate_name": state["candidate_name"],
                "start_date": "2026-04-01"
            },
            timestamp=datetime.now().isoformat(),
            reasoning="Send welcome email to new employee"
        )
        
        result = self.tools.send_welcome_email(**{
            "candidate_email": state["candidate_email"],
            "candidate_name": state["candidate_name"],
            "start_date": "2026-04-01"
        })
        
        state["welcome_sent"] = True
        state["tool_calls"].append(tool_call.model_dump())
        
        print(f"✓ Welcome email sent to {state['candidate_email']}")
        
        return state
    
    def _update_hris_node(self, state: OnboardingState) -> OnboardingState:
        """Update HRIS"""
        
        tool_call = ToolCall(
            tool_name="add_to_hris",
            agent_id="onboarding_agent",
            tool_input={
                "candidate_id": state["candidate_id"],
                "candidate_name": state["candidate_name"],
                "candidate_email": state["candidate_email"],
                "position": "Senior Engineer",
                "salary": 150000,
                "start_date": "2026-04-01"
            },
            timestamp=datetime.now().isoformat(),
            reasoning="Add employee to HRIS system"
        )
        
        result = self.tools.add_to_hris(**{
            "candidate_id": state["candidate_id"],
            "candidate_name": state["candidate_name"],
            "candidate_email": state["candidate_email"],
            "position": "Senior Engineer",
            "salary": 150000,
            "start_date": "2026-04-01"
        })
        
        state["hris_updated"] = True
        state["tool_calls"].append(tool_call.model_dump())
        
        print(f"✓ Added to HRIS: {result.get('employee_id')}")
        
        return state
    
    def _finish_node(self, state: OnboardingState) -> OnboardingState:
        """Finish onboarding"""
        print("✓ Onboarding complete")
        return state
    
    def process(self, approval_result: dict, thread_id: str) -> dict:
        """Run onboarding agent"""
        
        initial_state = OnboardingState(
            candidate_id=approval_result["candidate_id"],
            candidate_name=approval_result["candidate_name"],
            candidate_email=approval_result["candidate_email"],
            tasks_created=False,
            welcome_sent=False,
            hris_updated=False,
            onboarding_complete=False,
            tool_calls=[]
        )
        
        final_state = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}}
        )
        
        return {
            "candidate_id": final_state["candidate_id"],
            "candidate_name": final_state["candidate_name"],
            "candidate_email": final_state["candidate_email"],
            "onboarding_complete": final_state["onboarding_complete"],
            "tool_calls": final_state["tool_calls"],
            "thread_id": thread_id
        }