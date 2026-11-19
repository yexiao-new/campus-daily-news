#!/usr/bin/env python3
"""生成 GitHub Pages 静态站点。

流程：读取历史状态 → 抓取公开页面 → 合并去重 → 生成当天 Word → 写 docs/data.js。
在 GitHub Actions 里每天定时执行；本地也可以手动运行：

    .venv/bin/python scripts/build_site.py
"""
import datetime as dt
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import config as cfgmod  # noqa: E402
from core import crawler, docgen  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")
STATE_FILE = ROOT / "state" / "news.json"
DOCS = ROOT / "docs"
FILES = DOCS / "files"
STYLE_SOURCE = ROOT / "web" / "style.css"
SITE_TITLE = "校园每日快讯"


def now():
    return dt.datetime.now(TZ)


def load_state():
    """优先读状态文件；第一次运行时从本地 SQLite 迁移已有数据。"""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text("utf-8"))
            if isinstance(data, dict) and "items" in data:
                return data
        except ValueError:
            print("状态文件损坏，重新生成")

    state = {"items": [], "digests": []}
    db = ROOT / "data" / "news.db"
    if not db.exists():
        return state

    print("首次运行：从本地数据库迁移历史数据")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute("SELECT * FROM news ORDER BY day, published_at, id"):
            item = dict(row)
            item.pop("id", None)
            state["items"].append(item)
        for row in conn.execute("SELECT * FROM digests ORDER BY day"):
            digest = dict(row)
            digest.pop("id", None)
            old_path = ROOT / "data" / "digests" / digest["filename"]
            new_name = f"files/digest-{digest['day']}.docx"
            if old_path.exists():
                FILES.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(old_path, DOCS / new_name)
            digest["filename"] = new_name
            digest["fingerprint"] = ""
            state["digests"].append(digest)
    finally:
        conn.close()
    return state


def crawl_sources(cfg, known_urls, today):
    """抓取所有启用的数据源，返回 (新条目, 错误信息)。"""
    fresh, errors, sources_by_id = {}, [], {}
    for src in cfg.get("sources", []):
        if not src.get("enabled"):
            continue
        sid = src.get("id", "")
        sources_by_id[sid] = src
        try:
            if src.get("type") == "demo":
                items = crawler.demo_items(dt.date.fromisoformat(today), src)
            else:
                url = (src.get("url") or "").strip()
                if not url.startswith(("http://", "https://")):
                    raise ValueError("数据源地址需要以 http:// 或 https:// 开头")
                html = crawler.http_get(url)
                items = crawler.parse_list(
                    html, url, src.get("selectors") or {},
                    max_items=int(src.get("max_items") or 30),
                    today=dt.date.fromisoformat(today),
                )
            for item in items:
                item["source_id"] = sid
                item["source_name"] = src.get("name") or sid
                if item["url"] not in known_urls and item["url"] not in fresh:
                    fresh[item["url"]] = item
        except Exception as exc:
            errors.append(f"{src.get('name') or sid}：{exc}")

    new_items = list(fresh.values())
    for sid, src in sources_by_id.items():
        if src.get("type") != "html" or not src.get("fetch_detail", True):
            continue
        subset = [it for it in new_items if it["source_id"] == sid and not it.get("summary")]
        if subset:
            try:
                crawler.enrich_details(subset, src)
            except Exception as exc:
                errors.append(f"{src.get('name') or sid} 详情页：{exc}")
    return new_items, errors


def normalize(item, today, timestamp):
    published = (item.get("published_at") or "").strip()
    day = published[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", published) else today
    if not re.match(r"^\d{4}-\d{2}-\d{2}", published):
        published = day
    return {
        "url": item["url"].strip(),
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "source_id": item.get("source_id", ""),
        "source_name": item.get("source_name", ""),
        "published_at": published,
        "day": day,
        "first_seen": timestamp,
    }


def main():
    stamp = now()
    today = stamp.date().isoformat()
    cfg = cfgmod.load()
    state = load_state()

    known_urls = {item["url"] for item in state["items"]}
    new_items, errors = crawl_sources(cfg, known_urls, today)
    normalized = [normalize(item, today, stamp.strftime("%Y-%m-%d %H:%M:%S")) for item in new_items]
    all_items = state["items"] + normalized

    # 去重 + 按日期倒序（同一天内按发布时间倒序）
    deduped = {}
    for item in all_items:
        deduped.setdefault(item["url"], item)
    all_items = sorted(
        deduped.values(),
        key=lambda it: (it.get("day") or "", it.get("published_at") or ""),
        reverse=True,
    )

    # 生成当天的 Word（内容没变化就不重复生成，减少仓库体积）
    today_items = [item for item in all_items if item["day"] == today]
    fingerprint = hashlib.sha1(
        "|".join(sorted(item["url"] for item in today_items)).encode("utf-8")
    ).hexdigest()[:16]
    digest = next((d for d in state["digests"] if d["day"] == today), None)
    filename = f"files/digest-{today}.docx"
    target = DOCS / filename

    if today_items and (
        digest is None
        or digest.get("fingerprint") != fingerprint
        or not target.exists()
    ):
        FILES.mkdir(parents=True, exist_ok=True)
        docgen.build_digest(
            today_items, today, FILES,
            title=SITE_TITLE,
            generated_at=stamp.replace(tzinfo=None),
            filename=f"digest-{today}.docx",
        )
        digest = {
            "day": today,
            "filename": filename,
            "item_count": len(today_items),
            "created_at": stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "fingerprint": fingerprint,
        }
        state["digests"] = [d for d in state["digests"] if d["day"] != today] + [digest]
        print(f"已生成 {filename}（{len(today_items)} 条）")
    elif digest:
        digest["filename"] = filename

    # 汇总
    counts = {}
    for item in all_items:
        counts[item["day"]] = counts.get(item["day"], 0) + 1
    days = [{"day": day, "count": count} for day, count in sorted(counts.items(), reverse=True)]
    digests = sorted(state["digests"], key=lambda d: d["day"], reverse=True)
    latest_day = days[0]["day"] if days else today

    payload = {
        "app": SITE_TITLE,
        "today": today,
        "latest_day": latest_day,
        "generated_at": stamp.strftime("%Y-%m-%d %H:%M"),
        "days": days,
        "items": [
            {key: item.get(key, "") for key in (
                "url", "title", "summary", "source_id", "source_name", "published_at", "day"
            )}
            for item in all_items
        ],
        "digests": [
            {key: d.get(key, "") for key in ("day", "filename", "item_count", "created_at")}
            for d in digests
        ],
        "sources": [
            {"name": s.get("name") or s.get("id"), "url": s.get("url") or ""}
            for s in cfg.get("sources", []) if s.get("enabled")
        ],
    }

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data.js").write_text(
        "window.__DIGEST__ = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        "utf-8",
    )
    if STYLE_SOURCE.exists():
        shutil.copyfile(STYLE_SOURCE, DOCS / "style.css")
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"items": all_items, "digests": digests}, ensure_ascii=False, indent=1) + "\n",
        "utf-8",
    )

    print(f"完成：共 {len(all_items)} 条，今日 {len(today_items)} 条，日报 {len(digests)} 份")
    if new_items:
        print(f"新增 {len(new_items)} 条")
    if errors:
        print("部分数据源失败：")
        for err in errors:
            print("  -", err)


if __name__ == "__main__":
    main()
