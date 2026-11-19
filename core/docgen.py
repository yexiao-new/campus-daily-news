"""把某一天的消息排版成一份 Word 文档。"""
import datetime as dt
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "微软雅黑"
ACCENT = RGBColor(0x1D, 0x4E, 0xD8)
INK = RGBColor(0x0F, 0x17, 0x2A)
BODY = RGBColor(0x33, 0x41, 0x55)
MUTED = RGBColor(0x64, 0x74, 0x8B)
LINK = RGBColor(0x25, 0x63, 0xEB)

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

TEMPLATE = {
    "kicker": "CAMPUS DAILY BRIEF",
    "title": "校园每日快讯",
}


# ---------------------------------------------------------------- 字体与装饰
def _set_run_font(run, size=None, bold=None, color=None):
    run.font.name = FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _style_font(style, size=None, color=None):
    style.font.name = FONT
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)
    if size is not None:
        style.font.size = Pt(size)
    if color is not None:
        style.font.color.rgb = color


def _add_border(paragraph, color="DCE3F0", size=8, space=6):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    ppr.insert_element_before(
        pbdr,
        "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
        "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
        "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
        "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
        "w:textDirection", "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl",
        "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
    )


def _para(doc, text="", size=10.5, color=INK, bold=False, align=None,
          space_before=0, space_after=0, line=1.5, keep_next=False):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = line
    if keep_next:
        fmt.keep_with_next = True
    if align is not None:
        paragraph.alignment = align
    if text:
        run = paragraph.add_run(text)
        _set_run_font(run, size=size, bold=bold, color=color)
    return paragraph


def _divider(doc, color="EEF2F9", size=6, space_before=10, space_after=10):
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = 1.0
    run = paragraph.add_run(" ")
    _set_run_font(run, size=1, color=MUTED)
    _add_border(paragraph, color=color, size=size, space=2)
    return paragraph


def _add_hyperlink(paragraph, url, text, size=8.5):
    r_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)
    rpr.append(rfonts)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "2563EB")
    rpr.append(color)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    run.append(rpr)

    text_el = OxmlElement("w:t")
    text_el.set(qn("xml:space"), "preserve")
    text_el.text = text
    run.append(text_el)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _add_page_field(paragraph, size=8):
    run = paragraph.add_run()
    _set_run_font(run, size=size, color=MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, separate, placeholder, end):
        run._r.append(el)


# ---------------------------------------------------------------- 组装文档
def build_digest(items, day, out_dir, title=None, generated_at=None, filename=None):
    if not items:
        raise ValueError("这一天还没有收录消息")

    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    generated_at = generated_at or dt.datetime.now()

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.1)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.3)
    section.right_margin = Cm(2.3)

    normal = doc.styles["Normal"]
    _style_font(normal, size=10.5, color=BODY)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)

    # 页眉装饰线：上方细线 + 刊头文字
    kicker = _para(doc, TEMPLATE["kicker"], size=7.5, color=MUTED,
                   align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, line=1.0)
    for run in kicker.runs:
        run.font.all_caps = True

    _para(doc, title or TEMPLATE["title"], size=22, color=INK, bold=True,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, line=1.15)

    date_line = f"{day.year}年{day.month}月{day.day}日 · {WEEKDAYS[day.weekday()]}"
    _para(doc, date_line, size=10.5, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER,
          space_after=12, line=1.2)

    _divider(doc, color="C7D2FE", size=12, space_before=0, space_after=14)

    ordered = sorted(items, key=lambda it: (it.get("published_at") or "", it.get("id") or 0))
    sources = []
    for item in ordered:
        name = item.get("source_name") or ""
        if name and name not in sources:
            sources.append(name)
    summary_line = f"本期共收录 {len(items)} 条校园消息"
    if sources:
        summary_line += "　·　来源：" + "、".join(sources[:3])
    _para(doc, summary_line, size=9, color=MUTED, space_after=14)

    for index, item in enumerate(ordered, start=1):
        number = f"{index:02d}"
        head = _para(doc, space_after=3, line=1.4, keep_next=True)
        nrun = head.add_run(number)
        _set_run_font(nrun, size=10, bold=True, color=ACCENT)
        head.add_run("    ")
        trun = head.add_run(item.get("title", "").strip())
        _set_run_font(trun, size=12.5, bold=True, color=INK)

        meta_bits = []
        if item.get("source_name"):
            meta_bits.append(f"来源：{item['source_name']}")
        if item.get("published_at"):
            meta_bits.append(f"发布时间：{item['published_at']}")
        if meta_bits:
            meta = _para(doc, space_after=5, line=1.3, keep_next=True)
            mrun = meta.add_run("　｜　".join(meta_bits))
            _set_run_font(mrun, size=8.5, color=MUTED)

        if item.get("summary"):
            _para(doc, item["summary"], size=10.5, color=BODY,
                  space_after=5, line=1.55)

        if item.get("url"):
            link_para = _para(doc, space_after=0, line=1.3)
            label = link_para.add_run("原文链接：")
            _set_run_font(label, size=8.5, color=MUTED)
            _add_hyperlink(link_para, item["url"], item["url"], size=8.5)

        if index < len(ordered):
            _divider(doc, color="EEF2F9", size=6, space_before=10, space_after=10)

    _para(doc, "— 完 —", size=9, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER,
          space_before=8, space_after=0, line=1.2)

    footer_text = f"校园每日快讯 · 自动生成于 {generated_at:%Y-%m-%d %H:%M} · 第 "
    footer = doc.sections[0].footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    frun = fp.add_run(footer_text)
    _set_run_font(frun, size=8, color=MUTED)
    _add_page_field(fp, size=8)
    end_run = fp.add_run(" 页")
    _set_run_font(end_run, size=8, color=MUTED)

    props = doc.core_properties
    props.title = f"{title or TEMPLATE['title']} {day.isoformat()}"
    props.author = "校园每日快讯"
    props.subject = "校园官网每日消息汇编"
    props.comments = "由校园每日快讯自动生成"

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = filename or f"{title or TEMPLATE['title']}_{day.isoformat()}.docx".replace("/", "-")
    path = out_dir / filename
    doc.save(str(path))
    return path
