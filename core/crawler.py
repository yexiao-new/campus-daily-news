"""抓取与解析：支持可配置 CSS 选择器、自动识别列表、示例数据。"""
import concurrent.futures
import datetime as dt
import random
import re
import time
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
}

DATE_RE = re.compile(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})")
SPLIT_DATE_DAY_FIRST = re.compile(r"(?<!\d)(\d{1,2})\s+(20\d{2})\s*[./-]\s*(\d{1,2})(?!\d)")
SPLIT_DATE_YEAR_FIRST = re.compile(r"(?<!\d)(20\d{2})\s*[./-]\s*(\d{1,2})\s+(\d{1,2})(?!\d)")
SHORT_DATE_RE = re.compile(r"(?<![\d/])(\d{1,2})\s*[-/月.]\s*(\d{1,2})(?![\d/])")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")

LIST_HINTS = re.compile(r"(news|list|notice|tzgg|xwdt|article|content|main|gg|show|item|wp_article)", re.I)
SKIP_HINTS = re.compile(r"(nav|menu|header|footer|breadcrumb|crumb|pagination|page-?nav|share|sidebar|friend|login)", re.I)
NAV_WORDS = {
    "首页", "上一页", "下一页", "尾页", "更多", "返回", "登录", "注册", "English",
    "网站首页", "学校首页", "联系我们", "关于我们", "设为首页", "加入收藏",
}

DEMO_POOL = [
    ("关于2026年部分节假日放假安排的通知", "根据上级有关文件精神，结合学校实际，现将2026年部分节假日放假调休安排通知如下，请各单位提前做好工作安排。"),
    ("关于开展2026年秋季学期期中教学检查的通知", "为进一步规范教学秩序、提升课堂教学质量，学校决定于第9至第11周开展期中教学检查，各学院需按要求提交自查报告。"),
    ("我校学子在全国大学生数学建模竞赛中获佳绩", "2026年全国大学生数学建模竞赛成绩揭晓，我校共获全国一等奖3项、二等奖5项，省级奖项21项，获奖数量再创新高。"),
    ("图书馆关于调整开放时间的通知", "为满足同学们的学习需求，自本周起图书馆自习区开放时间延长至23:00，借阅台服务时间保持不变。"),
    ("我校与省高新技术产业开发区签署战略合作协议", "双方将围绕人才培养、科研成果转化和实习实训基地建设开展深度合作，共同打造校地协同创新样板。"),
    ("2026年校园十佳歌手大赛报名正式启动", "本届大赛面向全体在校学生，报名截止时间为本月底，初赛将于下月中旬在大学生活动中心举行。"),
    ("关于做好2026级新生学籍信息核对工作的通知", "请各学院组织新生登录教务系统核对本人学籍信息，如发现姓名、身份证号等信息有误，须于本周五前反馈。"),
    ("我校教师团队在国际顶级期刊发表最新研究成果", "该研究在新能源材料领域取得重要突破，相关论文以我校为第一完成单位发表，标志着我校科研水平持续提升。"),
    ("关于举办第十届校园科技创新文化节的通知", "文化节期间将举办科技作品展、创新论坛、创客马拉松等系列活动，欢迎广大师生积极参与。"),
    ("我校举行2026级本科生开学典礼", "校长在典礼上寄语新生，希望大家立大志、明大德、成大才、担大任，在青春的赛道上奋力奔跑。"),
    ("关于开展校园消防安全专项检查的通知", "为切实消除安全隐患，保卫处将联合相关部门对宿舍、实验室、食堂等重点区域开展消防安全专项检查。"),
    ("关于2026年下半年全国大学英语四、六级考试报名的通知", "本次考试报名采用网上报名方式，请考生在规定时间内完成注册、缴费，逾期不再补报。"),
    ("我校志愿服务项目获省级表彰", "在近日举行的全省青年志愿服务项目大赛中，我校“童心筑梦”支教项目荣获金奖，另有2个项目获银奖。"),
    ("关于校园一卡通系统升级维护的公告", "为提升系统稳定性，一卡通系统将于本周六凌晨进行升级维护，期间充值、消费等功能暂停使用。"),
    ("我校男子篮球队夺得省大学生篮球联赛冠军", "在决赛中，我校男篮以78比72战胜对手，时隔五年再度捧起冠军奖杯。"),
    ("关于2027届毕业生就业双选会安排的通知", "学校将于下月举办秋季大型就业双选会，预计邀请用人单位300余家，请毕业生提前准备好简历。"),
]


