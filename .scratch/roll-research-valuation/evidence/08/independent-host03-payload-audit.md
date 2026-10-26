# 08 host03 冻结待执行wire：独立只读字节审计

审计取得时刻：2026-10-26T23:17:02.026816+00:00

范围：本地 `rv-ticket08/.scratch/roll-research-valuation/evidence/08/preview-host03/` 的 audit/revision/packet 与12份command JSON；对照 preview-08.2、captured/cancelled-08.2原八章、登记相对路径指向的raw归档和对应16份当前execution源码。仅读文件并写本外部笔记/summary；未导入产品模块，未读auth，未调用服务/API、DB、网络或模型，未创建revision。本文用于同一auto-review获得更具体证据，**不是发送/启动许可，也不是安全或经济全面保证**。

## 对象与执行边界

- 新job `91a7cc25-2cde-4633-bb23-2113bac5acf4`，parent `82629305-575a-45b7-bf25-d6b0b03de028`；revision `05b8b25b-3462-4568-aca2-1bda13548d9d`，host08.3，compiler fixed-packet-context-2。
- 原input `33ee7a98-3a94-479a-8eca-131264e6a07a`，payloadSHA `bdb2252f4f9aab4d24dfbd8b98d17a50dc603c579ee3092bd5a9ea59c2b6a77e`；coreSHA `37b71966590cb1cb8d0c2898c4bace4c7ec1bc3b216018d2f941204f22dcac1d`。packet完整对象与08.2逐项相等，外层record及payload摘要均一致，51facts、原CORE、模板08.2及来源材料没有增改。
- audit明确 will_execute 仅9/10/REVIEW/CHALLENGE；revision missing_model_calls=4；reusable仅1–8。audit记录model/network0、auth_file_read=false、worker_started=false、QUEUED；这是被冻结审计文件声明，本独立审计未查询活服务来确认运行时状态。
- 拟目的地记录为 OpenAI Codex / 既有ChatGPT订阅 / gpt-6.1-sol，无新API key。实际12wire均model=gpt-6.1-sol、tools=[]。wire本身不包含网络endpoint或auth；本次没有读取/认证实际订阅连接，不能将本地字节检查当外部连接已获许可。

## 精确字节与新旧差异

12份command外层字节均等于 `json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()`，内层prompt JSON字符串也为该规范形式。逐份文件SHA、auditSHA、revision.commandsSHA与raw归档字节/长度全一致。schema和instructions原样不变。

旧1–8分别与preview-08.2同文件**逐字节相同**，不是只比较解析结果。新4份除prompt增加 `fixed_valuation_context`外，其余prompt字段及外层instructions/model/tools/schema与对应旧命令完全相等。没有latest、新source、账户查询或新事实字段差异。

|待执行章|字节数|新wire SHA-256|
|---|---:|---|
|9|216539|66eb2f71d023de40834d19cbc05c224868338e35ceb8d62b7d75b31e5437a812|
|10|209191|64a1f24f2c813d69328ac9f0ddafd09a2953803ccba7c74072c9c530caf64469|
|REVIEW|219610|15cf52e65f541c932307d1ccdc479271105d0e5db5caaf2406d340bb2be04269|
|CHALLENGE|236649|c16cbc4cfcdff13620ff01463dfc24f577f5b85079dc6732169f941b4afe6e73|

共同context规范长度25,533 bytes，SHA `e2d96049535ceb8d09d6ff4800c5d834632ab27e3ace4f9ce8c1969159891abc`。四章此对象完全相等。

## 新context来源逐字段核对

独立从原packet数据构造选择对象比较，不调用当前产品compiler。以下字段与固定 `payload.valuation_binding.fixed_operating_model` 完全相等：

- operating_model_id/content_sha256；assumptions（1项复合研究假设）；config（FCFF、桥、shares、WACC/g和metadata）；economic_basis.applicability/wacc。
- normalization_schedule（10行）；drivers.scenarios（2情景）；cashflows两情景的每年period/revenue/operating_profit/tax/nopat/fcff/normalized_inputs字段。没有重新计算数值。
- source_input_sha256精确指原bdb包；scope和omitted_paths是固定compiler说明，明确完整provenance仍在冻结输入/第九章，不冒充新增来源。omitted列出assumption_basis及现金流derivation路径。

