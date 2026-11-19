"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  today: null,
  now: null,
  days: [],
  digests: [],
  config: null,
  status: null,
  news: [],
  selected: "today",
  busy: false,
};

const DOW = ["日", "一", "二", "三", "四", "五", "六"];

const ICON_DOC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>`;
const ICON_DOWNLOAD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>`;

/* ------------------------------------------------------------ 小工具 */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function fmtDate(day) {
  const [, m, d] = String(day).split("-").map(Number);
  return `${m}月${d}日`;
}

function weekdayCN(day) {
  const dt = new Date(`${day}T00:00:00`);
  return `星期${DOW[dt.getDay()]}`;
}

function plusDays(day, n) {
  const dt = new Date(`${day}T00:00:00`);
  dt.setDate(dt.getDate() + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

function timeOf(value) {
  const m = String(value || "").match(/(\d{2}:\d{2})/);
  return m ? m[1] : "";
}

function tagClass(source) {
  let hash = 0;
  for (const ch of String(source || "")) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  return ["", "b", "c", "d"][hash % 4];
}

const TOKEN_KEY = "campus_access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (method !== "GET") {
    const token = getToken();
    if (token) headers["X-Access-Token"] = token;
  }
  const doFetch = () => fetch(path, { ...options, headers });

  let res = await doFetch();

  // 写操作需要口令：弹窗输入一次，记住后自动重试
  if (res.status === 401 && method !== "GET") {
    let body = null;
    try { body = await res.clone().json(); } catch (err) { /* 忽略 */ }
    if (body && body.auth_required) {
      const input = window.prompt("此操作需要访问口令，请输入：", "");
      if (input === null || !input.trim()) {
        throw new Error("已取消：需要访问口令才能执行此操作");
      }
      localStorage.setItem(TOKEN_KEY, input.trim());
      headers["X-Access-Token"] = input.trim();
      res = await doFetch();
    }
  }

  let data = null;
  try { data = await res.json(); } catch (err) { /* 非 JSON 响应 */ }
  if (!res.ok) throw new Error((data && data.error) || `请求失败（${res.status}）`);
  return data;
}

function toast(message, type = "ok") {
  const wrap = $("#toastWrap");
  const el = document.createElement("div");
  el.className = `toast${type === "error" ? " error" : ""}`;
  el.textContent = message;
  wrap.appendChild(el);
  setTimeout(() => {
    el.classList.add("hide");
    setTimeout(() => el.remove(), 260);
  }, 3600);
}

function setBusy(busy) {
  state.busy = busy;
  $("#btnCrawl").disabled = busy;
  $("#btnDigest").disabled = busy;
}

/* ------------------------------------------------------------ 数据加载 */
async function refresh() {
  const data = await api("/api/state");
  state.today = data.today;
  state.now = data.now;
  state.days = data.days || [];
  state.digests = data.digests || [];
  state.config = data.config || {};
  state.status = data.status || {};

  renderHeader();
  renderChips();
  renderDigest();
  renderHistory();
  renderSources();
  renderMeta();
  setBusy(!!state.status.running);
}

async function loadNews(day = state.selected) {
  state.selected = day;
  const data = await api(`/api/news?day=${encodeURIComponent(day)}`);
  state.news = data.items || [];
  renderChips();
  renderNews();
  renderMeta();
}

/* ------------------------------------------------------------ 渲染 */
function renderHeader() {
  const pill = $("#todayPill");
  if (!state.today) return;
  const [y, m, d] = state.today.split("-").map(Number);
  pill.textContent = `${y}年${m}月${d}日 ${weekdayCN(state.today)}`;
}

function renderMeta() {
  const total = state.status?.total_news ?? 0;
  const todayCount = (state.days.find((x) => x.day === state.today) || {}).count || 0;
  const last = state.status?.last_crawl_at;
  let text = `共收录 ${total} 条 · 今日 ${todayCount} 条`;
  if (last) text += ` · 最近抓取 ${last.slice(11, 16)}`;
  if (state.status?.last_error) text += " · 上次抓取有错误";
  $("#feedMeta").textContent = text;
}

