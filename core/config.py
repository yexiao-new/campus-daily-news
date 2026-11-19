"""配置读写：config.json 用 json 保存，首次启动自动生成默认配置。"""
import copy
import json
import os
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
DIGEST_DIR = DATA_DIR / "digests"

DEFAULT_CONFIG = {
    "app": {
        "name": "校园每日快讯",
        "version": "0.1.0",
    },
    "digest": {
        "time": "08:00",
        "limit": 60,
    },
    "sources": [
        {
            "id": "demo",
            "name": "示例数据源",
            "type": "demo",
            "enabled": True,
            "url": "",
            "max_items": 30,
            "fetch_detail": False,
            "selectors": {"item": "", "title": "a", "link": "a", "date": ""},
        },
        {
            "id": "school_news",
            "name": "校园官网 · 新闻动态",
            "type": "html",
            "enabled": False,
            "url": "https://www.example.edu.cn/xwdt.htm",
            "max_items": 30,
            "fetch_detail": True,
            "selectors": {"item": "ul li", "title": "a", "link": "a", "date": ""},
        },
    ],
}

_lock = threading.Lock()


def _merge_defaults(cfg):
    merged = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(cfg, dict):
        return merged
    for key, value in cfg.items():
        if key == "sources" and isinstance(value, list):
            merged["sources"] = value
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def load():
    """读取配置；不存在或损坏时使用默认配置。"""
    with _lock:
        if not CONFIG_PATH.exists():
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            _write(cfg)
            return cfg
        try:
            cfg = json.loads(CONFIG_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            _write(cfg)
            return cfg
        return _merge_defaults(cfg)


def save(cfg):
    with _lock:
        merged = _merge_defaults(cfg)
        _write(merged)
        return merged


def _write(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(CONFIG_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, CONFIG_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
