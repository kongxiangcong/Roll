# 08.4 host04 冻结工件：最后小型只读核对

读取取得时刻：2026-10-27T00:12:09.048278+00:00

范围：rv-ticket08 的 evidence/08/preview-host04/{audit,revision,packet,12command}.json、host-revision04.json；对照host03冻结文件、以前独立payload审计summary、原父任务最终回执、对应内容寻址raw与17份本地execution源码。没有导入/调用产品方法，没有读取DB/auth，没有启动服务、模型、网络，没有修改实现或原工件。仅写本外部笔记及 `rv08-host04-final-audit-summary.json`。

## 核对结果

142项具体文件/摘要/字段关系核对无不一致（summary.failures=[]）。范围仅限所列实际文件，不签整票审核、经济批准或启动许可。根据父任务提供的状态，人类对四个请求的明确授权仍待答复；本审计不将此前auto-review拒绝替换为许可。

- job `416d3883-f0a6-4454-a40d-3104c018ba0f`；revision `6008a00c-d3d9-4ed4-ad19-570430712ef2`，host08.4。
- previous_host_revision_id明确为 `05b8b25b-3462-4568-aca2-1bda13548d9d`；对应旧job `91a7cc25-2cde-4633-bb23-2113bac5acf4`。host-revision04.json记录其已取消、旧immutable记录不变；**本次只确认该本地回执声明，未读活DB独立确认当前状态**。旧03的audit/revision文件SHA与本子任务先前审计summary一致，旧revision规范raw仍保留。
- 原生成parent仍是 `82629305-575a-45b7-bf25-d6b0b03de028`，input仍 `33ee7a98-3a94-479a-8eca-131264e6a07a`，payloadSHA仍 `bdb2252f4f9aab4d24dfbd8b98d17a50dc603c579ee3092bd5a9ea59c2b6a77e`；packet.json与host03**逐字节相同**，没有重写原bdb输入。
- 14项generation map原样保留；17项execution map与audit、revision、host-revision04回执一致。17份当前实际源码及execution_algorithm_archives的SHA/长度逐项匹配，包括新增 `research/company/report_coverage.py`；所有raw相对路径resolve均在指定数据根内。没有扩大结构/算法审阅。

## 外发wire与host03完全相同

12份命令逐字节与host03相同；外层规范JSON、内层prompt规范JSON、SHA、raw归档长度/字节均匹配。四条findings与八项reusable也与host03相同。will_execute仍只9/10/REVIEW/CHALLENGE，missing_model_calls=4；全部model=gpt-6.1-sol、tools=[]。

|待执行章|字节数|SHA-256（与host03同）|
|---|---:|---|
|9|216539|66eb2f71d023de40834d19cbc05c224868338e35ceb8d62b7d75b31e5437a812|
|10|209191|64a1f24f2c813d69328ac9f0ddafd09a2953803ccba7c74072c9c530caf64469|
|REVIEW|219610|15cf52e65f541c932307d1ccdc479271105d0e5db5caaf2406d340bb2be04269|
|CHALLENGE|236649|c16cbc4cfcdff13620ff01463dfc24f577f5b85079dc6732169f941b4afe6e73|

因此复用 `rv08-host03-payload-audit.md`/summary 的逐字段context与递归敏感字段审计，有**新wire逐字相等**作为依据，未把旧扫描结论泛化到其他未查文件。该旧审计检查44,522节点、33,318字符串（含解包prompt），未发现密钥、私人绝对路径或账户持仓字段；新增context仍包含研究预测与假设，不是全发行人披露事实。

本地sourcebook没有加入任何外发prompt：四新wire无source_coverage/ledger_markdown/sourcebook新增字段，原有fixed_valuation_context仍与原bdb选择相同。目的地只由audit声明既有ChatGPT订阅CODEX，本次未读取auth或认证实际远端连接。

## 本地sourcebook、明确父链与最终check

`revision.source_coverage`是本地记录；content_sha256 `719dd4882cabecca29712fca38945d43e9f4bf88d82e5621706e4ee479515c22`，规范18,303 bytes；record摘要验证通过。它**作为整个revision的一部分归档**，并非我观察到单独sourcebook_archive descriptor。完整revision规范rawSHA为 `c943f2edd0f2d86c94d34eb3a696f77f0a3698d580b0d38444e272285d1a6371`，实际raw字节与revision规范对象完全一致。

sourcebook.current_job_id=`82629305-575a-45b7-bf25-d6b0b03de028`，即原packet owner；lineage明确 `[82629305…, d60722dc-5dc3-4dcf-8938-e8e9d7424a77]`。这是本地复核原输入来源链，不表示新416d任务执行了历史取数。

- packet.acquisition仍NOT_REQUESTED/network=false，原REUSE语义完整保留。ledger明确“本次未发起该类别网络检查”，未将历史获取写为本次新取。
- 本体类两条attempt均relation=EXPLICIT_PARENT_HISTORY、job_id=d60722dc…，包含完整verified_check记录且各自record hash通过。strip新增job/relation/verified_check后，与captured/failed-08.1/job.json原最终receipt完全一致。
- check `3cf4b796-2629-4490-8960-8a9a2638b2de`对应2023原件SHA `10501f7a2b295ae00fec12e81de456bb291b259d865c9589f004807ba151ed13`；实际取得2026-10-26T21:52:51.080701Z。
- check `f6307daa-8e6c-4f5a-adb6-149f33d56f2b`对应2022更新原件SHA `609b60a5bd4d83c76dd9bc204f9d0a65509de107362b5e71bb4ab78f58fe3e0f`；实际取得21:52:53.825939Z。两条最终status=SUCCESS、主体/材料/完成scope一致，实际rawSHA/长度匹配。
- 原material.upstream的中间FAILED快照没有被改写；ledger明确该中间状态与绑定的最终成功回执分开，不静默覆盖旧记录。sourcebook本体state=ACQUIRED描述历史原件存在，不能解释为本次新取或全部分析完成。

## 宏观角色与真实附录缺口

本地fact_source_roles将4条business=EXTERNAL_VALUATION_INPUT（中债收益率、NYU ERP、NYU beta、近似历史市值）明确标为EXTERNAL_VALUATION_INPUT；没有改写旧packet默认reference角色或将这些来源称发行人/监管结论。估值序列state=REFERENCED、4材料、0本次attempt，ledger明确“不是发行人披露，也不等于完整历史价格/估值序列”。行业时序/产业链/同业/研报/官方监管均NOT_CHECKED、0attempt，不虚构已查渠道或公司不存在风险。

真实A/B/C仍全部UNKNOWN、appendix_rows为空；没有从原件标题、研发费用、期末股数猜沿革/股东/产能人员表。本地支持未来有源事实推进，不意味着当前真实露露case达到完整覆盖。quote_proofs为空，不声称存在本次逐字运营quote核验。

## 文件摘要与当前未核范围

- audit.json SHA `a66986cf51eea6f60dfc9055c215e12887c4fdd864b917f1723febaa31353c5f`
- revision.json SHA `4009a8ff1201ce270fb69e0a29980cde3cd097a78d17da78c80ea7351d1524c4`
- packet.json SHA `3d6aa21ece94fcd590d2bf491c637cb9da1674035d8c06c9c07516519242e43c`

本次读取时未见queued-restore04.json/revalidated-restore04.json，故没有把host03恢复记录当作新17源码/sourcebook的恢复证明；后续若出现可另按实际文件核对。未检查活服务/DB/订阅、未重新审阅整个新覆盖算法、未启动四模型请求。原03敏感字段结论只因12wire字节一致而复用。
