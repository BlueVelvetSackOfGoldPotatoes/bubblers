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

# Idea

What’s been tried (and where it tends to break)
1) Classic threaded comments (tree + “most relevant” sorting)

What it solves: basic reply structure.
Where it fails: readers don’t want to traverse a deep tree; topics/arguments fork and intertwine; temporal order and topical order conflict. This is why “conversation disentanglement” is a whole research area: even identifying which sub-thread a comment “belongs to” is non-trivial in messy, real-world dialogue. 
arxiv.org
+2
jyunyu.csie.org
+2

Implication for your idea: you’re explicitly fixing the “topic vs time vs reply” mismatch by adding an abstraction layer (clusters/categories) while conserving the raw comments.

2) Argument mapping (Kialo-style pro/con trees)

What it solves: clean logical structure; great for debate and pedagogy. 
Kialo
+1

Where it fails as a general social feature: requires users to author in the structure (turn every contribution into a claim, attach it as pro/con, keep it coherent). That’s heavy friction unless the community is explicitly doing structured debate.

Implication: your system should not require structured authoring. Let people comment normally; the structure is inferred.

3) Opinion-space mapping (Pol.is)

What it solves: turns many statements into clusters by collecting votes (agree/disagree/pass) and projecting participants/statements into an opinion landscape. 
gwern.net
+1

Where it fails for “comments under a post”:

It’s a different interaction primitive: people must vote repeatedly; statements are short; it’s closer to deliberation/survey than free-form conversation. 
lesswrong.com
+1

Even fans complain the visualization can be confusing (axes/meaning unclear), which matters if you want this to be mainstream UX. 
GitHub

Implication: you want Pol.is-like clarity (clusters + exploration) without requiring voting as the core mechanic.

4) Recursive summarization systems (Wikum)

What it solves: scalable sensemaking by producing layered summaries of large discussions, while keeping drill-down to original comments. 
people.csail.mit.edu
+1

Where it fails for an MVP social feature: it relies on editorial workflow/human-in-the-loop “summarizers,” which is hard to ship as a default commenting UI.

Implication: steal the interaction contract (“summary you can drill into”), but automate most of it and only ask humans for lightweight corrections.

5) “Fix the comments” publisher platforms (Civil Comments, Coral/Talk)

What they solved: moderation + civility + newsroom workflows, not semantic organization. Civil Comments ultimately shut down (Dec 2017), and the ecosystem heavily emphasizes the operational cost and difficulty of keeping comment spaces healthy. 
Digital Content Next
+3
Coral by Vox Media Guides
+3
huggingface.co
+3

Also, “real names” or switching platforms often didn’t magically improve quality. 
Nieman Reports

Implication: if your feature increases engagement, it will also increase moderation exposure—so the MVP should include at least basic safety/misuse handling and “don’t misrepresent people” safeguards.

6) “Everything app” collaboration UIs (Google Wave lesson)

Wave is a canonical example of “too many affordances, not enough guidance,” leading to adoption failure; it also had network effects issues (useful only if others adopt). 
arstechnica.com
+1

Implication: your MVP must be one obvious workflow: “read the post → see the evolving map of interpretations → drill down → optionally correct.”

Why many attempts fail (compressed into design constraints)

Friction kills: if users must learn a formalism (argument maps) or do extra work (voting a lot), adoption drops.

Abstraction betrayal: if a cluster label misrepresents someone’s comment, users lose trust quickly.

Ambiguity is real: many comments belong to multiple themes; forcing single-category assignment feels wrong.

Concept drift over time: early clusters change meaning as new comments arrive; your UI must show evolution without gaslighting.

Moderation load scales: any system that surfaces “hot clusters” can amplify conflict unless you design throttles and safety defaults. 
Digital Content Next
+1

A better proposal (your idea, tightened into an MVP-ready concept)
Core object: “Interpretation Bubbles” over time

Each bubble is a category created from comments: a short label + a 1–3 sentence “essence” (hypothesis/impression/argument) + optional facets (stance, emotion, asked-question, evidence-cited).

The raw comments are conserved and always reachable (click bubble → list comments).

The system is explicitly temporal: bubbles appear, grow, split, merge, fade.

Key upgrade vs. prior art

Unlike Kialo, structure is inferred.

Unlike Pol.is, no voting is required (though you can optionally add quick reactions later).

Unlike Wikum, no editorial labor is required (but you allow micro-corrections).

Unlike standard threads, you provide a “map-first” reading mode.

MVP feature set (minimum to ship something testable)
A) Input

Create a post (title + body).

Add comments (free text). Replies are allowed, but MVP can treat them as just comments with a reply_to pointer.

