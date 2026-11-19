"""校园每日快讯 · 本地 Web 应用入口。

启动：.venv/bin/python app.py   →   http://127.0.0.1:7878
"""
import datetime as dt
import os
import re
import secrets
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import config as cfgmod  # noqa: E402
from core import crawler, docgen  # noqa: E402
from core.scheduler import Scheduler  # noqa: E402
from core.store import Store  # noqa: E402

DATA_DIR = ROOT / "data"
DIGEST_DIR = DATA_DIR / "digests"
WEB_DIR = ROOT / "web"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DIGEST_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/static")
store = Store(DATA_DIR / "news.db")

# ---- 访问口令：公开部署时保护写操作。只读浏览任何人都可以。----
# 环境变量 ACCESS_TOKEN 优先；否则从 data/access_token 读取；都没有则生成随机口令写入文件。
TOKEN_PATH = DATA_DIR / "access_token"


def _load_or_create_token():
    env = os.environ.get("ACCESS_TOKEN", "").strip()
    if env:
        return env
    if TOKEN_PATH.exists():
        try:
            value = TOKEN_PATH.read_text("utf-8").strip()
            if value:
                return value
        except OSError:
            pass
    value = secrets.token_urlsafe(6)
    try:
        TOKEN_PATH.write_text(value, "utf-8")
    except OSError:
        pass
    return value


ACCESS_TOKEN = _load_or_create_token()


def _require_auth():
    """写接口校验；返回 None 表示通过，否则返回 (response, status)。"""
    supplied = request.headers.get("X-Access-Token", "")
    if supplied and secrets.compare_digest(supplied, ACCESS_TOKEN):
        return None
    return jsonify({"error": "需要访问口令", "auth_required": True}), 401


def _auth_required_flag():
    return bool(ACCESS_TOKEN)


_run_lock = threading.Lock()
_status = {
    "running": False,
    "last_crawl_at": None,
    "last_crawl_new": 0,
    "last_error": None,
}


class Busy(Exception):
    pass


def _now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today():
    return dt.date.today().isoformat()


# ---------------------------------------------------------------- 核心流程
def crawl_sources(dry_run=False, source_id=None):
    cfg = cfgmod.load()
    sources = [
        s for s in cfg.get("sources", [])
        if s.get("enabled") and (source_id is None or s.get("id") == source_id)
    ]
    if not sources:
        raise RuntimeError("没有启用的数据源，请先在「数据源设置」里启用或填写一个。")

    today = _today()
    collected, errors = {}, []
    for src in sources:
        try:
            if src.get("type") == "demo":
                items = crawler.demo_items(dt.date.today(), src)
            else:
                url = (src.get("url") or "").strip()
                if not url.startswith(("http://", "https://")):
                    raise ValueError("数据源地址需要以 http:// 或 https:// 开头")
                html = crawler.http_get(url)
                items = crawler.parse_list(
                    html, url, src.get("selectors") or {},
                    max_items=int(src.get("max_items") or 30),
                )
            for item in items:
                item["source_id"] = src.get("id", "")
                item["source_name"] = src.get("name") or src.get("id", "")
                existing = collected.get(item["url"])
                if existing:
                    if not existing.get("summary") and item.get("summary"):
                        existing["summary"] = item["summary"]
                else:
                    collected[item["url"]] = item
        except Exception as exc:
            errors.append({"source": src.get("name") or src.get("id"), "error": str(exc)})

    unique = list(collected.values())
    if dry_run:
        preview = []
        for item in unique[:40]:
            preview.append({
                "title": item["title"],
                "url": item["url"],
                "published_at": item.get("published_at", ""),
                "source_name": item.get("source_name", ""),
            })
        return {"dry_run": True, "scanned": len(unique), "items": preview, "errors": errors}

    known = store.existing_urls([item["url"] for item in unique])
    fresh = [item for item in unique if item["url"] not in known]

    for src in sources:
        if src.get("type") != "html" or not src.get("fetch_detail", True):
            continue
        subset = [
            item for item in fresh
            if item.get("source_id") == src.get("id") and not item.get("summary")
        ]
        if subset:
            try:
                crawler.enrich_details(subset, src)
            except Exception as exc:
                errors.append({"source": src.get("name"), "error": f"详情页抓取失败：{exc}"})

    normalized = [_normalize(item, today) for item in fresh]
    added = store.add_items(normalized)
    return {
        "added": len(added),
        "scanned": len(unique),
        "errors": errors,
        "items": [
            {"title": it["title"], "url": it["url"], "day": it["day"]}
            for it in added[:20]
        ],
    }