function renderChips() {
  if (!state.today) return;
  const days = state.days || [];
  const has = (day) => days.some((x) => x.day === day);
  const countOf = (day) => (days.find((x) => x.day === day) || {}).count || 0;
  const yesterday = plusDays(state.today, -1);

  const chips = [{ key: "today", label: "今天", count: countOf(state.today) }];
  if (has(yesterday)) chips.push({ key: yesterday, label: "昨天", count: countOf(yesterday) });
  days
    .filter((x) => x.day !== state.today && x.day !== yesterday)
    .slice(0, 4)
    .forEach((x) => chips.push({ key: x.day, label: fmtDate(x.day), count: x.count }));
  chips.push({ key: "all", label: "全部", count: null });

  $("#dayChips").innerHTML = chips.map((c) => `
    <button class="chip${state.selected === c.key ? " active" : ""}" data-day="${esc(c.key)}">
      ${esc(c.label)}${c.count ? ` <b>${c.count}</b>` : ""}
    </button>`).join("");

  $$("#dayChips .chip").forEach((btn) => {
    btn.addEventListener("click", () => loadNews(btn.dataset.day));
  });
}

function renderNews() {
  const list = $("#newsList");
  if (!state.news.length) {
    const isToday = state.selected === "today";
    list.innerHTML = `
      <div class="empty">
        <div class="big">${isToday ? "今天还没有抓到新消息" : "这一天没有收录消息"}</div>
        点击「立即抓取」从校园官网拉取最新内容，有了消息才能生成 Word。
        <div><button class="btn primary" id="emptyCrawl" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
          立即抓取
        </button></div>
      </div>`;
    $("#emptyCrawl").addEventListener("click", crawl);
    return;
  }

  list.innerHTML = state.news.map((item) => {
    const prefix = state.selected === "all" ? `${fmtDate(item.day)} ` : "";
    return `
      <article class="news">
        <div class="news-top">
          <span class="tag ${tagClass(item.source_id)}" title="${esc(item.source_name)}">${esc(item.source_name || "未知来源")}</span>
          <span class="dot"></span>
          <time>${esc(prefix)}${esc(timeOf(item.published_at))}</time>
        </div>
        <h3><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a></h3>
        ${item.summary ? `<p class="summary">${esc(item.summary)}</p>` : ""}
        <div class="news-foot">
          <a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">查看原文
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M7 7h10v10"/></svg>
          </a>
        </div>
      </article>`;
  }).join("");
}

function renderDigest() {
  const card = $("#digestCard");
  if (!card) return;
  const digest = state.digests.find((d) => d.day === state.today);
  const todayCount = (state.days.find((x) => x.day === state.today) || {}).count || 0;

  if (digest) {
    const created = (digest.created_at || "").slice(11, 16);
    card.innerHTML = `
      <div class="digest-eyebrow">Today's Digest</div>
      <div class="digest-body">
        <div class="doc-icon">${ICON_DOC}</div>
        <div>
          <div class="digest-title">今日 Word 已生成</div>
          <div class="digest-meta">${esc(digest.filename)}<br>${digest.item_count} 条消息${created ? ` · ${esc(created)} 生成` : ""}</div>
        </div>
      </div>
      <div class="digest-actions">
        <a class="btn primary" href="/api/download/${encodeURIComponent(digest.filename)}" download>${ICON_DOWNLOAD}下载 Word</a>
        <button class="btn ghost" id="btnRegen" type="button">重新生成</button>
      </div>`;
    $("#btnRegen").addEventListener("click", generateDigest);
    return;
  }

  card.innerHTML = `
    <div class="digest-eyebrow">Today's Digest</div>
    <div class="digest-body">
      <div class="doc-icon">${ICON_DOC}</div>
      <div>
        <div class="digest-title">今日文档还没有生成</div>
        <div class="digest-meta">${todayCount ? `今天已收录 ${todayCount} 条消息` : "先抓取校园官网的新消息"}</div>
      </div>
    </div>
    <div class="digest-actions">
      <button class="btn primary" id="btnMake" type="button">${ICON_DOC}生成今日 Word</button>
    </div>`;
  $("#btnMake").addEventListener("click", generateDigest);
}

