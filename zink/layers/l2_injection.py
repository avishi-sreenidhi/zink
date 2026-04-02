import re
from zink.schemas import ValidationRequest, LayerResult, LayerStatus
from zink.layers.base import Layer

class InjectionDetect(Layer):
    name = "l2_injection"

    def __init__(self, custom_patterns: list[str] = None, context_field: str = "prompt_text"):
        """
        Compile injection patterns at init time (once), not at eval time.

        Args:
            custom_patterns: Optional list of regex patterns to add 
            context_field: Key to read from request.context (default: "prompt_text")
        """
        self._context_field = context_field

        default_patterns = [
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
            r"you\s+(are|'re)\s+now",
            r"disregard\s+your|forget\s+your",
            r"new\s+persona|act\s+as",
            r"pretend\s+you\s+have\s+no|pretend\s+you\s+are",
            r"from\s+now\s+on\s+you",
            r"your\s+previous\s+instructions",
        ]

        if custom_patterns:
            default_patterns.extend(custom_patterns)

        self._patterns = [re.compile(pattern, re.IGNORECASE) for pattern in default_patterns]

    def evaluate(self, request: ValidationRequest)-> LayerResult:
        text = request.context.get(self._context_field)

        if not text:
            return LayerResult(
                status= LayerStatus.PASS,
                layer = self.name,
            )

        for pattern in self._patterns:
            if pattern.search(text):
                return LayerResult(
                    status= LayerStatus.BLOCK,
                    layer= self.name,
                    reason = f"Injection pattern detected: '{pattern.pattern}'"
                )
        
        return LayerResult(
            status = LayerStatus.PASS,
            layer=self.name
        )

    
    
