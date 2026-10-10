# 补录、声明与对账契约（05）

所有账户写入继续经过 `Ledger.prepare` 与唯一 SQLite `BEGIN IMMEDIATE` 确认链。草稿不改变资产；原始命令、CSV 文件、原事件、旧回执及 `account_versions` 只追加。05 不新增数据库迁移，已有 `user_version=2` 保持。

## 双时间与当前投影

事件 `effective_at` 是实际发生时间，`recorded_at` 是系统确认获知时间，回执保留本次原输入时点。每次确认按当前可知的实际时间重建完整投影，迟补买入会改变后续 FIFO 分摊，已发布旧版本不会重算。基线前事实无法可靠重建，保留为待核草稿。

`GET /api/account/as-of?known_by=<带时区时间>&effective_at=<带时区时间>` 先按系统知悉时间筛选，再按实际时间筛选。缺省为当前时间；版本表示所选知悉范围的确认版本，不意味着那个实际时点已有同号发布快照。`GET /api/account/versions/{version}` 查询原发布快照。当前 `effective_at` / `latest_effective_fact_at` 是所保留有效事实的最新实际时点；`latest_confirmed_input_at` 是最近确认输入的原发生时点；`system_known_at` 是最新系统获知时间。范围声明的截至时点另存 `confirmed_as_of`，不把声明时间冒称为现金事实时间。

初始现金事件按原实际时点固定每个已知券商资金字段的快照日期，未知字段日期为null；权限确认不更新冻结/可取资金日期。

晚补 11 点买入之后，已知的 13 点卖出仍留在当前投影，当前账户事实截至 13 点；11 点券商可用快照不会覆盖已知 13 点的快照。旧 `known_by` 返回原已知状态，新 `known_by` 可重建同一个实际历史时点的修订事实。完整 `GET /api/account/replay` 与当前已确认投影一致；查询时待核材料造成的状态由查询服务另行解释。

## 追加替代与冲正

`CORRECTION` 的 payload 精确为 `effective_at, source, record_id, target_event_id, reason, replacement`。target 指原事件或当前替代链末端，replacement 为同种原事实的完整 `{kind,payload}`；显式 null 为冲正。类型与 `record_id` / 关联 `target_record_id` 不改变，身份在投影局部规范化，原材料不改写。后继引用旧链末端会待核。原因、原根 ID、前一节点、回执和知悉时间公开在 `account.corrections`，当前可选关系由 `/api/account/correction-candidates` 返回。

支持实际成交、费用补充、04 当前资金/权益种类、权限事实、声明和对账。初始现金与初始持仓基线不能冲正；无法重建的早期差异通过有依据的分项对账记录说明。冲正应收之前必须处理关联结算，冲正买入之前须处理依赖卖出；不删除关联事实来强行成功。校验失败仍保留原草稿，确认不写任何事实。

04 的 `CASH_CORRECTION` 是对原金额的更正，不是另一次实际退款：重建时随原记录的有效时点应用，以保证后续合法部分结算按更正后应收/应付余额核对；原更正输入的实际时间和系统时间仍保留在原事件/回执。05 完整替代同样保留原材料，在所替代的实际时间重建。费用与 paid rights 仍使用既有费用分拆契约，金额更正不把实际支付重复计入费用或外部投入。

## 声明与用途检查

`ACCOUNT_DECLARATION` payload 为 `effective_at,source,record_id,scope,changes,basis`。scope 是 TRADES、ORDERS、CASH、EQUITY 的非空不重复列表；changes 为 NONE、UNRECORDED 或 EXTERNAL_ORDER_PENDING。声明不改变资金/数量/可卖，也不释放外部委托占用。

