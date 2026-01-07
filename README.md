# Comment Bubbles MVP (Dummy Showcase)

A small FastAPI app that demonstrates:

- Create a post
- Add comments
- Comments are embedded (deterministic mock), clustered into bubbles, and labeled (deterministic mock)
- Click bubbles to drill into underlying comments
- Bubble timeline updates as comments arrive

This is a **dummy showcase**: the pipeline is real and end-to-end runnable, but embeddings and labeling are mocked for determinism.

## Requirements

- Python 3.11+ recommended

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- http://127.0.0.1:8000

## API

- `POST /api/posts` { "title": "...", "body": "..." }
- `POST /api/posts/{post_id}/comments` { "author": {"id":"...", "display_name":"..."}, "text":"...", "reply_to_comment_id": null }
- `GET /api/posts/{post_id}/state`

## Notes

- In-memory store only. Restart resets state.
- Deterministic mock embeddings and labeling for consistent demos.
