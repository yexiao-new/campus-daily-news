"""核心模块的轻量测试：.venv/bin/python -m unittest discover -s tests"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import crawler, docgen  # noqa: E402
from core.store import Store  # noqa: E402

SAMPLE_HTML = """
<html><head><title>通知公告</title></head><body>
<nav><a href="/">首页</a><a href="/xwdt.htm">新闻动态</a></nav>
<div class="news-list">
  <ul>
    <li><a href="/info/1001.html" title="关于期中教学检查的通知">关于期中教学检查的通知</a>
        <span class="date">2026-10-29</span></li>
    <li><a href="https://example.edu.cn/info/1002.html">我校学子在全国竞赛中获奖</a>
        <span class="date">10-30 09:12</span></li>
    <li><a href="javascript:void(0)">更多</a></li>
  </ul>
</div>
<footer><a href="/about.htm">关于我们</a></footer>
</body></html>
"""


class TestParseDatetime(unittest.TestCase):
    def test_full_and_short(self):
        today = dt.date(2026, 10, 30)
        self.assertEqual(crawler.parse_datetime("2026-10-29", today), "2026-10-29")
        self.assertEqual(crawler.parse_datetime("2026年10月29日 09:12", today), "2026-10-29 09:12")
        self.assertEqual(crawler.parse_datetime("10-30 09:12", today), "2026-10-30 09:12")
        self.assertEqual(crawler.parse_datetime("2026/12/1", today), "2026-12-01")
        # 高校列表页常见的“日 + 年.月”拆开写法
        self.assertEqual(crawler.parse_datetime("30 2026.10", today), "2026-10-30")
        self.assertEqual(crawler.parse_datetime("2026.10 30", today), "2026-10-30")
        self.assertEqual(crawler.parse_datetime("26 2026.10 09:12", today), "2026-10-26 09:12")
        self.assertEqual(crawler.parse_datetime("没有日期", today), "")
        self.assertEqual(crawler.parse_datetime("2026-02-31", today), "")


class TestParseList(unittest.TestCase):
    def test_configured_selectors(self):
        items = crawler.parse_list(
            SAMPLE_HTML, "https://www.example.edu.cn/tzgg.htm",
            {"item": "ul li", "title": "a", "link": "a", "date": "span"},
            today=dt.date(2026, 10, 30),
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["url"], "https://www.example.edu.cn/info/1001.html")
        self.assertEqual(items[0]["published_at"], "2026-10-29")
        self.assertEqual(items[1]["published_at"], "2026-10-30 09:12")

    def test_auto_detect(self):
        items = crawler.parse_list(
            SAMPLE_HTML, "https://www.example.edu.cn/tzgg.htm",
            selectors={}, today=dt.date(2026, 10, 30),
        )
        titles = [item["title"] for item in items]
        self.assertIn("关于期中教学检查的通知", titles)
        self.assertNotIn("更多", titles)
        self.assertNotIn("首页", titles)


class TestStore(unittest.TestCase):
    def test_dedupe_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "news.db")
            base = {
                "summary": "摘要", "source_id": "demo", "source_name": "示例",
                "published_at": "2026-10-30 09:00", "day": "2026-10-30",
                "first_seen": "2026-10-30 10:00:00",
            }
            first = store.add_items([{**base, "url": "https://a.cn/1", "title": "消息一"}])
            again = store.add_items([{**base, "url": "https://a.cn/1", "title": "消息一"}])
            self.assertEqual(len(first), 1)
            self.assertEqual(len(again), 0)
            self.assertEqual(store.day_counts()[0]["count"], 1)
            self.assertEqual(store.total(), 1)
            self.assertEqual(store.existing_urls(["https://a.cn/1"]), {"https://a.cn/1"})

            store.upsert_digest("2026-10-30", "a.docx", 1, "2026-10-30 10:05")
            store.upsert_digest("2026-10-30", "b.docx", 1, "2026-10-30 10:06")
            self.assertEqual(store.get_digest("2026-10-30")["filename"], "b.docx")


class TestDemoAndDocx(unittest.TestCase):
    def test_demo_is_stable(self):
        day = dt.date(2026, 10, 30)
        a = crawler.demo_items(day, {"id": "demo", "name": "示例"})
        b = crawler.demo_items(day, {"id": "demo", "name": "示例"})
        self.assertEqual([x["title"] for x in a], [x["title"] for x in b])
        self.assertTrue(6 <= len(a) <= 8)
        for item in a:
            self.assertTrue(item["published_at"].startswith("2026-10-30"))

    def test_build_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = [
                {"title": "测试消息一", "summary": "第一条摘要。", "source_name": "示例数据源",
                 "published_at": "2026-10-30 09:10", "url": "https://example.edu.cn/1"},
                {"title": "测试消息二", "summary": "", "source_name": "示例数据源",
                 "published_at": "2026-10-30 10:20", "url": "https://example.edu.cn/2"},
            ]
            path = docgen.build_digest(items, "2026-10-30", tmp)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 5000)
            from docx import Document
            text = "\n".join(p.text for p in Document(str(path)).paragraphs)
            self.assertIn("校园每日快讯", text)
            self.assertIn("测试消息一", text)
            self.assertIn("本期共收录 2 条", text)


if __name__ == "__main__":
    unittest.main()
