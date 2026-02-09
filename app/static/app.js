let state = null;
let selectedBubbleVersionId = null;
let rawMode = false;
let appConfig = null;

const els = {
  postTitle: document.getElementById("postTitle"),
  postBody: document.getElementById("postBody"),
  postCreatedAt: document.getElementById("postCreatedAt"),
  postAdvancedToggle: document.getElementById("postAdvancedToggle"),
  postAdvanced: document.getElementById("postAdvanced"),
  createPostBtn: document.getElementById("createPostBtn"),
  postMeta: document.getElementById("postMeta"),
  postSelector: document.getElementById("postSelector"),

  authorName: document.getElementById("authorName"),
  commentText: document.getElementById("commentText"),
  commentCreatedAt: document.getElementById("commentCreatedAt"),
  commentAdvancedToggle: document.getElementById("commentAdvancedToggle"),
  commentAdvanced: document.getElementById("commentAdvanced"),
  addCommentBtn: document.getElementById("addCommentBtn"),
  status: document.getElementById("status"),

  commentFeed: document.getElementById("commentFeed"),
  timeline: document.getElementById("timeline"),
  inspector: document.getElementById("inspector"),

  rawToggle: document.getElementById("rawToggle"),
};

function esc(s) {
  if (typeof s !== "string") return "";
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function datetimeLocalToISO(datetimeLocal) {
  if (!datetimeLocal) return null;
  const dt = new Date(datetimeLocal);
  if (isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

async function createPost() {
  els.status.textContent = "";
  els.postMeta.textContent = "Creating...";
  const payload = {
    title: els.postTitle.value,
    body: els.postBody.value,
  };
  const customDate = datetimeLocalToISO(els.postCreatedAt.value);
  if (customDate) {
    payload.created_at = customDate;
  }
  const res = await fetch("/api/posts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "unknown error" }));
    els.postMeta.textContent = "Error: " + (err.detail || "unknown");
    return;
  }
  state = await res.json();
  selectedBubbleVersionId = null;
  els.postMeta.textContent = `Post created: ${state.post.id}`;
  els.postCreatedAt.value = "";
  els.postAdvanced.style.display = "none";
  await loadPostList();
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
  const payload = {
    author: { id: "demo-user", display_name: els.authorName.value || "You" },
    text,
    reply_to_comment_id: null,
  };
  const customDate = datetimeLocalToISO(els.commentCreatedAt.value);
  if (customDate) {
    payload.created_at = customDate;
  }
  const res = await fetch(`/api/posts/${state.post.id}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "unknown error" }));
    els.status.textContent = "Error: " + (err.detail || "unknown");
    return;
  }
  state = await res.json();
  els.commentText.value = "";
  els.commentCreatedAt.value = "";
  els.commentAdvanced.style.display = "none";
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
    const vote = c.vote ? `<span class="vote-badge vote-${c.vote}">${esc(c.vote)}</span>` : "";
    return `
      <div class="feed-item">
        <div class="meta">
          <span>${esc(c.author?.display_name || "Anon")}</span>
          <span>•</span>
          <span>${esc(fmtTime(c.created_at))}</span>
          ${vote}
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

  const commentsById = {};
  for (const c of (state.comments || [])) commentsById[c.id] = c;
  
  const bubbleDivs = bvs.map(bv => {
    const p = posPx[bv.id];
    if (!p) return "";
    const isSelected = bv.id === selectedBubbleVersionId;
    const pxSize = Math.max(42, 20 + p.size * 14);
    const left = p.x;
    const top = p.y;
    const label = bv.label || "…";
    const commentCount = bv.comment_ids.length;
    
    const votes = { agree: 0, disagree: 0, pass: 0 };
    for (const cid of bv.comment_ids) {
      const comment = commentsById[cid];
      if (comment && comment.vote) {
        votes[comment.vote] = (votes[comment.vote] || 0) + 1;
      }
    }
    const totalVotes = votes.agree + votes.disagree + votes.pass;
    const voteSummary = totalVotes > 0 
      ? `✓${votes.agree} ✗${votes.disagree} ○${votes.pass}`
      : `${commentCount} comment(s)`;
    
    const border = isSelected ? "border-color:#94a3b8;" : "";
    const confidenceColor = bv.confidence > 0.7 ? "#10b981" : bv.confidence > 0.4 ? "#f59e0b" : "#ef4444";
    return `
      <div class="bubble" data-bvid="${esc(bv.id)}" style="left:${left}px;top:${top}px;min-width:${pxSize}px;${border}" title="${esc(bv.essence || label)}">
        <span class="bubble-label">${esc(label)}</span>
        <span class="sub">${esc(voteSummary)}</span>
        <span class="sub" style="font-size:10px;opacity:0.7;">conf: ${bv.confidence.toFixed(2)}</span>
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

  const votes = { agree: 0, disagree: 0, pass: 0 };
  for (const cid of bv.comment_ids) {
    const comment = commentsById[cid];
    if (comment && comment.vote) {
      votes[comment.vote] = (votes[comment.vote] || 0) + 1;
    }
  }
  const totalVotes = votes.agree + votes.disagree + votes.pass;
  const voteSummary = totalVotes > 0 
    ? `<div class="vote-summary">
         <span class="vote-badge vote-agree">✓ ${votes.agree} agree</span>
         <span class="vote-badge vote-disagree">✗ ${votes.disagree} disagree</span>
         <span class="vote-badge vote-pass">○ ${votes.pass} pass</span>
       </div>`
    : "";

  els.inspector.innerHTML = `
    <div>
      <div class="pill">bubble: ${esc(bv.bubble_id.slice(0, 8))}</div>
      <div class="pill" style="background: ${bv.confidence > 0.7 ? 'rgba(16, 185, 129, 0.2)' : bv.confidence > 0.4 ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)'}; border-color: ${bv.confidence > 0.7 ? '#10b981' : bv.confidence > 0.4 ? '#f59e0b' : '#ef4444'};">confidence: ${esc(bv.confidence.toFixed(2))}</div>
      <div class="pill">${esc(bv.comment_ids.length)} comments</div>
      <div class="pill">window end: ${esc(fmtTime(bv.window?.end_at || bv.created_at))}</div>
    </div>

    <h3>Label</h3>
    <div style="font-weight:600;color:#f3f4f6;">${esc(bv.label || "")}</div>

    <h3>Essence</h3>
    <div style="white-space:pre-wrap;color:#d1d5db;">${esc(bv.essence || "")}</div>

    ${voteSummary}

    <h3>Representative comments</h3>
    <div class="list">${repHtml}</div>

    <h3>All comments in bubble</h3>
    <div class="list">${allHtml}</div>
  `;
}

function renderCommentCard(c) {
  const vote = c.vote ? `<span class="vote-badge vote-${c.vote}">${esc(c.vote)}</span>` : "";
  return `
    <div class="list-item">
      <div class="meta">
        <span>${esc(c.author?.display_name || "Anon")}</span>
        <span>•</span>
        <span>${esc(fmtTime(c.created_at))}</span>
        ${vote}
      </div>
      <div class="text">${esc(c.text)}</div>
    </div>
  `;
}

async function loadPostList() {
  try {
    const res = await fetch("/api/posts/list");
    if (res.ok) {
      const data = await res.json();
      const posts = data.posts || [];
      
      els.postSelector.innerHTML = '<option value="">Select conversation...</option>';
      posts.forEach(p => {
        const option = document.createElement("option");
        option.value = p.id;
        option.textContent = `${p.title} (${p.comment_count} comments, ${p.bubble_count} bubbles)`;
        els.postSelector.appendChild(option);
      });
      
      if (posts.length > 0 && !state?.post) {
        els.postSelector.value = posts[0].id;
        await loadPost(posts[0].id);
      }
    }
  } catch (e) {
    console.log("Error loading post list:", e);
  }
}

async function loadPost(postId) {
  if (!postId) return;
  
  try {
    const res = await fetch(`/api/posts/${postId}/load`, { method: "POST" });
    if (res.ok) {
      state = await res.json();
      els.postSelector.value = postId;
      selectedBubbleVersionId = null;
      renderAll();
      els.postMeta.textContent = `Loaded: ${state.post.title}`;
    }
  } catch (e) {
    console.log("Error loading post:", e);
  }
}

async function loadCurrentState() {
  try {
    const res = await fetch("/api/current-state");
    if (res.ok) {
      const data = await res.json();
      if (data.post) {
        state = data;
        els.postSelector.value = data.post.id;
        renderAll();
        els.postMeta.textContent = `Loaded: ${state.post.title}`;
      }
    }
  } catch (e) {
    console.log("No existing post");
  }
  await loadPostList();
}

els.createPostBtn.addEventListener("click", () => createPost());
els.addCommentBtn.addEventListener("click", () => addComment());
els.rawToggle.addEventListener("click", () => {
  rawMode = !rawMode;
  els.rawToggle.textContent = rawMode ? "Raw mode: On" : "Raw mode: Off";
  renderAll();
});

els.postAdvancedToggle.addEventListener("click", () => {
  const isVisible = els.postAdvanced.style.display !== "none";
  els.postAdvanced.style.display = isVisible ? "none" : "block";
  els.postAdvancedToggle.textContent = isVisible ? "⚙️ Set custom date/time" : "⚙️ Hide date/time";
});

els.commentAdvancedToggle.addEventListener("click", () => {
  const isVisible = els.commentAdvanced.style.display !== "none";
  els.commentAdvanced.style.display = isVisible ? "none" : "block";
  els.commentAdvancedToggle.textContent = isVisible ? "⚙️ Set custom date/time" : "⚙️ Hide date/time";
});

els.postSelector.addEventListener("change", async (e) => {
  const postId = e.target.value;
  if (postId) {
    await loadPost(postId);
  }
});

// Chat elements
const chatCard = document.getElementById("chatCard");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      appConfig = await res.json();
      const indicator = document.getElementById("modeIndicator");
      if (appConfig.mode === "llm") {
        indicator.textContent = "LLM mode \u2014 GPT-powered clustering and labeling";
        indicator.style.color = "#10b981";
      } else {
        indicator.textContent = "Local mode \u2014 sentence-transformers + VADER (no API key)";
        indicator.style.color = "#f59e0b";
      }
      if (appConfig.has_chat && chatCard) {
        chatCard.style.display = "block";
      }
    }
  } catch (e) {
    console.log("Error loading config:", e);
  }
}

async function sendChatMessage() {
  if (!state?.post?.id) return;
  const msg = chatInput.value.trim();
  if (!msg) return;

  appendChatMessage("user", msg);
  chatInput.value = "";
  chatSendBtn.disabled = true;

  try {
    const res = await fetch(`/api/posts/${state.post.id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    if (res.ok) {
      const data = await res.json();
      appendChatMessage("assistant", data.reply);
    } else {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      appendChatMessage("assistant", "Error: " + (err.detail || "Unknown error"));
    }
  } catch (e) {
    appendChatMessage("assistant", "Error: Could not reach server.");
  }

  chatSendBtn.disabled = false;
}

function appendChatMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chat-message ${role}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

if (chatSendBtn) {
  chatSendBtn.addEventListener("click", sendChatMessage);
}
if (chatInput) {
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
}

loadConfig();
loadCurrentState();
renderAll();
