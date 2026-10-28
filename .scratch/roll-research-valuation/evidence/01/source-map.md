# 参考能力与许可逐文件映射

检查日：2026-10-26。来源为当时可读的本地 `deep-dive-research` 文件；快照[manifest](../../../../docs/reference/deep-dive-research/20261026/manifest.json)逐字节SHA-256是版本依据。

`git -C D:/dsh-proj/deep-dive-research rev-parse HEAD`和`status --short`均实际返回Permission denied，未核实Git提交/分支/dirty状态，不推断它是某个提交。原始绝对路径仅是审计出处，运行和复现仅用仓库内快照。

LICENSE明确代码、skill及references/scripts/assets为MIT（da-damu 2026）；配套书籍为CC BY-NC 4.0。本次不复制书籍。计算器另改编Sirius MIT上游，原MIT全文及THIRD_PARTY_NOTICES均随快照保留。后续实际改编记录自己的差异和文件hash，不能把本票映射当成第三方库的许可结论。

冻结目录是供实施审计的参考快照，不注册为生产Agent指令；不复制SKILL.md、不继承开发技能权限，不增加评级、Kelly仓位、交易、蒙特卡洛/EVA执行器。

| 源文件（快照根目录内） | 字节数 | SHA-256 | 处置 | 进入Roll的位置/边界 |
| --- | ---: | --- | --- | --- |
| references/00-铁律与偏好.md | 60605 | `e70f979eed3ea3b2addf13dc48821527b2cdbd6d1465a7017f979d04993adb7f` | 适配 | 08：数据/报告铁律、免责声明、来源/字数/文体规则；不继承技能权限 |
| references/01-公司类型判定与模块装配.md | 19808 | `1645853e07a15043e96ebadc5ed20d99456ac49f0a7ae6ea89435282a541488a` | 适配 | 05/08：公司类型和观察视角；不新增多角色代理 |
| references/02-问题链与报告结构.md | 31603 | `176425bcf992f5b186b50b5b45a0ee894526c7aa920dcdad7b3cf1879d6453fb` | 适配 | 08：完整速览/四部分十节/附录A—I，逐项映射见报告模板映射 |
| references/03-数据源地图.md | 35992 | `55064344693c7924fe07c7821e770118f9ad345af23166c47408c9437b61abe1` | 仅参考 | 02：使用已配置来源；不照搬全部来源或安装新服务 |
| references/04-排雷清单.md | 11972 | `84f962cff9e48ddaaf81f8c8b8fc736da34b9efbd3e3a0296f3a4fb9e463e104` | 适配 | 08：A28/HK38排雷逐项检查，未知留缺口 |
| references/05-估值模型库.md | 27993 | `43a52ef41952edc40e842d2720de458fb8cae2a1e728b58f610b16b4b34fc863` | 仅参考 | 04/05：方法适用性与周期口径；不自动增加行业执行器 |
| references/06-成稿与PDF交付.md | 35072 | `52ee35a3d71f1ed3585997136623429af5b96807e1e55e6e76018af9d6891fc0` | 适配 | 09：Markdown/PDF版式与视觉核验；渲染技术按Roll环境选择 |
| references/07-市场规模测算与分行业估值.md | 13025 | `8c0be63c3baca4ba774cd4e1a9e962f792c5c221186ed814df42f20e2cc7d415` | 仅参考 | 05/08：行业空间/估值方法；无新行业执行器 |
| references/08-产业周期与择时.md | 39939 | `e64bb86cfcfda0333d5a6636ea0d7c15fc243878e1dbaf57d19a0e6e04acdac4` | 仅参考 | 05/08：周期分型/见顶与中继，不以短期归因取代事实 |
| references/09-行业专家视角.md | 23946 | `e26e1697fb24a7608011ba7679f566c4a5c9df520215ee1ee15db5543ca9eaa4` | 仅参考 | 05/08：行业观察视角，单模型候选而非多角色辩论 |
| references/10-投资人视角复核.md | 10150 | `aea40c1bba8ab44cf578715464bdc38d484f1ce59ada2ed3a20a6d0f50895558` | 适配 | 08：有据复核底稿，不等于独立人工审核或资格 |
| references/11-反向质疑与遗漏排查.md | 26592 | `7c0acfa7925edc7a7803a25e40bf2e9c27251b75ce89b91e16f732aa9b4f0f50` | 适配 | 08：反证/遗漏/榜单核查/未答问题，不凑证据 |
| references/12-模型自检与交叉验证.md | 16844 | `df8636cadef85c8a192f770ea901d75aab7b086ca4ccca606d65bb3953672c54` | 适配 | 05/08：口径对照外推/单位数/模型自检 |
| references/13-历史股价复盘.md | 22616 | `f8e7069ce8ffaaa96ec37d3824321abe5b33d7818415227dcb06a323c2277c10` | 适配 | 08：中长线股价复盘，历史时点真实性仍须核验 |
| references/14-反AI文稿.md | 29966 | `84fe565c2f0d30aa9672727a9f40a3e54ab8c175bd3c46fab690e9b6ed768fcd` | 仅参考 | 08：报告文体提示，不能代替研究质量 |
| references/15-基本面估值计算与接入.md | 7182 | `915b618cf2b65059117ab86b775d9461849ba47b747541d6a9ea782fd4b33ac4` | 适配 | 04/05：FCFF、反向DCF、EPV与经济审核边界 |
| scripts/fundamental_valuation.py | 13550 | `64e56fc61487e3e61568f8580d9dfaf7546e5ff7c06da6e138512c1bc02aa1d8` | 适配 | 04：经测试后内置算法；补足证据/币种/AH输入验证，代码不验证经济事实 |
| scripts/check_gates.py | 59614 | `7434fedc06fdc94b39c9f17b38887a07592f2a7bdfa046c989471d898d1fadcb` | 适配 | 08：94处检查调用逐项映射；路径适配，失败允许PARTIAL但不冒充FULL |
| scripts/md_to_pdf.py | 38086 | `02763189dc83c982d58068493727025ca6bbeb5d6684a607d3086556579eb0f1` | 仅参考 | 09：原脚本允许HTML/文件处理，不直接作为不可信材料渲染器；另做清理与受控资源 |
| scripts/cycle_valuation.py | 27055 | `a529b3e02bb9ecdbefbaf35520133ad2e7b3a31089025cb06b9dca71ddace8ec` | 仅参考 | 05/08：周期算法边界；本期不新增周期专用执行器要求 |
| scripts/validate_jiangxi_copper.py | 29227 | `bafae73fda326d60b001f3b768db1793f7eb0115e4e40b7acd113ca25272457b` | 适配 | 05/12：真实案例算法核查及blocked缺口；不是当前估值或严格PIT |
| tests/test_fundamental_valuation.py | 5954 | `0d442a2d7de957aca59b4c1f6f2ab441cec53d96c49ead97bbfda20f38aaec79` | 适配 | 04：复用算式回归，补Roll公开计算边界验证；本票未运行 |
| examples/valuation-assumptions.json | 1179 | `ec1a536535639af3d5c85cd7a3c876784f439f39e10c20f004b814cc9065b036` | 仅参考 | 04：合成示例，不作为真实公司生产默认输入 |
| examples/jiangxi-copper-2025-facts.json | 6281 | `a5bffecf05f603814253347aef82aa7a116eb1d3679a9de297a1d466a922d730` | 适配 | 05/12：公开年报案例索引，原件需02实际归档及引用核查 |
| LICENSE | 3534 | `fd1f83ae6fba20b61e0626c99f49eeb4db3282d9f518c568e459d00e2542a6ca` | 直接复用 | 引用/改编代码和references时完整保留MIT声明；书籍CC BY-NC内容不复制 |
| equity-research-LICENSE.txt | 1084 | `dbf2c96de51d753ede9713ec2c399bdc82496b206feb90206a80302d40a89484` | 直接复用 | 保留Sirius MIT计算算法上游许可 |
| THIRD_PARTY_NOTICES.md | 1028 | `707412991755db7414f442436e56da947604cd79c959b84383849ae53b7c341a` | 直接复用 | 保留计算器上游出处/实际hash和改动说明；其Git版本亦未核实 |

27个实际文件已冻结。`scripts/check_gates.py`的每一处Runner.add检查对应[逐项清单](gate-rule-map.json)；原名称表达式、原级别、行号和Roll处置均保留。

本票不执行估值/模型或复制参考测试到生产测试目录。来源样例的合成/真实属性保留，真实资料的实际归档与时点核验归02；计算数值回归归04，经济审核归05。
