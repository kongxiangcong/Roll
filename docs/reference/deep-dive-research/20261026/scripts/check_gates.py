#!/usr/bin/env python3
"""深度研究项目的机械闸门校验（Gate 1 / Gate 2 / Gate 3 / Gate 3.5）。

为什么有这个脚本：这份 skill 最容易的失败方式是「少做」——少取一类数据、少跑一项排雷、
少写一行溯源，成稿照样能渲染成 PDF，从外面看不出来。文字纪律靠自觉，脚本靠退出码。
任何一个 agent 跑同一条命令得到同一套判断，不受模型强弱与上下文压缩影响。

只用标准库，任何 Python 3 都能跑。

用法：
    python3 scripts/check_gates.py --project outputs/2026-10-13-齐翔腾达002408
    python3 scripts/check_gates.py --project <目录> --stage 2      # 只查 Gate 2
    python3 scripts/check_gates.py --portable                      # 查 skill 包本身的可移植性

退出码：0 全部通过；1 有未通过项；2 用法错误。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 复核触发线：成稿中文字数低于此值时必须回答「内容本来就少还是取数没做完」。
DRAFT_MIN_CJK = 15000
# 排雷表项数：A 股 28 项；港股在三层之上加第四层 10 项，合计 38 项。
LANDMINE_ROWS = {"A": 28, "HK": 38}
# 附录 E 可比公司下限：总数 ≥ 5 家，其中上市的国际同业 ≥ 2 家。
PEER_MIN, PEER_INTL_MIN = 5, 2
# 重点标注上限与速览页区间（见 references/06 第四节）。
EMPHASIS_CAP = 30
OVERVIEW_RANGE = (4, 7)
# 正文图数下限与必画节次（见 references/06 第五节）。只卡总数与四张必画——
# 四张正好落在四个部分各一节，数量与分布一起解决，不给"为了凑数画图"留口子。
FIG_MIN = 8
FIG_REQUIRED_SECTIONS = (3, 4, 6, 8)

# 文体可数阈值（见 references/00 第六节）：超线只提示（warn），不阻断交付。
DASH_CAP = 9                       # 破折号「——」插入语个数
TRANSITION_WORDS = ["值得注意的是", "综上所述", "换言之", "需要指出的是"]
SELFREF = re.compile(r"本报告|本节|笔者")
EXPLAIN_MARK = re.compile(r"这一节回答一个问题|本节回答的是|\*\*读法\*\*|读法[:：]|必须说清楚|必须点出")

# AI 腔体检（见 references/00 第六节《去 AI 味》）：超线只提示（warn），不阻断交付。
# 甲、零容忍：在对读研报的人眼里，这些词等于零信息量。
AI_CLICHE_ZERO = ["闭环", "赋能", "抓手", "反哺", "破局", "心智", "协同增效", "颗粒度"]
# 乙、限频：词本身合法，出问题的是密度。元组为（显示名, 正则, 每万字上限）。
AI_CLICHE_DENSITY = [
    ("意味着", r"意味着", 2.0),
    ("这一", r"这一", 4.5),
    ("中枢", r"中枢", 1.2),
    ("兑现", r"(?<!出清)兑现", 1.2),
    ("护城河", r"护城河", 1.0),
    ("结构性", r"结构性", 1.2),
    ("自洽", r"自洽", 0.6),
    ("边际", r"边际", 1.5),
    ("锚（名词化，不含“锚定”）", r"锚(?!定)", 3.0),
    ("本质上／归根结底", r"本质上|归根结底", 1.0),
    ("不是……而是", r"不是[^。！？\n]{1,30}?而是", 0.6),
]
# 结构类：表格后复述表内容（“上表显示”类）。隐喻词与“标签：”式小标题不做机械判定——
# 二者要结合行业上下文判断（术语表、机械行业实指都会误报），改用第六节的成稿前搜索命令。
TABLE_ECHO = re.compile(r"上表显示|上表列出|由表可见|如上表|下表显示|下表列出|下表汇总")

# 周期路径与见顶对撞（见 references/08 第一、四节，2026-10-15 新增）。
# 东方钽业成稿的机械特征：用 A 类（过剩出清型）的措辞描述 B 类（需求拉动／资源约束型）行业；
# 或者区间涨幅已达数倍、股价先行见顶之后，成稿仍写"尚未出清、第一波上涨的触发条件尚未凑齐"。
CYCLE_A_WORDING = re.compile(r"尚未出清|第一波上涨|出清前夜")
# 编号式波次：读者不知道从哪儿数起（见 references/08 第二节末）。只提示，不阻断。
WAVE_NUMBER = re.compile(r"第\s*[一二三四五六七八九十]\s*波\s*(?:上涨|行情|反弹|下跌)")
# 把方向说反的进度式说法：判据还没转好，句子却读成"只差临门一脚"
# （见 references/08 第二节末、references/00 第六节·行业状态写方向）。只提示，不阻断。
# 只抓"没到"这一侧——判据真的齐了、写"已经凑齐"是正当用法，不抓。
PROGRESS_PHRASING = re.compile(r"尚未凑齐|未凑齐|未经凑齐|凑齐了没有|是否凑齐|是否已凑齐")
CYCLE_A_LABEL = re.compile(r"(?<!非)(?<!属于)过剩出清型|A 类")
CYCLE_A_NEGATED = re.compile(r"(?:非|不是|不属于|并非|不算|亦非)\s*过剩出清型")
CYCLE_B_LABEL = re.compile(r"需求拉动|资源约束型|资源品型|B 类")
CYCLE_TOPPING = re.compile(r"见顶")
# 上升中继一侧的说法："行情还没走完"（references/08 第四节）。
CYCLE_MIDWAY = re.compile(r"中继|尚未走完|未走完|没有走完|仍在进行|趋势未改")
# 段表里的涨跌幅：前后带全角或半角正负号的百分数（＋170.0% / -51.0%）。
CYCLE_GAIN_PCT = re.compile(r"[+＋](\d{1,4}(?:\.\d+)?)\s*%")
CYCLE_DROP_PCT = re.compile(r"[-−](\d{1,3}(?:\.\d+)?)\s*%")

# 行话与术语（见 references/00 第六节·行话与术语，2026-10-15 新增）：圈内简称读者看不懂，
# 正文一律换成通用说法。超线只提示（warn），与本节其余文体阈值同一档。
JARGON_BANNED = ["主导侧", "共振", "双杀", "双击"]
# 「倍数」只在跟了指标名时才合法（市盈率 15 倍 / PB 1.8 倍）；单用不行。
# 判法：往前 14 个字里找不到指标名或「覆盖」这类有明确分母的说法，即算裸用。
MULTIPLE_OK = re.compile(
    r"市盈率|市净率|市销率|市现率|股息率|PE|PB|PS|EV|EBITDA|分红|覆盖|放大|翻")
# 字母缩写：全文找不到对应的中文名，即视为首次出现没有展开。
ABBR_NAMES = {
    "PEG": "市盈率相对盈利增长比率",
    "EBITDA": "息税折旧摊销前利润",
    "ROE": "净资产收益率",
    "ROA": "总资产收益率",
    "TTM": "滚动十二个月",
    "FCF": "自由现金流",
    "CAGR": "复合年均增长率",
    "NPS": "净推荐值",
    "PS": "市销率",
    "PE": "市盈率",
    "PB": "市净率",
    "EV": "企业价值",
}
# 机器腔（见 references/00 第六节·机器腔，2026-10-15 新增）：表格与底稿的记法漏进正文。
# 只扫正文行（表格行、标题行、代码块不扫）；命中只提示（warn），不阻断交付。
MACHINE_FORMS = [
    r"[ABCD]\s*[·・]\s*(?:底部反转|上升中继|顶部结束|下跌中继)",
    r"(?:读数|证据|信号|理由)\s*\d+\s*条",
    r"\d+\s*条\s*对",
    r"(?:理由|依据)即",
    r"(?<![A-Za-z])n\s*=\s*\d+",
    r"四态\s*[ABCD](?![A-Za-z])",
]
# 规则文档指针：正文里指本 skill 的文件编号（见 references/00 第六节·报告要自足）。
POINTER_FORMS = [
    r"(?<![\d,.])`?0[0-9]`?(?![\d])\s*(?:\d+\.\d|判读规则|第\s*[一二三四五六七八九十\d]+\s*节)",
    r"`?references/\d",
    r"`0[0-9]-[^`\s]*\.md",
]
# 过程自述：作者的作业流程搬进了正文（见 references/00 第六节·过程自述）。只提示，不阻断。
PROCESS_FORMS = [
    r"(?:四层判定表|取数台账|单位数核查|模型自检|指标核查|反向质疑|成稿自检记录)[^）\n]{0,16}栏",
    r"(?:行业)?专家角色(?:取|选|定为|是|为)",
    r"按[^。，；：\n]{0,8}(?:这一问|该问)(?:排列|排序|展开|组织)",
    r"各节权重|本报告按[^。\n]{0,12}(?:顺序|结构)展开",
    r"分流三问|分流判定",
]
# 附录 H 术语表：行数与列名下限（见 references/02 第四节与 references/00 第六节）。
APX_H_MIN_ROWS = 15

# 榜单、评分与名次类信息（见 references/11 第九节）：公式照抄年报没有用，必须核口径、比基准、查背离、定档。
# 命中即要求独立的指标核查底稿；只提示不阻断的是 Gate 2 那一处计数。
HONOR_PAT = re.compile(
    r"NPS|净推荐|满意度|品牌力|忠诚度|推荐度|美誉度|口碑榜|口碑第一"
    r"|行业第一|全国第一|全球第一|世界第一|排名第一|位列第一|销量第一|市占率第一|份额第一"
    r"|第一名|第\s*1\s*名|冠军|销冠|夺冠|榜首|居首|蝉联|行业领先|市场领先"
)
# 年报里的标准标签（第一大客户／第一大股东／排名第一的供应商）是列示口径，不是荣誉，
# 先把它们剔掉再计数，免得闸门被这类词反复触发。
HONOR_SKIP = re.compile(r"(排名第[一1]的?|第[一1]大)\s*(客户|股东|供应商|经销商)")

# 自算的派生数字（吨成本、吨毛利、单店收入、单客价值这一类）：见 references/12。
# 它们看起来像实测值，实际是拿几个大数除出来的，必须过口径与独立源对照。
UNIT_PRICE_PAT = re.compile(
    r"元\s*/\s*(吨|公斤|千克|升|立方米|平方米|平米|亩|台|头|只|辆|人|度|千瓦|件|店|卡|人次)")
UNIT_DERIVED_PAT = re.compile(r"吨成本|吨毛利|单吨|单店|单客|单车|单瓦|个险|人均月薪")
# 由反推得到的临界值，不得写进速览页的"必记数字"。
BACKSOLVED_PAT = re.compile(r"盈亏平衡|平衡价|打平|临界价|临界成本|隐含价格")


def honor_hits(text: str):
    return HONOR_PAT.findall(HONOR_SKIP.sub("", text or ""))

# 投资建议禁则：高置信词组直接判不通过。
BANNED_HARD = [
    "目标价", "合理价位", "目标市值", "上涨空间", "买入评级", "卖出评级", "增持评级",
    "减持评级", "投资评级", "建议买入", "建议卖出", "建议增持", "建议减持", "建议关注",
    "值得买入", "逢低", "建仓", "满仓", "抄底", "加仓", "减仓", "仓位建议", "建议仓位",
]
# 出现即提示，可能是股东行为的事实陈述（如“大股东减持”），也可能是越界。
BANNED_SOFT = ["评级", "仓位", "止损", "估值修复空间"]
# 这些上下文里出现禁词是合法的（免责声明、边界声明）。
BANNED_ALLOW = re.compile(
    r"不构成|禁止|不得|不提供|不给出|不出现|不涉及|不含|非投资建议|风险自担|免责|边界|不写|不许"
    # 澄清句与信用评级语境里出现禁词是合法的，避免误报。
    r"|不是目标价|并非|不算|信用评级|资信|主体及债项|评级机构|评级下调|评级上调|跟踪评级|评级报告"
)
# 方法论底本不得进入交付物。
SOURCEBOOK = ["本书", "该书", "如何快速了解一个行业", "按书中", "与书中", "书中方法", "书中口径"]

# 台账七类：每一类都必须填。
LEDGER_SECTIONS = ["本体披露", "行业时序", "产业链", "同业对照", "估值序列", "研报", "官方监管"]
PLACEHOLDER = re.compile(r"^\s*(待填|待补|待定|未知|TODO|TBD|\?|？|-|—|/|无)\s*$", re.I)
# 国际同业的识别标记（代码列或市场列命中其一即可）。
INTL_MARK = re.compile(
    r"纽交所|纳斯达克|NYSE|NASDAQ|伦敦|伦交所|东京|东证|港交所|韩交所|新交所|台湾|"
    r"国际|海外|境外|美国|日本|德国|法国|韩国|英国|\bLSE\b|\bHK\b|\.HK\b"
)


class Runner:
    """收集检查结果，最后统一出报告。错误分级：fail 影响退出码，warn 只提示。"""

    def __init__(self):
        self.items = []

    def add(self, gate, name, ok, detail="", level="fail"):
        self.items.append({"gate": gate, "name": name, "ok": bool(ok),
                           "detail": detail, "level": level})

    def gate(self, gate):
        return [x for x in self.items if x["gate"] == gate]

    def failed(self, gate=None):
        return [x for x in self.items if not x["ok"] and x["level"] == "fail"
                and (gate is None or x["gate"] == gate)]

    def render(self):
        out = []
        for gate in ("Gate 1", "Gate 2", "Gate 3", "Gate 3.5", "可移植性"):
            items = self.gate(gate)
            if not items:
                continue
            bad = len(self.failed(gate))
            warns = sum(1 for it in items if not it["ok"] and it["level"] == "warn")
            tail = f"，另有 {warns} 项提示" if warns else ""
            head = f"{gate}：{'通过' if bad == 0 else f'未通过（{bad} 项）'}{tail}"
            out.append(f"\n{head}")
            for it in items:
                mark = "✅" if it["ok"] else ("⚠️ " if it["level"] == "warn" else "❌")
                line = f"  {mark} {it['name']}"
                if it["detail"]:
                    line += f" — {it['detail']}"
                out.append(line)
        return "\n".join(out)


def read(path: Path):
    """读文件；不存在返回 None，避免到处写 try。"""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def table_rows(text):
    """解析 Markdown 表格的数据行，返回 [[单元格, ...]]（跳过表头与 |---| 分隔行）。"""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:\-|]+\|", line):
            continue
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def section(text, keyword, level=2):
    """取标题里含 keyword 的那一节正文；找不到返回 None。"""
    m = re.search(rf"^#{{1,{level}}}\s*(?!#).*{re.escape(keyword)}.*$", text, re.M)
    if not m:
        return None
    start = m.end()
    nxt = re.search(rf"^#{{1,{level}}}\s", text[start:], re.M)
    return text[start:start + nxt.start()] if nxt else text[start:]


def appendix_i(draft: str):
    """取「附录 I」那一节的正文；找不到返回 None。

    用途：核「附录 I 是免责声明」这一条（2026-10-15 统一：待核实清单不是附录，
    数据缺口与未答问题落在正文第 10 节，见 references/02 第四节）。
    """
    m = re.search(r"^#{1,3}\s*附录\s*[IＩ](?![\w\u4e00-\u9fff])[^\n]*$", draft, re.M)
    if not m:
        return None
    nxt = re.search(r"^#{1,3}\s", draft[m.end():], re.M)
    return draft[m.end():m.end() + nxt.start()] if nxt else draft[m.end():]


def cjk_count(text):
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def appendix_h(draft: str):
    """取「附录 H」那一节的正文；找不到返回 None。

    用途：核术语表行数（见 references/02 第四节、references/00 第六节·行话与术语）。
    """
    m = re.search(r"^#{1,3}\s*附录\s*[HＨ](?![\w\u4e00-\u9fff])[^\n]*$", draft, re.M)
    if not m:
        return None
    nxt = re.search(r"^#{1,3}\s", draft[m.end():], re.M)
    return draft[m.end():m.end() + nxt.start()] if nxt else draft[m.end():]


def body_only(draft: str):
    """取正文（附录之前的部分）。

    用途：术语扫描只扫正文。附录 H 的术语表里本来就会出现"戴维斯双击"这类对照写法，
    附录 D 排雷表里也会出现"覆盖倍数"，扫全篇会一路误报。
    """
    m = re.search(r"^#{1,3}\s*附录\s*[A-ZＡ-Ｚ]", draft, re.M)
    return draft[:m.start()] if m else draft


def jargon_hits(text: str):
    """圈内简称：出现即提示，逐条列出（见 references/00 第六节·行话与术语）。"""
    return [f"{w}×{text.count(w)}" for w in JARGON_BANNED if w in text]


def bare_multiple(text: str):
    """找单用的「倍数」：前文没有指标名（市盈率 / 市净率 / PB 等）的，算裸用。"""
    out = []
    for m in re.finditer(r"倍数", text):
        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 14):m.start()])
        if not MULTIPLE_OK.search(ctx):
            out.append(ctx.strip()[-10:] + "倍数")
    return out


def abbr_not_expanded(text: str):
    """字母缩写出现了，但全文找不到对应中文名 —— 首次出现没展开。"""
    miss = []
    for ab, cn in ABBR_NAMES.items():
        if re.search(rf"(?<![A-Za-z]){ab}(?![A-Za-z])", text) and cn not in text:
            miss.append(f"{ab}（应展开为「{cn}」）")
    return miss


def count_numbered_rows(text):
    """数「一行一项」的行数：首列是序号。用于排雷表与附录 D。"""
    return sum(1 for r in table_rows(text) if r and re.fullmatch(r"\d+", r[0]))


def find_draft(proj: Path):
    d = proj / "03-交付物"
    if not d.is_dir():
        return None
    mds = sorted(d.glob("*.md"))
    for p in mds:
        if "深度研究" in p.name:
            return p
    return mds[0] if mds else None


def detect_market(*texts):
    """A 股还是港股：台账／判定表里明确提到港股且不是「非 A+H」的 A 股标的，才算港股。"""
    blob = "\n".join(t for t in texts if t)
    if re.search(r"港股|\.HK\b|HKEX|港交所", blob) and not re.search(r"非\s*A\s*\+?\s*H|非港股|不适用港股", blob):
        return "HK"
    return "A"


def check_gate1(r: Runner, proj: Path, ledger: str | None):
    wd = proj / "02-工作底稿"
    if ledger is None:
        r.add("Gate 1", "取数台账存在", False, f"缺 {wd}/取数台账.md")
        return
    r.add("Gate 1", "取数台账存在", True, "02-工作底稿/取数台账.md")

    empty_sections = []
    blank_cells = 0
    short_gaps = []
    for name in LEDGER_SECTIONS:
        body = section(ledger, name)
        rows = table_rows(body) if body else []
        # 去掉表头行：表头行的状态列不会出现「已取／缺口／引用」
        rows = [x for x in rows if len(x) >= 2 and not x[1].startswith("状态")]
        if not rows:
            empty_sections.append(name)
            continue
        for cells in rows:
            status = cells[1] if len(cells) > 1 else ""
            if PLACEHOLDER.match(status) or not status:
                blank_cells += 1
            if status.startswith("缺口"):
                row = " ".join(cells)
                # 「已试路径」的同义写法都算数；引用另一条缺口行的，不重复记三行。
                tried = re.search(r"已试|已查|已核|已检索|已确认|已取|已下|已测|已调|已看过|已比对", row)
                nxt = re.search(r"可继续查|还能去|下一步|可补|渠道|路径", row)
                cond = "条件" in row
                xref = re.search(r"见.{0,10}缺口", row)
                if not ((tried and nxt and cond) or xref):
                    short_gaps.append(cells[0][:24])
    r.add("Gate 1", "台账七类齐全", not empty_sections,
          "缺：" + "、".join(empty_sections) if empty_sections else "本体披露／行业时序／产业链／同业对照／估值序列／研报／官方监管")
    r.add("Gate 1", "状态列无空位", blank_cells == 0, f"{blank_cells} 行未填状态" if blank_cells else "各行状态已标")
    r.add("Gate 1", "缺口三行齐全", not short_gaps,
          "缺「已试路径／可继续查渠道／需要条件」中至少一行：" + "、".join(short_gaps) if short_gaps else "缺口项均按三行写明")

    src = proj / "01-原始资料"
    n = len([p for p in src.rglob("*") if p.is_file()]) if src.is_dir() else 0
    r.add("Gate 1", "原始资料已落盘", n >= 5, f"{n} 个文件" + ("" if n >= 5 else "（少于 5，疑似只做了 lean read）"))

    # 派生文件落 02-工作底稿/，不混进原件目录（见 references/00 第七节第 5 条）。只提示，不阻断。
    derived = ([x for x in src.rglob("*") if x.suffix.lower() in (".txt", ".md", ".html")]
               if src.is_dir() else [])
    r.add("Gate 1", "原始资料只有原件", not derived,
          ("抽取副本这类派生物应落 02-工作底稿/文本/，项目结束列清单清掉："
           + "、".join(str(x.relative_to(proj)) for x in derived[:6]))
          if derived else "未见抽取副本混进 01-原始资料/", level="warn")


def cycle_topped(hpr_text: str):
    """段表里"涨完一轮又回撤、其间没有重新走强"的形态。

    判的是"最后一次大涨之后一路回撤、期间没有像样的反弹"，命中返回 (True, 说明)；
    取不到数据返回 (False, "")——**取不到就不下判断**。
    这是**提示性**判据：命中只要求成稿把中继与见顶两侧都写到，不代表已经见顶。
    """
    rows = [x for x in hpr_text.splitlines() if x.startswith("|")]
    # 只看带价格走向的行（含"→"，如"14.20→90.60"），避免把净利润同比、EPS 变动当成股价涨幅。
    price_rows = [x for x in rows if "→" in x] or rows

    peak_i, peak_gain = None, None
    for i, ln in enumerate(price_rows):
        for m in CYCLE_GAIN_PCT.finditer(ln):
            v = float(m.group(1))
            if 100 <= v <= 3000:
                peak_i, peak_gain = i, v   # 行序 + 行内取第一个 ≥100% 的涨幅
                break
    if peak_i is None:
        return False, ""

    drops = []
    for ln in price_rows[peak_i + 1:]:
        for m in CYCLE_DROP_PCT.finditer(ln):
            v = float(m.group(1))
            if 30 <= v <= 100:
                drops.append(v)
        for m in CYCLE_GAIN_PCT.finditer(ln):
            if float(m.group(1)) >= 30:
                return False, ""            # 其后有过像样的反弹，不算"涨完一轮"
    if drops:
        return True, (f"底稿段表里最后一次大涨 {peak_gain:.0f}%，其后回撤 {drops[0]:.0f}%，"
                      "其间没有重新走强")
    return False, ""


def check_gate2(r: Runner, proj: Path, market: str, draft_path, draft: str | None):
    wd = proj / "02-工作底稿"
    need = LANDMINE_ROWS[market]
    tag = "A 股" if market == "A" else "港股"

    if draft is None:
        r.add("Gate 2", "成稿存在", False, "03-交付物/ 下没有 Markdown 成稿")
        return
    n_cjk = cjk_count(draft)
    r.add("Gate 2", "篇幅触发线", n_cjk >= DRAFT_MIN_CJK,
          f"中文字 {n_cjk:,}（触发线 {DRAFT_MIN_CJK:,}）"
          + ("" if n_cjk >= DRAFT_MIN_CJK else "；低于触发线，必须先回答「内容本来就少，还是取数没做完」并写进自检记录"))

    land = read(wd / "排雷表.md")
    if land is None:
        r.add("Gate 2", f"排雷表 {tag} {need} 项", False, "缺 02-工作底稿/排雷表.md")
    else:
        k = count_numbered_rows(land)
        r.add("Gate 2", f"排雷表 {tag} {need} 项", k >= need, f"{k} 项")

    apx_d = section(draft, "附录 D", level=1) or ""
    k = count_numbered_rows(apx_d)
    r.add("Gate 2", f"成稿附录 D 逐项成行", k >= need,
          f"{k} 行" if k >= need else f"{k} 行，少于 {need}；「全部未命中」式合并写法不算逐项")

    apx_e = section(draft, "附录 E", level=1) or ""
    rows = [x for x in table_rows(apx_e) if len(x) >= 3]
    intl = sum(1 for x in rows if INTL_MARK.search(" ".join(x)))
    ok_e = len(rows) >= PEER_MIN and intl >= PEER_INTL_MIN
    r.add("Gate 2", "附录 E 可比公司", ok_e,
          f"{len(rows)} 家，其中国际同业 {intl} 家（下限 {PEER_MIN} 家含国际 {PEER_INTL_MIN} 家）")

    apx_g = section(draft, "附录 G", level=1) or ""
    k = len([x for x in table_rows(apx_g) if x and x[0] and not x[0].startswith("关键数字")])
    r.add("Gate 2", "附录 G 溯源逐数字成行", k >= 20, f"{k} 行" + ("" if k >= 20 else "（偏少，正文关键数字应逐行）"))

    # 图的数量与分布（见 references/06 第五节）。图不够，报告读着像一份数据汇编。
    fig_secs = [int(x) for x in re.findall(r"!\[图\s*(\d+)\s*[-–]", draft)]
    n_fig = len(fig_secs)
    r.add("Gate 2", "正文图数", n_fig >= FIG_MIN,
          f"{n_fig} 张（下限 {FIG_MIN}）"
          + ("" if n_fig >= FIG_MIN else "；图太少，见 references/06 第五节"))
    missing_fig = [n for n in FIG_REQUIRED_SECTIONS if n not in fig_secs]
    r.add("Gate 2", "必画图在位", not missing_fig,
          ("缺第 " + "、".join(str(n) for n in missing_fig) + " 节的图（变量／周期位置／财务／股价复盘）"
           if missing_fig else
           "第 " + "、".join(str(n) for n in FIG_REQUIRED_SECTIONS) + " 节各 ≥ 1 张"))

    apx_f = section(draft, "附录 F", level=1) or ""
    kf = len([x for x in table_rows(apx_f) if x and x[0] and not x[0].startswith("编号")])
    r.add("Gate 2", "附录 F 图表索引逐张成行", kf >= n_fig and kf > 0,
          f"{kf} 行（正文图 {n_fig} 张）", level="warn")

    # 重点标注：成对、不超上限、速览页密度。
    key, risk = draft.count("==") // 2, draft.count("@@") // 2
    odd = [m for m, c in (("==", draft.count("==")), ("@@", draft.count("@@"))) if c % 2]
    r.add("Gate 2", "重点标成对", not odd, "落单：" + "、".join(odd) if odd else f"关键结论 {key} 处｜风险 {risk} 处")
    r.add("Gate 2", "标注不超上限", key + risk <= EMPHASIS_CAP,
          f"共 {key + risk} 处（上限 {EMPHASIS_CAP}）")
    ov = section(draft, "速览", level=1) or ""
    ov_n = ov.count("==") // 2 + ov.count("@@") // 2
    lo, hi = OVERVIEW_RANGE
    r.add("Gate 2", "速览页标注密度", lo <= ov_n <= hi,
          f"{ov_n} 处（{lo}~{hi}）", level="warn")

    # 速览页的"股价节奏坐标"（上一轮高点、已调整多久、这类调整通常多久）：见 references/13 第十节。
    r.add("Gate 2", "速览页股价节奏坐标", ("股价节奏坐标" in draft) or ("调整已持续" in ov),
          "见 references/13 第十节", level="warn")

    # 反推得来的临界值不进速览必记数字：速览页的数字会被当成公司的属性记住，见 references/12 第五节。
    bk = re.search(r"必记[^\n]{0,12}数字(.{0,4000}?)(?=\n##|\Z)", ov, re.S)
    if bk and BACKSOLVED_PAT.search(bk.group(1)):
        r.add("Gate 2", "必记数字不含反推值", False,
              f"速览「必记的数字」里出现「{BACKSOLVED_PAT.search(bk.group(1)).group(0)}」；"
              "反推值（盈亏平衡价、隐含价格）只在第 9 节出现，并写明假设与移动幅度")
    else:
        r.add("Gate 2", "必记数字不含反推值", True,
              "速览必记数字未混入反推得来的临界值")

    # 两侧标注相当（优势与风险同权，见 references/06 第四节）。
    if min(key, risk) == 0 or max(key, risk) / max(min(key, risk), 1) > 3:
        r.add("Gate 2", "两侧标注相当", False,
              f"关键结论 {key} 处｜风险 {risk} 处（一侧过重）", level="warn")
    else:
        r.add("Gate 2", "两侧标注相当", True, f"关键结论 {key} 处｜风险 {risk} 处")

    # Gate 3.5 的正文落点（工作底稿本身在 Gate 3.5 里查）。
    r.add("Gate 2", "多空对垒表", bool(re.search(r"多空对垒|多方论据|多方观点|多方逻辑", draft)) and "空方" in draft,
          "见 references/11 第二节", level="warn")
    r.add("Gate 2", "未能回答的关键问题", bool(re.search(r"本报告未能回答|未能回答的关键问题|回答不了的关键问题", draft)),
          "见 references/11 第六节", level="warn")
    r.add("Gate 2", "速览页最大证伪点", ("证伪点" in ov) or ("最大证伪" in draft),
          "见 references/11 第一节", level="warn")

    judge = read(wd / "四层判定表.md") or ""
    r.add("Gate 2", "四层判定表含专家角色", bool(judge) and ("角色" in judge), "见 references/09",
          level="fail")
    ref_band = read(wd / "估值参照带.md")
    r.add("Gate 2", "估值参照带落盘", ref_band is not None, "02-工作底稿/估值参照带.md")
    if ref_band is not None:
        # 参照带里的每个数字都要过口径、对照与外推检查：见 references/12。
        ms = read(wd / "模型自检.md")
        if ms is None:
            r.add("Gate 2", "模型自检落盘", False,
                  "有估值参照带却没有 02-工作底稿/模型自检.md（见 references/12 第六节）")
        else:
            keys = [k for k in ("口径", "对照", "外推", "极值", "降级", "翻转") if k in ms]
            n = cjk_count(ms)
            r.add("Gate 2", "模型自检落盘", n >= 400 and len(keys) >= 2,
                  f"中文字 {n}，写到「{'／'.join(keys)}」"
                  + ("" if n >= 400 and len(keys) >= 2
                     else "（少于 400 字或未写到口径／对照／外推中任何两项，疑似走过场）"))
    if market == "A" or market == "HK":
        cycle_hit = re.search(r"周期型|周期股", judge + (ref_band or ""))
        if cycle_hit:
            outs = list(wd.glob("*cycle_valuation*")) + list(wd.glob("*参照带*输出*"))
            r.add("Gate 2", "参照带脚本复算留档", bool(outs),
                  f"{outs[0].name}" if outs else "周期型标的须用 scripts/cycle_valuation.py 复算并把输出留在 02-工作底稿/")

    # 历史股价复盘（references/13，2026-10-15 新增铁律 21）：不做日线归因，但必须有中长线段、
    # EPS／PE 拆解、调整段的结束标志，以及"本公司历史 / 行业经验"的时长对照。
    hpr = read(wd / "历史股价复盘.md")
    if hpr is None:
        r.add("Gate 2", "历史股价复盘落盘", False,
              "缺 02-工作底稿/历史股价复盘.md（见 references/13 与铁律 21）。"
              "上市不足 3 年的按 references/13 第一节的例外写法写明，不许直接跳过")
    else:
        wide = sum(1 for x in table_rows(hpr) if len(x) >= 6)
        segs = max(count_numbered_rows(hpr), wide)
        n_hp = cjk_count(hpr)
        has_split = bool(re.search(r"EPS|每股收益", hpr)) and bool(re.search(r"PE|市盈率|倍数", hpr))
        has_adj = ("调整" in hpr) and ("结束" in hpr)
        has_bench = ("行业" in hpr) and bool(re.search(r"经验|对照", hpr))
        miss = []
        if n_hp < 300:
            miss.append(f"中文字 {n_hp}（少于 300，疑似走过场）")
        if segs < 3:
            miss.append(f"宽表仅 {segs} 行（下限 3）")
        if not has_split:
            miss.append("未见利润侧与估值侧两列（每股收益变动 / 市盈率变动）")
        if not has_adj:
            miss.append("调整段没写结束标志")
        if not has_bench:
            miss.append("缺行业调整期对照")
        r.add("Gate 2", "历史股价复盘落盘", not miss,
              f"宽表合计 {segs} 行，中文字 {n_hp}" + ("；" + "、".join(miss) if miss else ""))

    # 周期路径与见顶对撞（references/08 第一、四节，2026-10-15 新增）。
    hit = CYCLE_A_WORDING.search(draft)
    if hit:
        # （1）用了 A 类措辞，成稿里必须写明这条路是 A 类还是 B 类。
        labeled = bool(CYCLE_A_LABEL.search(draft) or CYCLE_B_LABEL.search(draft))
        r.add("Gate 2", "周期路径已标明", labeled,
              "成稿用了「" + hit.group(0) + "」，但没写明这条周期走的是 A 类（过剩出清型）"
              "还是 B 类（需求拉动／资源约束型）——见 references/08 第一节" if not labeled
              else "周期路径已写明（A 类／B 类）",
              level="warn")
        # （2）路径冲突：底稿判成 B 类却在用 A 类措辞；或成稿自述"非过剩出清型"却用 A 类措辞。
        base = (hpr or "") + judge
        conflict = []
        if CYCLE_B_LABEL.search(base) and not CYCLE_A_LABEL.search(base):
            conflict.append("底稿把这条路判成需求拉动／资源约束型（B 类）")
        if CYCLE_A_NEGATED.search(draft):
            conflict.append("成稿自己写明不属于过剩出清型")
        r.add("Gate 2", "周期路径与措辞一致", not conflict,
              ("；".join(conflict) + "，成稿却在用「" + hit.group(0) + "」这套 A 类措辞："
               "这条路没有全行业亏损到产能退出的那一段，套用出清措辞会把位置判反"
               "（references/08 第三节末，东方钽业实盘）") if conflict
              else "措辞与底稿的路径判定一致")
        # （3）股价已经涨完一轮又回撤、成稿却仍答"尚未出清"时，必须补见顶判定。
        topped, why = cycle_topped(hpr or "")
        if topped:
            miss_topping = []
            if not CYCLE_TOPPING.search(draft):
                miss_topping.append("全文未见「见顶」二字")
            r.add("Gate 2", "已涨完一轮须答见顶", not miss_topping,
                  (why + "，成稿却仍在写「" + hit.group(0) + "」；" + "、".join(miss_topping)
                   + "。行业见顶信号与股价见顶信号要逐条写「已出现／未出现」（references/08 第四节）")
                  if miss_topping else why + "；成稿已给见顶判断")

    # 中继与见顶两侧对照（references/08 第四节，2026-10-15 补）：
    # 段表里"涨完一轮又回撤"时，成稿必须两侧都写——判成顶部要写明为什么排除中继，反之亦然。
    topped2, why2 = cycle_topped(hpr or "")
    if topped2:
        has_top = bool(CYCLE_TOPPING.search(draft))
        has_mid = bool(CYCLE_MIDWAY.search(draft))
        if has_top and has_mid:
            detail = why2 + "；成稿已给中继与见顶两侧的对照"
        else:
            detail = (why2 + "。" + ("成稿只写了见顶，没有写明为什么排除上升中继" if has_top
                                     else "成稿只写了行情未走完，没有写明为什么排除见顶" if has_mid
                                     else "成稿既没有见顶判断，也没有中继判断")
                      + "：判成顶部要写明为什么排除中继，判成中继要写明为什么排除见顶"
                      "（references/08 第四节）")
        r.add("Gate 2", "中继与见顶两侧对照", has_top and has_mid, detail)

    # 见顶结论的判据（references/08 第四节 4.8／4.9，2026-10-15 补）：判顶部看的是利润增速是否
    # 放缓、供给投放进度是否明确，不是利润水平。写了"见顶"却通篇没有这两类读数的，提示回补。
    if CYCLE_TOPPING.search(draft):
        miss_top = []
        if not re.search(r"增速|同比|环比", draft):
            miss_top.append("没有增速类读数（同比／环比）")
        if not re.search(r"供给|投放|在建|新增产能|复产", draft):
            miss_top.append("没有供给投放类读数")
        r.add("Gate 2", "见顶结论有增速与投放读数", not miss_top,
              ("成稿写了见顶，但" + "、".join(miss_top) + "：判顶部要写利润增速是否在放缓、"
               "供给投放进度是否已明确（股价不等投放那天才跌）"
               "（references/08 第四节 4.8／4.9）") if miss_top
              else "见顶结论带了增速与供给投放读数", level="warn")

    # 自算的单位数（吨成本、吨毛利、单店收入……）必须落一份核查底稿：见 references/12。
    unit_hits = ([m.group(0) for m in UNIT_PRICE_PAT.finditer(draft)]
                 + [m.group(0) for m in UNIT_DERIVED_PAT.finditer(draft)])
    if not unit_hits:
        r.add("Gate 2", "单位数核查", True, "成稿未出现按单位计量的自算数字", level="warn")
    else:
        uf = read(wd / "单位数核查.md")
        if uf is None:
            kinds = "」「".join(sorted(set(unit_hits))[:4])
            r.add("Gate 2", "单位数核查", False,
                  f"成稿出现按单位计量的数字 {len(unit_hits)} 处（如「{kinds}」），"
                  "缺 02-工作底稿/单位数核查.md。底稿是一张清单："
                  "数值 ／ 来源 ／ 实测或倒推 ／ 对照基准 ／ 档位（见 references/12 第四节）")
        else:
            urows = [x for x in table_rows(uf) if any(c.strip() for c in x)]
            urows = [x for x in urows if not re.match(r"^\s*(数值|数字|指标|单位数)\s*$", x[0])]
            has_bench = bool(re.search(r"对照|基准", uf))
            back = [x for x in urows if "倒推" in " ".join(x)]
            back_bad = [x for x in back
                        if not (re.search(r"对照|基准", " ".join(x))
                                and len([c for c in x if c.strip() and not PLACEHOLDER.match(c)]) >= 4)]
            if not has_bench:
                r.add("Gate 2", "单位数核查", False,
                      f"单位数核查.md 表格行 {len(urows)}，但没有写到「对照基准」这一栏")
            elif back_bad:
                r.add("Gate 2", "单位数核查", False,
                      f"{len(back_bad)} 行标注为倒推，却没有写对照基准"
                      "（倒推值须降级为「推算值，仅供量级参考」，见 references/12 第二节法五）")
            else:
                r.add("Gate 2", "单位数核查", len(urows) >= 1,
                      f"表格行 {len(urows)}，含对照基准"
                      + (f"，其中倒推 {len(back)} 行" if back else ""))

    self_check = read(wd / "成稿自检记录.md")
    ok_sc = bool(self_check) and len(self_check.splitlines()) >= 15 and re.search(r"\d{3,}", self_check)
    r.add("Gate 2", "自检记录是数字不是空话", bool(ok_sc),
          "含字数／行数／标注处数的机械核对结果" if ok_sc else "缺 02-工作底稿/成稿自检记录.md 或只有一句话")

    # 文体体检（可数阈值，见 references/00 第六节）。只提示，不阻断。
    dash = draft.count("——")
    r.add("Gate 2", "破折号插入语", dash <= DASH_CAP, f"{dash} 处（上限 {DASH_CAP}）", level="warn")
    bold_sent = re.findall(r"\*\*[^*\n]{8,}[。！？]\*\*", draft)
    r.add("Gate 2", "无整句加粗", not bold_sent,
          f"{len(bold_sent)} 处整句加粗（加粗只用于词与短语）" if bold_sent else "加粗只用于词与短语", level="warn")
    tras = [w for w in TRANSITION_WORDS if draft.count(w) > 1]
    r.add("Gate 2", "过渡词各不超一次", not tras,
          "超次：" + "、".join(f"{w}×{draft.count(w)}" for w in tras) if tras else "过渡词未超次", level="warn")
    selfref = len(SELFREF.findall(draft))
    r.add("Gate 2", "自我指涉克制", selfref <= 4, f"本报告／本节／笔者 {selfref} 处", level="warn")
    expl = EXPLAIN_MARK.findall(draft)
    r.add("Gate 2", "无讲解文标记", not expl,
          "命中：" + "、".join(sorted(set(expl))) if expl else "未见讲解文标记", level="warn")
    straight = draft.count('"')
    r.add("Gate 2", "中文引号用全角", straight <= 2, f"直引号 {straight} 个", level="warn")
    r.add("Gate 2", "参照带四项齐备",
          all(w in (section(draft, "估值", level=2) or draft) for w in ("推导", "样本", "假设", "局限")),
          "推导链／样本区间／假设清单／局限说明（见 references/05）", level="warn")

    # AI 腔体检（见 references/00 第六节《去 AI 味》）。按每万字折算，只提示，不阻断。
    wan = max(cjk_count(draft), 1) / 10000.0
    ai_hits = []
    for w in AI_CLICHE_ZERO:
        n = len(re.findall(re.escape(w), draft))
        if n:
            ai_hits.append(f"{w}×{n}")
    for name, pat, cap in AI_CLICHE_DENSITY:
        n = len(re.findall(pat, draft))
        if n and n / wan > cap:
            ai_hits.append(f"{name}×{n}（超 {cap}/万字）")
    r.add("Gate 2", "无 AI 腔用词", not ai_hits,
          "超线：" + "、".join(ai_hits) if ai_hits else "AI 腔词未超线，见 references/00 第六节", level="warn")

    # 行话与术语（见 references/00 第六节·行话与术语，2026-10-15 新增）。只提示，不阻断。
    body = body_only(draft)
    jg = jargon_hits(body)
    r.add("Gate 2", "无圈内行话", not jg,
          ("命中：" + "、".join(jg)
           + "（改通用说法：主导侧→涨跌来源；共振→利润与估值同时上升；双杀→同时下降；双击→同上）")
          if jg else "未见主导侧／共振／双杀／双击", level="warn")
    bm = bare_multiple(body)
    r.add("Gate 2", "「倍数」不单用", not bm,
          (f"{len(bm)} 处单用：「" + "、".join(bm[:4]) + "」"
           "（要写指标名与算法：市盈率（PE，股价 ÷ 每股收益）X 倍）")
          if bm else "倍数都跟着指标名", level="warn")
    ab = abbr_not_expanded(draft)
    r.add("Gate 2", "缩写首次出现已展开", not ab,
          ("未展开：" + "、".join(ab[:6])) if ab else "字母缩写都能找到中文名", level="warn")
    # 机器腔（见 references/00 第六节·机器腔）：代号、条数计数、指针互指、统计记法。只提示，不阻断。
    prose = [ln for ln in draft.splitlines()
             if not ln.lstrip().startswith(("|", "#", "```"))]
    mach = []
    for ln in prose:
        for pat in MACHINE_FORMS:
            m = re.search(pat, ln)
            if m:
                mach.append(m.group(0))
                break
    r.add("Gate 2", "无机器腔（状态行）", not mach,
          (f"{len(mach)} 处字段串（如「{mach[0]}」）：代号、条数计数、指针互指、参数串都属于表格与底稿，"
           "正文一句话只装一件事（references/00 第六节·机器腔）") if mach
          else "未见状态行式的字段串", level="warn")
    # 过程自述（见 references/00 第六节·过程自述）：报告的正文不介绍作者自己怎么做的。
    proc = []
    for ln in prose:
        for pat in PROCESS_FORMS:
            m = re.search(pat, ln)
            if m:
                proc.append(m.group(0))
                break
    r.add("Gate 2", "无过程自述", not proc,
          (f"{len(proc)} 处（如「{proc[0]}」）：正文不交代作者怎么取角、怎么排章节，"
           "也不引用底稿栏位；主语该是公司或行业（references/00 第六节·过程自述）") if proc
          else "未见取角与排章节的自述", level="warn")
    # 报告要自足（见 references/00 第六节·报告要自足）：正文不把读者指去别的文件。
    # 只扫正文（附录之前）；附录 G 溯源表里列文件路径是来源登记，不算违规。
    ptr = []
    for ln in body_only(draft).splitlines():
        s = ln.strip()
        if not s or s.startswith(("|", "#", "```")):
            continue
        if "底稿" in s:
            ptr.append("底稿")
            continue
        for pat in POINTER_FORMS:
            m = re.search(pat, s)
            if m:
                ptr.append(m.group(0))
                break
    r.add("Gate 2", "正文不指向底稿与规则", not ptr,
          (f"{len(ptr)} 处（如「{ptr[0]}」）：正文不把读者指去底稿、规则文档或别的文件——"
           "判据与结论写进正文，完整版放附录（references/00 第六节·报告要自足）") if ptr
          else "正文未指向底稿与规则", level="warn")
    # 编号式波次（见 references/08 第二节末）：底稿里有已完成的大涨时一并提示。
    hits = [m.group(0) for m in WAVE_NUMBER.finditer(body_only(draft))]
    forms = sorted(set(hits))
    big = None
    if hits:
        seg = read(wd / "历史股价复盘.md") or ""
        pcts = [int(float(x)) for x in CYCLE_GAIN_PCT.findall(seg)]
        if pcts and max(pcts) >= 50:
            big = max(pcts)
    prog = [m.group(0) for m in PROGRESS_PHRASING.finditer(body_only(draft))]
    r.add("Gate 2", "位置结论带方向", not prog,
          (f"{len(prog)} 处（如「{prog[0]}」）：进度式说法读的是\"条件到没到\"，读者要的是**方向**——"
           "出清是在恶化还是在改善、供给是在扩张还是在收缩。判据还没转好，就写"
           "\"出清没有进展、基本面还在走坏、价格缺乏上行动力\"，不写\"尚未凑齐\""
           "（那三个字读起来是\"只差临门一脚\"），见 references/08 第二节末") if prog
          else "位置结论未见进度式说法", level="warn")
    r.add("Gate 2", "不写编号式波次", not hits,
          (f"{len(hits)} 处（{'、'.join(forms)}）"
           + (f"；底稿段表里有 +{big}% 的上涨段" if big else "")
           + "：读者不知道你从哪儿数起，换成相对当前的说法（下一轮由供给收缩驱动的上涨），"
             "并回头把这句与同页的股价节奏坐标连起来读一遍（references/08 第二节末）") if hits
          else "未见编号式波次", level="warn")
    # 表头与表题用读者语言（见 references/06 第五节）：表头出现圈内词即提示。
    hdr = []
    for m in re.finditer(r"^\|[^\n]*\|\s*\n\|[\s\-:|]+\|", draft, re.M):
        head = m.group(0).splitlines()[0]
        if any(w in head for w in ("读数", "取数")):
            hdr.append(head.strip()[:60])
    r.add("Gate 2", "表头不用圈内词", not hdr,
          (f"{len(hdr)} 张表的表头带圈内词（如「{hdr[0]}」）：「读数」→ 本轮的实际情况；"
           "「取数」→ 直接写数值或来源（references/06 第五节）") if hdr
          else "表头未见圈内词", level="warn")

    apx_h = appendix_h(draft)
    if apx_h is None:
        r.add("Gate 2", "附录 H 术语表", False,
              "找不到「附录 H」。附录 A—I 九项里 H 固定放术语表（见 references/02 第四节）",
              level="warn")
    else:
        hrows = [x for x in table_rows(apx_h)
                 if len(x) >= 2 and not re.match(r"^\s*(术语|名词|缩写|英文)\s*$", x[0])]
        para = False
        if not hrows:
            # 兼容"**术语**：解释"的段落式写法（前几份成稿用的是这种），仍要求逐条成行。
            hrows = re.findall(r"^\*\*[^*\n]+\*\*\s*[:：]", apx_h, re.M)
            para = True
        nrow = len(hrows)
        r.add("Gate 2", "附录 H 术语表", nrow >= APX_H_MIN_ROWS,
              f"{nrow} 行（下限 {APX_H_MIN_ROWS}）"
              + ("" if nrow >= APX_H_MIN_ROWS
                 else "：正文用到的缩写、财务词、行业词要逐条成行，三列（术语 ／ 一句话解释 ／ 首次出现的位置）")
              + ("（段落式写法：改成三列表更便于按行核对）" if para and nrow < APX_H_MIN_ROWS else ""),
              level="warn")
    honor = honor_hits(draft)
    if honor:
        uniq = "、".join(sorted(set(honor))[:8])
        r.add("Gate 2", "榜单类指标须核口径", False,
              f"命中 {len(honor)} 处（{uniq}）：逐处核口径／基准／背离并按 references/11 第九节定档",
              level="warn")
    else:
        r.add("Gate 2", "榜单类指标须核口径", True, "未出现 NPS／满意度／名次类表述", level="warn")

    # 段落体检（references/02 第五节《数据不进段落》）：只提示"回去读一遍"，不按字数判拆段。
    # 拆段按内容（这一段是不是在说一件事），不按长度；同一件事被拆碎的要并回去。
    long_paras = [ln for ln in draft.splitlines()
                  if len(ln) > 400 and not ln.lstrip().startswith(("|", "#", "-", "*", ">", "["))]
    r.add("Gate 2", "段落体检", not long_paras,
          (f"{len(long_paras)} 段超过 400 字（最长 {max(len(x) for x in long_paras)} 字）："
           "疑似一段多事，回去读一遍——该拆的按内容拆，同一件事被拆碎的还要并回去"
           "（references/02 第五节）") if long_paras
          else "未见需要回读的段落", level="warn")

    echo = TABLE_ECHO.findall(draft)
    r.add("Gate 2", "表格后不复述", not echo,
          "命中：" + "、".join(sorted(set(echo))) if echo else "未见“上表显示”类复述句", level="warn")

    # 禁则扫描：只扫正文行，免责声明等合法上下文跳过。
    hits_hard, hits_soft = [], []
    for i, line in enumerate(draft.splitlines(), 1):
        if BANNED_ALLOW.search(line):
            continue
        for w in BANNED_HARD:
            if w in line:
                hits_hard.append(f"{i}:{w}")
        for w in BANNED_SOFT:
            if w in line:
                hits_soft.append(f"{i}:{w}")
    r.add("Gate 2", "无投资建议措辞", not hits_hard,
          "、".join(hits_hard[:6]) + ("…" if len(hits_hard) > 6 else "") if hits_hard else "未见买入／卖出／目标价／仓位类表述")
    r.add("Gate 2", "无软性越界措辞", not hits_soft, "、".join(hits_soft[:6]) if hits_soft else "未见评级／仓位类表述", level="warn")

    srcbook = [w for w in SOURCEBOOK if w in draft]
    r.add("Gate 2", "无方法论底本字段", not srcbook, "命中：" + "、".join(srcbook) if srcbook else "全文未出现底本对照")
    r.add("Gate 2", "免责声明在位", "不构成任何投资建议" in draft, "正文开头与附录 I 各一处")
    # 引用坐标应落在原件（页码／表号）上，不写抽取副本的行号（references/00 第二节第 1 条）。
    line_refs = re.findall(r"第\s*\d+\s*(?:[—－~～-]\s*\d+\s*)?行", draft)
    r.add("Gate 2", "引用坐标落在原件上", not line_refs,
          (f"{len(line_refs)} 处行号式引用（如 {line_refs[0]}）：抽取副本项目结束就清掉，"
           "行号届时无人能核——改成原件页码或表号（references/00 第二节第 1 条）")
          if line_refs else "未见抽取副本行号式引用", level="warn")

    apx_i = appendix_i(draft)
    if apx_i is None:
        r.add("Gate 2", "附录 I 是免责声明", False,
              "找不到「附录 I」。附录 A—I 九项里 I 固定放免责声明（见 references/02 第四节）；"
              "待核实与数据缺口不进附录，落在正文第 10 节")
    else:
        r.add("Gate 2", "附录 I 是免责声明", "不构成任何投资建议" in apx_i,
              "附录 I 放的是免责声明，不是待核实清单" if "不构成任何投资建议" in apx_i
              else "附录 I 里有内容但缺免责声明文本；待核实与数据缺口应落在正文第 10 节")


def check_gate3(r: Runner, proj: Path, draft: str | None = None):
    """Gate 3 与 Gate 3.5 各自独立：一份底稿缺了，不遮住另一份的检查结果。"""
    wd = proj / "02-工作底稿"

    text = read(wd / "投资人视角复核.md")
    if text is None:
        r.add("Gate 3", "投资人视角复核落盘", False, "缺 02-工作底稿/投资人视角复核.md")
    else:
        n = cjk_count(text)
        r.add("Gate 3", "复核记录有实质内容", n >= 600, f"中文字 {n}")
        rows = len(table_rows(text))
        r.add("Gate 3", "逐条给结论与证据", rows >= 3, f"表格行 {rows}")
        vague = re.search(r"已复核[，,]?\s*(内容)?(详实|完整|无问题|通过)", text)
        r.add("Gate 3", "非橡皮图章", vague is None,
              "出现「已复核，内容详实」式结论" if vague else "未见空泛通过语")

    # Gate 3.5：反向质疑（见 references/11）。
    qtext = read(wd / "反向质疑.md")
    if qtext is None:
        r.add("Gate 3.5", "反向质疑落盘", False, "缺 02-工作底稿/反向质疑.md（见 references/11）")
    else:
        r.add("Gate 3.5", "反向质疑落盘", True, "02-工作底稿/反向质疑.md")
        nq = cjk_count(qtext)
        r.add("Gate 3.5", "质疑记录有实质内容", nq >= 500, f"中文字 {nq}（下限 500）")
        missing = [t for t in ("前提", "死因", "激励", "空头") if t not in qtext]
        r.add("Gate 3.5", "四张表齐全", not missing,
              "缺：" + "、".join(missing) if missing else
              "前提清单｜死因清单｜激励地图｜空头反证（第五问的产物是 02-工作底稿/单位数核查.md，"
              "在 Gate 2 核对）")
        vague_q = re.search(r"已从反面思考[，,]?\s*(未发现|无)(重大问题|问题|异常)", qtext)
        r.add("Gate 3.5", "非橡皮图章", vague_q is None,
              "出现「已从反面思考，未发现重大问题」式结论" if vague_q else "未见空泛通过语")

    # 成稿出现榜单、评分、名次类信息时，必须另有一份指标核查底稿（见 references/11 第九节）。
    if draft and honor_hits(draft):
        mf = read(wd / "指标核查.md")
        if mf is None:
            r.add("Gate 3.5", "榜单类指标核查落盘", False,
                  "成稿命中 NPS／满意度／名次类表述，缺 02-工作底稿/指标核查.md（见 references/11 第九节）")
        else:
            rows = len(table_rows(mf))
            keys = [k for k in ("口径", "样本", "调查方法", "背离") if k in mf]
            ok_mf = rows >= 1 and bool(keys)
            detail = (f"指标核查.md：表格行 {rows}，含「{'／'.join(keys)}」" if keys
                      else f"指标核查.md 表格行 {rows}，但未写到口径／样本／调查方法／背离中任何一项")
            r.add("Gate 3.5", "榜单类指标核查落盘", ok_mf, detail)


def check_portable(r: Runner, root: Path):
    """skill 包本身的可移植性：开源前必须过这一关。"""
    me = Path(__file__).resolve()
    targets = [root / "SKILL.md", root / "README.md"]
    for sub in ("references", "scripts"):
        d = root / sub
        if d.is_dir():
            # 跳过扫描器自己：它里面的正则字面量会自我命中。
            targets += [p for p in sorted(d.iterdir())
                        if p.suffix in (".md", ".py") and p.resolve() != me]
    readme = read(root / "README.md")
    skill = read(root / "SKILL.md") or ""

    # 明确声明"不使用本机路径"的句子不算违规（如"不读写 ~/.codex/风格档案"）。
    NEGATED = re.compile(
        r"不读|不写|不调用|不走|不依赖|不接入|不需要|若存在|没有装|未装|别人|对方|换机器|换台"
        # 各 agent 约定的 skills 安装目录对所有用户都一样，不是个人标识。
        r"|skills/|skills\\"
    )
    abs_hits, home_hits, lib_hits = [], [], []
    for p in targets:
        if not p.is_file():
            continue
        for i, line in enumerate((read(p) or "").splitlines(), 1):
            if NEGATED.search(line):
                continue
            if re.search(r"/Users/|C:\\\\Users", line):
                abs_hits.append(f"{p.relative_to(root)}:{i}")
            if re.search(r"~/\.cache|~/\.[a-z-]*codex|codex-runtimes|codex-primary-runtime", line):
                lib_hits.append(f"{p.relative_to(root)}:{i}")
            if re.search(r"~/(Documents|Desktop|Downloads)", line):
                home_hits.append(f"{p.relative_to(root)}:{i}")

    r.add("可移植性", "无绝对路径与家目录路径", not abs_hits and not home_hits,
          "、".join((abs_hits + home_hits)[:6]) if (abs_hits or home_hits) else "示例一律用相对路径或占位符")
    r.add("可移植性", "不依赖本机私有运行时", not lib_hits,
          "、".join(lib_hits[:6]) + "（他人机器上不存在，须改为探测）" if lib_hits else "解释器与依赖改为探测式")

    other_skills = []
    for p in targets:
        if not p.is_file():
            continue
        for i, line in enumerate((read(p) or "").splitlines(), 1):
            if re.search(r"\b(doc-format|wechat-article|xhs-copy|storyboard-gen|huashu-gpt-image|imagegen-cn)\b", line):
                other_skills.append(f"{p.relative_to(root)}:{i}")
    r.add("可移植性", "无其他 skill 硬依赖", not other_skills,
          "、".join(other_skills[:6]) + "（对方环境未必装，须写成「若存在则用」）" if other_skills else "未硬引用其他 skill",
          level="warn")

    fm_ok = skill.startswith("---") and re.search(r"^name:\s*\S", skill, re.M) and re.search(r"^description:\s*\S", skill, re.M)
    r.add("可移植性", "SKILL.md frontmatter 合规", bool(fm_ok), "name + description 齐备")
    r.add("可移植性", "README 在位", readme is not None, "写明环境要求与安装方式")
    r.add("可移植性", "降级路径已写明", "降级" in skill, "低能力工作台照它跑，下限不塌")
    r.add("可移植性", "机械校验入口", (root / "scripts" / "check_gates.py").is_file(), "scripts/check_gates.py")


def main():
    ap = argparse.ArgumentParser(description="深度研究 skill 的机械闸门校验")
    ap.add_argument("--project", help="项目目录，如 outputs/2026-10-13-齐翔腾达002408")
    ap.add_argument("--stage", choices=["1", "2", "3", "all"], default="all")
    ap.add_argument("--market", choices=["A", "HK", "auto"], default="auto")
    ap.add_argument("--portable", action="store_true", help="校验 skill 包本身的可移植性")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    r = Runner()

    if args.portable:
        check_portable(r, root)
    if args.project:
        proj = Path(args.project).expanduser().resolve()
        if not proj.is_dir():
            print(f"找不到项目目录：{proj}", file=sys.stderr)
            return 2
        wd = proj / "02-工作底稿"
        ledger = read(wd / "取数台账.md")
        judge = read(wd / "四层判定表.md") or ""
        market = args.market if args.market != "auto" else detect_market(ledger, judge, wd.name)
        draft_path = find_draft(proj)
        draft = read(draft_path) if draft_path else None

        print(f"项目：{proj.name}\n判定：{'港股' if market == 'HK' else 'A 股'}"
              + (f"（自动识别，可用 --market 覆盖）" if args.market == "auto" else "（手工指定）"))
        if args.stage in ("1", "all"):
            check_gate1(r, proj, ledger)
        if args.stage in ("2", "all"):
            check_gate2(r, proj, market, draft_path, draft)
        if args.stage in ("3", "all"):
            check_gate3(r, proj, draft)

    if not args.project and not args.portable:
        ap.print_help()
        return 2

    print(r.render())
    bad = len(r.failed())
    print(f"\n结论：{'全部通过' if bad == 0 else f'{bad} 项未通过，补完再往前一步'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
