from zink.schemas import AgentConfig, ValidationRequest, ValidationResult, build_result
from zink.config.parser import ConfigError
from zink.layers import Layer, InjectionDetect, ScopeCheck

class ZinkEngine:
    """
    holds the layer registry, builds the pipeline, 
    exposes one validate() endpoint. 
    Every tool call flows through here.
    """

    def __init__(self, agent_cfg: AgentConfig):
        self._agent_cfg = agent_cfg
        self._layers: list[Layer] = []
        self.build_layers()
        
    def build_layers(self)-> None:
        """ Instantiate layers from config in order """
        custom_patterns = self._agent_cfg.injection_patterns.get("custom", [])
        registry = {
            "l2_injection": lambda: InjectionDetect(custom_patterns=custom_patterns),
            "l9_scope":     lambda: ScopeCheck(self._agent_cfg),
        }

        for layer_name in self._agent_cfg.default_layers:
            if layer_name not in registry:
                raise ConfigError(f"Layer '{layer_name}' is not implemented yet")
            self._layers.append(registry[layer_name]())

    def validate(self, request:ValidationRequest)->ValidationResult:
        """
        Run request through all layers.
        First BLOCK stops everything.
        All PASS/FLAG → approved.
        """
        results = []
        for layer in self._layers:
            result = layer.evaluate(request)
            results.append(result)

            if result.blocked:
                return build_result(results)
            
        return build_result(results)