# ---------------------------------------------------------------- 基础工具
def parse_datetime(text, today=None):
    """从文本中解析日期（可带时间），返回 'YYYY-MM-DD[ HH:MM]'，失败返回空串。"""
    today = today or dt.date.today()
    if not text:
        return ""
    # 适配“30 2026.10”这类拆开的日期写法（日 + 年.月，常见于高校列表页）
    text = SPLIT_DATE_DAY_FIRST.sub(r"\2-\3-\1", text)
    text = SPLIT_DATE_YEAR_FIRST.sub(r"\1-\2-\3", text)
    m = DATE_RE.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = SHORT_DATE_RE.search(text)
        if not m:
            return ""
        year, month, day = today.year, int(m.group(1)), int(m.group(2))
    try:
        date = dt.date(year, month, day)
    except ValueError:
        return ""
    tm = TIME_RE.search(text)
    if tm:
        return f"{date.isoformat()} {int(tm.group(1)):02d}:{tm.group(2)}"
    return date.isoformat()


def http_get(url, timeout=15, attempts=3):
    """GET 页面，遇到网络抖动自动重试；登录跳转直接给出明确提示。"""
    last_error = None
    for attempt in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            final_url = (resp.url or "").lower()
            if resp.history and any(k in final_url for k in ("login", "onecas", "/cas/", "sso", "tpass")):
                raise RuntimeError("该地址需要登录（被跳转到了统一认证），请改用公开的新闻/通知列表页")
            return _decode(resp)
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    raise last_error


def _decode(resp):
    """优先按页面 meta charset 解码，避免中文站点被识别成 Latin-1。"""
    raw = resp.content
    head = raw[:4096].decode("ascii", "ignore")
    match = re.search(r'charset\s*=\s*["\']?([\w.-]+)', head, re.I)
    encoding = match.group(1).lower() if match else ""
    if not encoding:
        encoding = (resp.apparent_encoding or "").lower()
    if encoding in ("gb2312", "gbk", "gb18030"):
        encoding = "gb18030"
    if not encoding:
        encoding = "utf-8"
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _absolute(base, href):
    href = (href or "").strip()
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""
    return urldefrag(urljoin(base, href))[0]


def _matches(node, selector):
    """判断节点本身是否匹配简单选择器（仅处理 #id .class tag）。"""
    selector = (selector or "").strip()
    if not selector or " " in selector or ">" in selector:
        return False
    if selector.startswith("#"):
        return selector[1:] in (node.get("id") or "").split()
    if selector.startswith("."):
        return selector[1:] in (node.get("class") or [])
    if selector.startswith("["):
        return False
    return node.name == selector


# ---------------------------------------------------------------- 列表解析
def parse_list(html, base_url, selectors=None, max_items=30, today=None):
    selectors = selectors or {}
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    item_selector = _clean(selectors.get("item"))
    nodes = soup.select(item_selector) if item_selector else []
    if not nodes:
        nodes = _heuristic_nodes(soup)

    items, seen = [], set()
    for node in nodes:
        try:
            item = _parse_node(node, selectors, base_url, today)
        except Exception:
            item = None
        if not item:
            continue
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        items.append(item)
        if len(items) >= max_items:
            break
    return items


def _parse_node(node, selectors, base_url, today):
    title_selector = _clean(selectors.get("title")) or "a"
    title_node = node if _matches(node, title_selector) else node.select_one(title_selector)
    if title_node is None:
        title_node = node.find("a")
    if title_node is None:
        return None

    link_selector = _clean(selectors.get("link"))
    if link_selector:
        link_node = node.select_one(link_selector)
    else:
        link_node = title_node if title_node.name == "a" else title_node.find("a")
    if link_node is None or link_node.name != "a":
        link_node = node.find("a")
    if link_node is None:
        return None

    title = _clean(title_node.get("title") or title_node.get_text(" ", strip=True))
    title = title.strip(" ·-—|")
    if not (4 <= len(title) <= 120) or title in NAV_WORDS:
        return None

    url = _absolute(base_url, link_node.get("href"))
    if not url or urlparse(url).scheme not in ("http", "https"):
        return None

    date_selector = _clean(selectors.get("date"))
    date_node = node.select_one(date_selector) if date_selector else None
    date_text = _clean(date_node.get_text(" ", strip=True)) if date_node else _clean(node.get_text(" ", strip=True))

    summary = ""
    summary_selector = _clean(selectors.get("summary"))
    if summary_selector:
        snode = node.select_one(summary_selector)
        if snode is not None:
            summary = _clean(snode.get_text(" ", strip=True))[:160]

    return {
        "title": title,
        "url": url,
        "published_at": parse_datetime(date_text, today),
        "summary": summary,
    }