def _normalize(item, today):
    published = (item.get("published_at") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", published):
        day = published[:10]
    else:
        day = today
        item["published_at"] = day
    item["day"] = day
    item["title"] = item["title"].strip()
    item["summary"] = (item.get("summary") or "").strip()
    item["first_seen"] = _now()
    return item


def generate_digest(day):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        raise RuntimeError("日期格式应为 YYYY-MM-DD")
    items = store.list_by_day(day)
    if not items:
        raise RuntimeError("这一天还没有收录消息，先点「立即抓取」试试。")
    cfg = cfgmod.load()
    title = (cfg.get("app") or {}).get("name") or "校园每日快讯"
    path = docgen.build_digest(items, day, DIGEST_DIR, title=title)
    created = _now()
    store.upsert_digest(day, path.name, len(items), created)
    return {"day": day, "filename": path.name, "count": len(items), "created_at": created}


def auto_job():
    if not _run_lock.acquire(blocking=False):
        return {"added": 0, "digest": "", "skipped": "busy"}
    _status["running"] = True
    try:
        result = crawl_sources()
        try:
            digest = generate_digest(_today())
            result["digest"] = digest["filename"]
        except Exception as exc:
            result["digest_error"] = str(exc)
        _status["last_crawl_at"] = _now()
        _status["last_crawl_new"] = result.get("added", 0)
        _status["last_error"] = None
        return result
    except Exception as exc:
        _status["last_error"] = str(exc)
        raise
    finally:
        _status["running"] = False
        _run_lock.release()


# ---------------------------------------------------------------- 页面与接口
@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/state")
def api_state():
    cfg = cfgmod.load()
    return jsonify({
        "today": _today(),
        "now": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "days": store.day_counts(),
        "digests": store.list_digests(),
        "config": cfg,
        "auth_required": _auth_required_flag(),
        "status": {
            "running": _status["running"],
            "last_crawl_at": _status["last_crawl_at"],
            "last_crawl_new": _status["last_crawl_new"],
            "last_error": _status["last_error"],
            "total_news": store.total(),
            "scheduler_time": (cfg.get("digest") or {}).get("time", "08:00"),
            "last_auto_at": store.meta_get("last_auto_at"),
            "last_auto_summary": store.meta_get("last_auto_summary"),
            "last_auto_error": store.meta_get("last_auto_error"),
        },
    })


@app.get("/api/news")
def api_news():
    day = (request.args.get("day") or "today").strip()
    if day == "today":
        day = _today()
    if day == "all":
        items = store.list_recent(limit=300)
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        items = store.list_by_day(day)
    else:
        return jsonify({"error": "日期参数不合法"}), 400
    return jsonify({"day": day, "items": items})


@app.post("/api/crawl")
def api_crawl():
    denied = _require_auth()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run"))
    source_id = payload.get("source_id") or None

    if not _run_lock.acquire(blocking=False):
        return jsonify({"error": "正在抓取中，请稍候再试"}), 409
    _status["running"] = True
    try:
        result = crawl_sources(dry_run=dry_run, source_id=source_id)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _status["last_error"] = str(exc)
        return jsonify({"error": f"抓取失败：{exc}"}), 500
    finally:
        _status["running"] = False
        _run_lock.release()

    if not dry_run:
        _status["last_crawl_at"] = _now()
        _status["last_crawl_new"] = result.get("added", 0)
        _status["last_error"] = None
    return jsonify(result)


@app.post("/api/digest")
def api_digest():
    denied = _require_auth()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    day = (payload.get("day") or _today()).strip()
    if not _run_lock.acquire(blocking=False):
        return jsonify({"error": "正在处理中，请稍候"}), 409
    _status["running"] = True
    try:
        result = generate_digest(day)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"生成失败：{exc}"}), 500
    finally:
        _status["running"] = False
        _run_lock.release()
    result["download"] = f"/api/download/{result['filename']}"
    return jsonify(result)


@app.get("/api/download/<path:filename>")
def api_download(filename):
    name = os.path.basename(filename)
    target = DIGEST_DIR / name
    if not name or not target.is_file() or target.resolve().parent != DIGEST_DIR.resolve():
        abort(404)
    return send_from_directory(DIGEST_DIR, name, as_attachment=True, download_name=name)


@app.post("/api/config")
def api_config():
    denied = _require_auth()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    cfg = cfgmod.load()

    digest = payload.get("digest")
    if isinstance(digest, dict):
        time_value = str(digest.get("time") or "").strip()
        if time_value:
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_value):
                return jsonify({"error": "自动生成时间格式应为 HH:MM"}), 400
            cfg.setdefault("digest", {})["time"] = time_value

    sources = payload.get("sources")
    if isinstance(sources, list):
        cleaned, ids = [], set()
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            sid = str(raw.get("id") or "").strip() or f"src{len(cleaned) + 1}"
            if not re.match(r"^[A-Za-z0-9_-]{1,32}$", sid):
                return jsonify({"error": f"数据源 ID 不合法：{sid}"}), 400
            if sid in ids:
                return jsonify({"error": f"数据源 ID 重复：{sid}"}), 400
            ids.add(sid)
            stype = raw.get("type") if raw.get("type") in ("demo", "html") else "html"
            url = str(raw.get("url") or "").strip()
            enabled = bool(raw.get("enabled"))
            if enabled and stype == "html" and not url.startswith(("http://", "https://")):
                return jsonify({"error": f"「{raw.get('name') or sid}」需要填写 http(s) 开头的网址"}), 400
            selectors = raw.get("selectors") or {}
            if not isinstance(selectors, dict):
                selectors = {}
            try:
                max_items = max(1, min(200, int(raw.get("max_items") or 30)))
            except (TypeError, ValueError):
                max_items = 30
            cleaned.append({
                "id": sid,
                "name": str(raw.get("name") or sid).strip(),
                "type": stype,
                "enabled": enabled,
                "url": url,
                "max_items": max_items,
                "fetch_detail": bool(raw.get("fetch_detail", stype == "html")),
                "selectors": {
                    key: str(selectors.get(key) or "").strip()
                    for key in ("item", "title", "link", "date", "summary", "detail")
                },
            })
        cfg["sources"] = cleaned

    saved = cfgmod.save(cfg)
    return jsonify({"ok": True, "config": saved})


@app.after_request
def _no_cache(resp):
    if request.path.endswith((".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def main():
    port = int(os.environ.get("PORT", "7878"))
    scheduler = Scheduler(auto_job, store)
    scheduler.start()
    print(f"[校园每日快讯] 已启动 → http://127.0.0.1:{port}")
    print(f"[校园每日快讯] 每日 {cfgmod.load()['digest'].get('time', '08:00')} 自动抓取并生成 Word")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
