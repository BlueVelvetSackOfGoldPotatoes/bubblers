from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, PipelineRun, PipelineRunLabeler, PipelineClusterDecision
from app.pipeline.clusterer import ClustererConfig, OnlineClusterer
from app.pipeline.embedding import EmbeddingProviderConfig, MockEmbeddingProvider
from app.pipeline.labeler import LabelerConfig, MockLabeler
from app.utils import new_id, now_iso_utc


@dataclass(frozen=True)
class PipelineConfig:
    assign_threshold: float = 0.72
    embedding_dim: int = 64
    embedding_model: str = "mock-embed-v1"
    labeler_mode: str = "mocked"


class Pipeline:
    """
    End-to-end pipeline for embedding, clustering, and labeling.

    Args:
        config: PipelineConfig controlling the mock model settings and thresholds.

    Returns:
        Updated store objects plus a PipelineRun record.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._embedder = MockEmbeddingProvider(EmbeddingProviderConfig(model=config.embedding_model, dim=config.embedding_dim))
        self._clusterer = OnlineClusterer(ClustererConfig(assign_threshold=config.assign_threshold, embedding_model=config.embedding_model, embedding_dim=config.embedding_dim))
        self._labeler = MockLabeler(LabelerConfig(mode=config.labeler_mode))

    def process_new_comment(
        self,
        post_id: str,
        comment: Comment,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, Bubble],
        bubble_versions_by_id: Dict[str, BubbleVersion],
        next_lane: int,
    ) -> Tuple[Optional[BubbleEdge], PipelineRun, int]:
        comment.embedding = self._embedder.embed(comment.text)

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
                mode="mocked",
                representative_comment_ids=rep_ids,
            ),
        )

        return edge, run, next_lane
