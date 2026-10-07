# Roll CSV · 03

`ROLL-CSV-1` 为冻结初版；当前下载 `ROLL-CSV-2` 覆盖已实现04事件。应用 `/api/account/csv/template` 下载UTF-8 BOM CSV；`/api/account/csv/guide` 提供对应字段说明。列定义在 `roll.accounts.csv_import.COLUMNS`，每行版本不可省略；应用只接收该明确格式，没有声称支持任何券商专用格式。`?version=ROLL-CSV-1`可下载原版，原列头/版本仍可解析，不暗改已有版本含义。后续05增加事件时发布后继模板并保留旧版解释。

初始文件恰有一行BASELINE_CASH、零至多行INITIAL_POSITION/PERMISSION，同一时点与来源，合成一个BASELINE命令。PERMISSION也可独立组成PERMISSIONS命令。初始状态、权限更新与后续事件分别上传，避免合并改变文件时序。FILL/FEE_ADJUSTMENT按原行顺序投影；字段、未知费用、成本与舍入复用[成交契约](fill-contract.md)，不另设财务计算。一次批次确认只产生一个账户版本，所有事件、最终投影、审计、幂等回执共用Ledger.confirm原事务。

## 原件、编码与错误

POST `/api/account/csv/drafts?filename=…&encoding=utf-8|utf-8-sig|gb18030&expected_account_version=N`，请求体是原CSV字节。4MiB/5000行上限；明确编码，不自动猜测。原件按SHA-256存到外置运行目录`raw/account-csv/<hash>`，flush/fsync及同目录rename完成后才保存SQLite草稿和文件映射。GET `/api/account/csv/files/{sha256}` 回查原字节并验证指纹；确认前再次验证必需原件，缺失/损坏409 `CSV_ORIGINAL_UNAVAILABLE`，不提交任何事实。

草稿保留上传文件名（仅basename）、编码、文件身份、上传实际时点、原预期账户版本、逐行原文和全部字段字符串。含引号/换行的CSV记录保留实际起始物理行号；原文件含BOM/换行的字节完整保留。代码前导零和数值原精度不经过数值类型推断，资金/数量校验使用Ledger Decimal契约。不使用pandas。列数、模板、编码、非法或无关列、业务错误均产生可查QUARANTINED草稿，指出原行和原因；没有缺费归零或逐行部分提交。

来源/依据中的“忽略风险规则”只作为材料文本；数值列中的此类文字为字段错误。CSV解析不调用模型、不执行脚本、不读取外部指令，文本不会增加工具或改变资金/资格状态。直接向普通JSON草稿入口发送CSV_BATCH被422拒绝；批命令只能由受控原文件解析构成。每个ACTUAL事件绑定文件SHA和来源行集合，基线聚合事件保留对应全组来源行，原始材料可由草稿查回。

## 身份、幂等与修订

同字节文件（包括改名重传）返回最初草稿/已有回执。文件映射与草稿同一SQLite事务写入，并发重传只产生一个canonical草稿。不同文件的记录ID若空，以文件SHA＋行号生成；可靠fill_id独立去重，同一委托不同分笔及同价同量不同分笔保留。不以价量或order_id去重。缺少可靠分笔标识的每行展示跨文件相似歧义，由用户整批确认独立事实；来源永不自动合并。可靠分笔重复或内容矛盾隔离整个批次并显示原回执/错误；批内尚未发布的重复分笔回执为null。

GET `/api/account/csv/drafts/{id}` 取得文件、原行、预览、错误、警告、命令、后继关系及已有回执。确认仍为POST `/api/account/confirm`。同键同内容返回原回执，异内容409；旧账户版本409带实际差异，批次整体失败。浏览器sessionStorage保存草稿ID和确认键，重载后恢复待确认结果；重复上传已确认文件显示原回执。

POST `/api/account/csv/drafts/{id}/revise` `{expected_account_version,encoding}` 对原字节重新解码/按当前版本预览；上传修订文件可显式给`revision_of`。保留原稿，READY后继原子将原稿标为SUPERSEDED，原稿不可再确认；失败后继不会清除原待核。已确认文件不能修订，要由新增账户更正事件处理。原有文件/账本不被覆盖。旧版本新上传也保留原始预期版本和冲突原因，不自动入账。

schema只创建当前需要的account_csv_imports及文件身份索引；不重置Ledger user_version。运行数据不进入源代码目录，依赖清单/锁文件无需改变。03已合并04实际现金/权益实现并用v2模板联验；每行事件复用04 EVENT_FIELDS精确字段与Ledger.prepare。05对账新增事件仍由对应票扩模板，03未实现对账逻辑。

## v2现金与权益

v2在v1原列后追加amount、item_type、corrected_amount、new_quantity。支持CASH_IN/CASH_OUT/DIVIDEND/INTEREST/TAX/FEE/PENDING_ITEM/SETTLEMENT/CASH_CORRECTION/SHARE_CHANGE；类型原字段复用[现金权益契约](cash-contract.md)。instrument由exchange/code组成（允许空仅在04契约允许时），record_id若空由文件SHA＋行号生成。待结算不变可用现金；到账关联、不重复收益、外部投入不计投资盈利及数量/成本守恒均由04同一投影完成。金额未知仍隔离待核；任何后续行错误使整个批次失败。
