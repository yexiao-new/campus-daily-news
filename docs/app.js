"use strict";

const DATA = window.__DIGEST__ || null;
const $ = (sel) => document.querySelector(sel);
const state = { selected: null };

const ICON_DOC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>`;
const ICON_DOWNLOAD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>`;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function clientToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtDate(day) {
  const [, m, d] = String(day).split("-").map(Number);
  return `${m}月${d}日`;
}

function weekdayCN(day) {
  const dow = ["日", "一", "二", "三", "四", "五", "六"];
  return `星期${dow[new Date(`${day}T00:00:00`).getDay()]}`;
}

function timeOf(value) {
  const match = String(value || "").match(/(\d{2}:\d{2})/);
  return match ? match[1] : "";
}

function tagClass(source) {
  let hash = 0;
  for (const ch of String(source || "")) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  return ["", "b", "c", "d"][hash % 4];
}

function countOf(day) {
  const found = (DATA.days || []).find((d) => d.day === day);
  return found ? found.count : 0;
}

function dataTodayLabel() {
  return DATA.today === clientToday() ? "今天" : fmtDate(DATA.today);
}

/* ------------------------------------------------------------ 渲染 */
function renderHeader() {
  const today = clientToday();
  $("#todayPill").textContent = `${today.slice(0, 4)}年${fmtDate(today)} ${weekdayCN(today)}`;
}

function renderStale() {
  const today = clientToday();
  if (DATA.today === today) return;
  const bar = $("#staleBar");
  bar.hidden = false;
  bar.querySelector("span").textContent =
    `页面数据生成于 ${DATA.generated_at}，今天（${fmtDate(today)}）的数据还没有更新。每天 07:20 起自动刷新，稍后再来看看。`;
}

function renderChips() {
  const chips = [{ key: DATA.today, label: dataTodayLabel(), count: countOf(DATA.today) }];
  (DATA.days || [])
    .filter((d) => d.day !== DATA.today)
    .slice(0, 4)
    .forEach((d) => chips.push({ key: d.day, label: fmtDate(d.day), count: d.count }));
  chips.push({ key: "all", label: "全部", count: null });

  $("#dayChips").innerHTML = chips.map((chip) => `
    <button class="chip${state.selected === chip.key ? " active" : ""}" data-day="${esc(chip.key)}" type="button">
      ${esc(chip.label)}${chip.count ? ` <b>${chip.count}</b>` : ""}
    </button>`).join("");

  document.querySelectorAll("#dayChips .chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selected = btn.dataset.day;
      renderChips();
      renderNews();
    });
  });
}

function renderNews() {
  const list = $("#newsList");
  const items = state.selected === "all"
    ? DATA.items
    : DATA.items.filter((item) => item.day === state.selected);

  if (!items.length) {
    const latest = (DATA.days || [])[0];
    const canJump = latest && latest.day !== state.selected;
    list.innerHTML = `
      <div class="empty">
        <div class="big">${state.selected === DATA.today ? "今天还没有消息" : "这一天没有收录消息"}</div>
        页面每天 07:20 / 12:10 / 18:10 / 22:10（北京时间）自动抓取，学校发布后会出现在这里。
        ${canJump ? `<div><button class="btn primary" type="button" id="btnLatest">
          看看最近一天（${esc(fmtDate(latest.day))}）</button></div>` : ""}
      </div>`;
    const jump = $("#btnLatest");
    if (jump) {
      jump.addEventListener("click", () => {
        state.selected = latest.day;
        renderChips();
        renderNews();
      });
    }
    return;
  }

  list.innerHTML = items.map((item) => {
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
  const digests = DATA.digests || [];
  const digest = digests.find((d) => d.day === DATA.today) || digests[0];

  if (!digest) {
    card.innerHTML = `
      <div class="digest-eyebrow">Daily Digest</div>
      <div class="digest-body">
        <div class="doc-icon">${ICON_DOC}</div>
        <div>
          <div class="digest-title">日报还没生成</div>
          <div class="digest-meta">当天有消息后会自动生成</div>
        </div>
      </div>`;
    return;
  }

  const isToday = digest.day === DATA.today && DATA.today === clientToday();
  const created = (digest.created_at || "").slice(11, 16);
  card.innerHTML = `
    <div class="digest-eyebrow">Daily Digest</div>
    <div class="digest-body">
      <div class="doc-icon">${ICON_DOC}</div>
      <div>
        <div class="digest-title">${isToday ? "今日 Word 已生成" : "最新 Word 日报"}</div>
        <div class="digest-meta">${esc(fmtDate(digest.day))} · ${digest.item_count} 条消息${created ? ` · ${esc(created)} 生成` : ""}</div>
      </div>
    </div>
    <div class="digest-actions">
      <a class="btn primary" href="${esc(digest.filename)}" download="校园每日快讯_${esc(digest.day)}.docx">${ICON_DOWNLOAD}下载 Word</a>
    </div>`;
}

function renderHistory() {
  const rows = DATA.digests || [];
  $("#docCount").textContent = rows.length ? `${rows.length} 份` : "";
  if (!rows.length) {
    $("#historyList").innerHTML = `<div class="empty" style="padding:22px 8px 8px;font-size:12.5px">还没有生成过日报</div>`;
    return;
  }
  const today = clientToday();
  $("#historyList").innerHTML = rows.map((d) => `
    <div class="history-row">
      <div>
        <div class="history-day">${d.day === today ? "今天" : esc(fmtDate(d.day))}
          <span class="muted" style="font-weight:400;font-size:11px">${esc(weekdayCN(d.day))}</span>
        </div>
        <div class="history-sub">${d.item_count} 条消息 · ${esc((d.created_at || "").slice(11, 16))} 生成</div>
      </div>
      <a class="mini-btn" href="${esc(d.filename)}" download="校园每日快讯_${esc(d.day)}.docx" title="下载 ${esc(fmtDate(d.day))} 日报">${ICON_DOWNLOAD}</a>
    </div>`).join("");
}

function renderSources() {
  const sources = DATA.sources || [];
  $("#sourceList").innerHTML = sources.length
    ? sources.map((s) => `
        <div class="source-row" title="${esc(s.url)}">
          <span class="source-dot on"></span>
          <span class="source-name">${esc(s.name)}</span>
        </div>`).join("")
    : "";
  $("#updatedAt").textContent = DATA.generated_at;
}

function renderMeta() {
  const label = DATA.today === clientToday() ? "今日" : "最新一天";
  $("#feedMeta").textContent =
    `共收录 ${DATA.items.length} 条 · ${label} ${countOf(DATA.today)} 条 · 数据生成于 ${DATA.generated_at}`;
}

/* ------------------------------------------------------------ 启动 */
function init() {
  $("#btnRefresh").addEventListener("click", () => location.reload());

  if (!DATA || !DATA.today) {
    $("#feedMeta").textContent = "数据尚未生成";
    $("#newsList").innerHTML = `
      <div class="empty">
        <div class="big">还没有数据</div>
        第一次部署后，等待 GitHub Actions 跑完（或手动运行一次）就会出现内容。
      </div>`;
    return;
  }

  // 今天还没消息时，先落到最近一天，避免打开就是空白
  state.selected = countOf(DATA.today) ? DATA.today : (DATA.latest_day || DATA.today);

  renderHeader();
  renderStale();
  renderChips();
  renderNews();
  renderDigest();
  renderHistory();
  renderSources();
  renderMeta();
}

document.addEventListener("DOMContentLoaded", init);
