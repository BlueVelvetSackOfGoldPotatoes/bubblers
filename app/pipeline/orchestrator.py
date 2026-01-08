from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, PipelineRun, PipelineRunLabeler, PipelineClusterDecision
from app.pipeline.clusterer import ClustererConfig, OnlineClusterer
from app.pipeline.embedding import EmbeddingProviderConfig, GPTEmbeddingProvider
from app.pipeline.labeler import LabelerConfig, GPTLabeler
from app.pipeline.voter import GPTVoter, VoterConfig
from app.utils import new_id, now_iso_utc


@dataclass(frozen=True)
class PipelineConfig:
    assign_threshold: float = 0.58
    embedding_dim: int = 1536
    embedding_model: str = "text-embedding-3-small"
    labeler_mode: str = "live"


class Pipeline:
    """
    End-to-end pipeline for embedding, clustering, and labeling.

    Args:
        config: PipelineConfig controlling the model settings and thresholds.

    Returns:
        Updated store objects plus a PipelineRun record.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._embedder = GPTEmbeddingProvider(EmbeddingProviderConfig(model=config.embedding_model, dim=config.embedding_dim))
        self._clusterer = OnlineClusterer(ClustererConfig(assign_threshold=config.assign_threshold, embedding_model=config.embedding_model, embedding_dim=config.embedding_dim))
        self._labeler = GPTLabeler(LabelerConfig(mode=config.labeler_mode))
        self._voter = GPTVoter(VoterConfig())

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
            embedding_model=self._config.embedding_model,
            cluster_decision=PipelineClusterDecision(
                assigned_bubble_id=assigned_bubble_id,
                similarity_to_assigned=float(sim),
                threshold=float(self._config.assign_threshold),
                created_new_bubble=bool(created_new),
            ),
            labeler=PipelineRunLabeler(
                mode="live",
                representative_comment_ids=rep_ids,
            ),
        )

        return edge, run, next_lane
