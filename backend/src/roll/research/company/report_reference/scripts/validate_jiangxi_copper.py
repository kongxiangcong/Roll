#!/usr/bin/env python3
"""Reproduce the 2025 annual-report case. This is an ex-post diagnostic, not a price target."""
import argparse
import copy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import statistics

import fundamental_valuation as model

ROOT = Path(__file__).resolve().parents[1]


def independent_dcf(fcfs, wacc, g, shares, adjustment):
    with localcontext() as ctx:
        ctx.prec = 40
        d = lambda x: Decimal(str(x))
        discount = 1 + d(wacc)
        present = sum(d(f) / discount ** (i + 1) for i, f in enumerate(fcfs))
        terminal = d(fcfs[-1]) * (1 + d(g)) / (d(wacc) - d(g))
        return float((present + terminal / discount ** len(fcfs) - d(adjustment)) / d(shares))


def generate(output):
    raw = (ROOT / "examples/jiangxi-copper-2025-facts.json").read_bytes()
    data = json.loads(raw)
    f = {k: v[0] for k, v in data["facts"].items()}
    a = data["assumptions"]
    market = data["market_inputs"]
    work = output / "02-工作底稿"
    value_dir = work / "估值"
    deliver = output / "03-交付物"
    value_dir.mkdir(parents=True, exist_ok=True)
    deliver.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, actual, expected, tolerance=.01):
        if abs(actual - expected) > tolerance:
            raise ValueError(f"{name}: {actual} != {expected}")
        checks.append({"check": name, "actual": actual, "expected": expected, "tolerance": tolerance, "passed": True})

    check("收入重述", f["revenue_2024_original"] + f["revenue_restatement"], f["revenue_2024_restated"])
    check("现金构成", f["cash_equivalents"] + f["non_equivalent_cash"], f["cash_total"])
    check("股份总数", f["a_issued"] + f["h_issued"], f["issued_total"])
    check("扣库存股后分母", f["issued_total"] - f["treasury_shares"], f["participating_shares"])
    check("CAS-IFRS归母利润差", f["net_income_parent_cas"] + f["safety_reserve_income_difference"], f["net_income_parent_ifrs"])
    debt = sum(f[k] for k in ["short_debt", "long_debt_all_maturities", "bonds_all_maturities", "long_payables_all_maturities", "leases_all_maturities"])
    check("融资负债变动表合计", debt, f["financing_liabilities_total"])
    # Retain, rather than conceal via an arbitrary tolerance, small A/H differences.
    ah_differences = {
        "cfo_cas_minus_ifrs_yuan": f["cfo_2025"] - (-6914103000),
        "capex_cas_minus_ifrs_sum_yuan": f["capex_2025"] - (4431081+26384+117304+2458+10046)*1000,
        "status": "Different presentations, not exactly reconciled; CAS is the primary input. Do not call these exact matches or assume rounding explains all differences."}
    history = []
    for year in (2023, 2024, 2025):
        cfo = f[f"cfo_{year}_restated"] if year == 2024 else f[f"cfo_{year}"]
        row = {"year": year, "cfo": cfo, "capex": f[f"capex_{year}"], "raw_cfo_less_capex": cfo - f[f"capex_{year}"]}
        if year != 2023:
            wc = sum(f[f"{kind}_cash_{year}"] for kind in ("inventory", "receivables", "payables"))
            row["working_capital_cash_effect"] = wc
            row["pre_working_capital_cash"] = cfo - wc
            row["cfo_ex_finance_principal_only"] = cfo - f[f"deposit_cash_{year}"] - f[f"loan_cash_{year}"]
            row["interest_classification_only_fcff_proxy"] = model.fcff_from_cfo(cfo, row["capex"], f[f"interest_paid_{year}"], a["tax_rate"], "financing")
            check(f"{year}营运资金桥接", row["pre_working_capital_cash"] + wc, cfo)
        history.append(row)
    # Two restated years, not claimed to be a full commodity cycle.
    pre_wc = statistics.mean(r["pre_working_capital_cash"] for r in history[1:])
    capex = statistics.mean(f[f"capex_{y}"] for y in (2024, 2025))
    interest = statistics.mean(f[f"interest_received_{y}"] for y in (2024, 2025))
    shield = statistics.mean(f[f"interest_paid_{y}"] for y in (2024, 2025)) * a["tax_rate"]
    seed = pre_wc - interest * (1-a["tax_rate"]) - shield - capex - a["normal_working_capital_investment"]
    # A/H are separate market prices for the same ordinary economic rights.
    market_equity = (f["a_issued"]-f["treasury_shares"]) * market["a_close_cny"] + f["h_issued"] * market["h_close_hkd"] * f["hkd_cny"]
    ke = market["rf"] + a["beta"] * a["equity_risk_premium"] + a["additional_equity_premium"]
    debt_weight = debt / (debt + market_equity)
    wacc = ke * (1-debt_weight) + a["debt_cost"] * (1-a["tax_rate"]) * debt_weight
    bridge = [
        ("融资负债（全期限）", debt, "A25 PDF210", "正值扣减；黄金租赁已含，不另加"),
        ("少数股东权益账面代理", f["nci_book"], "A25 PDF102", "合并现金流含少数股东；账面代理需市场价值复核"),
        ("可用现金代理", -(f["cash_equivalents"]-a["operating_cash_reserve"]), "A25 PDF212 + analyst reserve assumption", "仅现金等价物减假设经营保有量；不将受限资金当富余现金"),
        ("第一量子投资公开报价", -f["fqm_quoted_fair_value"], "A25 PDF218", "未纳入集团经营FCFF的联营权益单列；处置税费暂未计"),
        ("其他联营合营账面代理", -(f["associate_total_book"]-f["fqm_book"]), "A25 PDF100/218", "不含第一量子，账面代理并非公允价值")]
    limitations = [
        "财务公司、贸易和工业现金流未取得完整合并抵销拆分；本模型不是完整去金融FCFF或SOTP",
        "两年去营运资金均值、30亿元正常投入及资本开支均为条件设置，不能证明跨周期或永续",
        "套保结算、保证金、少数股东公允价值、富余现金、租赁续租和投资处置税费仍待核验",
        "税率25%是母公司税率代理，不能证明集团可实际实现全部利息税盾",
        "历史A/H收盘价及精确国债收益率仅数据库证据；2025年底基准使用2026年年报，存在事后信息",
    ]
    cfg = {
        "metadata": {"company": data["company"], "as_of": data["balance_sheet_date"], "research_date": data["research_date"],
                     "listing_structure": "A+H", "currency": "CNY", "amount_unit": "million", "shares_unit": "million_shares",
                     "sources": data["sources"], "assumptions": [a["explanation"], "See facts JSON field-level PDF pages; no current-price assertion"]},
        "review": {"status": "blocked", "limitations": limitations},
        "cash_flow_basis": "FCFF", "shares": f["participating_shares"] / 1e6,
        "equity_bridge": [{"name": n, "amount": x/1e6, "source": s, "treatment": t} for n,x,s,t in bridge],
        "wacc": wacc, "terminal_g": a["terminal_g"],
        "scenarios": [{"name": name, "probability": prob, "fcf": [(seed + pre_wc*(factor-1))/1e6]*5}
                      for name, factor, prob in zip(("stress_low", "diagnostic_base", "stress_high"), a["cash_generation_factors"], a["scenario_probabilities"])],
        "sensitivity": {"scenario": "diagnostic_base", "wacc": [wacc-.01,wacc,wacc+.01], "terminal_g": [0,.01,.02]},
        "reverse": {"scenario": "diagnostic_base", "market_equity_value": market_equity/1e6},
        "epv": {"normalized_fcff": seed/1e6},
    }
    result = model.run(cfg)
    for row in result["scenarios"]:
        independent = independent_dcf(row["fcff"], wacc, a["terminal_g"], cfg["shares"], result["equity_adjustment"])
        check("Decimal独立折现-"+row["name"], row["per_share"], independent, 1e-9)
    roundtrip = model.reverse(result["scenarios"][1]["per_share"], cfg["shares"], result["equity_adjustment"], wacc, a["terminal_g"], cfg["scenarios"][1]["fcf"], [], 1)
    check("正反向回代", roundtrip["terminal_fcf_required"], seed/1e6*(1+a["terminal_g"]), 1e-7)
    variants = {}
    for label, transform in {
        "FQM按账面而非公开报价": lambda c: c["equity_bridge"][3].update(amount=-f["fqm_book"]/1e6),
        "经营现金保有量翻倍至100亿元": lambda c: c["equity_bridge"][2].update(amount=-(f["cash_equivalents"]-2*a["operating_cash_reserve"])/1e6),
        "少数股东价值提高25%": lambda c: c["equity_bridge"][1].update(amount=f["nci_book"]*1.25/1e6),
        "正常营运资金投入减半": lambda c: [s.update(fcf=[x+a["normal_working_capital_investment"]/2/1e6 for x in s["fcf"]]) for s in c["scenarios"]],
        "正常营运资金投入翻倍": lambda c: [s.update(fcf=[x-a["normal_working_capital_investment"]/1e6 for x in s["fcf"]]) for s in c["scenarios"]],
    }.items():
        variant = copy.deepcopy(cfg)
        # Only compare base DCF; EPV/reverse/sensitivity would require consistent changes.
        for key in ("epv", "reverse", "sensitivity"):
            variant.pop(key)
        variant["scenarios"] = [copy.deepcopy(cfg["scenarios"][1])]
        variant["scenarios"][0]["probability"] = 1
        transform(variant)
        try:
            variants[label] = model.run(variant)["scenarios"][0]["per_share"]
        except ValueError as exc:
            variants[label] = "拒绝: " + str(exc)
    bvps = f["parent_equity"] / f["participating_shares"]
    crosschecks = {"book_value_per_share": bvps, "net_income_per_participating_share": f["net_income_parent_cas"] / f["participating_shares"],
                  "ddm": [{"ke": k, "g": g, "value": 1*(1+g)/(k-g)} for k in (.08,.10,.12) for g in (0,.02)],
                  "pb_roe": [{"roe": r, "ke": ke, "g": .02, "pb": (r-.02)/(ke-.02), "value": bvps*(r-.02)/(ke-.02)} for r in (.07,.09,.11)]}
    diagnostic = {"facts_sha256": hashlib.sha256(raw).hexdigest(), "checks": checks, "history": history, "ah_differences": ah_differences,
                  "normalization": {"pre_wc_mean": pre_wc, "cash_interest_mean": interest, "tax_shield_proxy": shield, "capex_mean": capex, "normal_wc_assumption": a["normal_working_capital_investment"], "fcff_seed": seed},
                  "capital_cost": {"rf": market["rf"], "ke": ke, "debt_weight": debt_weight, "wacc": wacc, "market_equity": market_equity},
                  "variants": variants, "crosschecks": crosschecks}
    config_path = value_dir / "assumptions.json"
    config_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    result["input_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    result["calculator_sha256"] = hashlib.sha256((ROOT/"scripts/fundamental_valuation.py").read_bytes()).hexdigest()
    for name, obj in [("result.json", result),("audit.json", diagnostic)]:
        (value_dir/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (work/"逐字段溯源.md").write_text("# 逐字段溯源\n\n金额单位：人民币元；每股、汇率及股数按字段说明。PDF页为从封面起1-based物理页。\n\n|字段|数值|原表位置|\n|---|---:|---|\n"+"\n".join(f"|{k}|{val:,}|{src}|" for k,(val,src) in data["facts"].items())+"\n",encoding="utf-8")
    manifest = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in (output/"01-原始资料").glob("*.pdf")]
    (work/"原件校验.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    write_report(deliver, work, data, f, a, cfg, result, diagnostic, bridge)
    print(json.dumps({"numeric_checks_passed": len(checks), "review_status": result["review"]["status"], "base_diagnostic_per_share": result["scenarios"][1]["per_share"], "wacc": wacc, "output": str(output)},ensure_ascii=False))
    return diagnostic


def write_report(deliver, work, data, f, a, cfg, result, audit, bridge):
    yi = lambda n: f"{n/1e8:,.4f}"
    lines = ["# 江西铜业：2025年报估值流程验证", "",
             "研究日期：2026-10-24。资产负债与市场比较基准：2025-12-31。金额默认人民币亿元，每股数默认人民币元。",
             "", "## 结论与使用边界", "",
             "真实年报取数、重述核对、现金流调整、条件估值、敏感性、反推与独立复算均已运行。计算验证通过，经济口径审核未通过。下文DCF数字是暴露假设影响的诊断输出，不能作为江西铜业的合理价格区间。",
             "基准日采用2025年底，信息来自2026年发布的年报，这是事后重建，不是2025年底可执行的投资回测；也不是截至2026年10月的现时估值。2026年中报、收购及资本结构变化未纳入该历史实验。",
             "本次最重要的发现：江西铜业合并经营现金流包括金融业务存贷款、期货保证金及贸易资金周转。公开年报可以校核金额，却不足以直接得到稳定的工业自由现金流。正式估值应拆分工业经营、财务公司权益和联营投资，不能强行把整个集团当作单一非金融公司。",
             "", "## 1. 原始证据与核验范围", "",
             "|编号|原件|本次作用|", "|---|---|---|",
             f"|A25|[2025 A股年报]({data['sources']['A25']})|中国会计准则主口径，262个PDF物理页；主表部分扫描，已目视核对|",
             f"|H25|[2025 H股年报]({data['sources']['H25']})|IFRS交叉核对；财表以人民币千元列示，不与A股元单位混用|",
             f"|A24|[2024 A股年报]({data['sources']['A24']})|核对重述前2024数及2023比较数|",
             "原件保存在01-原始资料，SHA-256及文件长度在底稿中登记。字段出处详见逐字段溯源。A/H两份报告同属公司披露，不是两项独立经营事实证据；独立数值复核另用Decimal公式实现。",
             "A/H现金流金额量级相符但没有完全相等：2025年A股CFO比H股千元数换算高1,685元；A股购建长期资产现金比H股五项加总少4,377元。差异单列保留，未扩大容差冒充精确勾稽；本次始终采用CAS原表，不宣称全部由四舍五入解释。",
             "", "## 2. 重述、准则和股份口径", "",
             f"2024年收入由{yi(f['revenue_2024_original'])}重述为{yi(f['revenue_2024_restated'])}，差额{yi(f['revenue_restatement'])}；经营现金流由{yi(f['cfo_2024_original'])}改为{yi(f['cfo_2024_restated'])}。原因是标准仓单交易会计政策调整，不能拼接数据库旧数。依据A25 PDF147、A24 PDF206。",
             f"2025年CAS归母利润{yi(f['net_income_parent_cas'])}，IFRS为{yi(f['net_income_parent_ifrs'])}，差额{yi(f['safety_reserve_income_difference'])}来自安全生产费用处理（A25 PDF8）。本次利润与账面权益交叉对照均沿用CAS。",
             f"发行股份{f['issued_total']:,}股，扣库存股{f['treasury_shares']:,}股，参与分配股数为{f['participating_shares']:,}股（A25 PDF195、198）。每股模型采用后者，未把库存股继续作为价值分母。",
             "", "## 3. 周期与业务边界", "",
             "公司2025年报PDF13称沪铜年均80,695元/吨、同比上升7.52%，铜矿紧缺但冶炼加工费承压。矿山受益与冶炼承压可以并存，不能把铜价上涨等同集团利润同比例上升。这里引用公司披露的行业描述，未独立重建交易所价格序列。",
             "PDF15披露自产铜精矿含铜26.99万吨，但脚注明确包含第一量子当年权益产量；2024为19.97万吨。第一量子采用权益法，不合并其收入，不能用这个产量同比增速预测集团收入，也不能把集团利润除以26.99万吨倒算自产矿吨成本。",
             "没有足够长且口径一致的铜价/公司PB序列，本次不伪造历史分档分位，不运行要求此类输入的cycle_valuation分档模块。采用PB-ROE和股利模型作为条件参照，同时检验现金流法的边界。",
             "", "## 4. 现金流重建", "",
             "|年度|经营现金流|现金购建长期资产|直接相减|口径|", "|---|---:|---:|---:|---|" ]
    for row in audit["history"]:
        lines.append(f"|{row['year']}|{yi(row['cfo'])}|{yi(row['capex'])}|{yi(row['raw_cfo_less_capex'])}|{'旧政策，仅背景，不纳入拟合' if row['year']==2023 else '2025年报可比口径'}|")
    lines += ["直接相减只用于展示历史现金缺口，不能命名为已正常化FCFF。购建长期资产现金含扩张与维护，年报没有给本次模型所需的完整拆分。",
              "", "### 4.1 金融业务与利息分类", "",
              "|年度|剔除财务公司存贷款本金变化后的CFO|说明|", "|---|---:|---|"]
    for r in audit["history"][1:]:
        lines.append(f"|{r['year']}|{yi(r['cfo_ex_finance_principal_only'])}|仍含利息、保证金、税及其他业务，不是工业FCFF|")
    lines += [f"2025年财务公司存款减少{yi(-f['deposit_cash_2025'])}、贷款收回{yi(f['loan_cash_2025'])}均在经营活动；商品期货保证金流出{yi(f['margin_deposit_outflow_2025'])}（A25 PDF208）。去掉两项金融本金，不等于完成金融业务剥离；需要子公司及合并抵销资料。",
              "H25 PDF194将已付利息列在融资活动。若利息及税盾可以同年实现：经营分类时FCFF=CFO−Capex+I×(1−T)；融资分类时FCFF=CFO−Capex−I×T。本次用25%作税盾代理；集团实际税率和资本化利息仍需逐项核对。错误地再加回税后利息，会比后一个公式多算完整的I。",
              f"2025已付利息约{yi(f['interest_paid_2025'])}，因此这个误用会令当期现金流多算同样金额。A25 PDF150显示母公司税率已由15%变为25%，不能沿用旧税率；它也不能代表每家境内外子公司的实际税负。",
              "", "### 4.2 诊断性正常化，不作为预测", "",
              "先从CFO中剔除附注现金流调节表里的存货、经营应收和经营应付变化；这些调整值已包括多类流动项目，不能再重复加回财务公司本金与保证金。然后减去税后现金利息收入代理、融资利息税盾代理、两年平均总资本开支及假设正常营运资金投入。",
              "|输入|亿元|性质|", "|---|---:|---|"]
    norm=audit["normalization"]
    for key,label,kind in [("pre_wc_mean","2024/25去营运资金变化现金均值","披露值推算，仍非纯工业现金"),("cash_interest_mean","现金利息收入均值","年报现金口径；按75%扣除是假设"),("tax_shield_proxy","利息税盾代理","假设25%可抵扣"),("capex_mean","总资本开支均值","历史现金，不等于维护开支"),("normal_wc_assumption","正常营运资金投入","研究者设置"),("fcff_seed","基准现金流种子","条件推算，未通过经济审核")]:
        lines.append(f"|{label}|{yi(norm[key])}|{kind}|")
    lines += ["压力情景只把去营运资金变化的现金生成能力上下调整15%，其余相同，连续五年输入后按2%增长进入终值。概率25%/50%/25%是展示设置，不是铜价概率预测。此处没有证明终值再投资足以支持增长，故系统保留blocked状态。",
              "", "## 5. 企业价值至归母权益的逐项调整", "",
              "正数从企业价值扣除，负数增加归母权益。下面是诊断口径，并非所有资产、负债的公允价值鉴证。",
              "|项目|调整额（亿元）|处理|", "|---|---:|---|"]
    lines += [f"|{name}|{yi(amount)}|{treatment}；{source}|" for name,amount,source,treatment in bridge]
    lines += [f"合计净扣项{result['equity_adjustment']/100:,.4f}亿元。短债内含黄金租赁{yi(f['gold_financing_in_short_debt'])}，未重复扣；长期借款、债券、租赁均已含一年内到期部分。",
              f"货币资金{yi(f['cash_total'])}，其中受限{yi(f['restricted_cash'])}；非现金等价物{yi(f['non_equivalent_cash'])}并不全部是受限资金。诊断仅使用现金等价物{yi(f['cash_equivalents'])}减假设经营保有量50亿元，遗漏的非受限定存须与质押对应关系一起补查，不能全部忽略后称保守公允价值。",
              "第一量子用年报所列公开报价，不与其权益法账面重复相加；未单独加回财务公司净资产，因为本诊断仍包含其合并经营结果。其他金融资产、衍生头寸和存款负债须成套拆分，不能只挑资产加回。少数股东用账面代理、联营持股处置税费未计，都是未放行原因。",
              "", "## 6. 折现率、A/H市值与时间", "",
              f"无风险利率1.847%取数据库2025-12-31中债10年数；beta=1.2、权益风险溢价6%、额外权益溢价1%、债务成本3.5%均为研究设置。Ke=1.847%+1.2×6%+1%={audit['capital_cost']['ke']:.3%}。按诊断融资负债及A/H合计市值权重，债务权重{audit['capital_cost']['debt_weight']:.3%}，税率25%，WACC={cfg['wacc']:.4%}。这不是独立校准的资本成本。",
              f"数据库返回A股54.92元、H股42.88港元；港元兑人民币0.90322与人民银行历史表匹配。合计市值=(A股数−库存股)×54.92+H股数×42.88×0.90322={yi(audit['capital_cost']['market_equity'])}亿元。两个历史收盘价尚未独立比对交易所原始行情，故反向结果同样只作诊断。",
              "A股价乘全部股数会把H股也按A股价格计价。计算器现支持同币种合计市值输入，标记A+H时拒绝单一股价反推。所有结果均先以人民币表达，未将人民币/股直接标为港元/股。",
              "", "## 7. 已运行的诊断结果（经济审核未通过）", "",
              "|情景|年度FCFF（亿元）|企业价值（亿元）|每股条件值（元）|终值占比|", "|---|---:|---:|---:|---:|"]
    for r in result["scenarios"]:
        lines.append(f"|{r['name']}|{r['fcff'][0]/100:.4f}|{r['enterprise_value']/100:.4f}|{r['per_share']:.4f}|{r['terminal_share_of_ev']:.2%}|")
    lines += [f"条件加权值{result['weighted_per_share']:.4f}元；无增长EPV诊断值{result['epv']['per_share']:.4f}元。二者共用现金流种子和权益调整，不构成独立印证，也不合成为目标价。负的每股剩余值只表示该套假设下企业价值不足以覆盖扣项，不是负股价、股东追加出资义务或有限责任股权的期权价值。",
              "", "### 7.1 WACC与增长敏感性", "", "|WACC|长期增长率|基准条件值（元）|", "|---:|---:|---:|"]
    lines += [f"|{r['wacc']:.4%}|{r['terminal_g']:.1%}|{r['per_share']:.4f}|" for r in result["sensitivity"]]
    lines += ["", "### 7.2 关键口径替换", "", "|只改一个假设|基准条件值（元）|", "|---|---:|"]
    lines += [f"|{key}|{val:.4f}|" if isinstance(val,(int,float)) else f"|{key}|{val}|" for key,val in audit["variants"].items()]
    lines += [f"反向DCF固定五年基准现金流，按A/H合计市值解出的第六年所需FCFF为{result['reverse']['terminal_fcf_required']/100:.4f}亿元。它是附条件解，不是预测。未把集团低利润率的贸易收入乘固定利润率强行转换为隐含铜产量或收入增长。",
              "", "## 8. 股权口径交叉对照", "",
              f"归母每股净资产={yi(f['parent_equity'])}亿元÷{f['participating_shares']/1e8:.6f}亿股={audit['crosschecks']['book_value_per_share']:.4f}元。按年末参与股数算的利润/股为{audit['crosschecks']['net_income_per_participating_share']:.4f}元，与披露EPS2.07在两位小数上相符；未把期末分母当作普遍适用的加权平均股数。",
              "2025全年每股1元股利包含年报提议的末期0.6元。以下DDM仅展示未来保持或增长该分红的条件值，不把方案当已支付现金。",
              "|权益成本|股利长期增长|股利条件值（元）|", "|---:|---:|---:|"]
    lines += [f"|{r['ke']:.0%}|{r['g']:.0%}|{r['value']:.4f}|" for r in audit["crosschecks"]["ddm"]]
    lines += ["稳态PB=(ROE−g)/(Ke−g)，隐含留存率g/ROE；它要求ROE可持续、净资产质量可靠且清洁盈余近似成立。FQM其他综合收益和周期性会破坏这种近似，故下面不是历史分位。", "", "|稳态ROE假设|PB|每股条件值（元）|", "|---:|---:|---:|"]
    lines += [f"|{r['roe']:.0%}|{r['pb']:.4f}|{r['value']:.4f}|" for r in audit["crosschecks"]["pb_roe"]]
    lines += ["三类方法的差异优先解释为现金流正常化、资本分配和账面资产口径差异，不能自动取平均来消除分歧。",
              "", "## 9. 修复与验证", "",
              "修复了利息分类转换函数；增加有来源和处理理由的权益调整明细，拒绝与净债务同时输入；支持A/H合计市值和只反推终值现金流；增加经济审核状态与--require-reviewed闸门。命令行计算成功不再等于经济审核通过。",
              f"本案例{len(audit['checks'])}项数值核对通过，包括重述、股份、现金构成、融资负债、CAS/IFRS利润差额、三个情景Decimal独立复算和正反向回代。A/H现金流小额差异另列，未计入通过项。通过范围是给定输入下的金额及算法，不是对未来假设的鉴证。",
              "复算命令（在仓库根目录）：", "", "```bash",
              "python -X utf8 scripts/validate_jiangxi_copper.py",
              "python -X utf8 scripts/fundamental_valuation.py --config outputs/2026-10-24-江西铜业估值验证/02-工作底稿/估值/assumptions.json --output outputs/2026-10-24-江西铜业估值验证/02-工作底稿/估值/result.json --require-reviewed",
              "python -m unittest discover -s tests -v", "```", "",
              "第二条命令预期退出码3：诊断结果仍留档，但经济审核未通过。这个状态是验收发现，不能为了退出码0手动改成reviewed。",
              "", "## 10. 补数与正式放行条件", "",
              "|缺口|已试路径与限制|具体补数渠道与条件|补齐后动作|", "|---|---|---|---|",
              "|工业/贸易/财务公司现金流及抵销|两地年报有部分存贷款与子公司概要，无完整抵销表|公司IR、财务说明会/专项披露；非公开管理账需公司授权|重建分部FCFF，财务公司单独股权估值|",
              "|维护、扩张及矿山储量接续资本开支|年报提供总购建现金、项目建设信息，不能推出永续维护额|IR资本开支计划、矿山技改与储量披露|重跑预测期与终值，有限矿山优先寿命期模型|",
              "|保证金、贸易净营运资金与套保结算|年报可核规模，不能证明未来完全收回或不再投入|公司季度披露、IR周转/套保说明|联动金属价格与资金占用，避免两次加回|",
              "|富余现金、金融负债和投资/少数股东公允价值|已核受限资金、债务注释与FQM报价，未完成市场价值/税费鉴证|公司质押/金融附注、恒邦年报和交易所行情、税务说明|重做逐项权益调整和敏感性|",
              "|历史行情、长周期价格序列与资本成本校准|妙想返回历史价与国债利率；汇率已核央行，其他未完成独立原始行情匹配|上交所、港交所、上期所、中债；Wind/Choice导出可补，权限费用需询价|核对A/H市值、周期分档、beta及WACC|",
              "|若需现时估值|本次冻结2025年末，不混入2026中报|2026中报、收购/融资公告、同日行情|建立新基准日完整版本，不只换股价|",
              "", "到此流程已经跑通，且明确识别了未放行的原因。下一次应优先补工业与金融业务拆分证据；在此之前增加更多DCF情景不会使估值更可信。"]
    report="\n".join(lines)+"\n"
    (deliver/"江西铜业-年报估值验证.md").write_text(report,encoding="utf-8")
    (work/"模型自检.md").write_text("# 模型自检\n\n"+json.dumps(audit["checks"],ensure_ascii=False,indent=2)+"\n\n经济审核：blocked。详见交付稿第10节；禁止将数值测试通过改写成估值通过。\n",encoding="utf-8")
    (work/"估值参照带.md").write_text("# 条件估值诊断\n\n本次经济审核未通过，不放行可用参照带。数值结果见估值/result.json，假设见估值/assumptions.json，独立复算见估值/audit.json。\n\n完整推导、样本区间、假设和局限见 ../03-交付物/江西铜业-年报估值验证.md。\n",encoding="utf-8")
    gap_start=report.index("## 10.")
    (work/"数据缺口与补数清单.md").write_text(report[gap_start:],encoding="utf-8")
    (work/"取数台账.md").write_text("# 取数台账\n\n妙想可用，首轮财务数据为旧重述口径，改用A/H年报原件覆盖。原件PDF下载已成功，文件哈希见原件校验.json。提取文本只作检索，主表扫描已目视核对。\n\n行情和国债利率来自妙想/Choice，历史行情未获交易所独立原始下载，保留诊断级；人民币港元汇率已核人民银行。其他未取到项与补数渠道见数据缺口与补数清单.md。\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"outputs/2026-10-24-江西铜业估值验证")
    args=parser.parse_args()
    generate(args.output)
