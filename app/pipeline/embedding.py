from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from app.models import Embedding
from app.utils import sha256_hex


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    model: str = "mock-embed-v1"
    dim: int = 64


class MockEmbeddingProvider:
    """
    Deterministic embedding provider for demo use.

    Args:
        config: EmbeddingProviderConfig controlling model name and dimension.

    Returns:
        Embedding objects with stable vectors derived from text.
    """

    def __init__(self, config: EmbeddingProviderConfig) -> None:
        self._config = config

    def embed(self, text: str) -> Embedding:
        h = sha256_hex(f"{self._config.model}:{text}")
        seed = int(h[:16], 16)
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self._config.dim)]
        return Embedding(vector=vec, dim=self._config.dim, model=self._config.model, hash=h)