function renderHistory() {
  const rows = state.digests || [];
  $("#docCount").textContent = rows.length ? `${rows.length} 份` : "";
  if (!rows.length) {
    $("#historyList").innerHTML = `<div class="empty" style="padding:22px 8px 8px;font-size:12.5px">还没有生成过文档</div>`;
    return;
  }
  $("#historyList").innerHTML = rows.map((d) => `
    <div class="history-row">
      <div>
        <div class="history-day">${d.day === state.today ? "今天" : esc(fmtDate(d.day))}
          <span class="muted" style="font-weight:400;font-size:11px">${esc(weekdayCN(d.day))}</span>
        </div>
        <div class="history-sub">${esc(d.filename)} · ${d.item_count} 条</div>
      </div>
      <a class="mini-btn" href="/api/download/${encodeURIComponent(d.filename)}" download title="下载 ${esc(d.filename)}">${ICON_DOWNLOAD}</a>
    </div>`).join("");
}

function renderSources() {
  const sources = state.config?.sources || [];
  $("#sourceList").innerHTML = sources.length
    ? sources.map((s) => `
        <div class="source-row" title="${esc(s.type === "demo" ? "示例数据源" : s.url || "")}">
          <span class="source-dot${s.enabled ? " on" : ""}"></span>
          <span class="source-name">${esc(s.name)}</span>
          <span class="source-type${s.type === "demo" ? " demo" : ""}">${s.type === "demo" ? "示例" : "网页"}</span>
        </div>`).join("")
    : `<div class="muted small">还没有配置数据源</div>`;

  const time = state.config?.digest?.time || "08:00";
  const auto = state.status?.last_auto_at;
  const autoError = state.status?.last_auto_error;
  let html = `每天 <strong>${esc(time)}</strong> 自动抓取并生成当天 Word`;
  if (auto) html += `<br>上次自动执行：${esc(auto.slice(5, 16))}`;
  if (autoError) html += `<br><span class="err">上次自动执行失败：${esc(autoError)}</span>`;
  $("#scheduleLine").innerHTML = html;
}

/* ------------------------------------------------------------ 设置弹窗 */
function openSettings() {
  const cfg = state.config || {};
  $("#digestTime").value = (cfg.digest && cfg.digest.time) || "08:00";
  renderSourceEditor(cfg.sources || []);
  $("#settingsModal").hidden = false;
}

function closeSettings() {
  $("#settingsModal").hidden = true;
}

function sourceRowTemplate(src, index) {
  const id = src.id || `src_${Date.now().toString(36)}${index}`;
  const s = src.selectors || {};
  const type = src.type === "demo" ? "demo" : "html";
  return `
    <div class="src-row${type === "demo" ? " demo" : ""}" data-id="${esc(id)}" data-max="${esc(src.max_items || 30)}">
      <div class="src-row-head">
        <label class="src-toggle"><input type="checkbox" data-f="enabled"${src.enabled ? " checked" : ""}> 启用</label>
        <label class="field"><span>名称</span>
          <input type="text" data-f="name" value="${esc(src.name || "")}" placeholder="数据源名称">
        </label>
        <select class="src-type" data-f="type" aria-label="数据源类型">
          <option value="html"${type === "html" ? " selected" : ""}>网页</option>
          <option value="demo"${type === "demo" ? " selected" : ""}>示例</option>
        </select>
        <button class="link-btn danger" data-remove type="button">移除</button>
      </div>
      <div class="src-grid">
        <label class="field full"><span>列表页网址</span>
          <input type="url" data-f="url" value="${esc(src.url || "")}" placeholder="https://www.xxx.edu.cn/tzgg.htm">
        </label>
        <label class="field"><span>列表项选择器</span><input type="text" data-f="item" value="${esc(s.item || "")}" placeholder="ul li"></label>
        <label class="field"><span>标题选择器</span><input type="text" data-f="title" value="${esc(s.title || "a")}" placeholder="a"></label>
        <label class="field"><span>链接选择器</span><input type="text" data-f="link" value="${esc(s.link || "a")}" placeholder="a"></label>
        <label class="field"><span>日期选择器</span><input type="text" data-f="date" value="${esc(s.date || "")}" placeholder=".date"></label>
        <label class="field"><span>摘要选择器</span><input type="text" data-f="summary" value="${esc(s.summary || "")}" placeholder="可选"></label>
        <label class="field"><span>正文选择器</span><input type="text" data-f="detail" value="${esc(s.detail || "")}" placeholder="可选，如 .article-content"></label>
      </div>
    </div>`;
}

