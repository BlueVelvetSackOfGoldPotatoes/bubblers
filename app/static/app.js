let state = null;
let selectedBubbleVersionId = null;
let rawMode = false;

const els = {
  postTitle: document.getElementById("postTitle"),
  postBody: document.getElementById("postBody"),
  createPostBtn: document.getElementById("createPostBtn"),
  postMeta: document.getElementById("postMeta"),

  authorName: document.getElementById("authorName"),
  commentText: document.getElementById("commentText"),
  addCommentBtn: document.getElementById("addCommentBtn"),
  status: document.getElementById("status"),

  commentFeed: document.getElementById("commentFeed"),
  timeline: document.getElementById("timeline"),
  inspector: document.getElementById("inspector"),

  rawToggle: document.getElementById("rawToggle"),
};

function esc(s) {
  return s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

async function createPost() {
  els.status.textContent = "";
  els.postMeta.textContent = "Creating...";
  const res = await fetch("/api/posts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: els.postTitle.value, body: els.postBody.value }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "unknown error" }));
    els.postMeta.textContent = "Error: " + (err.detail || "unknown");
    return;
  }
  state = await res.json();
  selectedBubbleVersionId = null;
  els.postMeta.textContent = `Post created: ${state.post.id}`;
  renderAll();
}

async function addComment() {
  if (!state?.post?.id) {
    els.status.textContent = "Create a post first.";
    return;
  }
  const text = els.commentText.value.trim();
  if (!text) {
    els.status.textContent = "Write a comment first.";
    return;
  }
  els.status.textContent = "Adding...";
  const res = await fetch(`/api/posts/${state.post.id}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      author: { id: "demo-user", display_name: els.authorName.value || "You" },
      text,
      reply_to_comment_id: null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "unknown error" }));
    els.status.textContent = "Error: " + (err.detail || "unknown");
    return;
  }
  state = await res.json();
  els.commentText.value = "";
  els.status.textContent = "Added.";
  if (!selectedBubbleVersionId) {
    const latest = latestBubbleVersionByCreatedAt(state.bubble_versions);
    if (latest) selectedBubbleVersionId = latest.id;
  }
  renderAll();
}

function latestBubbleVersionByCreatedAt(bvs) {
  if (!bvs?.length) return null;
  let best = bvs[0];
  for (const x of bvs) {
    if (x.created_at > best.created_at) best = x;
  }
  return best;
}

function renderAll() {
  if (!state) {
    els.commentFeed.innerHTML = "";
    els.timeline.innerHTML = "";
    els.inspector.innerHTML = `<div class="muted">Create a post to begin.</div>`;
    return;
  }
  renderComments();
  if (rawMode) {
    els.timeline.innerHTML = `<div class="muted" style="padding:10px;">Raw mode enabled. Timeline hidden.</div>`;
    els.inspector.innerHTML = `<div class="muted">Raw mode enabled. Inspector hidden.</div>`;
  } else {
    renderTimeline();
    renderInspector();
  }
}

function renderComments() {
  const items = state.comments || [];
  if (!items.length) {
    els.commentFeed.innerHTML = `<div class="muted">No comments yet.</div>`;
    return;
  }
  els.commentFeed.innerHTML = items.map(c => {
    const bubble = c.assigned_bubble_id ? `<span class="pill">bubble: ${esc(c.assigned_bubble_id.slice(0, 8))}</span>` : "";
    return `
      <div class="feed-item">
        <div class="meta">
          <span>${esc(c.author?.display_name || "Anon")}</span>
          <span>•</span>
          <span>${esc(fmtTime(c.created_at))}</span>
        </div>
        <div class="text">${esc(c.text)}</div>
        <div style="margin-top:8px;">${bubble}</div>
      </div>
    `;
  }).join("");
}

function renderTimeline() {
  const positions = state.ui_hints?.layout?.bubble_version_positions || {};
  const bvs = state.bubble_versions || [];
  const edges = state.bubble_edges || [];

  const laneHeight = 70;
  const topPad = 20;
  const leftPad = 40;
  const xScale = 60;

  let maxLane = 0;
  let maxT = 0;
  for (const [id, pos] of Object.entries(positions)) {
    maxLane = Math.max(maxLane, pos.lane);
    maxT = Math.max(maxT, pos.t);
  }

  const width = leftPad + (maxT + 2) * xScale;
  const height = Math.max(520, topPad + (maxLane + 2) * laneHeight);

  const posPx = {};
  for (const [id, pos] of Object.entries(positions)) {
    const x = leftPad + pos.t * xScale;
    const y = topPad + pos.lane * laneHeight;
    posPx[id] = { x, y, size: pos.size };
  }

  const edgeDivs = edges.map(e => {
    const a = posPx[e.from_bubble_version_id];
    const b = posPx[e.to_bubble_version_id];
    if (!a || !b) return "";
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.sqrt(dx*dx + dy*dy);
    const angle = Math.atan2(dy, dx) * 180 / Math.PI;
    const left = a.x + 20;
    const top = a.y + 18;
    return `<div class="edge" style="left:${left}px;top:${top}px;width:${len}px;transform:rotate(${angle}deg);"></div>`;
  }).join("");

  const bubbleDivs = bvs.map(bv => {
    const p = posPx[bv.id];
    if (!p) return "";
    const isSelected = bv.id === selectedBubbleVersionId;
    const pxSize = Math.max(42, 20 + p.size * 14);
    const left = p.x;
    const top = p.y;
    const label = bv.label || "…";
    const sub = `${bv.comment_ids.length} comment(s)`;
    const border = isSelected ? "border-color:#94a3b8;" : "";
    return `
      <div class="bubble" data-bvid="${esc(bv.id)}" style="left:${left}px;top:${top}px;min-width:${pxSize}px;${border}">
        <span>${esc(label)}</span>
        <span class="sub">${esc(sub)}</span>
      </div>
    `;
  }).join("");

  els.timeline.innerHTML = `
    <div class="timeline-inner" style="width:${width}px;height:${height}px;">
      ${edgeDivs}
      ${bubbleDivs}
    </div>
  `;

  for (const el of els.timeline.querySelectorAll(".bubble")) {
    el.addEventListener("click", () => {
      selectedBubbleVersionId = el.getAttribute("data-bvid");
      renderTimeline();
      renderInspector();
    });
  }
}

function renderInspector() {
  if (!selectedBubbleVersionId) {
    els.inspector.innerHTML = `<div class="muted">Click a bubble to inspect it.</div>`;
    return;
  }
  const bv = (state.bubble_versions || []).find(x => x.id === selectedBubbleVersionId);
  if (!bv) {
    els.inspector.innerHTML = `<div class="muted">Bubble version not found.</div>`;
    return;
  }
  const commentsById = {};
  for (const c of (state.comments || [])) commentsById[c.id] = c;

  const reps = (bv.representative_comment_ids || []).map(cid => commentsById[cid]).filter(Boolean);
  const all = (bv.comment_ids || []).map(cid => commentsById[cid]).filter(Boolean);

  const repHtml = reps.length ? reps.map(c => renderCommentCard(c)).join("") : `<div class="muted">No representatives.</div>`;
  const allHtml = all.length ? all.map(c => renderCommentCard(c)).join("") : `<div class="muted">No comments.</div>`;

  els.inspector.innerHTML = `
    <div>
      <div class="pill">bubble: ${esc(bv.bubble_id.slice(0, 8))}</div>
      <div class="pill">confidence: ${esc(bv.confidence.toFixed(2))}</div>
      <div class="pill">window end: ${esc(fmtTime(bv.window?.end_at || bv.created_at))}</div>
    </div>

    <h3>Label</h3>
    <div>${esc(bv.label || "")}</div>

    <h3>Essence</h3>
    <div style="white-space:pre-wrap;">${esc(bv.essence || "")}</div>

    <h3>Representative comments</h3>
    <div class="list">${repHtml}</div>

    <h3>All comments in bubble</h3>
    <div class="list">${allHtml}</div>
  `;
}

function renderCommentCard(c) {
  return `
    <div class="list-item">
      <div class="meta">
        <span>${esc(c.author?.display_name || "Anon")}</span>
        <span>•</span>
        <span>${esc(fmtTime(c.created_at))}</span>
        <span>•</span>
        <span>${esc(c.id.slice(0, 8))}</span>
      </div>
      <div class="text">${esc(c.text)}</div>
    </div>
  `;
}

els.createPostBtn.addEventListener("click", () => createPost());
els.addCommentBtn.addEventListener("click", () => addComment());
els.rawToggle.addEventListener("click", () => {
  rawMode = !rawMode;
  els.rawToggle.textContent = rawMode ? "Raw mode: On" : "Raw mode: Off";
  renderAll();
});

renderAll();
