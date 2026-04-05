from typing import Any, Callable, Optional
from pydantic import PrivateAttr
from langchain_core.tools import BaseTool
from zink.adapters.base import create_governed_callable
from zink.engine import ZinkEngine

class GovernedTool(BaseTool):
    """
    Wraps a LangChain/LangGraph tool with Zink enforcement.
    Preserves .name, .description, .args_schema exactly.
    Agent sees no difference.
    """
    _governed_fn: Callable = PrivateAttr()

    def __init__(self, tool: Any, engine: ZinkEngine, agent_name: str, context_fn: Optional[Callable] = None):
        super().__init__(
            name = tool.name,
            description = tool.description,
            args_schema = tool.args_schema  # type: ignore[arg-type]
        )
        self._governed_fn = create_governed_callable(tool, engine, agent_name, tool.name, context_fn)

    def _run(self, **kwargs: Any) -> Any:
        try:
            return self._governed_fn(**kwargs)
        except PermissionError as e:
            return {"zink_blocked": True, "reason": str(e)}
        
    
