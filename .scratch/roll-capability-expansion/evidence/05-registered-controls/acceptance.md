# 05 原登记基准增量验收

基线 HEAD `4fd8c18`，仅实现 METHOD 费用前缀上的原登记 CASH/START_HOLD/MA5_MA20 消费者，05保持 partial。方法先保存于 `method-before-derivation.json`；不修改旧冻结指纹所依赖的引擎。

公开 API 先404失败（25.31s），最终1 PASS/37.54s：45声明帧形成46净值点，START_HOLD 买入后不自动卖出；MA 在23入场、42退出，保留观察后20而非入场后20。完整窗口 MA 无前置上下文，明确 eligibility gap，相对收益为未知。检查幂等、列表、原账户/模型/冻结不变、重启与保存重放。

继续保存47/48/49帧后保留缺46及未知47；50点完整跨度不压缩。47未知、48前收盘未知被适配拒绝，49的11与11.00用Decimal等值比较而恢复支持；候选全窗口未知，相对结果不补值，原45帧结果仍可重放。测试源见 `backend/tests/application/test_successor_registered_controls.py`，日志 `api-red.log`、`api-final.log`。

Chrome 1 PASS/37.4s（`browser-green.log`、`browser-results.json`）：公开页面创建、保存、查看时点/支持/未授资格、显式重放、刷新恢复及390px截图 `mobile.png`。同一流程还读取六费用、时间三段和 CASH 控制。隔离 profile `.scratch/r05bb`，未启动主账户服务。TypeScript/Vite构建通过（`build.log`）。

标准与规格两路只读审查开放发现0，见 `standards-review.md`、`spec-review.md`。15份既有脏文件保护核对0差异，12份旧模型依赖保持不变（`preservation.json`、`model-preservation.json`）。原 SSE 修改不纳入本提交。

原登记基准提供描述性 METHOD 轨迹，不证明真实日历、前置MA上下文、共同风险匹配、独立支持或完整G5。G4只保留绝对风险硬FAIL，否则INCONCLUSIVE；risk_matched_qualification=false，未拟合、未访问SEALED、未授资格、未启真实前向。余下延迟/部分成交、邻域、迁移、真实输入及完整冻结继续按05原验收推进。