B) Live abstraction pipeline (simple, cheap, explainable)

Embed each comment (local embedding model or API; MVP decision).

Online clustering into bubbles (incremental algorithm; allow “soft membership” later, but MVP can start with single assignment + “also relates to” suggestions).

LLM labeling for each bubble:

label: 3–7 words

essence: 1–3 sentences

why_included: bullet list of 2–4 representative paraphrases

representative_comments: 3–5 comment ids (for audit/drill-down)

Temporal linking between bubble versions:

bubble at time t links to bubble at time t+1 if centroid similarity is high

detect split/merge events and show them in UI

This “cluster → label → provenance” pattern is a known approach in long-discussion summarization work (cluster + generative labeling), and it maps well to your bubbles. 
downloads.webis.de

C) UI (the “dummy interface” behavior you asked for)

You want one screen with four panes:

Post composer / post view (top)

Comment entry + chronological feed (left)

Bubble map timeline (center)

X-axis = time (or comment index)

bubbles positioned by semantic similarity (2D layout) or simply stacked lanes (safer for MVP)

bubble size = number of comments / recent activity

edges show bubble continuity; split/merge shown as branch/join

Bubble inspector (right)

label + essence

“top comments” list (click opens full text + permalink)

“what changed” since last version (new subtheme emerged, split reason, etc.)

User correction controls (MVP-critical for trust):

“This label is wrong” → propose 2 alternative labels (LLM) + allow manual rename

“Move this comment” → reassign comment to another bubble

“Pin this comment as representative”

D) Trust & safety defaults (light but non-optional)

Every bubble shows provenance: “based on these 3 representative comments” (clickable).

A “Raw mode” toggle: chronological-only (no abstraction).

If labeling confidence is low, show “Uncertain” bubble or delay labeling until N≥k comments.

Rate limit “hot cluster” amplification (avoid turning it into a rage amplifier).

The temporal graph model (data you’ll actually need)

A practical MVP graph:

Comment

id, author_id(optional), created_at, text, reply_to(optional)

embedding

BubbleVersion

id, bubble_id, created_at_window

label, essence

comment_ids

representative_comment_ids

centroid_embedding

Edges

bubble_version_id -> bubble_version_id with type: continue|split_from|merge_from

weight = similarity / overlap

This avoids overcomplicating: you’re versioning bubbles over time instead of trying to keep one bubble object that mutates invisibly.

What to test in the MVP (so you know it’s working)

Navigation time: can a new reader answer “what are people saying?” faster than scrolling?

Fidelity complaints: how often do users say “this bubble misrepresents me?”

Stability: do labels thrash as new comments arrive? (Track rename rate + split/merge rate.)

Drill-down usage: do users actually open comments from bubbles (and do they trust what they see)?

The one design choice that will decide if it feels “real”

Make correction cheap and visible. The fastest path to trust is:

“Here’s the abstraction”

“Here’s exactly what it was derived from”

“Fix it in one click”

That’s the bridge between “LLM made up a category” and “community-validated map of the conversation.”

0) Summary: objectives, goals, subgoals
Objective

Build a dummy showcase UI that demonstrates “comments → evolving bubble categories over time” for a single post, where:

Users can create a post and add comments.

Comments are clustered into “bubbles” as they arrive.

Each bubble shows an LLM-generated label + essence (can be mocked), and clicking a bubble reveals the underlying comments.

The underlying data structures and the end-to-end workflow (ingest → embed → cluster → label → render) are real and runnable.

Goals

Demonstrate the interaction: map-first view of discussion with drill-down to raw comments.

Show temporal evolution: bubbles appear/grow; optionally split/merge.

Preserve provenance: every bubble shows which comments it summarizes.

Subgoals

Provide a clean API boundary so the “model parts” can later be swapped from mocked → real LLM/embeddings.

Keep the MVP minimal: single post, single page, simple clustering, simple timeline layout.

Non-goals (explicit)

Production-grade moderation, scalability, auth, multi-post feeds, real-time multi-user sync, perfect clustering quality, perfect summarization quality.

1) MVP scope: what engineers must implement
User-visible features (MVP)

Post composer

Title + body → “Create Post”

Comment entry

Text input → “Add Comment”

Visualization

A “bubble timeline” panel that updates as comments are added.

Bubble size reflects comment count.

Bubble label + essence displayed.

Bubble drill-down

Click bubble → show list of comments in bubble.

Show representative comments used for label.

Raw mode toggle

Toggle: “Raw chronological feed only” vs “Map view”

Minimal correctness requirements

Every added comment goes through the pipeline:

