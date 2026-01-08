from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from datetime import datetime

from app.models import Bubble, BubbleEdge, BubbleVersion, Comment, Post, PostState, PostStateUiHints, PostStateUiHintsLayout, BubblePosition, PipelineRun
from app.utils import new_id, now_iso_utc


@dataclass
class PostData:
    post: Post
    comments_by_id: Dict[str, Comment]
    bubbles_by_id: Dict[str, Bubble]
    bubble_versions_by_id: Dict[str, BubbleVersion]
    bubble_edges: List[BubbleEdge]
    pipeline_runs: List[PipelineRun]
    next_lane: int


class InMemoryPostStore:
    _posts: Dict[str, PostData] = {}
    _current_post_id: Optional[str] = None

    def __init__(self) -> None:
        if not hasattr(self, '_posts'):
            self._posts = {}
        if not hasattr(self, '_current_post_id'):
            self._current_post_id = None

    @property
    def post(self) -> Optional[Post]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].post
        return None

    @property
    def comments_by_id(self) -> Dict[str, Comment]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].comments_by_id
        return {}

    @property
    def bubbles_by_id(self) -> Dict[str, Bubble]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].bubbles_by_id
        return {}

    @property
    def bubble_versions_by_id(self) -> Dict[str, BubbleVersion]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].bubble_versions_by_id
        return {}

    @property
    def bubble_edges(self) -> List[BubbleEdge]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].bubble_edges
        return []

    @property
    def pipeline_runs(self) -> List[PipelineRun]:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].pipeline_runs
        return []

    @property
    def next_lane(self) -> int:
        if self._current_post_id and self._current_post_id in self._posts:
            return self._posts[self._current_post_id].next_lane
        return 0

    @next_lane.setter
    def next_lane(self, value: int) -> None:
        if self._current_post_id and self._current_post_id in self._posts:
            self._posts[self._current_post_id].next_lane = value

    def list_posts(self) -> List[Post]:
        """List all available posts."""
        return [data.post for data in self._posts.values()]

    def get_post_data(self, post_id: str) -> Optional[PostData]:
        """Get post data by ID."""
        return self._posts.get(post_id)

    def set_current_post(self, post_id: str) -> bool:
        """Set the current active post."""
        if post_id in self._posts:
            self._current_post_id = post_id
            return True
        return False

    def create_post(self, title: str, body: str, created_at: str | None = None) -> Post:
        post_id = new_id()
        p = Post(id=post_id, created_at=created_at or now_iso_utc(), title=title, body=body)
        
        post_data = PostData(
            post=p,
            comments_by_id={},
            bubbles_by_id={},
            bubble_versions_by_id={},
            bubble_edges=[],
            pipeline_runs=[],
            next_lane=0
        )
        
        self._posts[post_id] = post_data
        self._current_post_id = post_id
        return p

    def list_comments(self) -> List[Comment]:
        if self._current_post_id and self._current_post_id in self._posts:
            return sorted(self._posts[self._current_post_id].comments_by_id.values(), key=lambda c: c.created_at)
        return []

    def list_bubbles(self) -> List[Bubble]:
        if self._current_post_id and self._current_post_id in self._posts:
            return sorted(self._posts[self._current_post_id].bubbles_by_id.values(), key=lambda b: b.created_at)
        return []

    def list_bubble_versions(self) -> List[BubbleVersion]:
        if self._current_post_id and self._current_post_id in self._posts:
            return sorted(self._posts[self._current_post_id].bubble_versions_by_id.values(), key=lambda bv: bv.created_at)
        return []
    
    def _parse_time(self, iso_str: str) -> float:
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            return 0.0

    def build_state(self) -> PostState:
        if self.post is None:
            raise ValueError("No post exists")

        comments = self.list_comments()
        comment_index = {c.id: i for i, c in enumerate(comments)}
        
        post_time = self._parse_time(self.post.created_at)
        comment_times = {c.id: self._parse_time(c.created_at) for c in comments}
        
        if comment_times:
            min_time = min(comment_times.values())
            max_time = max(comment_times.values())
            time_range = max_time - min_time if max_time > min_time else 1.0
        else:
            min_time = post_time
            time_range = 1.0

        positions = {}
        for bv in self.list_bubble_versions():
            if bv.comment_ids:
                times = [comment_times.get(cid, post_time) for cid in bv.comment_ids if cid in comment_times]
                if times:
                    latest_time = max(times)
                    t = (latest_time - min_time) / time_range if time_range > 0 else 0.0
                else:
                    t = 0.0
            else:
                t = 0.0
            
            bubble = self.bubbles_by_id.get(bv.bubble_id) if self._current_post_id and self._current_post_id in self._posts else None
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
