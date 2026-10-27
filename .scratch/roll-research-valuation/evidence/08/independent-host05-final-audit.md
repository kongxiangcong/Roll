# 08.5 host05 最终冻结工件：只读artifact审计

取得时刻：2026-10-27T01:34:57.372225+00:00

仅核对rv-ticket08 evidence/08/preview-host05冻结文件及其raw、host-revision05回执、offline-sections/preview05、queued-restore05与指定恢复raw。未调用产品方法、未读取DB/auth、未执行模型/网络/估值、未改实现或原工件。本文不是启动许可/全面财务背书；父任务告知人类对四个请求的明确授权仍未答复，本子任务不推断批准。

## 固定输入、源码与wire

- 新job `cf414530-5dee-45d3-af28-0e7e3f9321ae`，revision `aed147d2-5b5b-409c-80c5-872e88c75828`，host08.5。
- previous_host_revision_id精确指host04 `6008a00c-d3d9-4ed4-ad19-570430712ef2`。host-revision05.json明确声明旧416d任务已取消、旧immutable记录不变；本次没有活DB独立核实其状态。新任务仍以原82629305任务、原bdb input为生成来源。
- packet.json与host04逐字节相同，文件SHA `3d6aa21ece94fcd590d2bf491c637cb9da1674035d8c06c9c07516519242e43c`；payloadSHA仍 `bdb2252f4f9aab4d24dfbd8b98d17a50dc603c579ee3092bd5a9ea59c2b6a77e`，原14项generation map不变。
- 18项execution map与audit/revision/启动回执一致；18份当前实际源码与对应raw archives SHA/长度逐项匹配，包含新report_summary.py。新旧revision的规范raw均保留且字节匹配。没有扩大新模块架构审查。
- 12wire与host04逐字节相同，canonical外层/inner prompt、audit SHA、revision SHA、raw字节/长度均匹配；model均gpt-6.1-sol、tools=[]。八复用输出不重新请求；仅下列四条will_execute，missing_model_calls=4。

|待执行章|字节|SHA-256（同03/04）|
|---|---:|---|
|9|216539|66eb2f71d023de40834d19cbc05c224868338e35ceb8d62b7d75b31e5437a812|
|10|209191|64a1f24f2c813d69328ac9f0ddafd09a2953803ccba7c74072c9c530caf64469|
|REVIEW|219610|15cf52e65f541c932307d1ccdc479271105d0e5db5caaf2406d340bb2be04269|
|CHALLENGE|236649|c16cbc4cfcdff13620ff01463dfc24f577f5b85079dc6732169f941b4afe6e73|

因此此前host03递归secret/private-path/account扫描可在**同字节wire**范围复用；没有为新增本地数据自动出具“全部安全”的保证。原预测上下文仍含研究派生与假设，不能改称全部发行人披露事实。

## 本地fixed_result_context是原结果，不是latest/重算

新增context只在revision/presentation使用，12外发prompt均没有fixed_result_context、source_coverage、observations、part_conclusions、ledger_markdown新增字段。

固定valuation_id `6da4d05b-e2fc-4e99-b57d-f37f12e45109`；valuation_sha `6b121d9af9b12bfe773374ba2133e20299b482417d76b5383ac9eef46ce01bcd`；result_archive SHA `44d7ca910f02f3844f9151f15483f8c6b28541c110907f02d8912de98f757366`、7884 bytes。三者与原packet.valuation_binding.fixed_calculation_reference精确一致。

实际归档是含valuation_id/input_sha256/result/algorithm的规范包装对象。独立核对包装.result与context.result完全相等，包装input_sha与固定计算引用相等，并用包装+result_archive重建原估值record摘要，得到上述6b121d9a… SHA一致。不是直接把整个包装误当result，也没有执行计算器或读latest。诊断结果中的基准条件数值进入本地上下文不代表当前可用价被批准。

## 31条本地摘要均能回到原段，隔离4处未回流

offline-sections05包含八个新host验证section，均record摘要、job/revision/input、source_section_version_id、原run、output_archive关系一致；原八输出raw仍逐字节等captured/cancelled-08.2。

31条observations逐条验证：output_sha指对应原输出；paragraph_index在原候选内；fact_version_ids与原段列表完全相同且属于51facts；摘要为原段第一非标题/表格行的第一句，数值仅用原事实+已有单位声明展开，没有新算术。31条逐字摘要与独立按原数据展开的结果相同。每条均保留REFERENCE_VALIDATED_CANDIDATE_NOT_INDEPENDENT_FACT_ENDORSEMENT。

原隔离4项与host04记录相同：第1章PARAGRAPH[3]，第3章PARAGRAPH[0]/PARAGRAPH[6]/GAP[0]，输出SHA/索引及此前已核引用不变、QUARANTINE且不作事实背书。三处PARAGRAPH均不在新observations内；原第3章GAP[0]仍以隔离工件保留，没有改旧raw。旧FAILED尝试记录不能因新host section COMPLETE被解释为旧validator通过；本次只核本地工件，没有改旧尝试。

## sourcebook真实边界未升级

新source_coverage除created_at/content_sha外与host04完全相同：原本体最终check引用与明确parent历史链保留；input.acquisition仍NOT_REQUESTED/network=false；4个宏观/估值输入的本地external角色不变。行业/产业链/peer/研报/监管的NOT_CHECKED未变成已查，估值资料仅REFERENCED，不冒充完整估值序列。A/B/C全部UNKNOWN、原空明细不凭摘要补数。旧bdb引用默认角色未被修改；本地overlay没有外发。

## 恢复与预览实际已落地范围

queued-restore05.json已存在：job/revision指新05、status QUEUED、records_equal=true、algorithm_archives_verified=32（14generation+18execution）、commands_verified=12。除核回执，本次还逐份读取指定恢复目标的18 execution raw及12 command raw，SHA/长度均匹配。没有读取恢复DB或调用restore，也没有将此视为运行授权。

offline-preview05.md/json与offline-sections05.json已落地；预览明确published=false/report_id=null、八章、94参考规则、quality PARTIAL。四缺章仍待生成。**预览摘要的哈希口径有一处需明确保留：**

- 实际Markdown文件含1034个CRLF，raw-file SHA `cc3bfcbe5716ec009d9b163840473266cb2f57005a174147e175a3f023257cb7`。
- offline-preview05.json.markdown_sha256=`41ef286a114974b8968dbb0ca4f9d2a8a4c810d03c7689ac5ab35e1bf0911e57`，匹配读取文本后LF规范化UTF-8的SHA，**不是raw文件SHA**。

两者差异由行尾口径解释，原文本内容一致；本审计同时保留两种摘要，不润色掉差异。它不涉及外发wire、固定估值数值或新模型请求，也不需要改变冻结模型命令才能澄清。

## 工件与结论边界

本次229项具体核对未发现其他不一致（机器summary.failures=[]；preview检查明确按其LF文本哈希口径）。唯一补充说明为上述离线Markdown raw/text摘要差异。不是宣称所有财务语句已被独立事实核实或所有94门已通过。

- audit.json SHA `6f4bd830b632a533ddab3b6b5e01acd4c892916d2e882e336b9486da01fcd632`
- revision.json SHA `994d5c37b150a2b3fb171bcfa69040b1e78c1611a17a0d83bfcf9e87930eef89`
- 机器明细同目录 `rv08-host05-final-audit-summary.json`，包含18源/归档、12wire、31原段绑定、4隔离及恢复/预览回执。
