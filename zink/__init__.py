# SPDX-License-Identifier: Apache-2.0
"""
zink/__init__.py
----------------
Public API surface.

    from zink import Zink

    zink = Zink()
    tool = zink.govern("agent_name", "path/to/config.yaml")(my_tool)
    tool = zink.govern_langchain("agent_name", "path/to/config.yaml", lc_tool)
"""

import os
from typing import Callable

from zink.config.loader import load_agent_config
from zink.store.sqlite import ZinkStore
from zink.engine import ZinkEngine
from zink.adapters.base import create_governed_callable


class Zink:

    def __init__(self, store_path: str | None = None) -> None:
        self._store_path = (
            store_path
            or os.getenv("ZINK_STORE_PATH", "zink_store.db")
        )

    def govern(
        self,
        agent_name: str,
        config_path: str,
        context_fn: Callable[[], dict] | None = None,
    ) -> Callable:
        """
        Returns a decorator that wraps any callable.

        Usage:
            @zink.govern("agent", "config.yaml")
            def my_tool(**kwargs): ...

            # or:
            my_tool = zink.govern("agent", "config.yaml")(my_tool)
        """
        cfg = load_agent_config(config_path)
        store = ZinkStore(self._store_path)
        engine = ZinkEngine(cfg, store)

        def decorator(fn: Callable) -> Callable:
            return create_governed_callable(
                fn=fn,
                engine=engine,
                agent_name=agent_name,
                resource_name=fn.__name__,
                context_fn=context_fn,
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
        store = ZinkStore(self._store_path)
        engine = ZinkEngine(cfg, store)

        return GovernedTool(
            tool=tool,
            engine=engine,
            agent_name=agent_name,
            context_fn=context_fn,
        )