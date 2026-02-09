from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models import Embedding
from app.pipeline.providers import EmbeddingProvider
from app.utils import sha256_hex


@dataclass(frozen=True)
class LocalEmbeddingConfig:
    model_name: str = "all-MiniLM-L6-v2"
    dim: int = 384


class LocalEmbeddingProvider(EmbeddingProvider):
    """sentence-transformers based embedding provider."""

    def __init__(self, config: LocalEmbeddingConfig | None = None) -> None:
        self._config = config or LocalEmbeddingConfig()
        self._model = None  # lazy-loaded

    def _load_model(self):
        if self._model is None:
            print(f"[local] Loading embedding model '{self._config.model_name}' (first time may download ~90 MB)...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._config.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return self._config.dim

    @property
    def model_name(self) -> str:
        return self._config.model_name

    def embed(self, text: str) -> Embedding:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        text = text.strip()[:8000]
        model = self._load_model()
        vec = model.encode(text).tolist()
        h = sha256_hex(f"{self._config.model_name}:{text}")
        return Embedding(vector=vec, dim=self._config.dim, model=self._config.model_name, hash=h)

    def embed_batch(self, texts: List[str]) -> List[Embedding]:
        if not texts:
            return []
        processed = []
        for t in texts:
            if not t or not t.strip():
                raise ValueError("Text cannot be empty in batch")
            processed.append(t.strip()[:8000])
        model = self._load_model()
        vecs = model.encode(processed).tolist()
        results = []
        for text, vec in zip(processed, vecs):
            h = sha256_hex(f"{self._config.model_name}:{text}")
            results.append(Embedding(vector=vec, dim=self._config.dim, model=self._config.model_name, hash=h))
        return results
