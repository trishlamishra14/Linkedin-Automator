/* LinkedIn Automator — dashboard frontend (vanilla JS).
   Talks to the FastAPI backend in src/api.py. */

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const state = {
  posts: [],
  trends: [],
  current: null,
  composeMode: "topic", // "topic" | "polish"
  postingMode: "manual_review",
};

const tabLabels = {
  dashboard: "Dashboard",
  compose: "Compose",
  trends: "Trends",
  setup: "Setup",
};

// =============================================================
// API helper
// =============================================================
async function api(path, options = {}) {
  const opts = { headers: { "Content-Type": "application/json" }, ...options };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

function timeAgo(iso) {
  if (!iso) return "";
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function setStatus(msg, kind = "ok") {
  const el = $("#status");
  if (!el) return;
  el.textContent = msg;
  const colorMap = {
    ok: "var(--brand-text)",
    warn: "var(--warning)",
    err: "#FCA5A5",
  };
  el.style.color = colorMap[kind] || colorMap.ok;
}

function escapeHtml(s) {
  if (s === undefined || s === null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// =============================================================
// Tab nav (sidebar + buttons with data-tab anywhere)
// =============================================================
function activate(target) {
  $$(".nav-item[data-tab]").forEach((n) => n.classList.toggle("is-active", n.dataset.tab === target));
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${target}`));
  const crumb = $("#crumbCurrent");
  if (crumb) crumb.textContent = tabLabels[target] || target;
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (target === "trends") loadTrends();
  if (target === "setup") loadProfile();
  if (target === "dashboard") refreshDashboard();
}

// every element with data-tab routes to that view
$$("[data-tab]").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    activate(el.dataset.tab);
  });
});

// New post button → Compose
const newPostBtn = $("#newPostBtn");
if (newPostBtn) newPostBtn.addEventListener("click", () => activate("compose"));

// =============================================================
// Compose mode toggle
// =============================================================
$$(".seg__btn[data-mode]").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.composeMode = btn.dataset.mode;
    $$(".seg__btn[data-mode]").forEach((b) => b.classList.toggle("is-active", b === btn));
    if (state.composeMode === "polish") {
      $("#topicLabel").textContent = "Your draft";
      $("#topic").placeholder = "Paste your rough draft. Claude will rewrite it in your voice.";
      $("#btnIdeas").style.display = "none";
    } else {
      $("#topicLabel").textContent = "Topic or angle";
      $("#topic").placeholder = "e.g. Why I stopped chaining LLMs and started routing them";
      $("#btnIdeas").style.display = "";
    }
  });
});

// =============================================================
// Health
// =============================================================
async function checkHealth() {
  try {
    const data = await api("/api/health");
    state.postingMode = data.mode;
    setStatus(`online · ${data.mode}`, "ok");
    const fs = $("#footerStatus");
    if (fs) fs.textContent = "All systems operational";
    const pm = $("#postingMode");
    if (pm) pm.textContent = data.mode;
  } catch {
    setStatus("offline", "err");
    const fs = $("#footerStatus");
    if (fs) fs.textContent = "Server offline";
  }
}

// =============================================================
// Dashboard
// =============================================================
function setGreeting() {
  const greetEl = $("#dashboardGreeting");
  const dateEl = $("#dashboardDate");
  if (!greetEl) return;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const name = $("#profileName")?.textContent || "";
  greetEl.textContent = name && name !== "Not connected" ? `${greeting}, ${name.split(" ")[0]}` : `${greeting}`;
  const opts = { weekday: "long", month: "long", day: "numeric" };
  dateEl.textContent = new Date().toLocaleDateString(undefined, opts);
}

async function refreshDashboard() {
  setGreeting();

  // Counts from posts list
  const published = state.posts.filter((p) => p.status === "published").length;
  const scheduled = state.posts.filter((p) => p.status === "scheduled").length;
  const drafts = state.posts.filter((p) => p.status === "draft").length;
  $("#statPublished").textContent = String(published);
  $("#statScheduled").textContent = String(scheduled);
  $("#statDrafts").textContent = String(drafts);
  $("#statScheduledDelta").textContent = scheduled === 0 ? "no posts queued" : "in queue";
  $("#statDraftsDelta").textContent = drafts === 0 ? "all caught up" : "awaiting review";

  // Top trend (best relevance from cached trends)
  try {
    const data = await api("/api/trends?limit=1");
    const top = (data.trends || [])[0];
    if (top) {
      $("#statTopTrend").textContent = String(Math.round(top.relevance_score || 0));
      $("#statTopTrendDelta").textContent = `${top.source} · ${top.title.slice(0, 36)}${top.title.length > 36 ? "…" : ""}`;
    } else {
      $("#statTopTrend").textContent = "—";
      $("#statTopTrendDelta").textContent = "no trends yet · refresh in Trends";
    }
  } catch {
    /* ignore */
  }

  renderDashboardActivity();
}

function renderDashboardActivity() {
  const list = $("#dashboardActivity");
  if (!list) return;
  if (!state.posts.length) {
    list.innerHTML = `
      <li>
        <div class="activity__dot activity__dot--draft"></div>
        <div class="activity__main">
          <div class="activity__title">No posts yet</div>
          <div class="activity__sub">Open <span style="color:var(--brand-text);cursor:pointer" data-tab="compose">Compose</span> to write your first post, or <span style="color:var(--brand-text);cursor:pointer" data-tab="trends">browse Trends</span>.</div>
        </div>
      </li>`;
    // re-bind data-tab clicks added dynamically
    list.querySelectorAll("[data-tab]").forEach((el) => {
      el.addEventListener("click", () => activate(el.dataset.tab));
    });
    return;
  }
  list.innerHTML = state.posts
    .slice(0, 6)
    .map((p) => {
      const dotClass = `activity__dot--${p.status}`;
      const subParts = [];
      if (p.status === "scheduled" && p.scheduled_for) subParts.push(`scheduled for ${new Date(p.scheduled_for).toLocaleString()}`);
      if (p.status === "published" && p.linkedin_url) subParts.push("on LinkedIn");
      if (p.status === "failed" && p.error) subParts.push(p.error.slice(0, 60));
      return `
        <li data-post-id="${p.id}" style="cursor:pointer">
          <div class="activity__dot ${dotClass}"></div>
          <div class="activity__main">
            <div class="activity__title">${escapeHtml(p.topic)}</div>
            <div class="activity__sub">${subParts.join(" · ") || `status: ${p.status}`}</div>
          </div>
          <div class="activity__time">${timeAgo(p.created_at)}</div>
        </li>`;
    })
    .join("");
  list.querySelectorAll("li[data-post-id]").forEach((li) => {
    li.addEventListener("click", () => {
      const id = Number(li.dataset.postId);
      const post = state.posts.find((p) => p.id === id);
      if (post) {
        state.current = post;
        activate("compose");
        showDraft(post);
        renderHistory();
      }
    });
  });
}

// =============================================================
// Ideas
// =============================================================
$("#btnIdeas")?.addEventListener("click", async () => {
  const focus = $("#topic").value.trim() || null;
  $("#btnIdeas").disabled = true;
  setStatus("generating ideas…", "warn");
  try {
    const data = await api("/api/ideas", { method: "POST", body: { count: 5, focus } });
    renderIdeas(data.ideas || []);
    setStatus("ideas ready", "ok");
  } catch (err) {
    setStatus(`ideas failed: ${err.message}`, "err");
  } finally {
    $("#btnIdeas").disabled = false;
  }
});

function renderIdeas(ideas) {
  const wrap = $("#ideas");
  const list = $("#ideasList");
  if (!wrap || !list) return;
  list.innerHTML = "";
  if (!ideas.length) { wrap.hidden = true; return; }
  wrap.hidden = false;
  ideas.forEach((idea) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="hook">${escapeHtml(idea.hook)}</div>
      <div class="meta">
        <span>${escapeHtml(idea.format || "")}</span><span>·</span>
        <span>${escapeHtml(idea.audience || "")}</span>
      </div>`;
    li.addEventListener("click", () => {
      $("#topic").value = idea.angle || idea.hook;
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    list.appendChild(li);
  });
}

// =============================================================
// Write / polish
// =============================================================
$("#btnWrite")?.addEventListener("click", async () => {
  const topic = $("#topic").value.trim();
  if (!topic) { setStatus("topic required", "warn"); return; }
  $("#btnWrite").disabled = true;
  setStatus(state.composeMode === "polish" ? "polishing draft…" : "writing post…", "warn");
  try {
    const data = await api("/api/posts/write", {
      method: "POST",
      body: { topic, polish: state.composeMode === "polish" },
    });
    state.current = data.post;
    await loadHistory();
    showDraft(data.post);
    setStatus("draft ready", "ok");
  } catch (err) {
    setStatus(`write failed: ${err.message}`, "err");
  } finally {
    $("#btnWrite").disabled = false;
  }
});

// =============================================================
// Draft preview
// =============================================================
function showDraft(post) {
  $("#previewEmpty").hidden = true;
  $("#draftCard").hidden = false;
  $("#draftTopic").textContent = post.topic;
  $("#draftContent").value = post.content || "";
  $("#draftHashtags").value = post.hashtags || "";
  const chip = $("#draftStatus");
  chip.textContent = post.status;
  chip.className = `chip chip--${post.status}`;

  const imgWrap = $("#draftImage");
  if (post.image_path) {
    const filename = post.image_path.replace(/\\/g, "/").split("/").pop();
    $("#draftImageEl").src = `/api/images/${encodeURIComponent(filename)}`;
    imgWrap.hidden = false;
  } else {
    imgWrap.hidden = true;
  }
}

$("#btnSave")?.addEventListener("click", async () => {
  if (!state.current) return;
  const data = await api(`/api/posts/${state.current.id}`, {
    method: "PATCH",
    body: { content: $("#draftContent").value, hashtags: $("#draftHashtags").value },
  });
  state.current = data.post;
  await loadHistory();
  setStatus("saved", "ok");
});

$("#btnImage")?.addEventListener("click", async () => {
  if (!state.current) return;
  $("#btnImage").disabled = true;
  setStatus("generating image…", "warn");
  try {
    await api(`/api/posts/${state.current.id}/generate-image`, { method: "POST" });
    const refreshed = await api(`/api/posts/${state.current.id}`);
    state.current = refreshed.post;
    showDraft(refreshed.post);
    setStatus("image ready", "ok");
  } catch (err) {
    setStatus(`image failed: ${err.message}`, "err");
  } finally {
    $("#btnImage").disabled = false;
  }
});

$("#btnPublish")?.addEventListener("click", async () => {
  if (!state.current) return;
  if (!confirm("Publish this post to LinkedIn now?")) return;
  setStatus("publishing…", "warn");
  try {
    await api(`/api/posts/${state.current.id}/publish-now`, { method: "POST" });
    setStatus("queued for immediate publish", "ok");
    setTimeout(loadHistory, 1500);
  } catch (err) {
    setStatus(`publish failed: ${err.message}`, "err");
  }
});

$("#btnSchedule")?.addEventListener("click", async () => {
  if (!state.current) return;
  const value = $("#scheduleAt").value;
  if (!value) { setStatus("pick a date/time first", "warn"); return; }
  const fireAt = new Date(value).toISOString();
  try {
    await api(`/api/posts/${state.current.id}/schedule`, {
      method: "POST", body: { fire_at: fireAt },
    });
    setStatus("scheduled", "ok");
    await loadHistory();
  } catch (err) {
    setStatus(`schedule failed: ${err.message}`, "err");
  }
});

$("#btnDelete")?.addEventListener("click", async () => {
  if (!state.current) return;
  if (!confirm("Delete this draft?")) return;
  await api(`/api/posts/${state.current.id}`, { method: "DELETE" });
  state.current = null;
  $("#draftCard").hidden = true;
  $("#previewEmpty").hidden = false;
  await loadHistory();
});

// =============================================================
// History
// =============================================================
$("#btnRefresh")?.addEventListener("click", loadHistory);

async function loadHistory() {
  try {
    const data = await api("/api/posts");
    state.posts = data.posts || [];
    renderHistory();
    if (!$("#view-dashboard").hidden) refreshDashboard();
  } catch (err) {
    setStatus(`history failed: ${err.message}`, "err");
  }
}

function renderHistory() {
  const list = $("#historyList");
  if (!list) return;
  list.innerHTML = "";
  if (!state.posts.length) {
    list.innerHTML = `<li class="muted" style="cursor:default;list-style:none;background:transparent;border:0;padding:14px 0;">No posts yet.</li>`;
    return;
  }
  state.posts.forEach((post) => {
    const li = document.createElement("li");
    if (state.current && state.current.id === post.id) li.classList.add("is-active");
    li.innerHTML = `
      <div class="row1">
        <span class="topic">${escapeHtml(post.topic)}</span>
        <span class="chip chip--${post.status}">${post.status}</span>
      </div>
      <div class="when">${timeAgo(post.created_at)}</div>`;
    li.addEventListener("click", () => {
      state.current = post;
      showDraft(post);
      renderHistory();
    });
    list.appendChild(li);
  });
}

// =============================================================
// Profile (Setup tab + sidebar chip)
// =============================================================
$("#btnAnalyze")?.addEventListener("click", async () => {
  const url = $("#profileUrl").value.trim();
  if (!url) { setStatus("profile url required", "warn"); return; }
  $("#btnAnalyze").disabled = true;
  setStatus("scraping + analyzing… (~30-60s)", "warn");
  try {
    const data = await api("/api/profile/analyze", {
      method: "POST",
      body: { url, headless: $("#profileHeadless").checked },
    });
    renderProfile(data.analysis);
    updateProfileChip(data.analysis);
    setStatus("profile analyzed", "ok");
  } catch (err) {
    setStatus(`analysis failed: ${err.message}`, "err");
  } finally {
    $("#btnAnalyze").disabled = false;
  }
});

async function loadProfile() {
  try {
    const data = await api("/api/profile");
    if (data.profile) {
      $("#profileUrl").value = data.profile.profile_url || "";
      if (data.profile.analysis) {
        renderProfile(data.profile.analysis);
        updateProfileChip(data.profile.analysis);
      }
    }
  } catch { /* ignore */ }
}

function renderProfile(a) {
  if (!a) return;
  $("#profileResult").hidden = false;
  const kv = $("#profileKv");
  kv.innerHTML = `
    <dt>Name</dt><dd>${escapeHtml(a.name || "")}</dd>
    <dt>Headline</dt><dd>${escapeHtml(a.headline || "")}</dd>
    <dt>Niche</dt><dd>${escapeHtml(a.niche || "")}</dd>
    <dt>Audience</dt><dd>${escapeHtml(a.audience || "")}</dd>
    <dt>Tone</dt><dd>${escapeHtml(a.tone || "")}</dd>
    <dt>CTA style</dt><dd>${escapeHtml(a.cta_style || "")}</dd>`;
  $("#profileHooks").innerHTML = (a.hook_patterns || [])
    .map((h) => `<li>${escapeHtml(h)}</li>`).join("");
  $("#profileTopics").innerHTML = (a.topics || [])
    .map((t) => `<span>${escapeHtml(t)}</span>`).join("");
}

function updateProfileChip(a) {
  if (!a || !a.name) return;
  const initials = a.name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  $("#profileAvatar").textContent = initials || "··";
  $("#profileName").textContent = a.name;
  $("#profileNiche").textContent = a.niche || "";
}

// =============================================================
// Trends
// =============================================================
$("#btnRefreshTrends")?.addEventListener("click", async () => {
  $("#btnRefreshTrends").disabled = true;
  setStatus("refreshing trends…", "warn");
  try {
    await api("/api/trends/refresh", { method: "POST" });
    setTimeout(loadTrends, 8000);
    setTimeout(loadTrends, 16000);
    setStatus("trend refresh queued", "ok");
  } catch (err) {
    setStatus(`refresh failed: ${err.message}`, "err");
  } finally {
    $("#btnRefreshTrends").disabled = false;
  }
});

async function loadTrends() {
  try {
    const data = await api("/api/trends");
    state.trends = data.trends || [];
    renderTrends();
  } catch (err) {
    setStatus(`trends failed: ${err.message}`, "err");
  }
}

function renderTrends() {
  const list = $("#trendsList");
  const empty = $("#trendsEmpty");
  if (!list) return;
  list.innerHTML = "";
  if (!state.trends.length) { if (empty) empty.hidden = false; return; }
  if (empty) empty.hidden = true;

  state.trends.forEach((t) => {
    const li = document.createElement("li");
    li.className = "trend";
    li.innerHTML = `
      <div class="trend__score">${Math.round(t.relevance_score || 0)}</div>
      <div>
        <div class="trend__title">${escapeHtml(t.title)}</div>
        <div class="trend__meta">
          <span class="src">${escapeHtml(t.source)}</span>
          <span>·</span>
          <span>score ${t.source_score}</span>
          ${t.url ? `<span>·</span><a href="${escapeHtml(t.url)}" target="_blank" rel="noopener" style="color:var(--text-3)">source</a>` : ""}
        </div>
        ${t.angle ? `<div class="trend__angle">${escapeHtml(t.angle)}</div>` : ""}
      </div>
      <button class="btn btn--primary btn--small">Write post</button>`;
    li.querySelector("button").addEventListener("click", async (e) => {
      e.stopPropagation();
      e.target.disabled = true;
      setStatus("drafting from trend…", "warn");
      try {
        const data = await api("/api/posts/from-trend", {
          method: "POST", body: { trend_id: t.id },
        });
        state.current = data.post;
        activate("compose");
        await loadHistory();
        showDraft(data.post);
        setStatus("draft ready", "ok");
      } catch (err) {
        setStatus(`draft failed: ${err.message}`, "err");
      }
    });
    list.appendChild(li);
  });
}

// =============================================================
// Keyboard shortcuts (D/C/T/S)
// =============================================================
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  const map = { d: "dashboard", c: "compose", t: "trends", s: "setup" };
  const target = map[e.key.toLowerCase()];
  if (target) {
    e.preventDefault();
    activate(target);
  }
});

// =============================================================
// Boot
// =============================================================
(async function main() {
  await checkHealth();
  await loadHistory();
  await loadProfile();
  refreshDashboard();
  setInterval(checkHealth, 15_000);
})();
