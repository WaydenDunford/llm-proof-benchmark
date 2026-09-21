"""Backend lifecycle: one adapter owns one model at a time."""
from abc import ABC, abstractmethod
import gc
import sys
from ..schemas import Generation, GenerationOutput, ModelConfig


class Adapter(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config

    def load(self) -> None:
        """Load resources, if required."""

    @abstractmethod
    def generate(self, prompt: str, settings: Generation) -> GenerationOutput:
        """Generate only the completion, excluding the input prompt."""

    def unload(self) -> None:
        gc.collect()
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
