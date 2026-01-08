from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.evaluation import DetailedEvaluator
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


@app.get("/api/posts/list")
def list_posts():
    """List all available posts."""
    posts = store.list_posts()
    return {
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "created_at": p.created_at,
                "comment_count": len(store.get_post_data(p.id).comments_by_id) if store.get_post_data(p.id) else 0,
                "bubble_count": len(store.get_post_data(p.id).bubbles_by_id) if store.get_post_data(p.id) else 0,
            }
            for p in posts
        ]
    }


@app.get("/api/current-state")
def get_current_state():
    """Get current state if a post exists."""
    if store.post is None:
        return {"post": None, "posts": []}
    state = store.build_state()
    posts = store.list_posts()
    return {
        **state.dict(),
        "available_posts": [
            {
                "id": p.id,
                "title": p.title,
                "created_at": p.created_at,
            }
            for p in posts
        ]
    }


@app.post("/api/posts/{post_id}/load")
def load_post(post_id: str):
    """Load a specific post as the current post."""
    if store.set_current_post(post_id):
        return store.build_state()
    raise HTTPException(status_code=404, detail="post not found")


@app.post("/api/posts")
def create_post(req: CreatePostRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="title must be non-empty")
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="body must be non-empty")
    post = store.create_post(title=req.title.strip(), body=req.body.strip(), created_at=req.created_at)
    return store.build_state()


@app.get("/api/posts/{post_id}/state")
def get_state(post_id: str):
    if not store.set_current_post(post_id):
        raise HTTPException(status_code=404, detail="post not found")
    return store.build_state()


@app.post("/api/posts/{post_id}/comments")
def add_comment(post_id: str, req: AddCommentRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")
    
    post_data = store.get_post_data(post_id)
    if not post_data:
        raise HTTPException(status_code=404, detail="post not found")
    
    if not store.set_current_post(post_id):
        raise HTTPException(status_code=404, detail="post not found")
    
    if req.reply_to_comment_id is not None and req.reply_to_comment_id not in post_data.comments_by_id:
        raise HTTPException(status_code=400, detail="reply_to_comment_id invalid")

    created_at = req.created_at or now_iso_utc()
    
    if req.embedding:
        embedding = req.embedding
    else:
        embedding = {"vector": [], "dim": 0, "model": "", "hash": ""}
    
    c = Comment(
        id=new_id(),
        post_id=post_id,
        created_at=created_at,
        author=req.author,
        text=req.text.strip(),
        reply_to_comment_id=req.reply_to_comment_id,
        embedding=embedding,
        assigned_bubble_id=None,
        assigned_bubble_version_id=None,
    )
    
    post_data.comments_by_id[c.id] = c

    try:
        edge, run, next_lane = pipeline.process_new_comment(
            post_id=post_id,
            comment=c,
            comments_by_id=post_data.comments_by_id,
            bubbles_by_id=post_data.bubbles_by_id,
            bubble_versions_by_id=post_data.bubble_versions_by_id,
            next_lane=post_data.next_lane,
            post_title=post_data.post.title,
            post_body=post_data.post.body,
        )
        post_data.next_lane = next_lane
        if edge is not None:
            post_data.bubble_edges.append(edge)
        post_data.pipeline_runs.append(run)
    except Exception as e:
        del post_data.comments_by_id[c.id]
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return store.build_state()


@app.get("/api/posts/{post_id}/evaluate")
def evaluate_post_endpoint(post_id: str):
    """Get detailed evaluation report for a post."""
    if not store.set_current_post(post_id):
        raise HTTPException(status_code=404, detail="post not found")
    
    state = store.build_state()
    post_data = store.get_post_data(post_id)
    pipeline_runs = post_data.pipeline_runs if post_data else []
    
    evaluator = DetailedEvaluator(threshold=0.58)
    report = evaluator.evaluate(state, pipeline_runs)
    
    from dataclasses import asdict
    
    return {
        "clustering_decisions": [asdict(d) for d in report.clustering_decisions],
        "bubble_analyses": [asdict(a) for a in report.bubble_analyses],
        "threshold_analysis": report.threshold_analysis,
        "recommendations": report.recommendations,
        "metrics_summary": report.metrics_summary
    }
