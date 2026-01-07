from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import AddCommentRequest, Comment, CreatePostRequest
from app.pipeline.orchestrator import Pipeline, PipelineConfig
from app.store import InMemoryPostStore
from app.utils import new_id, now_iso_utc


app = FastAPI(title="Comment Bubbles MVP", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

store = InMemoryPostStore()
pipeline = Pipeline(PipelineConfig())


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.post("/api/posts")
def create_post(req: CreatePostRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="title must be non-empty")
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="body must be non-empty")
    post = store.create_post(title=req.title.strip(), body=req.body.strip())
    return store.build_state()


@app.get("/api/posts/{post_id}/state")
def get_state(post_id: str):
    if store.post is None or store.post.id != post_id:
        raise HTTPException(status_code=404, detail="post not found")
    return store.build_state()


@app.post("/api/posts/{post_id}/comments")
def add_comment(post_id: str, req: AddCommentRequest):
    if store.post is None or store.post.id != post_id:
        raise HTTPException(status_code=404, detail="post not found")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")
    if req.reply_to_comment_id is not None and req.reply_to_comment_id not in store.comments_by_id:
        raise HTTPException(status_code=400, detail="reply_to_comment_id invalid")

    c = Comment(
        id=new_id(),
        post_id=post_id,
        created_at=now_iso_utc(),
        author=req.author,
        text=req.text.strip(),
        reply_to_comment_id=req.reply_to_comment_id,
        embedding={"vector": [], "dim": 0, "model": "", "hash": ""},
        assigned_bubble_id=None,
        assigned_bubble_version_id=None,
    )

    store.comments_by_id[c.id] = c

    edge, run, next_lane = pipeline.process_new_comment(
        post_id=post_id,
        comment=c,
        comments_by_id=store.comments_by_id,
        bubbles_by_id=store.bubbles_by_id,
        bubble_versions_by_id=store.bubble_versions_by_id,
        next_lane=store.next_lane,
    )
    store.next_lane = next_lane
    if edge is not None:
        store.bubble_edges.append(edge)
    store.pipeline_runs.append(run)

    return store.build_state()