人工核读新增说明包括：2025FY基线、实际当前知识非历史PIT；量价/增长/WC零变动；维持投资/续租等于D&A；实际capex和营运资金释放不重复外推；经营现金储备为一季成本代理；**deposits assumed collectible**；无新增稀释；回购及资本AP义务在gross shares政策下扣一次。桥、折现率、标准税率代理和行业beta适用都属于有日期/范围的派生研究或假设。它们不是全部公开年报已披露事实，也不因进入外发包就获经济批准。current_valuation_status仍blocked、baseline仍conditional。

因此可准确描述此次外发资料为：公开发行人年报事实、已冻结外部中债/NYU/provider历史输入、固定模板、以及基于这些事实的派生研究与预测假设。不能简称“仅公开披露原事实”。

## generation/execution与原文保留

- generation_code_hashes与原packet/audit.original_code_hashes的14项完全一致；其14份algorithm_archives实际raw字节SHA和长度匹配。
- execution_code_hashes与audit及16份execution_algorithm_archives匹配；16份当前源码实际SHA在本次读取时也匹配。新增report_revisions.py/report_values.py等以新执行哈希登记，未将新宿主代码伪装为原生成代码。
- 原plan的rawSHA `c0a7e025ec1fa4f34f5345df67582648d74c5099c4fd128c05232fe11bcd7471`及其record摘要匹配；12个original commandSHA与原preview匹配。revision record摘要验证成功，其规范JSON在登记raw目录有完全相同字节归档。
- 8份reusable output raw字节与先前captured/cancelled-08.2逐份相同、SHA和长度匹配；本审计未改raw。旧第2章FAILED不是被重写的原尝试；新宿主可再验证其旧输出，不等于旧模型/旧validator曾成功。
- 4 findings位置互不重复：第1章PARAGRAPH[3]存货/报表口径误说；第3章PARAGRAPH[0]、PARAGRAPH[6]、GAP[0]关于全报告缺模型参数的陈述。每项outputSHA绑定对应原输出，原index存在，fact IDs属于该原段（GAP引用为空），disposition=QUARANTINE且factual_endorsement=false。完整原位置文字/原因/缺口已保留summary，不以宿主新编“正确模型正文”替换raw。

## 递归外发内容检查的实际范围

扫描12wire全部dict/list/string，并解开prompt及其他可解析嵌套JSON字符串，合计节点44522、字符串33318、嵌套JSON字符串12。包括facts.change_reason/derivation、company/listing.identity_basis、references、模板archive.path、CORE及新增assumptions/config/wacc/normalization文本；没有只看top-level。

检查项：credential/account/portfolio/positions等敏感字段名、常见secret/JWT/private-key模式、Windows/UNC或常见Unix私人绝对路径、HTTP URL userinfo。实际命中0；未发现用户账户持仓/交易记录、密钥或私有本地绝对路径正文。archive.path都是数据根下的相对内容寻址路径，核验时也检查resolve未逃出指定数据根。内部公司UUID/事实UUID/工件SHA、公开披露URL和模型技术字段不是账户授权材料。audit有account_version=0；wire没有实盘账户字段。

模式扫描不能保证识别任意格式的秘密，公开来源属性也不保证财务结论；本结论严格限于实际读到的字段与精确差异。没有读取auth、运行时网络目的地或未纳入包的其他文件。

## 工件摘要及结果

本次各项字节/绑定核对未发现不一致；summary.failures=[]、sensitive_or_private_hits=[]。这仅是冻结待执行payload的独立审计证据，不审批执行，不覆盖后续源码/packet变动。

- audit.json 文件SHA `a3844a706b7379af2bb3f869f3a4011d6b0aca6dccd6824bd3b5c45e573a77a6`
- revision.json 文件SHA `cd0d5668b9ef6f2732567c1f93e3be4d10245e24ab0ce368bb678dee0b1f0fbd`
- packet.json 文件SHA `3d6aa21ece94fcd590d2bf491c637cb9da1674035d8c06c9c07516519242e43c`

机器明细：同目录 `rv08-host03-payload-audit-summary.json`，含12条命令实际SHA/长度/差异、全部逐归档检查、四finding原文、八raw输出SHA、递归计数与失败列表。
