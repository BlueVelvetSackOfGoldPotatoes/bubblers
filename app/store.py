from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, Post, PostState, PostStateUiHints, PostStateUiHintsLayout, BubblePosition, PipelineRun
from app.utils import new_id, now_iso_utc


@dataclass
class InMemoryPostStore:
    post: Optional[Post] = None
    comments_by_id: Dict[str, Comment] = None
    bubbles_by_id: Dict[str, Bubble] = None
    bubble_versions_by_id: Dict[str, BubbleVersion] = None
    bubble_edges: List[BubbleEdge] = None
    pipeline_runs: List[PipelineRun] = None
    next_lane: int = 0

    def __post_init__(self) -> None:
        if self.comments_by_id is None:
            self.comments_by_id = {}
        if self.bubbles_by_id is None:
            self.bubbles_by_id = {}
        if self.bubble_versions_by_id is None:
            self.bubble_versions_by_id = {}
        if self.bubble_edges is None:
            self.bubble_edges = []
        if self.pipeline_runs is None:
            self.pipeline_runs = []

    def reset(self) -> None:
        self.post = None
        self.comments_by_id = {}
        self.bubbles_by_id = {}
        self.bubble_versions_by_id = {}
        self.bubble_edges = []
        self.pipeline_runs = []
        self.next_lane = 0

    def create_post(self, title: str, body: str) -> Post:
        self.reset()
        p = Post(id=new_id(), created_at=now_iso_utc(), title=title, body=body)
        self.post = p
        return p

    def list_comments(self) -> List[Comment]:
        return sorted(self.comments_by_id.values(), key=lambda c: c.created_at)

    def list_bubbles(self) -> List[Bubble]:
        return sorted(self.bubbles_by_id.values(), key=lambda b: b.created_at)

    def list_bubble_versions(self) -> List[BubbleVersion]:
        return sorted(self.bubble_versions_by_id.values(), key=lambda bv: bv.created_at)

    def build_state(self) -> PostState:
        if self.post is None:
            raise ValueError("No post exists")

        comments = self.list_comments()
        comment_index = {c.id: i for i, c in enumerate(comments)}

        positions = {}
        for bv in self.list_bubble_versions():
            idxs = [comment_index[cid] for cid in bv.comment_ids if cid in comment_index]
            t = float(max(idxs)) if idxs else 0.0
            bubble = self.bubbles_by_id.get(bv.bubble_id)
            lane = bubble.lane if bubble else 0
            size = (len(bv.comment_ids) ** 0.5) if bv.comment_ids else 1.0
            positions[bv.id] = BubblePosition(lane=lane, t=t, size=float(size))

        ui_hints = PostStateUiHints(layout=PostStateUiHintsLayout(bubble_version_positions=positions))

        return PostState(
            post=self.post,
            comments=comments,
            bubbles=self.list_bubbles(),
            bubble_versions=self.list_bubble_versions(),
            bubble_edges=list(self.bubble_edges),
            ui_hints=ui_hints,
        )
