"""
ScreeningAgent: Autonomous agent with structured payloads and Trace Logs.
FIXED: Universal defensive key handling to prevent KeyErrors across all nodes.
NEED TO FIX: defensive manuals checks instead of pydantic models, code quality plugin for the same? 
"""

import uuid
from zink import Zink
from datetime import datetime
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from tools.screening_tools import ScreeningTools
from models import ToolCall

class ScreeningState(TypedDict):
    resume_text: str
    extracted_resume: dict  
    candidate_score: dict   
    screening_decision: dict  
    candidate_id: str
    tool_calls: list  
    logs: list 

class ScreeningAgent:
    def __init__(self, dummy_mode: bool = False):
        self.tools = ScreeningTools()
        self.dummy_mode = dummy_mode

        self._current_prompt = ""

        zink = Zink("examples/hr_workflow/configs/")
        governed = zink.govern(
            "screening_agent",
            [
                self.tools.extract_resume,
                self.tools.score_candidate,
                self.tools.log_to_excel_tool,
                self.tools.send_email_tool,
            ],
            context=lambda: {"hour": datetime.now().hour, "prompt_text": self._current_prompt}
        )
        self.tools.extract_resume    = governed[0]
        self.tools.score_candidate   = governed[1]
        self.tools.log_to_excel_tool = governed[2]
        self.tools.send_email_tool   = governed[3]

        self.graph = self._build_graph()
    
    def _add_log(self, state: ScreeningState, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        state["logs"].append(f"[{timestamp}] {message}")

    def _build_graph(self):
        workflow = StateGraph(ScreeningState)
        workflow.add_node("decide_action", self._decide_action_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("score", self._score_node)
        workflow.add_node("reject", self._reject_node)
        workflow.add_node("escalate", self._escalate_node)
        workflow.add_node("approve", self._approve_node)
        workflow.add_node("finish", self._finish_node)
        
        workflow.add_edge(START, "decide_action")
        workflow.add_conditional_edges(
            "decide_action",
            self._choose_next_tool,
            {"extract": "extract", "score": "score", "reject": "reject", "escalate": "escalate", "approve": "approve", "finish": "finish"}
        )
        
        workflow.add_edge("extract", "decide_action")
        workflow.add_edge("score", "decide_action")
        workflow.add_edge("reject", "finish")
        workflow.add_edge("escalate", "finish")
        workflow.add_edge("approve", "finish")
        workflow.add_edge("finish", END)
        
        return workflow.compile(checkpointer=MemorySaver())

    # ====================================================================
    # NODES (WITH DEFENSIVE LOGIC)
    # ====================================================================

    def _decide_action_node(self, state: ScreeningState) -> ScreeningState:
        if not state.get("extracted_resume") or not state.get("candidate_score"): 
            return state
        
        score = state["candidate_score"].get("score", 0)
        self._add_log(state, f"BRAIN: Evaluating score {score}")

        if score < 0.6: decision = "reject"
        elif score > 0.8: decision = "approve"
        else: decision = "escalate"
            
        state["screening_decision"] = {"decision": decision, "score": score}
        return state
    
    #routing function
    def _choose_next_tool(self, state: ScreeningState) -> str:
        if not state.get("extracted_resume"): return "extract"
        if not state.get("candidate_score"): return "score"
        return state.get("screening_decision", {}).get("decision", "finish")

    def _extract_node(self, state: ScreeningState) -> ScreeningState:
        self._add_log(state, "NODE: Extracting...")
        state["tool_calls"].append(ToolCall(
            tool_name="extract_resume",
            agent_id="screening_agent",
            tool_input={"resume_text": "OMITTED"}, 
            reasoning="Extracting structured data.",
            timestamp=datetime.now().isoformat()
        ).model_dump())

        self._current_prompt = state["resume_text"]
        result = self.tools.extract_resume.invoke({"resume_text": state["resume_text"]})
        state["extracted_resume"] = result if isinstance(result, dict) else {}
        self._add_log(state, f"TRACE: Extracted {state['extracted_resume'].get('name', 'Unknown')}")
        return state
    
    def _score_node(self, state: ScreeningState) -> ScreeningState:
        extracted = state.get("extracted_resume", {})
        email = extracted.get("email", "unknown")

        tool_input = {
            "name": extracted.get("name", "Unknown"),
            "years_experience": extracted.get("years_experience", 0),
            "skills": extracted.get("skills", []),
            "education": extracted.get("education", "")
        }

        result = self.tools.score_candidate.invoke(tool_input)

        state["tool_calls"].append(ToolCall(
            tool_name="score_candidate",
            agent_id="screening_agent",
            tool_input=tool_input,
            reasoning=result.get("reasoning", ""),
            timestamp=datetime.now().isoformat()
        ).model_dump())

        state["candidate_score"] = result
        return state
    
    def _approve_node(self, state: ScreeningState) -> ScreeningState:
        self._add_log(state, "NODE: Processing Approval")
        resume = state.get("extracted_resume", {})
        score = state.get("candidate_score", {}).get("score", 0)
        email = resume.get("email") or resume.get("email_address") or "unknown@example.com"
        name = resume.get("name", "Candidate")
        
        candidate_id = f"CAND-{uuid.uuid4().hex[:4].upper()}"
        
        state["tool_calls"].append(ToolCall(
            tool_name="log_to_excel",
            agent_id="screening_agent",
            tool_input={"id": candidate_id},
            reasoning="Logging approval.",
            timestamp=datetime.now().isoformat()
        ).model_dump())
        
        self.tools.log_to_excel_tool.invoke({"candidate_id": candidate_id, "name": name, "email": email, "score": score, "decision": "approve"})
        self.tools.send_email_tool.invoke({"candidate_email": email, "candidate_name": name, "decision": "pass", "score": score})
        
        state["candidate_id"] = candidate_id
        return state

    def _reject_node(self, state: ScreeningState) -> ScreeningState:
        self._add_log(state, "NODE: Processing Rejection")
        resume = state.get("extracted_resume", {})
        score = state.get("candidate_score", {}).get("score", 0)
        # DEFENSIVE FIX: Check both 'email' and 'email_address'
        email = resume.get("email") or resume.get("email_address") or "unknown@example.com"
        name = resume.get("name", "Candidate")
        if not state.get("candidate_id"):
            state["candidate_id"] = f"CAND-{uuid.uuid4().hex[:4].upper()}"

        state["tool_calls"].append(ToolCall(
            tool_name="send_email",
            agent_id="screening_agent",
            tool_input={"to": email, "template": "reject"},
            reasoning="Sending rejection.",
            timestamp=datetime.now().isoformat()
        ).model_dump())

        self.tools.send_email_tool.invoke({"candidate_email": email, "candidate_name": name, "decision": "reject", "score": score})
        return state

    def _escalate_node(self, state: ScreeningState) -> ScreeningState:
        self._add_log(state, "NODE: Escalating...")
        resume = state.get("extracted_resume", {})
        name = resume.get("name", "Candidate")
        email = resume.get("email") or "unknown@example.com"
        score = state.get("candidate_score", {}).get("score", 0)
        if not state.get("candidate_id"):
            state["candidate_id"] = f"CAND-{uuid.uuid4().hex[:4].upper()}"

        self.tools.log_to_excel_tool.invoke({"candidate_id": "PENDING", "name": name, "email": email, "score": score, "decision": "escalate"})
        return state
    
    def _finish_node(self, state: ScreeningState) -> ScreeningState:
        self._add_log(state, "FINISH: Complete")
        return state
    
    def process(self, resume_text: str, thread_id: str | None = None) -> dict:
        """Run screening agent and return a flat dict for main.py"""
        if thread_id is None: 
            thread_id = f"screening_{uuid.uuid4().hex[:8]}"
            
        initial_state = {
            "resume_text": resume_text, 
            "extracted_resume": {}, 
            "candidate_score": {},
            "screening_decision": {}, 
            "candidate_id": "", 
            "tool_calls": [], 
            "logs": []
        }
        
        # 1. Run the Graph
        final_state = self.graph.invoke(
            initial_state, 
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # 2. Print the Trace for your eyes
        print("\n--- AGENT TRACE LOG ---")
        for log in final_state.get("logs", []): 
            print(log)
            
        # 3. Return what main.py actually wants
        # We use .get() here too, just in case
        decision_data = final_state.get("screening_decision", {})
        
        extracted = final_state.get("extracted_resume", {})
        return {
            "decision": decision_data.get("decision", "unknown"),
            "score": decision_data.get("score", 0),
            "candidate_id": final_state.get("candidate_id", ""),
            "candidate_name": extracted.get("name", "Unknown"),
            "candidate_email": extracted.get("email") or extracted.get("email_address") or "unknown@example.com",
            "tool_calls": final_state.get("tool_calls", []),
            "thread_id": thread_id
        }