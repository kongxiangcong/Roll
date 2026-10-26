# 16 接手复核与评测纠正（partial）

2026-10-18，Asia/Shanghai。起始分支`codex/roll-capability-expansion`，HEAD `b4fb4407a9e6e91876f314ac9ad5bde7d0e7f35e`；既有379条dirty/untracked受保护。旧handoff记录的7b6940c为历史，现场以本次HEAD为准。

本轮推进16，未完成16，未推进有依赖的17/18/22/26。完整阅读根AGENTS、三份agents约定、spec/ticket-plan/execution-status/handoff、16 issue/evidence及领域词汇和相关ADR后动手。

## 交付与纠正

- 公开元数据核查新增checkpoint-discovery-02—06计划、回执及原件；查到9个FinBERT2同名仓库并逐类排除。官方base/large是MLM；Riverise微调是环境主题且许可不明。未取得可验收的FinBERT2情绪checkpoint，未下载不适用权重。
- 查实可供选择的中文金融BERT替代：yiyanghkust/finbert-tone-chinese，Apache-2.0，固定版本e91b1a3a…，0中性/1正向/2负向，约409MB；不是FinBERT2。等待用户对替代路线的选择，不把当前受限组件追认成合格。
- 修正指标计算：`sentiment_evaluation.py`把拒判计作真实类别FN，把中性/不相关误判计作目标类别FP；零支持返回null。`correct_evaluation.py`只读旧混淆、输出新报告，不重新调参或修改旧推理。新增指标行为测试。
- reference固定纠正报告摘要、口径、支持/混淆/每类指标和时间隔离缺口；新分类通过现有API与持久化保存该版本。页面解释新口径；旧保存包仍可重放，明确旧口径不作验收依据。
- 浏览器截图路径可由环境变量指定；所有新截图/结果留在本目录，未覆盖原票证据。

## 真实与METHOD

真实资源核查：宿主22次请求/126160B，零重试；GitHub403、README404均原样留存，不能写成成功。此前沙箱8次ProxyError/0B记录单列。

真实本地运行：既有Erlangshen权重，对已归档10条真实新闻的新副本作修改前与修改后两次新分类（不同幂等键）。最终`real-sentiment-corrected.json`及`runtime-corrected.json`：COMPLETE / REAL_LOCAL_CLASSIFICATION，POSITIVE2、ABSTAIN_FUND_FLOW3、ABSTAIN_NO_DIRECTIONAL_CUE5，覆盖0.2，网络0，账户0→0；旧包查询对象完全不变。新API包内evaluation与最终reference逐项相等。此结果不是新候选评测，也不证明分类正确或授予资格。

METHOD：API注入worker测试正负分类/拒判/幂等/截止/重启/账户不变，新闻用固定响应。新增纯指标测试验证拒判FN、跨类FP、缺失支持和错误输入；不把这些测试当真实模型效果。

纠正的150条旧真实语料诊断（非独立代理标签）：

| 集合 | 二类macro-F1 | 正向召回 | 负向召回 |
| --- | --- | --- | --- |
| 设计120 | 0.622680 | 41/45=0.911111 | 6/24=0.250 |
| 留出30 | 0.263158 | 5/8=0.625 | 0/6=0.000 |
| 合并150 | 0.563218 | 46/53=0.867925 | 6/30=0.200 |

合并中性支持18、直接分类召回0、拒判12；不相关支持49、直接分类召回0、拒判44。二分类模型不输出中性/不相关概率。总拒判81/150=0.540，p95沿用旧真实推理0.3687s，门槛完全未改且未通过。完整各类混淆/支持见`corrected-evaluation.json`。

`corpus-audit.json`确认design日期08-09—10-16与holdout09-08—09-15交叠；holdout无中性，精确hash组不等于语义事件组。不得继续把旧120/30称作事件/时间隔离的未见评测。

## 验证

- 基线：`pytest-host.log`，5 passed/35.47s；`build.log`通过；`browser.log` Chrome 1 passed/21.5s。
- 修改后：`pytest-corrected-short.log`，10 passed/37.93s；`build-corrected.log` TypeScript/Vite通过（原有>500kB chunk提示保留）；`browser-corrected.log` Chrome 1 passed/12.7s，390px无横向溢出，指标0.200及新口径可见，无分类POST。截图`mobile-corrected.png`已视觉核查。
- 失败记录：`pytest.log`首次沙箱无输出后中止；`pytest-corrected.log` 5 failed/5 passed，深层临时文件超过Windows路径限制；同一组测试换新短basetemp `.scratch/r16cg`通过。
- 双轴审查：`spec-review.md`、`standards-review.md`；`final-code-versions.json`记录最终产品/测试指纹，`inherited-code-verification.json`记录动手前继承核对。

## 仍缺与下一票

16继续partial/needs-info。需要合适checkpoint路线（用户选择中文FinBERT替代评估，或另行批准FinBERT2有界微调方案），以及在新候选推理前冻结的语义事件互斥/时间互斥评测、各类支持和拒判门槛。新候选不自动替换现有reference；失败仍研究受限。16真实完成后再17→18/22→26，05/06/08/07/23—25原外部门槛不变。未推送、未建PR、未建立真实前向起点、未授资金或能力。