Comment created

embedding produced (can be fake but deterministic)

comment assigned to a cluster/bubble

bubble version updated

bubble label/essence generated (can be mocked but deterministic + derived from comments)

UI renders updated state

2) System architecture (dummy showcase)
Recommended architecture (simple, robust for MVP)

Single-process backend + frontend (separation keeps it realistic and extensible):

Frontend (React / Next.js or plain React)

Renders post, comments, bubble timeline, inspector.

Subscribes to state updates via polling or SSE/WebSocket.

Backend (Node/Express or FastAPI)

Holds in-memory state for the post.

Runs the pipeline on each new comment.

Exposes API endpoints for create post, add comment, fetch state.

If you want ultra-minimal: you can do everything in the frontend with in-memory state, but still implement the pipeline modules as if they were “services” with clear interfaces.

3) Data model (canonical, must be implemented as-is)
IDs and time

IDs: UUIDv4 strings.

Time: ISO-8601 strings (UTC), e.g. "2026-01-07T20:55:00Z".

3.1 Core entities
Post
{
  "id": "uuid",
  "created_at": "iso",
  "title": "string",
  "body": "string"
}

Comment
{
  "id": "uuid",
  "post_id": "uuid",
  "created_at": "iso",
  "author": { "id": "string", "display_name": "string" },
  "text": "string",
  "reply_to_comment_id": "uuid|null",

  "embedding": { "vector": "number[]", "dim": "number", "model": "string", "hash": "string" },

  "assigned_bubble_id": "uuid|null",
  "assigned_bubble_version_id": "uuid|null"
}


embedding.hash is a stable hash of (model + text) so you can cache and keep determinism in the demo.

Bubble (stable identity)
{
  "id": "uuid",
  "post_id": "uuid",
  "created_at": "iso",
  "is_active": true
}

BubbleVersion (time-sliced snapshot used by UI)
{
  "id": "uuid",
  "bubble_id": "uuid",
  "post_id": "uuid",

  "created_at": "iso",
  "window": { "start_at": "iso", "end_at": "iso" },

  "label": "string",
  "essence": "string",
  "confidence": "number",

  "comment_ids": ["uuid"],
  "representative_comment_ids": ["uuid"],

  "centroid_embedding": { "vector": "number[]", "dim": "number", "model": "string", "hash": "string" }
}

BubbleEdge (temporal graph)
{
  "id": "uuid",
  "post_id": "uuid",
  "from_bubble_version_id": "uuid",
  "to_bubble_version_id": "uuid",
  "type": "continue|split_from|merge_from",
  "weight": "number"
}

3.2 View model (what frontend consumes)
PostState (single payload to render everything)
{
  "post": { "...": "Post" },
  "comments": ["Comment"],
  "bubbles": ["Bubble"],
  "bubble_versions": ["BubbleVersion"],
  "bubble_edges": ["BubbleEdge"],
  "ui_hints": {
    "layout": {
      "bubble_version_positions": {
        "<bubble_version_id>": { "lane": "number", "t": "number", "size": "number" }
      }
    }
  }
}


t is a normalized timeline coordinate (e.g., comment index or seconds since start).

lane is an integer row for a simple, stable MVP layout (avoid UMAP/TSNE for the demo).

4) Pipeline modules (interfaces + responsibilities)

Implement these as swappable components with the same input/output types.

4.1 EmbeddingProvider

Input: comment.text
Output: Embedding (vector + metadata)

MVP implementation options:

Deterministic fake embedding: hash text → seeded PRNG → fixed-dim vector (fast, no deps).

Local embedding model (optional): e.g., a small sentence transformer.

Remote embedding API (optional): behind config.

Contract

Same input text must produce identical embedding when model unchanged.

Dim fixed, e.g. 64 or 128 for the demo.

4.2 Clusterer (online / incremental)

Input: existing bubbles + bubble_versions + new comment embedding
Output: assignment decision + updated bubbles/bubble_versions/edges

MVP algorithm (simple, deterministic):

Compute similarity between comment embedding and each active bubble’s latest centroid.

If best similarity ≥ ASSIGN_THRESHOLD, assign to that bubble.

Else create a new bubble.

Recompute centroid for the bubble version.

Required parameters

ASSIGN_THRESHOLD: e.g. cosine similarity ≥ 0.72 (tune for demo).

MIN_BUBBLE_SIZE_FOR_LABEL: e.g. 2 comments before labeling confidently.

Optional split/merge detection (nice-to-have, can be simplified):

Split: if bubble becomes internally incoherent (avg similarity to centroid drops below SPLIT_THRESHOLD), run a 2-means on its comments and create two bubbles.

