from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from .types import LLMMessage, StreamChunk, ToolDefinition


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        history: List[LLMMessage],
        tools: List[ToolDefinition],
        system_instruction: str,
    ) -> AsyncIterator[StreamChunk]:
        """Return an async iterator of StreamChunks for a single generation."""
        pass
