#!/usr/bin/env python3
"""成稿 Markdown → 交付 PDF：封面 + 目录 + 正文 + 页码 + 书签。

为什么自建这一条链路，而不是走 doc-format 的 Word 中转：
  1. 本机没有 pandoc、LaTeX、WeasyPrint；doc-format 的 PDF 路径依赖 LibreOffice，
     而这台机器上也没有 LibreOffice —— 走它必然失败，不是「不好用」而是「跑不通」。
  2. Word 中转多一道工序，也带进三类与内容无关的坑（列表编号连号、空白页、首页不同）。
     Markdown 直接排成 PDF 没有这些中间态，改稿也就少一次翻译。

引擎选本机现成的 Google Chrome 无头打印：它对 CSS 分页（@page / break-before）和最全的
中文字体族支持最好。页码与 PDF 书签由 PyMuPDF 后处理补上 —— Chrome 的 @page 不支持
counter()，页码没法靠 CSS 出，只能打完再盖。

用法：
    python3 scripts/md_to_pdf.py \
        --input  "03-交付物/某某公司-深度研究.md" \
        --output "03-交付物/某某公司-深度研究.pdf"

可选参数：--no-toc 不出目录；--no-page-numbers 不盖页码；--keep-html 保留中间 HTML。
"""

import argparse
import base64
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

# 本 skill 依赖两个第三方库：markdown（Markdown → HTML）与 PyMuPDF（页码、书签、校验）。
# 不做静默降级 —— 缺了就直接报错并给出安装命令，免得生成出一份「看起来成功、其实没页码」的 PDF。
try:
    import markdown as md_lib
except ImportError:
    md_lib = None

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

# Markdown 扩展：表格、连续列表分块、代码块、行内属性。
# 少一个 tables，报告里所有财务表都会退化成一段竖线文本 —— 这是最不能忍的静默失败。
MD_EXTENSIONS = ["tables", "sane_lists", "fenced_code", "attr_list"]

# 图：Markdown 里写 ![题注](图/xxx.svg)，题注取 alt 文本，渲染成 figure + figcaption。
# 图片一律 base64 内联进 HTML —— HTML 建在临时目录里，相对路径到那时已经断了；
# 外链与缺图都直接报错退出，不做静默降级（图表是交付物的一部分，丢了就是丢了）。
# 一次匹配两种写法：独占一段的图，与夹在文字里的图。**必须一趟做完** ——
# 先替换 <p><img></p> 再扫裸 <img> 的话，第一趟生成的 figure 会被第二趟再包一层题注。
IMG_BLOCK = re.compile(r"(?:<p>\s*)?(<img\b[^>]*>)(?:\s*</p>)?")
IMG_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}

# 重点标注的两个标记：==关键结论==（主色）、@@风险与雷@@（红）。
# 规则写在 references/06-成稿与PDF交付.md 第四节；密度上限 30 处，超了就失去作用。
EMPHASIS = [
    (re.compile(r"==(.+?)=="), "mk-key"),
    (re.compile(r"@@(.+?)@@"), "mk-risk"),
]
EMPHASIS_CAP = 30

# 各系统常见的 Chrome / Chromium 位置。换台机器不必改脚本，也可以用 CHROME_BIN 覆盖。
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/opt/homebrew/bin/chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    """按「环境变量 → 常见安装位置 → PATH」的顺序找 Chrome 可执行文件。"""
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def normalize_markdown(text):
    """成稿规范化：只修「会静默失败」的地方，不动内容。

    修的是两类：整行的分隔线 --- （分节已有强制分页，留着只会在页脚多一条横线），
    以及块级元素前缺空行 —— Python-Markdown 要求标题与表格前必须有空行，缺了不报错、
    直接把标题当正文、把表格当普通段落，属于最阴的一类问题。
    """
    lines = text.split("\n")
    out = []
    for raw in lines:
        line = raw.rstrip()
        is_heading = re.match(r"^#{1,6} ", line) is not None
        is_table_row = line.startswith("|")
        prev = out[-1] if out else ""

        # 整行分隔线直接丢掉（--- / *** / ___）
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            continue

        # 块级元素前补空行：上一行非空，且不是同类块的一部分
        if line and prev:
            prev_is_table_row = prev.startswith("|")
            if is_heading or (is_table_row and not prev_is_table_row):
                out.append("")
        out.append(line)
    return "\n".join(out)


