from pathlib import Path
from typing import Callable, Optional
from zink.config.loader import load_agent_config
from zink.config.parser import ConfigError
from zink.schemas import (
    AgentConfig,
    ScopeEntry,
    DeniedEntry,
    Constraint,
    ValidationRequest,
    LayerStatus,
    LayerResult,
    ValidationResult,
    build_result,
)
from zink.engine import ZinkEngine
from zink.adapters import GovernedTool

__all__ = [
    "load_agent_config",
    "ConfigError",
    "AgentConfig",
    "ScopeEntry",
    "DeniedEntry",
    "Constraint",
    "ValidationRequest",
    "LayerStatus",
    "LayerResult",
    "ValidationResult",
    "build_result",
    "ZinkEngine",
    "GovernedTool"
]

class Zink:
    """
    Single entry point. Developer imports only this.
    
    Usage:
        zink = Zink("./configs/")
        governed_tools = zink.govern(
            "screening_agent",
            [extract_resume, score_candidate],
            context=lambda: {"hour": datetime.now().hour}
        )
    """

    def __init__(self, config_dir: str):
        self._config_dir = Path(config_dir)

        domain_configs = list(self._config_dir.glob("*.zink.yaml"))
        if not domain_configs:
            raise ConfigError(f"No domain config found in {config_dir} — expected a *.zink.yaml file")
        if len(domain_configs)>1:
            raise ConfigError(f"Multiple config files found in {config_dir} - expected exaclty one.")
        self._domain_config_path= domain_configs[0]

    def govern(self, agent_name: str, tools: list, context: Optional[Callable] = None) -> list:
        agent_config_path = self._config_dir / "agents" / f"{agent_name}.yaml"

        if not agent_config_path.exists():
            raise ConfigError(f"No config found for agent '{agent_name}' — "
                f"expected {agent_config_path}")
        
        cfg = load_agent_config(agent_config_path)
        engine = ZinkEngine(cfg)
        
        return [
            GovernedTool(tool,engine, agent_name, context_fn=context) for tool in tools
        ]
