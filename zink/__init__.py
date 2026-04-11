# SPDX-License-Identifier: Apache-2.0
"""
zink/__init__.py
----------------
Public API surface.

    from zink import Zink

    # Decorator style (single tool, explicit config path):
    zink = Zink(store_path="zink.db")
    tool = zink.govern("agent_name", "path/to/config.yaml")(my_tool)

    # List style (multiple tools, config resolved from config_dir):
    zink = Zink("path/to/configs/")
    governed = zink.govern("agent_name", [tool1, tool2], context=lambda: {...})

    # LangChain single tool:
    tool = zink.govern_langchain("agent_name", "path/to/config.yaml", lc_tool)
"""

import os
from pathlib import Path
from typing import Callable

from zink.config.loader import load_agent_config
from zink.store.sqlite import ZinkStore
from zink.engine import ZinkEngine
from zink.adapters.base import create_governed_callable


class Zink:

    def __init__(
        self,
        config_dir: str | None = None,
        *,
        store_path: str | None = None,
    ) -> None:
        """
        Args:
            config_dir:  Root directory for YAML configs. When set, govern()
                         resolves agent configs automatically from agent name.
            store_path:  Path to SQLite store. Defaults to ZINK_STORE_PATH env
                         var or 'zink_store.db'.
        """
        self._config_dir = config_dir
        self._store_path = store_path or os.getenv("ZINK_STORE_PATH", "zink_store.db")
        # One shared store for the lifetime of this Zink instance.
        self._store = ZinkStore(self._store_path)

    def _resolve_config(self, agent_name: str) -> str:
        """Resolve config YAML path from agent name using config_dir."""
        if self._config_dir is None:
            raise ValueError(
                "config_dir not set — pass it to Zink('path/to/configs/') "
                "or provide an explicit config_path to govern()."
            )
        base = Path(self._config_dir)
        candidates = [
            base / "agents" / f"{agent_name}.yaml",
            base / f"{agent_name}.yaml",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            f"No config found for agent '{agent_name}' in '{self._config_dir}'. "
            f"Looked for: {[str(c) for c in candidates]}"
        )

    def _wrap_tool(
        self,
        tool,
        engine: ZinkEngine,
        agent_name: str,
        context_fn: Callable[[], dict] | None,
    ):
        """Wrap one tool — LangChain BaseTool or plain callable."""
        try:
            from langchain_core.tools import BaseTool
            if isinstance(tool, BaseTool):
                from zink.adapters.langchain import GovernedTool
                return GovernedTool(
                    tool=tool,
                    engine=engine,
                    agent_name=agent_name,
                    context_fn=context_fn,
                )
        except ImportError:
            pass
        return create_governed_callable(
            fn=tool,
            engine=engine,
            agent_name=agent_name,
            resource_name=getattr(tool, "__name__", str(tool)),
            context_fn=context_fn,
        )

    def govern(
        self,
        agent_name: str,
        tools_or_config,
        context_fn: Callable[[], dict] | None = None,
        *,
        context: Callable[[], dict] | None = None,
        resource_name: str | None = None,
    ):
        """
        Two calling conventions:

        Decorator style — pass a config path, get back a decorator:
            @zink.govern("agent", "config.yaml")
            def my_tool(**kwargs): ...

            my_tool = zink.govern("agent", "config.yaml", resource_name="ec2.launch_instance")(fn)

        List style — pass a list of tools, get back a governed list:
            governed = zink.govern("agent", [tool1, tool2], context=lambda: {...})
        """
        effective_context = context_fn or context

        if isinstance(tools_or_config, list):
            config_path = self._resolve_config(agent_name)
            cfg = load_agent_config(config_path)
            engine = ZinkEngine(cfg, self._store)
            return [self._wrap_tool(t, engine, agent_name, effective_context) for t in tools_or_config]

        # Decorator style — tools_or_config is a config path string.
        cfg = load_agent_config(tools_or_config)
        engine = ZinkEngine(cfg, self._store)

        def decorator(fn: Callable) -> Callable:
            return create_governed_callable(
                fn=fn,
                engine=engine,
                agent_name=agent_name,
                resource_name=resource_name or getattr(fn, "__name__", str(fn)),
                context_fn=effective_context,
            )

        return decorator

    def govern_langchain(
        self,
        agent_name: str,
        config_path: str,
        tool,
        context_fn: Callable[[], dict] | None = None,
    ):
        """
        Wraps a LangChain BaseTool with Zink enforcement.
        Lazy import — langchain_core only imported if this method is called.
        """
        from zink.adapters.langchain import GovernedTool

        cfg = load_agent_config(config_path)
        engine = ZinkEngine(cfg, self._store)

        return GovernedTool(
            tool=tool,
            engine=engine,
            agent_name=agent_name,
            context_fn=context_fn,
        )