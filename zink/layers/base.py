# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/base.py
-------------------
Abstract base class for all Zink layers.

Every layer must implement evaluate().
Stateful layers (L4, L6, L8) should implement post_execute().
Stateless layers ignore post_execute() — the default does nothing.
"""

from abc import abstractmethod, ABC
from typing import Any
from zink.schemas import ValidationRequest, LayerResult

class Layer(ABC):
    name: str  # subclasses must set this as a class attribute

    @abstractmethod
    def evaluate(self, request: ValidationRequest)->LayerResult:
        """
        Pre-execution check. Called before tool.invoke().
        Return BLOCK to stop the pipeline.
        Return FLAG to continue but mark as suspicious.
        Return PASS to continue cleanly.
        """

    def post_execute(self, request:ValidationRequest, outcome:Any)-> None:
        """
        Post-execution hook. Called after tool.invoke() succeeds.
        Stateful layers override this to write back outcomes.
        Stateless layers leave this as-is — it does nothing.

        outcome: whatever the tool returned. None if tool was blocked.
        """
        pass
    
