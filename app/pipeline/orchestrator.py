from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, PipelineRun, PipelineRunLabeler, PipelineClusterDecision
from app.pipeline.clusterer import ClustererConfig, OnlineClusterer
from app.pipeline.providers import EmbeddingProvider, Labeler, Voter
from app.utils import new_id, now_iso_utc

load_dotenv()


@dataclass(frozen=True)
class PipelineConfig:
    mode: str = "auto"  # "auto" | "llm" | "local"
    assign_threshold: Optional[float] = None  # None = auto per mode
    embedding_dim: Optional[int] = None
    embedding_model: Optional[str] = None
    labeler_mode: str = "live"


def _detect_mode(config: PipelineConfig) -> str:
    if config.mode == "llm":
        return "llm"
    if config.mode == "local":
        return "local"
    return "llm" if os.getenv("GPT_KEY") else "local"


class Pipeline:
    """
    End-to-end pipeline for embedding, clustering, and labeling.
    Auto-detects LLM vs local mode based on GPT_KEY environment variable.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        config = config or PipelineConfig()
        self._config = config
        self._mode = _detect_mode(config)

        if self._mode == "llm":
            from app.pipeline.embedding import EmbeddingProviderConfig, GPTEmbeddingProvider
            from app.pipeline.labeler import LabelerConfig, GPTLabeler
            from app.pipeline.voter import GPTVoter, VoterConfig

            self._effective_model = config.embedding_model or "text-embedding-3-small"
            self._effective_dim = config.embedding_dim or 1536
            self._effective_threshold = config.assign_threshold if config.assign_threshold is not None else 0.58

            self._embedder: EmbeddingProvider = GPTEmbeddingProvider(
                EmbeddingProviderConfig(model=self._effective_model, dim=self._effective_dim)
            )
            self._labeler: Labeler = GPTLabeler(LabelerConfig(mode=config.labeler_mode))
            self._voter: Voter = GPTVoter(VoterConfig())
        else:
            from app.pipeline.local_embedding import LocalEmbeddingConfig, LocalEmbeddingProvider
            from app.pipeline.local_labeler import LocalLabeler
            from app.pipeline.local_voter import LocalVoter

            self._effective_model = config.embedding_model or "all-MiniLM-L6-v2"
            self._effective_dim = config.embedding_dim or 384
            self._effective_threshold = config.assign_threshold if config.assign_threshold is not None else 0.45

            self._embedder = LocalEmbeddingProvider(
                LocalEmbeddingConfig(model_name=self._effective_model, dim=self._effective_dim)
            )
            self._labeler = LocalLabeler()
            self._voter = LocalVoter()

        self._clusterer = OnlineClusterer(ClustererConfig(
            assign_threshold=self._effective_threshold,
            embedding_model=self._effective_model,
            embedding_dim=self._effective_dim,
        ))

        print(f"[pipeline] Mode: {self._mode} | Model: {self._effective_model} | Threshold: {self._effective_threshold}")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def has_chat(self) -> bool:
        return self._mode == "llm"

    def process_new_comment(
        self,
        post_id: str,
        comment: Comment,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, Bubble],
        bubble_versions_by_id: Dict[str, BubbleVersion],
        next_lane: int,
        post_title: str = "",
        post_body: str = "",
    ) -> Tuple[Optional[BubbleEdge], PipelineRun, int]:
        if not comment.embedding.vector or comment.embedding.dim == 0:
            comment.embedding = self._embedder.embed(comment.text)

        if post_title and post_body and not comment.vote:
            comment.vote = self._voter.classify(post_title, post_body, comment.text)

        assigned_bubble_id, sim, created_new, _, new_bv, edge, next_lane = self._clusterer.assign(
            post_id=post_id,
            comment=comment,
            comments_by_id=comments_by_id,
            bubbles_by_id=bubbles_by_id,
            bubble_versions_by_id=bubble_versions_by_id,
            next_lane=next_lane,
        )

        label, essence, confidence, rep_ids = self._labeler.label(new_bv, comments_by_id)
        new_bv.label = label
        new_bv.essence = essence
        new_bv.confidence = float(confidence)
        new_bv.representative_comment_ids = rep_ids

        run = PipelineRun(
            id=new_id(),
            post_id=post_id,
            comment_id=comment.id,
            created_at=now_iso_utc(),
            embedding_model=self._effective_model,
            cluster_decision=PipelineClusterDecision(
                assigned_bubble_id=assigned_bubble_id,
                similarity_to_assigned=float(sim),
                threshold=float(self._effective_threshold),
                created_new_bubble=bool(created_new),
            ),
            labeler=PipelineRunLabeler(
                mode="live",
                representative_comment_ids=rep_ids,
            ),
        )

        return edge, run, next_lane
