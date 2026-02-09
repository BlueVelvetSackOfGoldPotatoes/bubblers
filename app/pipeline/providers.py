from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Literal, Tuple

from app.models import BubbleVersion, Comment, Embedding

VoteType = Literal["agree", "disagree", "pass"]


class EmbeddingProvider(ABC):

    @abstractmethod
    def embed(self, text: str) -> Embedding: ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[Embedding]: ...

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class Labeler(ABC):

    @abstractmethod
    def label(
        self, bubble_version: BubbleVersion, comments_by_id: Dict[str, Comment]
    ) -> Tuple[str, str, float, List[str]]:
        """Returns (label, essence, confidence, representative_comment_ids)."""
        ...


class Voter(ABC):

    @abstractmethod
    def classify(self, post_title: str, post_body: str, comment_text: str) -> VoteType: ...