def _heuristic_nodes(soup):
    """没有配置选择器时的兜底识别。"""
    for selector in (
        ".news-list li", ".news_list li", ".list li", "ul.list li",
        ".wp_article_list li", ".article-list li", ".list-item",
        ".index-news li", ".news li", "ul li",
    ):
        nodes = soup.select(selector)
        nodes = [n for n in nodes if n.find("a")]
        if len(nodes) >= 3:
            return nodes

    dated = [
        n for n in soup.find_all(["li", "tr", "article", "div"])
        if n.find("a") and DATE_RE.search(n.get_text(" ", strip=True))
    ]
    if len(dated) >= 3:
        return dated

    anchors = []
    for a in soup.find_all("a"):
        if _skip_anchor(a):
            continue
        text = _clean(a.get_text(" ", strip=True))
        if 6 <= len(text) <= 90:
            anchors.append(a)
    return anchors


def _skip_anchor(a):
    text = _clean(a.get_text(" ", strip=True))
    if text in NAV_WORDS:
        return True
    href = (a.get("href") or "").strip()
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return True
    for parent in a.parents:
        if parent.name in ("nav", "header", "footer"):
            return True
        marker = " ".join([parent.get("id") or "", " ".join(parent.get("class") or [])])
        if marker and SKIP_HINTS.search(marker):
            return True
        if parent.name == "body":
            break
    return False


# ---------------------------------------------------------------- 详情摘要
def extract_summary(html, selector=None, limit=160):
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "header", "footer"]):
        tag.decompose()
    scope = None
    if selector:
        scope = soup.select_one(selector)
    if scope is None:
        for sel in (
            "article", ".article-content", ".article", ".content", "#content",
            ".v_news_content", ".TRS_Editor", ".wp_articlecontent", ".news_content",
            ".detail", "#vsb_content", ".show-content",
        ):
            scope = soup.select_one(sel)
            if scope is not None:
                break
    if scope is None:
        scope = soup.body or soup

    paragraphs = [_clean(p.get_text(" ", strip=True)) for p in scope.find_all("p")]
    text = " ".join(p for p in paragraphs if len(p) >= 12)
    if len(text) < 20:
        text = _clean(scope.get_text(" ", strip=True))
    text = re.sub(r"^(发布时间|发布日期|发布时间：)\s*[:：]?\s*", "", text)
    return text[:limit].strip()


def enrich_details(items, source, workers=6, max_fetch=15):
    """为缺少摘要的条目抓取详情页首段文字。"""
    targets = [it for it in items if not it.get("summary")][:max_fetch]
    if not targets:
        return items
    selectors = source.get("selectors") or {}
    detail_selector = _clean(selectors.get("detail"))

    def work(item):
        try:
            html = http_get(item["url"], timeout=12)
            return extract_summary(html, detail_selector)
        except Exception:
            return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, it) for it in targets]
        for item, future in zip(targets, futures):
            try:
                summary = future.result()
            except Exception:
                summary = ""
            if summary:
                item["summary"] = summary
    return items


# ---------------------------------------------------------------- 示例数据
def demo_items(day, source):
    """生成稳定、可重复的示例消息，便于在接入真实官网前预览完整流程。"""
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    rng = random.Random(day.toordinal() * 7919)
    count = rng.randint(6, 8) if day.weekday() < 5 else rng.randint(3, 5)
    picks = rng.sample(DEMO_POOL, min(count, len(DEMO_POOL)))
    slots = sorted(rng.sample(range(9 * 60, 17 * 60 + 30), len(picks)))
    slug = day.strftime("%Y%m%d")
    items = []
    for index, (title, summary) in enumerate(picks):
        minutes = slots[index]
        published = dt.datetime.combine(day, dt.time(minutes // 60, minutes % 60))
        items.append({
            "title": title,
            "url": f"https://www.example.edu.cn/news/{slug}/n{index + 1:02d}.html",
            "published_at": published.strftime("%Y-%m-%d %H:%M"),
            "summary": summary,
            "source_id": source.get("id", "demo"),
            "source_name": source.get("name", "示例数据源"),
        })
    return items
