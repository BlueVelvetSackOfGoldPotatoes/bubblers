from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.evaluation import DetailedEvaluator
from app.models import AddCommentRequest, Comment, CreatePostRequest, PostState
from app.pipeline.orchestrator import Pipeline, PipelineConfig
from app.store import InMemoryPostStore
from app.utils import new_id, now_iso_utc


store = InMemoryPostStore()
pipeline = Pipeline(PipelineConfig())

# In-memory chat history per post
chat_histories: Dict[str, List[dict]] = {}


def _auto_load_sample_data() -> None:
    """Load tests.txt sample data if no posts exist."""
    if store.list_posts():
        return

    sample_file = Path("tests.txt")
    if not sample_file.exists():
        print("[startup] No sample data file (tests.txt) found, starting empty.")
        return

    print("[startup] Loading sample data from tests.txt...")
    from app.reddit_parser import RedditParser

    parser = RedditParser()
    text = sample_file.read_text(encoding="utf-8")
    reddit_post, reddit_comments = parser.parse(text)

    post = store.create_post(
        title=reddit_post.title,
        body=reddit_post.body,
        created_at=reddit_post.created_at,
    )
    post_id = post.id
    post_data = store.get_post_data(post_id)

    loaded = 0
    for rc in reddit_comments:
        c = Comment(
            id=new_id(),
            post_id=post_id,
            created_at=rc.created_at,
            author=rc.author,
            text=rc.text,
            reply_to_comment_id=rc.reply_to_comment_id,
            embedding={"vector": [], "dim": 0, "model": "", "hash": ""},
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
            loaded += 1
            if loaded % 5 == 0:
                print(f"  [startup] Processed {loaded}/{len(reddit_comments)} comments...")
        except Exception as e:
            del post_data.comments_by_id[c.id]
            print(f"  [startup] Skipped comment: {e}")

    print(f"[startup] Loaded {loaded} comments into '{reddit_post.title}'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _auto_load_sample_data()
    yield


app = FastAPI(title="Comment Bubbles MVP", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/config")
def get_config():
    return {
        "mode": pipeline.mode,
        "has_chat": pipeline.has_chat,
        "embedding_model": pipeline._effective_model,
        "embedding_dim": pipeline._effective_dim,
        "threshold": pipeline._effective_threshold,
    }


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

    evaluator = DetailedEvaluator(threshold=pipeline._effective_threshold)
    report = evaluator.evaluate(state, pipeline_runs)

    from dataclasses import asdict

    return {
        "clustering_decisions": [asdict(d) for d in report.clustering_decisions],
        "bubble_analyses": [asdict(a) for a in report.bubble_analyses],
        "threshold_analysis": report.threshold_analysis,
        "recommendations": report.recommendations,
        "metrics_summary": report.metrics_summary
    }


# --------------- Chat ---------------

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


def _build_chat_context(state: PostState) -> str:
    """Build a system prompt with full conversation context."""
    comments_by_id = {c.id: c for c in state.comments}
    bv_by_id = {bv.id: bv for bv in state.bubble_versions}

    lines = [
        "You are a helpful assistant that answers questions about an online conversation.",
        "Below is the full context of the conversation including the original post, all comments,",
        "and the AI-generated bubble clusters with their labels.",
        "",
        "## Original Post",
        f"Title: {state.post.title}",
        f"Body: {state.post.body}",
        "",
        f"## Comments ({len(state.comments)} total)",
    ]

    for i, c in enumerate(state.comments, 1):
        vote_str = f" [Vote: {c.vote}]" if c.vote else ""
        lines.append(f"{i}. {c.author.display_name}: {c.text}{vote_str}")

    lines.append("")
    lines.append(f"## Bubble Clusters ({len(state.bubbles)} bubbles)")

    for bubble in state.bubbles:
        if not bubble.latest_bubble_version_id:
            continue
        bv = bv_by_id.get(bubble.latest_bubble_version_id)
        if not bv:
            continue

        votes = {"agree": 0, "disagree": 0, "pass": 0}
        for cid in bv.comment_ids:
            c = comments_by_id.get(cid)
            if c and c.vote:
                votes[c.vote] += 1

        lines.append(f"### Bubble: {bv.label}")
        lines.append(f"Essence: {bv.essence}")
        lines.append(f"Comments: {len(bv.comment_ids)} | Votes: {votes['agree']} agree, {votes['disagree']} disagree, {votes['pass']} pass")
        for cid in bv.comment_ids:
            c = comments_by_id.get(cid)
            if c:
                lines.append(f"  - {c.author.display_name}: {c.text[:200]}")
        lines.append("")

    lines.append("Answer questions about this conversation. You can summarize themes,")
    lines.append("identify areas of agreement/disagreement, find specific comments, etc.")

    return "\n".join(lines)


@app.post("/api/posts/{post_id}/chat")
def chat_about_post(post_id: str, req: ChatRequest):
    if not pipeline.has_chat:
        raise HTTPException(
            status_code=400,
            detail="Chat is only available in LLM mode. Set GPT_KEY in .env to enable.",
        )

    post_data = store.get_post_data(post_id)
    if not post_data:
        raise HTTPException(status_code=404, detail="post not found")

    if not store.set_current_post(post_id):
        raise HTTPException(status_code=404, detail="post not found")

    state = store.build_state()
    context = _build_chat_context(state)

    if post_id not in chat_histories:
        chat_histories[post_id] = []

    history = chat_histories[post_id]

    messages = [{"role": "system", "content": context}]
    messages.extend(history[-20:])
    messages.append({"role": "user", "content": req.message})

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("GPT_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content or "I couldn't generate a response."
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})

    return ChatResponse(reply=reply)
