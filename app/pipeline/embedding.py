from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

from app.models import Embedding
from app.utils import sha256_hex

load_dotenv()


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    model: str = "text-embedding-3-small"
    dim: int = 1536


class GPTEmbeddingProvider:
    """
    OpenAI embedding provider using GPT embedding models.

    Args:
        config: EmbeddingProviderConfig controlling model name and dimension.

    Returns:
        Embedding objects with vectors from OpenAI API.
    """

    def __init__(self, config: EmbeddingProviderConfig) -> None:
        self._config = config
        api_key = os.getenv("GPT_KEY")
        if not api_key:
            raise ValueError("GPT_KEY not found in environment variables")
        self._client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> Embedding:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        text = text.strip()
        if len(text) > 8000:
            text = text[:8000]
        
        try:
            response = self._client.embeddings.create(
                model=self._config.model,
                input=text,
                dimensions=self._config.dim,
            )
            vec = response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {str(e)}") from e
        
        h = sha256_hex(f"{self._config.model}:{text}")
        return Embedding(vector=vec, dim=self._config.dim, model=self._config.model, hash=h)
    
    def embed_batch(self, texts: List[str]) -> List[Embedding]:
        """
        Generate embeddings for multiple texts in a single API call.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            List of Embedding objects in the same order as input texts.
        """
        if not texts:
            return []
        
        processed_texts = []
        for text in texts:
            if not text or not text.strip():
                raise ValueError("Text cannot be empty in batch")
            t = text.strip()
            if len(t) > 8000:
                t = t[:8000]
            processed_texts.append(t)
        
        try:
            response = self._client.embeddings.create(
                model=self._config.model,
                input=processed_texts,
                dimensions=self._config.dim,
            )
            
            embeddings = []
            for i, text in enumerate(processed_texts):
                vec = response.data[i].embedding
                h = sha256_hex(f"{self._config.model}:{text}")
                embeddings.append(Embedding(vector=vec, dim=self._config.dim, model=self._config.model, hash=h))
            
            return embeddings
        except Exception as e:
            raise RuntimeError(f"Failed to generate batch embeddings: {str(e)}") from e
