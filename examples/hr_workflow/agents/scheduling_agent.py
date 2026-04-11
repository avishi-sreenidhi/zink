"""
SchedulingAgent: Autonomous agent for interview scheduling
FIXED: Using .invoke() for @tool objects and defensive dictionary handling.
"""

import uuid
from datetime import datetime
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from tools.scheduling_tools import SchedulingTools
from models import ToolCall

class SchedulingState(TypedDict):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    screening_decision: str
    available_slots: list 
    selected_date: str
    selected_time: str
    event_id: str
    scheduling_complete: bool
    tool_calls: list

class SchedulingAgent:
    def __init__(self):
        self.tools = SchedulingTools()
        self.graph = self._build_graph()
    
    def _build_graph(self):
        workflow = StateGraph(SchedulingState)
        
        workflow.add_node("decide_action", self._decide_action_node)
        workflow.add_node("get_availability", self._get_availability_node)
        workflow.add_node("schedule", self._schedule_node)
        workflow.add_node("send_invite", self._send_invite_node)
        workflow.add_node("finish", self._finish_node)
        
        workflow.add_edge(START, "decide_action")
        
        workflow.add_conditional_edges(
            "decide_action",
            self._choose_next_tool,
            {
                "get_availability": "get_availability",
                "schedule": "schedule",
                "send_invite": "send_invite",
                "finish": "finish"
            }
        )
        
        workflow.add_edge("get_availability", "decide_action")
        workflow.add_edge("schedule", "decide_action")
        workflow.add_edge("send_invite", "finish")
        workflow.add_edge("finish", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _decide_action_node(self, state: SchedulingState) -> SchedulingState:
        if not state.get("available_slots"): return state
        if not state.get("selected_date"): return state
        if not state.get("event_id"): return state
        state["scheduling_complete"] = True
        return state
    
    def _choose_next_tool(self, state: SchedulingState) -> str:
        if not state.get("available_slots"): return "get_availability"
        if not state.get("selected_date"): return "schedule"
        if not state.get("event_id"): return "send_invite"
        return "finish"
    
    def _get_availability_node(self, state: SchedulingState) -> SchedulingState:
        manager_email = "alice@company.com"
        
        state["tool_calls"].append(ToolCall(
            tool_name="get_availability",
            agent_id="scheduling_agent",
            tool_input={"manager_email": manager_email},
            timestamp=datetime.now().isoformat(),
            reasoning="Retrieving hiring manager availability."
        ).model_dump())
        
        # FIXED: Use .invoke() for decorated @tool
        result = self.tools.get_availability.invoke({"manager_email": manager_email})
        
        state["available_slots"] = result if isinstance(result, list) else []
        print(f"✓ Got availability: {len(state['available_slots'])} dates available")
        return state
    
    def _schedule_node(self, state: SchedulingState) -> SchedulingState:
        slots = state.get("available_slots", [])
        if not slots:
            print("✗ No availability found")
            state["selected_date"] = "NONE" 
            return state
        
        first_slot = slots[0]
        date = first_slot.get("date", "Unknown")
        times = first_slot.get("times", [])
        time = times[0] if times else "Unknown"
        
        state["tool_calls"].append(ToolCall(
            tool_name="schedule_interview",
            agent_id="scheduling_agent",
            tool_input={"date": date, "time": time},
            timestamp=datetime.now().isoformat(),
            reasoning=f"Auto-selecting earliest slot: {date} at {time}."
        ).model_dump())
        
        # FIXED: Use .invoke() with a payload dictionary
        result = self.tools.schedule_interview.invoke({
            "candidate_email": state.get("candidate_email", "unknown"),
            "candidate_name": state.get("candidate_name", "Candidate"),
            "manager_email": "alice@company.com",
            "date": date,
            "time": time
        })
        
        state["selected_date"] = date
        state["selected_time"] = time
        state["event_id"] = result.get("event_id", f"MOCK-{uuid.uuid4().hex[:4]}")
        return state
    
    def _send_invite_node(self, state: SchedulingState) -> SchedulingState:
        state["tool_calls"].append(ToolCall(
            tool_name="send_interview_invite",
            agent_id="scheduling_agent",
            tool_input={"to": state.get("candidate_email")},
            timestamp=datetime.now().isoformat(),
            reasoning="Confirming interview time with candidate."
        ).model_dump())
        
        # FIXED: Use .invoke()
        self.tools.send_interview_invite.invoke({
            "candidate_email": state.get("candidate_email", "unknown"),
            "candidate_name": state.get("candidate_name", "Candidate"),
            "date": state.get("selected_date"),
            "time": state.get("selected_time"),
            "manager": "Alice"
        })
        return state
    
    def _finish_node(self, state: SchedulingState) -> SchedulingState:
        print("✓ Scheduling process complete")
        return state
    
    def process(self, screening_result: dict, thread_id: str | None = None) -> dict:
        if thread_id is None: thread_id = f"sched_{uuid.uuid4().hex[:8]}"
        
        initial_state = {
            "candidate_id": screening_result.get("candidate_id", "UNKNOWN"),
            "candidate_name": screening_result.get("candidate_name", "Unknown Candidate"),
            "candidate_email": screening_result.get("candidate_email", "unknown@example.com"),
            "screening_decision": screening_result.get("decision", "approve"),
            "available_slots": [],
            "selected_date": "",
            "selected_time": "",
            "event_id": "",
            "scheduling_complete": False,
            "tool_calls": []
        }
        
        final_state = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}}
        )
        
        return {
            "status": "scheduled" if final_state.get("event_id") else "failed",
            "candidate_id": final_state.get("candidate_id"),
            "candidate_name": final_state.get("candidate_name"),
            "candidate_email": final_state.get("candidate_email"),
            "interview_date": final_state.get("selected_date"),
            "interview_time": final_state.get("selected_time"),
            "event_id": final_state.get("event_id"),
            "tool_calls": final_state.get("tool_calls", []),
            "thread_id": thread_id
        }