def split_cover_body(text):
    """把成稿切成「封面」与「正文」。

    规则：第一个一级标题及其后、到第二个一级标题之前的内容算封面（标题 + 免责声明 + 数据基准）。
    这条规则不依赖公司名或节名，换一份成稿照样成立；只有一个一级标题时视为没有封面。
    """
    lines = text.split("\n")
    h1_idx = [i for i, ln in enumerate(lines) if re.match(r"^# ", ln)]
    if len(h1_idx) < 2:
        return "", text
    cut = h1_idx[1]
    return "\n".join(lines[:cut]).strip(), "\n".join(lines[cut:]).strip()


def apply_emphasis(text):
    """把重点标注标记转成带颜色的 span（在 Markdown 转换之前做）。

    `==关键结论==` → 主色；`@@风险与雷@@` → 红。转换后的 span 是行内 HTML，
    python-markdown 会原样保留，且仍会解析 span 内部的 `**加粗**`。
    代码块（``` 围起来的部分）里的标记不转换，避免误伤示例命令。
    """
    out, in_fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            for pat, cls in EMPHASIS:
                line = pat.sub(lambda m, c=cls: f'<span class="{c}">{m.group(1)}</span>', line)
        out.append(line)
    return "\n".join(out)


_PLACEHOLDER_CELLS = {"—", "–", "-", "/", "无", "缺", "缺席", "暂无", "不适用",
                     "未披露", "未取得", "n/a", "n.a.", "na", "null"}
_NUMBER_CELL = re.compile(
    r"[\u2212+\-]?\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|％|亿元|万元|亿吨|万吨|亿股|万股|亿美元|美元|欧元|元|亿|万|倍|年|个月|天|吨|股|个)?")


