from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, Embedding, TimeWindow
from app.utils import cosine_similarity, mean_vector, new_id, now_iso_utc, sha256_hex


@dataclass(frozen=True)
class ClustererConfig:
    assign_threshold: float = 0.72
    embedding_model: str = "mock-embed-v1"
    embedding_dim: int = 64


class OnlineClusterer:
    """
    Incremental clusterer for assigning a new comment to an existing bubble or a new bubble.

    Args:
        config: ClustererConfig controlling thresholds and embedding metadata.

    Returns:
        (assigned_bubble_id, similarity, created_new_bubble, new_bubble_version, optional_edge)
    """

    def __init__(self, config: ClustererConfig) -> None:
        self._config = config

    def assign(
        self,
        post_id: str,
        comment: Comment,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, Bubble],
        bubble_versions_by_id: Dict[str, BubbleVersion],
        next_lane: int,
    ) -> Tuple[str, float, bool, Bubble, BubbleVersion, Optional[BubbleEdge], int]:
        best_bubble_id, best_sim = self._find_best_bubble(comment.embedding, bubbles_by_id, bubble_versions_by_id)
        created_new = False

        if best_bubble_id is None or best_sim < self._config.assign_threshold:
            bubble = Bubble(id=new_id(), post_id=post_id, created_at=now_iso_utc(), is_active=True, lane=next_lane)
            bubbles_by_id[bubble.id] = bubble
            next_lane += 1
            created_new = True
            prev_version_id = None
            assigned_sim = 1.0
        else:
            bubble = bubbles_by_id[best_bubble_id]
            prev_version_id = bubble.latest_bubble_version_id
            assigned_sim = best_sim

        new_version, edge = self._create_new_version(
            post_id=post_id,
            bubble=bubble,
            prev_version_id=prev_version_id,
            comment=comment,
            comments_by_id=comments_by_id,
            bubble_versions_by_id=bubble_versions_by_id,
            similarity=assigned_sim,
        )

        bubble.latest_bubble_version_id = new_version.id
        comment.assigned_bubble_id = bubble.id
        comment.assigned_bubble_version_id = new_version.id

        return bubble.id, assigned_sim, created_new, bubble, new_version, edge, next_lane

    def _find_best_bubble(
        self,
        embedding: Embedding,
        bubbles_by_id: Dict[str, Bubble],
        bubble_versions_by_id: Dict[str, BubbleVersion],
    ) -> Tuple[Optional[str], float]:
        best_id: Optional[str] = None
        best_sim = -1.0
        for bubble in bubbles_by_id.values():
            if not bubble.is_active or not bubble.latest_bubble_version_id:
                continue
            bv = bubble_versions_by_id.get(bubble.latest_bubble_version_id)
            if not bv:
                continue
            sim = cosine_similarity(embedding.vector, bv.centroid_embedding.vector)
            if sim > best_sim:
                best_sim = sim
                best_id = bubble.id
        return best_id, best_sim

    def _create_new_version(
        self,
        post_id: str,
        bubble: Bubble,
        prev_version_id: Optional[str],
        comment: Comment,
        comments_by_id: Dict[str, Comment],
        bubble_versions_by_id: Dict[str, BubbleVersion],
        similarity: float,
    ) -> Tuple[BubbleVersion, Optional[BubbleEdge]]:
        created_at = now_iso_utc()
        if prev_version_id is None:
            comment_ids: List[str] = [comment.id]
            window = TimeWindow(start_at=created_at, end_at=created_at)
            edge = None
        else:
            prev = bubble_versions_by_id[prev_version_id]
            comment_ids = list(prev.comment_ids) + [comment.id]
            window = TimeWindow(start_at=prev.window.start_at, end_at=created_at)
            edge = BubbleEdge(
                id=new_id(),
                post_id=post_id,
                from_bubble_version_id=prev.id,
                to_bubble_version_id="",
                type="continue",
                weight=float(similarity),
            )

        centroid_vec = mean_vector(
            (comments_by_id[cid].embedding.vector for cid in comment_ids if cid in comments_by_id),
            dim=self._config.embedding_dim,
        )
        centroid_hash = sha256_hex("centroid:" + "|".join(comments_by_id[cid].embedding.hash for cid in comment_ids if cid in comments_by_id))
        centroid = Embedding(vector=centroid_vec, dim=self._config.embedding_dim, model=self._config.embedding_model, hash=centroid_hash)

        bv = BubbleVersion(
            id=new_id(),
            bubble_id=bubble.id,
            post_id=post_id,
            created_at=created_at,
            window=window,
            label="",
            essence="",
            confidence=0.0,
            comment_ids=comment_ids,
            representative_comment_ids=[],
            centroid_embedding=centroid,
        )
        bubble_versions_by_id[bv.id] = bv

        if edge is not None:
            edge.to_bubble_version_id = bv.id

        return bv, edge