function bindSourceRow(row) {
  row.querySelector('[data-f="type"]').addEventListener("change", (event) => {
    row.classList.toggle("demo", event.target.value === "demo");
  });
  row.querySelector("[data-remove]").addEventListener("click", () => row.remove());
}

function renderSourceEditor(sources) {
  const editor = $("#sourceEditor");
  editor.innerHTML = sources.map(sourceRowTemplate).join("");
  $$(".src-row", editor).forEach(bindSourceRow);
}

function addSourceRow() {
  const editor = $("#sourceEditor");
  const wrapper = document.createElement("div");
  wrapper.innerHTML = sourceRowTemplate({
    id: `src_${Date.now().toString(36)}`,
    name: "新的数据源",
    type: "html",
    enabled: false,
    url: "",
    max_items: 30,
    selectors: { item: "", title: "a", link: "a", date: "" },
  }, $$(".src-row", editor).length);
  const row = wrapper.firstElementChild;
  editor.appendChild(row);
  bindSourceRow(row);
  row.querySelector('[data-f="name"]').focus();
}

function collectSources() {
  return $$("#sourceEditor .src-row").map((row) => {
    const val = (field) => (row.querySelector(`[data-f="${field}"]`)?.value || "").trim();
    return {
      id: row.dataset.id,
      name: val("name") || "未命名数据源",
      type: val("type") === "demo" ? "demo" : "html",
      enabled: !!row.querySelector('[data-f="enabled"]')?.checked,
      url: val("url"),
      max_items: Number(row.dataset.max) || 30,
      fetch_detail: true,
      selectors: {
        item: val("item"),
        title: val("title"),
        link: val("link"),
        date: val("date"),
        summary: val("summary"),
        detail: val("detail"),
      },
    };
  });
}

async function saveSettings() {
  const btn = $("#btnSave");
  const time = $("#digestTime").value;
  if (!/^\d{2}:\d{2}$/.test(time)) {
    toast("请选择有效的自动生成时间", "error");
    return;
  }
  btn.disabled = true;
  try {
    const data = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ digest: { time }, sources: collectSources() }),
    });
    state.config = data.config;
    closeSettings();
    await refresh();
    toast("设置已保存");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

/* ------------------------------------------------------------ 动作 */
async function crawl() {
  if (state.busy) return;
  setBusy(true);
  try {
    const res = await api("/api/crawl", { method: "POST", body: "{}" });
    const errors = res.errors || [];
    if (errors.length) {
      toast(`抓取完成，但「${errors[0].source}」失败：${errors[0].error}`, "error");
    } else if (res.added) {
      toast(`抓取完成，新增 ${res.added} 条消息`);
    } else {
      toast("抓取完成，暂时没有新消息");
    }
    await refresh();
    await loadNews(state.selected);
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setBusy(false);
  }
}

async function generateDigest() {
  if (state.busy) return;
  setBusy(true);
  try {
    const res = await api("/api/digest", { method: "POST", body: JSON.stringify({ day: state.today }) });
    await refresh();
    toast(`已生成《${res.filename}》，共 ${res.count} 条消息`);
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setBusy(false);
  }
}

/* ------------------------------------------------------------ 事件绑定 */
function bindEvents() {
  $("#btnCrawl").addEventListener("click", crawl);
  $("#btnDigest").addEventListener("click", generateDigest);
  $("#btnSettings").addEventListener("click", openSettings);
  $("#btnOpenSettings").addEventListener("click", openSettings);
  $("#btnSave").addEventListener("click", saveSettings);
  $("#btnAddSource").addEventListener("click", addSourceRow);

  $$("[data-close]").forEach((el) => el.addEventListener("click", closeSettings));
  $("#settingsModal").addEventListener("click", (event) => {
    if (event.target === $("#settingsModal")) closeSettings();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#settingsModal").hidden) closeSettings();
  });
}

async function init() {
  bindEvents();
  try {
    await refresh();
    await loadNews("today");
  } catch (err) {
    toast(`无法连接本地服务：${err.message}`, "error");
    $("#newsList").innerHTML = `<div class="empty">本地服务未连接，请确认程序仍在运行。</div>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