def _split_table_row(line):
    """`| a | b |` → ["a", "b"]。首尾的竖线可有可无。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _cell_is_number(cell):
    """数字返回 True，占位符（—、不适用）返回 None，其余返回 False。"""
    s = strip_inline(cell).replace(" ", "").replace("\u3000", "")
    if not s or s.lower() in _PLACEHOLDER_CELLS:
        return None
    return bool(_NUMBER_CELL.fullmatch(s))


def align_numeric_columns(text):
    """给「整列都是数字」的表列补上右对齐。

    成稿里不写对齐（见 references/06 第五节）——对齐是排版的事，不是写作的事。
    这里只改分隔行（`| --- |` → `| ---: |`），python-markdown 的 tables 扩展
    会把它转成单元格上的行内 style。**已有对齐标记的列不覆盖**，作者写了就听作者的。

    判定从严：整列除了占位符（`—`、`不适用`）之外必须都是数字，才算数字列；
    至少要有两个真数字。混着单位、百分号、带中文的单元格照算数字（`−5.75 亿元`、
    `3.21%`），但只要有一格是文字，整列就留在左边——宁可漏排，不可错排。
    """
    lines = text.split("\n")
    out, i = list(lines), 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = lines[i:j]
        # 第二行是分隔行；表格至少要有表头、分隔行、一行正文
        if len(block) >= 3 and re.fullmatch(r"[\|\s:\-]+", block[1].strip()):
            out[i:j] = _align_table_block(block)
        i = j
    return "\n".join(out)


def _align_table_block(block):
    header, delim, body = block[0], block[1], block[2:]
    cols = len(_split_table_row(header))
    delim_cells = _split_table_row(delim)
    if len(delim_cells) != cols:
        return block

    right = [False] * cols
    for c in range(cols):
        marks = []
        for row in body:
            cells = _split_table_row(row)
            if c < len(cells):
                marks.append(_cell_is_number(cells[c]))
        real = [m for m in marks if m is not None]
        right[c] = len(real) >= 2 and all(real)

    new_delim = []
    for c, cell in enumerate(delim_cells):
        if ":" in cell or not right[c]:
            new_delim.append(cell)
        else:
            new_delim.append(cell.rstrip() + ":")
    return [header, "| " + " | ".join(new_delim) + " |"] + body


def report_emphasis(raw_md):
    """统计重点标注并做密度校验，返回 (关键结论数, 风险警报数)。

    标记必须成对：`==` 的总出现次数应正好是标记数的两倍，`@@` 同理。
    落单的标记不会被转换，会在正文里留下字面字符，属于必须拦下的错误。
    代码块里的字符不参与统计——apply_emphasis 也不转换那里的标记，两边口径一致。
    """
    counted, in_fence = [], False
    for line in raw_md.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            counted.append(line)
    text = "\n".join(counted)
    key = len(EMPHASIS[0][0].findall(text))
    risk = len(EMPHASIS[1][0].findall(text))
    for ch, n in (("==", key), ("@@", risk)):
        if text.count(ch) != n * 2:
            print(f"  ! 有落单的 {ch} 标记：共出现 {text.count(ch)} 次，只配成 {n} 对，请检查成稿",
                  file=sys.stderr)
    total = key + risk
    print(f"  重点标注 {total} 处（关键结论 {key}｜风险警报 {risk}）｜上限 {EMPHASIS_CAP}")
    if total > EMPHASIS_CAP:
        print(f"  ! 重点标注 {total} 处已超过上限 {EMPHASIS_CAP} 处，读者会不再注意，请删减",
              file=sys.stderr)
    return key, risk


def collect_headings(body_md):
    """取出正文里的一级、二级标题，供目录与书签使用。"""
    heads = []
    for line in body_md.split("\n"):
        m = re.match(r"^(#{1,2}) (.+)$", line)
        if m:
            # 标题里的行内标记（含重点标注）去掉，目录与书签里只留纯文字
            heads.append((len(m.group(1)), strip_inline(m.group(2))))
    return heads


def md_fragment(text):
    """Markdown 片段 → HTML 片段。"""
    return md_lib.markdown(text, extensions=MD_EXTENSIONS)


def _img_html(tag: str, base_dir: Path) -> tuple:
    """把 <img> 标签换成内联 data URI，返回 (新标签, 题注)。"""
    src_m = re.search(r'src="([^"]*)"', tag)
    alt_m = re.search(r'alt="([^"]*)"', tag)
    src = src_m.group(1) if src_m else ""
    alt = (alt_m.group(1) if alt_m else "").strip()
    if not src:
        return tag, alt
    if src.startswith("data:"):
        return tag, alt
    if re.match(r"https?://", src):
        sys.exit(f"报告里的图必须随报告落盘，不能外链：{src}\n"
                 "（外链图在别人机器上打开就是空白，也失去了可复算性。）")
    path = (base_dir / unquote(src)).resolve()
    if not path.is_file():
        sys.exit(f"找不到图：{src}\n按成稿所在目录解析为 {path}。\n"
                 "图要用 scripts/chart_svg.py 之类的脚本从数据生成，放在成稿同级的 图/ 目录下。")
    mime = IMG_MIME.get(path.suffix.lower())
    if mime is None:
        sys.exit(f"不支持的图格式：{path.name}（用 .svg / .png / .jpg）")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{b64}" alt="{alt}">', alt


def inline_images(html: str, base_dir: Path) -> str:
    """把 HTML 里的本地图片内联成 data URI，并按题注包成 figure。"""
    def repl(m):
        img, alt = _img_html(m.group(1), base_dir)
        return f"<figure>{img}<figcaption>{alt}</figcaption></figure>" if alt else img

    return IMG_BLOCK.sub(repl, html)


def strip_inline(text):
    """去掉行内标记，得到与 PDF 抽取文本一致的纯文本（用于定位页）。"""
    text = re.sub(r'<span class="mk-(?:key|risk)">(.+?)</span>', r"\1", text)
    text = re.sub(r"==(.+?)==", r"\1", text)
    text = re.sub(r"@@(.+?)@@", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.strip()


def first_body_probe(body_md):
    """取正文第一段正文（非标题、非表格）的前若干字，用来在 PDF 里找正文起始页。"""
    for line in body_md.split("\n"):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|") or s.startswith(">") or s.startswith("-"):
            continue
        s = strip_inline(s)
        if len(s) >= 8:
            return s[:24]
    return ""


CSS = """
@page { size: A4; margin: 22mm 19mm 20mm 19mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", "Source Han Serif SC", "AR PL UMing CN", serif; font-size: 11.5pt;
       line-height: 1.65; color: #000; margin: 0; }
p { margin: 0 0 6pt; text-indent: 2em; }

/* 标题三级：一级是「部分」，二级是「节」，三级是小标题。
   颜色与表格、封面、重点标注共用同一个主色（陶土），形成一套色。 */
h1 { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 16.5pt; color: #8f3a2b;
     break-before: page; margin: 0 0 10pt; padding: 0 0 5pt; border-bottom: 1.4pt solid #8f3a2b;
     line-height: 1.42; }
h2 { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 12.5pt; color: #7a2f22;
     margin: 15pt 0 7pt; padding-left: 7pt; border-left: 3.4pt solid #8f3a2b; line-height: 1.45; }
h3 { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 11.5pt; color: #2b2b2b; margin: 12pt 0 5pt; line-height: 1.45; }
h1 + h2, h1 + h3 { margin-top: 4pt; }
strong { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-weight: 600; }
.mk-key { color: #8f3a2b; font-weight: 700; background: #f7ebe6; padding: 0 1.5pt; }
.mk-risk { color: #c62828; font-weight: 700; background: #fde7e5; padding: 0 1.5pt; }

ul, ol { margin: 0 0 8pt; padding-left: 2.2em; }
li { margin: 0 0 3pt; }
blockquote { margin: 0 0 10pt; padding: 7pt 12pt; background: #faf3ef;
             border-left: 2.6pt solid #8f3a2b; }
blockquote p { text-indent: 0; margin: 0 0 4pt; font-size: 10.5pt; }
blockquote p:last-child { margin-bottom: 0; }

/* 表格：三线表 + 浅底表头。原来的满格灰框是 Excel 味，也是最像「机器排版」的一处。 */
table { border-collapse: collapse; width: 100%; margin: 5pt 0 10pt; font-size: 10pt;
        border-top: 1.1pt solid #8f3a2b; border-bottom: 1.1pt solid #8f3a2b; }
th, td { border: 0; border-bottom: 0.5pt solid #ecdfd8; padding: 3.2pt 5pt;
         vertical-align: top; text-align: left; line-height: 1.45; }
thead { display: table-header-group; }
th { background: #f7ece6; color: #8f3a2b; font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-weight: 600; text-align: center;
     border-bottom: 0.5pt solid #8f3a2b; }
tbody tr:last-child td { border-bottom: 0; }
tr { break-inside: avoid; }

figure { margin: 9pt 0 12pt; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 180mm; }
figcaption { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 9.5pt; color: #333; margin-top: 4pt;
             text-align: center; text-indent: 0; line-height: 1.5; }
img { max-width: 100%; }
hr { border: 0; border-top: 0.6pt solid #c9c9c9; margin: 10pt 0; }

/* 封面。顶部色带与底部细线由 PyMuPDF 满幅画上去（HTML 到不了页面边缘），
   这里只管色带以下的文字块。 */
section.cover { break-after: page; height: 246mm; display: flex; flex-direction: column; }
.cv-hero { margin-top: 34mm; }
.cv-title { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 27pt; color: #8f3a2b; line-height: 1.32;
            margin: 0 0 7mm; padding: 0; border: 0; break-before: auto; }
.cv-sub { font-size: 12pt; line-height: 1.75; color: #1a1a1a; text-indent: 0; margin: 0 0 12mm;
          padding-left: 9pt; border-left: 3pt solid #dcc3b8; }
.cv-lower { margin-top: auto; }
.cv-meta { border-top: 0.8pt solid #c9c9c9; border-bottom: 0.8pt solid #c9c9c9;
           padding: 6pt 0; font-size: 10pt; line-height: 1.8; }
.cv-meta div { text-indent: 0; }
.cv-meta b { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; color: #8f3a2b; font-weight: 600; }
.cv-foot { margin-top: 7mm; }
.cv-basis { font-size: 8.6pt; line-height: 1.62; color: #444; text-indent: 0;
            background: #faf3ef; border-left: 2.6pt solid #8f3a2b; padding: 6pt 9pt; margin: 0 0 6pt; }
.cv-basis b { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; color: #8f3a2b; }
.cv-disc { font-size: 8.2pt; line-height: 1.6; color: #666; text-indent: 0; margin: 0; }

/* 目录 */
section.toc { break-before: page; }
.toc-title { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-size: 16pt; color: #8f3a2b; text-align: center;
             margin: 0 0 9mm; padding-bottom: 4pt; border-bottom: 1.4pt solid #8f3a2b; }
.toc ul { list-style: none; margin: 0; padding: 0; }
.toc li { display: flex; align-items: baseline; font-size: 10.5pt; line-height: 1.85;
          text-indent: 0; margin: 0; }
.toc li.lvl-1 { font-family: "Heiti SC", "STHeiti", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", sans-serif; font-weight: 600; color: #7a2f22; }
.toc li.lvl-2 { font-size: 10pt; padding-left: 1.8em; line-height: 1.72; color: #333; }
.toc .dots { flex: 1 1 auto; border-bottom: 0.8pt dotted #b4b4b4; margin: 0 6pt;
             transform: translateY(-3pt); }
.toc .pg { flex: 0 0 auto; font-variant-numeric: tabular-nums; }
"""

# 封面顶部色带左侧的字样。这是用户自己的研究档案，不是任何机构的产品，
# 所以不写机构名，用品类名占位 —— 换任何一份成稿都成立。
COVER_BRAND = "上市公司深度研究"

HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head><body>
{cover}
{toc}
<section class="body">{body}</section>
</body></html>
"""


def build_toc_html(headings, page_map=None):
    """生成目录 HTML。

    传进来的 page_map 必须是**正文页码**（从 1 起），不是 PDF 物理页序 ——
    目录上印的数字要和页脚上的数字对得上，两者差一个正文起始页的偏移。
    page_map 为空时出无页码版，用于第一遍排版。
    """
    items = []
    for idx, (level, text) in enumerate(headings):
        cls = "lvl-1" if level == 1 else "lvl-2"
        pg = ""
        if page_map and idx in page_map:
            pg = str(page_map[idx])
        items.append(
            f'<li class="{cls}"><span class="t">{text}</span>'
            f'<span class="dots"></span><span class="pg">{pg}</span></li>'
        )
    return '<section class="toc"><div class="toc-title">目录</div><ul>' + "".join(items) + "</ul></section>"


def parse_cover(cover_md):
    """把封面段拆成 (标题, 副标题, 免责声明, 数据基准)。

    封面段的契约见 references/06 第一节：第一行是 `# 公司名（代码）深度研究`，
    之后可以有一句副标题，再是 `> 免责声明`，最后是 `**数据基准**：……`。
    任何一块缺了都不报错 —— 缺的那块不渲染，旧成稿照样能出版面完整的封面。
    """
    title, subtitle, quotes, basis = "", "", [], []
    for line in cover_md.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ") and not title:
            title = s[2:].strip()
        elif s.startswith(">"):
            quotes.append(s.lstrip("> ").strip())
        elif s.lstrip("*").startswith("数据基准"):
            basis.append(strip_inline(s))
        elif title and not subtitle and not s.startswith("**") and not s.startswith("|"):
            subtitle = strip_inline(s)
    text = " ".join(basis).strip()
    for lab in ("数据基准：", "数据基准:", "数据基准"):
        if text.startswith(lab):
            text = text[len(lab):].strip()
            break
    return title, subtitle, " ".join(quotes), text


def derive_subtitle(body_md):
    """封面段没写副标题时，从「速览 · 一句话」里取第一句顶上。

    这是兜底，不是规范：作者写了副标题就用作者的（见 references/06 第一节）。
    """
    lines = body_md.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("## ") and "一句话" in line:
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s:
                    continue
                if s.startswith(("#", "|", ">", "-", "*", "!")):
                    break
                s = strip_inline(s)
                first = re.split(r"(?<=[。！？])", s)[0] or s
                return first if len(first) <= 96 else first[:95] + "…"
    return ""


def split_cover_title(title):
    """`齐翔腾达（002408.SZ）深度研究` → (公司名, 报告类型)。"""
    m = re.match(r"^(.*?)\s*(深度研究|研究报告|公司研究)$", title)
    if m and m.group(1):
        return m.group(1).strip(), m.group(2)
    return title, "深度研究"


def build_cover(title, subtitle, disclaimer, basis, date_cn):
    """封面 HTML。四条信息各就各位，缺哪条不渲染哪条。"""
    if not title:
        return ""
    name, kind = split_cover_title(title)
    meta = []
    if date_cn:
        meta.append(f"<div><b>报告日期</b>　{date_cn}</div>")
    meta.append(f"<div><b>报告性质</b>　{kind}　不构成投资建议，不提供评级与目标价</div>")
    html = ['<section class="cover">', '<div class="cv-hero">']
    if name:
        html.append(f'<h1 class="cv-title">{name}</h1>')
    if subtitle:
        html.append(f'<p class="cv-sub">{subtitle}</p>')
    html.append("</div>")
    html.append('<div class="cv-lower">')
    html.append('<div class="cv-meta">' + "".join(meta) + "</div>")
    if basis or disclaimer:
        html.append('<div class="cv-foot">')
        if basis:
            html.append(f'<div class="cv-basis"><b>数据基准</b>　{basis}</div>')
        if disclaimer:
            html.append(f'<div class="cv-disc">{disclaimer}</div>')
        html.append("</div>")
    html.append("</div>")
    html.append("</section>")
    return "".join(html)


def build_html(cover_html, toc_html, body_md, title, base_dir=None):
    body = md_fragment(body_md)
    if base_dir is not None:
        body = inline_images(body, Path(base_dir))
    return HTML_TEMPLATE.format(
        title=title, css=CSS, cover=cover_html or "", toc=toc_html, body=body
    )


def render_pdf(chrome, html_path, pdf_path):
    """用 Chrome 无头模式打印。--print-to-pdf 只认绝对路径，故先转绝对路径。"""
    if Path(pdf_path).exists():
        Path(pdf_path).unlink()
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={Path(pdf_path).resolve()}",
        Path(html_path).resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not Path(pdf_path).exists():
        raise RuntimeError(
            "Chrome 没能生成 PDF。\n命令：" + " ".join(cmd) + "\n输出：" + (proc.stderr or "")[-800:]
        )


def page_texts(doc):
    """一次性取出每页的「去空白纯文本」，后面所有定位都在这上面做。"""
    return [re.sub(r"\s+", "", p.get_text()) for p in doc]


def locate_first(texts, needle, start=0, limit=None):
    """从 start 页起找第一个包含 needle 的页（0 基）；找不到返回 None。"""
    if not needle:
        return None
    end = len(texts) if limit is None else min(len(texts), limit)
    for i in range(start, end):
        if needle in texts[i]:
            return i
    return None


def locate_headings(texts, headings, body_start):
    """顺序扫描，给每个标题定页（0 基）。标题在正文里只出现一次，顺序扫描即可。"""
    page_map = {}
    cursor = body_start
    for idx, (level, text) in enumerate(headings):
        needle = re.sub(r"\s+", "", strip_inline(text))
        hit = None
        for i in range(cursor, len(texts)):
            if needle and needle in texts[i]:
                hit = i
                break
        if hit is None:
            continue
        page_map[idx] = hit
        cursor = hit
    return page_map


def roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def draw_mixed(page, x, y, text, fontsize, color, right_edge=None):
    """中西文混排一行：数字与拉丁字母用 helv，中文用 china-s。

    PyMuPDF 的内置中文字体把阿拉伯数字也按全角渲染，日期与「（002408.SZ）」
    这类混合串会被撑得很空。这里按字符类型切字体，宽度按各自字体的实际字宽累加，
    右对齐时用总宽反推起点。
    """
    parts = re.findall(r"[\x00-\x7f]+|[^\x00-\x7f]+", text)
    fonts = ["helv" if s[0].isascii() else "china-s" for s in parts]
    widths = [pymupdf.get_text_length(s, fontname=f, fontsize=fontsize)
              for s, f in zip(parts, fonts)]
    x0 = right_edge - sum(widths) if right_edge is not None else x
    for s, f, w in zip(parts, fonts, widths):
        page.insert_text((x0, y), s, fontsize=fontsize, fontname=f, color=color)
        x0 += w


def stamp_and_bookmark(pdf_path, texts, headings, page_map, toc_start, body_start,
                       report_name="", date_cn="", brand="", has_cover=False,
                       header_footer=True):
    """盖页眉页脚与页码、画封面色带、写 PDF 书签。

    页码分三段：封面不排、目录用罗马数字、正文从 1 起 —— 与纸质报告的习惯一致。
    页眉页脚用 PyMuPDF 盖而不是 CSS：Chrome 的 @page 不支持 counter()，
    margin box（@top-center 之类）在无头打印里也不生效，只能打完再盖。
    中文字形用 PyMuPDF 内置的 china-s（黑体），与正文标题同一族。
    """
    doc = pymupdf.open(pdf_path)
    NAVY = (0.561, 0.227, 0.169)      # #8f3a2b
    GREY = (0.42, 0.42, 0.42)
    RULEC = (0.72, 0.72, 0.72)
    for pno in range(doc.page_count):
        page = doc[pno]
        width, height = page.rect.width, page.rect.height
        M = 54                             # 左右页边距（19mm ≈ 54pt）

        # 封面：满幅色带。HTML 到不了纸张边缘，所以这两条带只能在这里画。
        if has_cover and pno == 0:
            page.draw_rect(pymupdf.Rect(0, 0, width, 74), color=None, fill=NAVY)
            if brand:
                draw_mixed(page, M, 47, brand, 11, (1, 1, 1))
            if date_cn:
                draw_mixed(page, 0, 47, date_cn, 10.5, (1, 1, 1), right_edge=width - M)
            page.draw_rect(pymupdf.Rect(0, height - 17, width, height), color=None, fill=NAVY)
            continue

        if not header_footer:
            continue

        label = None
        if pno >= toc_start:
            label = (roman(pno - toc_start + 1) if pno < body_start
                     else str(pno - body_start + 1))

        # 页眉：左报告名、右日期，下面一条细线
        if report_name:
            draw_mixed(page, M, 36, report_name, 8.5, GREY)
        if date_cn:
            draw_mixed(page, 0, 36, date_cn, 8.5, GREY, right_edge=width - M)
        page.draw_line(pymupdf.Point(M, 48), pymupdf.Point(width - M, 48),
                       color=RULEC, width=0.6)

        # 页脚：左免责提示、右页码，上面一条细线
        page.draw_line(pymupdf.Point(M, height - 44), pymupdf.Point(width - M, height - 44),
                       color=RULEC, width=0.6)
        page.insert_text((M, height - 32), "本报告仅供研究参考，不构成投资建议",
                         fontsize=7.5, fontname="china-s", color=GREY)
        if label is not None:
            page.insert_textbox(pymupdf.Rect(width - M - 120, height - 40, width - M, height - 22),
                                label, fontsize=9, fontname="helv",
                                color=(0.25, 0.25, 0.25), align=pymupdf.TEXT_ALIGN_RIGHT)
    bookmarks = []
    for idx, (level, text) in enumerate(headings):
        if idx in page_map:
            bookmarks.append([level, strip_inline(text), page_map[idx] + 1])
    if bookmarks and header_footer:
        doc.set_toc(bookmarks)
    # 文档属性里留着 HeadlessChrome / Skia 是明显的机器痕迹，改成报告自己的信息
    doc.set_metadata({
        "title": report_name or "上市公司深度研究",
        "author": brand or "",
        "subject": "上市公司深度研究｜不构成投资建议，不提供评级与目标价",
        "creator": brand or "",
        "producer": brand or "",
    })
    doc.saveIncr()
    doc.close()


def main():
    ap = argparse.ArgumentParser(description="成稿 Markdown → 交付 PDF")
    ap.add_argument("--input", required=True, help="Markdown 成稿路径")
    ap.add_argument("--output", required=True, help="PDF 输出路径")
    ap.add_argument("--title", default=None, help="PDF 标题（缺省取成稿第一个标题）")
    ap.add_argument("--no-toc", action="store_true", help="不生成目录")
    ap.add_argument("--no-page-numbers", action="store_true", help="不盖页眉页脚页码、不写书签")
    ap.add_argument("--no-cover", action="store_true", help="不出封面，直接把标题段并入正文")
    ap.add_argument("--date", default=None, help="封面与页眉的日期（缺省取今天，格式 2026年10月16日）")
    ap.add_argument("--keep-html", default=None, help="把中间 HTML 另存到该路径，便于查排版")
    args = ap.parse_args()

    if md_lib is None:
        sys.exit("缺少 markdown 库。请用带货的解释器安装：\n    python3 -m pip install markdown")
    if pymupdf is None:
        sys.exit("缺少 PyMuPDF。请安装：\n    python3 -m pip install pymupdf")

    chrome = find_chrome()
    if chrome is None:
        sys.exit("找不到 Chrome / Chromium。装一个，或用 CHROME_BIN 指定可执行文件路径。")

    src = Path(args.input)
    out = Path(args.output)
    if not src.exists():
        sys.exit(f"找不到成稿：{src}")
    out.parent.mkdir(parents=True, exist_ok=True)

    raw = src.read_text(encoding="utf-8")
    report_emphasis(raw)
    text = align_numeric_columns(apply_emphasis(normalize_markdown(raw)))
    cover_md, body_md = split_cover_body(text)
    headings = collect_headings(body_md) if not args.no_toc else []
    title = args.title or (re.match(r"^# (.+)$", raw.split("\n")[0]) or [None, "深度研究"])[1]

    today = datetime.date.today()
    date_cn = args.date or f"{today.year}年{today.month}月{today.day}日"
    c_title, c_sub, c_disc, c_basis = parse_cover(cover_md)
    if c_title and not c_sub:
        c_sub = derive_subtitle(body_md)
    cover_html = "" if args.no_cover else build_cover(c_title, c_sub, c_disc, c_basis,
                                                      date_cn)

    workdir = Path(tempfile.mkdtemp(prefix="md2pdf-"))
    html_path = (Path(args.keep_html) if args.keep_html else workdir / "report.html")

    # 目录页码与正文页序互相牵制：目录多占一页，正文页码就整体挪一位。
    # 因此迭代排版，直到「印上去的页码」与「实际所在页」一致为止；通常两轮收敛。
    page_map = None       # PDF 物理页序（0 基），用于判断是否收敛
    display_map = None    # 正文页码（从 1 起），这才是印在目录上的数字
    texts, toc_start, body_start = [], 0, 0
    probe = first_body_probe(body_md)
    converged = not headings
    for attempt in range(4):
        toc_html = build_toc_html(headings, display_map) if headings else ""
        html_path.write_text(
            build_html(cover_html, toc_html, body_md, title, base_dir=src.parent),
            encoding="utf-8")
        render_pdf(chrome, html_path, out)

        doc = pymupdf.open(out)
        texts = page_texts(doc)
        doc.close()

        toc_start = locate_first(texts, "目录", limit=12) if headings else 0
        toc_start = toc_start if toc_start is not None else 0
        body_start = locate_first(texts, probe.replace(" ", ""), start=toc_start)
        if body_start is None:
            body_start = toc_start + (1 if headings else 0)
            print("  ! 正文起始页没定位到，按目录后一页估算，请目视复核首节位置", file=sys.stderr)

        new_map = locate_headings(texts, headings, body_start) if headings else {}
        new_display = {i: p - body_start + 1 for i, p in new_map.items()}
        # 收敛判据直接比「这一版印上去的页码」与「这一版实测的页码」——
        # 只要两者相等，交付的这份 PDF 上，目录数字就与页脚数字一致。
        if display_map is not None and new_display == display_map:
            page_map, display_map, converged = new_map, new_display, True
            break
        page_map, display_map = new_map, new_display
    if not converged:
        print("  ! 目录页码迭代 4 轮仍未收敛，已按最后一版输出，请目视复核目录页码",
              file=sys.stderr)

    if headings and page_map:
        missing = [headings[i][1] for i in range(len(headings)) if i not in page_map]
        if missing:
            print("  ! 以下标题没能定位到页码（目录里会留空）：" + "、".join(missing), file=sys.stderr)

    has_cover = bool(cover_html)
    if has_cover or not args.no_page_numbers:
        stamp_and_bookmark(out, texts, headings, page_map, toc_start, body_start,
                           report_name=title, date_cn=date_cn, brand=COVER_BRAND,
                           has_cover=has_cover, header_footer=not args.no_page_numbers)

    doc = pymupdf.open(out)
    total = doc.page_count
    doc.close()
    if not args.keep_html and workdir.exists():
        for f in workdir.iterdir():
            f.unlink()
        workdir.rmdir()

    print(f"已生成 {out}")
    seg = []
    if has_cover:
        seg.append("封面 第 1 页")
    if headings and toc_start < body_start:
        seg.append(f"目录 {toc_start + 1}–{body_start} 页（罗马）")
    seg.append(f"正文 {body_start + 1}–{total} 页（阿拉伯，从头数）")
    print(f"  总页数 {total}｜" + "｜".join(seg))
    if args.keep_html:
        print(f"  中间 HTML：{html_path}")


if __name__ == "__main__":
    main()
