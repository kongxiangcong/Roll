# 从今建立 PIT 数据库与虚拟模型框架

2026-10-10 用户接受：停止寻找旧 PIT 档案，先开发框架和虚拟模型，真实证据积累充分后再考虑可用资格。使用既有 SQLite／Parquet／按SHA原件归档；没有新数据库服务或付费来源。

## 两个数据目录

- `.roll-data/pit/roll.sqlite3`：真实来源采集计划、批次和事实版本；相关原件在同目录 `raw/`，规范事实在 `parquet/`。当前明确范围为江西铜业 `SSE:600362`，未扩展到全市场。
- `.roll-data/synthetic19/roll.sqlite3`：独立虚拟开发模型、执行标签、校准器、预测、尝试及冻结清单；METHOD_CASE，无真实账户与真实研究家族预算。

两个目录受 `.gitignore` 保护。完整备份须同时保存数据库及引用原件，不能只复制SQLite文件。既有 Roll 备份入口会覆盖新表和已登记归档。旧真实账户数据库不迁移、不修改。

## 采集与时点

在仓库根目录运行 `backend\.venv\Scripts\python.exe -B -X utf8 scripts\collect_prospective.py`。固定当前来源：搜狐RAW日线、新浪报价／状态线索、东方财富权益与公告。每次最多45自然日回看、12调用、15秒宿主期限，保留未能确认的来源与事实缺口。有限回看是当次已知上下文，不是搜寻旧发布档案。

2026-10-10另经用户授权接入固定版本CNEquity补充路径（TDX／东财日线、当前状态、公司行为及巨潮索引），按来源单独登记、有界访问、清洗隔离、差异保留并在完整性通过后备份。运行环境、上限与维护契约见[CNEquity数据层](cnequity-data-contract.md)。上段15秒／12调用仅属于原有采集，不代表整个补充任务的总上限。

起点由宿主当前时钟创建，不接受客户端起点或可得时间。`known_at` 不早于宿主取得、快照完成和PIT登记时间；事件日期／公告日期不等同于系统获知时点。取得的旧日线可以支持未来观察，不能被用来补造旧预测或旧PIT证据。

`pit_collection_plans` 保存不重置的起点；`pit_collection_batches` 保存成功、PARTIAL、FAILED／INTERRUPTED与缺口；`pit_fact_versions` 保存每次采集版本。重复登记同run_id复用既有批次。原始源保留所有版，按时点查询按来源分别选取当时最新已知版，不混源择优；迟到登记不覆盖后来实际版本。未知状态或权益不填正常／无事件。

每天16:10 Asia/Shanghai 的 Codex heartbeat `roll-pit` 调用采集脚本，常规无实质变化保持安静，只在失败／重要缺口变化／完整性故障或需用户处理时通知。本地执行依赖宿主可运行；关机、离线或未成功执行时不宣称已记录，更不能后补为当日已知。

## API与查看

- `POST /api/research/collections`：建立／复用指定证券计划，body为instrument、basis。
- `POST /api/research/collections/{id}/collect`：当前有界采集并追加入库。
- `GET /api/research/collections/{id}/batches`：已保存批次和缺口。
- `GET /api/research/collections/{id}/as-of?cutoff=<带时区时点>`：离线校验原件后重放当时已知事实；未来或无时区时点拒绝。
- `GET /api/research/collections/{id}/readiness`：显示覆盖和待验证条件，不签发资格。
- `POST /api/research/development-runs`：仅空账户、无既有研究的隔离实例生成一次固定虚拟开发；失败／重复结果保留，不重置再拟合。

查看实际积累页面时，用 `ROLL_DATA_DIR=D:\dsh-proj\Roll\.roll-data\pit` 启动另一个 Roll 实例；查看虚拟模型时用独立 `synthetic19` 目录。原默认实例不会自动切换或重启。开发页不把虚拟模型显示成真实合格模型。

## 虚拟构建与可用门禁

运行 `backend\.venv\Scripts\python.exe -B -X utf8 scripts\build_virtual_model.py`。固定420日合成序列，DEV160／embargo20／CAL160／embargo20／SEALED60；DEV前20行为特征上下文，各窗跨边界成熟标签清除。使用既有四特征L2 logit、DEV标准化、固定lambda1、CAL原预测先归档后唯一截距校准、现金／固定MA与买入持有边界展示、工件指纹、ForecastBundle及零联网重放。连续买入持有NAV与经济政策仍属于20，本票不把重叠独立往返损益串成连续财富。

虚拟冻结是工程版本冻结，不是完整真实实验冻结或PASS。真实路径仍须从新PIT库准备预登记DEV/CAL输入，核验完整状态、权益和规则，接通非METHOD特征、标签、真实拟合／校准冻结；既有真实准入继续拒绝未完成路径，避免资料行数增长后绕过检查。后续该接通工作由代理负责，不要求用户搜旧档案或保证技术有效。

数据覆盖、成熟标签、CAL每类至少20、时间依赖支持和全部原资格条件满足前，显示COLLECTING／尚不可用。正式可用还需要20/21的完整冻结与确认性验证、30/32的真实前向验证、模型技术审阅和能力授权；不得只靠行数、校准内Brier、虚拟成功或日期到达启用。不承诺数据积累完成日，不把数据采集起点当三个月G7起点。
