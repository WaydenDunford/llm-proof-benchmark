"""Lazy factory: mock/API usage does not require torch."""
from .base import Adapter
from ..schemas import ModelConfig


def create_adapter(config: ModelConfig) -> Adapter:
    if config.backend == "mock":
        from .mock_adapter import MockAdapter
        return MockAdapter(config)
    if config.backend == "transformers":
        from .transformers_adapter import TransformersAdapter
        return TransformersAdapter(config)
    if config.backend == "vllm":
        from .vllm_adapter import VLLMAdapter
        return VLLMAdapter(config)
    from .openai_compatible_adapter import OpenAICompatibleAdapter
    return OpenAICompatibleAdapter(config)