`POST /api/account/use-check` 接收 purpose 与 required_as_of；MARKET_OBSERVATION 不要求账户声明，ACCOUNT_ANALYSIS 要成交/现金/权益，NEW_RISK 要四项范围，REDUCTION 核对成交/委托/权益三个与数量相关范围。无变化声明必须覆盖本次所需截至时点，且知悉时间不早于最新资产事实确认。缺范围/截至时点为 STALE_DECLARATION；未补录/外部委托待结果为 UPDATE_PENDING；待核材料、未决对账、未知关键资金/可卖为 RECONCILE_REQUIRED；覆盖且已核对为 CONFIRMED_AS_OF。REDUCTION 同时返回独立的 fact_scope_state：仅现金/费用待核且持仓/可卖及三个范围有依据时，总体 state 可保持 RECONCILE_REQUIRED 或 UPDATE_PENDING，allowed 表示后续合格政策可继续账户事实核对；未决成交/股份、更正、数量差异、未知可卖或所需范围声明不足仍受限。现金与费用事件不自动令已核对的数量范围失效，新的数量知识则必须由后续范围声明覆盖。allowed 不代表降风险动作或政策获准。账户权限、资金门禁、技术资格和正式动作资格仍独立检查，不因本服务返回 allowed 就输出交易动作。始终 `executable_quantity=null`，不生成 HOLD。

声明只在实际依赖账户的用途检查，不要求每日打卡；独立市场观察始终可继续。账户与今天页共用 `consistency` 对当前待核状态解释，声明页展示用途检查的同一状态与下一步。已知持仓始终可见。

## 分项对账与材料处理

`RECONCILIATION` payload 为 `effective_at,source,record_id,reason,snapshot,resolved_draft_ids`。snapshot 精确包含 cash_balance、broker_available、broker_frozen、withdrawable、investment_income、investment_expenses（十进制金额字符串或 null），positions（instrument/quantity/sellable_quantity），pending_items（record_id/outstanding_amount）。不存在的券商行是未提供，不推成零。

预览/恢复查询提供 reconciliation_differences，分别列镜像、券商、MATCH/MISMATCH/UNKNOWN 和有据差额。明确确认后仅按用户核对的已知当前现金/持仓/可卖及券商资金快照对齐：现金对齐差额单列 UNEXPLAINED_ALIGNMENT，不冒称收入/外部转入；数量重建关闭活跃旧成本批次但保留它们，并创建成本 UNKNOWN 的当前批次，不推定买卖历史。未知可卖继续 null，未决差异继续可见。

收入、独立税费以及待结算余额不能靠快照猜补。用户须追加利息、真实结算、税费更正等有凭证事实，后再核对；已确认应收、已部分实际到账和未结余额单列，不能因现金未增就重复录收入。可取资金未知作为展示缺口；关键现金/券商可用/冻结/数量/可卖/未结权益 UNKNOWN 仍待核。

`resolved_draft_ids` 仅引用未确认 READY/QUARANTINED 材料，确认事务内标为 RESOLVED；材料仍可查询，原 CSV 文件和原行不删除。已确认、已处理或不存在的引用使整次确认失败。`GET /api/account/pending-drafts` 返回实际尚未处理材料。

## CSV 与后续联合验收

ROLL-CSV-3 在 v2 后追加 reason,target_event_id,replacement_kind,replacement_payload,scope,changes,snapshot,resolved_draft_ids 八列。scope/snapshot/resolved_draft_ids 和完整替代 payload 使用标准 JSON 单元格，由 CSV 引号规则转义，金额仍是字符串，未知 null。两项 replacement 都空为显式冲正，不能只填其中一项。v1/v2 头与种类集合冻结，三种05新事实仅在 v3 接受。所有行复用同一 prepare/confirm，整批一个版本与回执，原件必须存在且 SHA 匹配。

每次确认的账户版本、回执、事件、审计及材料状态原子推进，真实并发旧版本收到409，幂等重试返回原回执。26/27 尚无真实动作：本票提供既有版本语义，不宣称完整动作失效联验；必须由26/27真实调用方在确认事务内联验旧动作失效。09仍需消费修订后的有效事实、应收/应付及费用口径完成估值/收益呈现。