Merge: if two bubble centroids become too similar (≥ MERGE_THRESHOLD), merge.

For MVP, you can skip split/merge and only do create/grow, but still keep BubbleEdge data model (edges just “continue”).

4.3 Labeler (LLM-backed or mocked)

Input: comments in bubble (or representative subset)
Output: {label, essence, confidence, representative_comment_ids}

MVP implementations:

Mock labeler (deterministic):

Extract keywords (TF-IDF-like) from bubble comments.

label = top 3 keywords in Title Case.

essence = template: “People are discussing X, focusing on Y and Z.”

confidence = min(1, log(1+n)/k) or similar.

Real LLM labeler (later):

Prompt with 3–8 representative comments and ask for label + essence + reps.

Hard requirement

Output must cite representative_comment_ids that exist in comment_ids.

5) End-to-end workflow (event-driven, must run)
5.1 Ingest comment: canonical sequence

When user submits a new comment:

Create Comment (id, timestamps, text, reply_to).

EmbeddingProvider.embed(text) → store comment.embedding.

Clusterer.assign(comment.embedding):

Decide bubble (existing or new).

Create new BubbleVersion for the affected bubble (append-only).

Create BubbleEdge from previous version → new version (type=continue, weight=similarity).

Labeler.label(bubble_version.comment_ids):

Fill in label, essence, confidence, representative_comment_ids.

Update comment.assigned_bubble_id and comment.assigned_bubble_version_id.

Emit updated PostState (or delta event) to frontend.

5.2 State update transport

Pick one:

Polling: frontend polls GET /state after each action (simplest).

SSE: backend pushes post_state_updated events.

WebSocket: overkill for MVP unless you want it.

For dummy showcase, polling is fine.

6) API specification (if using a backend)
6.1 Endpoints
Create post

POST /api/posts

{ "title": "string", "body": "string" }


Response: PostState (empty comments)

Add comment

POST /api/posts/{post_id}/comments

{ "author": { "id": "string", "display_name": "string" }, "text": "string", "reply_to_comment_id": "uuid|null" }


Response: PostState (updated)

Get state

GET /api/posts/{post_id}/state
Response: PostState

6.2 Error cases (MVP)

404 post not found

400 empty title/body/comment

400 reply_to_comment_id invalid

7) UI specification (dummy but precise)
Layout (single page)

Header

Post title/body

“New Post” button (resets state)

Left column

Comment composer

Chronological comment feed (always visible)

Center column

Bubble timeline visualization

Each bubble version rendered as a node

Edges between versions rendered as lines

Right column

Bubble inspector (selected bubble version)

Shows label, essence, counts, rep comments, full list of comments

Bubble timeline rendering rules (lane-based, stable)

t coordinate = comment index of the latest comment in that bubble version.

lane assignment:

Keep bubble in same lane across versions.

New bubbles go to the next free lane.

size = sqrt(#comments_in_bubble) or linear.

Interaction

Clicking a bubble version sets selected_bubble_version_id.

Inspector shows:

label, essence, confidence

representative comments (full text)

all comment texts in the bubble

Toggle “Raw mode”:

hides timeline + inspector; shows only chronological feed.

8) Determinism and “demo modes”

Implement a config switch:

DemoMode = MOCKED

Fake deterministic embeddings

Mock deterministic labeling

Clustering deterministic

DemoMode = LIVE (optional later)

Real embeddings + real LLM labeling

The MVP should ship with MOCKED working out of the box.

9) Logging + provenance (MVP minimal)

For each comment ingest, append a PipelineRun record (in memory) for debugging:

{
  "id": "uuid",
  "post_id": "uuid",
  "comment_id": "uuid",
  "created_at": "iso",
  "embedding_model": "string",
  "cluster_decision": {
    "assigned_bubble_id": "uuid",
    "similarity_to_assigned": "number",
    "threshold": "number",
    "created_new_bubble": "boolean"
  },
  "labeler": {
    "mode": "mocked|live",
    "representative_comment_ids": ["uuid"]
  }
}


Not required for UI, but makes the demo credible and debuggable.

10) Acceptance criteria (engineers can test against this)

Create post → state loads with empty comments and no bubbles.

Add 1 comment:

comment has embedding

one bubble exists

one bubble version exists with that comment id

label/essence filled (even if low confidence)

Add 10 comments with mixed topics:

multiple bubbles created

each new comment assigned exactly one bubble

bubble timeline updates after each comment

Clicking a bubble shows only the comments assigned to it.

Provenance is consistent:

every representative_comment_id is in that bubble version’s comment_ids.
