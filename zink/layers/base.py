from abc import abstractmethod, ABC
from zink.schemas import ValidationRequest, LayerResult

class Layer(ABC):
    name: str  # subclasses must set this as a class attribute

    @abstractmethod
    def evaluate(self, request: ValidationRequest)->LayerResult:
        pass
