from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Author(BaseModel):
    id: str
    display_name: str


class Embedding(BaseModel):
    vector: List[float]
    dim: int
    model: str
    hash: str


class Post(BaseModel):
    id: str
    created_at: str
    title: str
    body: str


class Comment(BaseModel):
    id: str
    post_id: str
    created_at: str
    author: Author
    text: str
    reply_to_comment_id: Optional[str] = None

    embedding: Embedding

    assigned_bubble_id: Optional[str] = None
    assigned_bubble_version_id: Optional[str] = None


class Bubble(BaseModel):
    id: str
    post_id: str
    created_at: str
    is_active: bool = True
    lane: int
    latest_bubble_version_id: Optional[str] = None


class TimeWindow(BaseModel):
    start_at: str
    end_at: str


class BubbleVersion(BaseModel):
    id: str
    bubble_id: str
    post_id: str

    created_at: str
    window: TimeWindow

    label: str
    essence: str
    confidence: float

    comment_ids: List[str] = Field(default_factory=list)
    representative_comment_ids: List[str] = Field(default_factory=list)

    centroid_embedding: Embedding


class BubbleEdge(BaseModel):
    id: str
    post_id: str
    from_bubble_version_id: str
    to_bubble_version_id: str
    type: Literal["continue", "split_from", "merge_from"]
    weight: float


class BubblePosition(BaseModel):
    lane: int
    t: float
    size: float


class PostStateUiHintsLayout(BaseModel):
    bubble_version_positions: Dict[str, BubblePosition] = Field(default_factory=dict)


class PostStateUiHints(BaseModel):
    layout: PostStateUiHintsLayout


class PostState(BaseModel):
    post: Post
    comments: List[Comment]
    bubbles: List[Bubble]
    bubble_versions: List[BubbleVersion]
    bubble_edges: List[BubbleEdge]
    ui_hints: PostStateUiHints


class CreatePostRequest(BaseModel):
    title: str
    body: str


class AddCommentRequest(BaseModel):
    author: Author
    text: str
    reply_to_comment_id: Optional[str] = None


class PipelineClusterDecision(BaseModel):
    assigned_bubble_id: str
    similarity_to_assigned: float
    threshold: float
    created_new_bubble: bool


class PipelineRunLabeler(BaseModel):
    mode: Literal["mocked", "live"]
    representative_comment_ids: List[str]


class PipelineRun(BaseModel):
    id: str
    post_id: str
    comment_id: str
    created_at: str
    embedding_model: str
    cluster_decision: PipelineClusterDecision
    labeler: PipelineRunLabeler
