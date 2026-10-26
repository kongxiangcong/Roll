# 05 增量：同窗口零暴露CASH控制

05仍partial。只接受明确空初始持仓，固定原现金、零暴露/利息/成交/费用，不替非空持仓假定清仓。CASH轨迹与候选使用原起始至末次声明会话的完整位置，跨度200上限；候选缺失None不压缩，完整收益未知不输出差值。

仅描述候选减CASH的收益差和风险差异，risk_matched=false，不授G4 PASS。保留原已知回撤失败；已观察暴露按原冻结上限及旧1e-12数值边界判定硬FAIL，即使完整窗口收益未知。已观察最大暴露不冒充缺失区段完整最大值。其他情况INCONCLUSIVE。原政策、期限、模型/账本不重算或改写。

方法先归档，原cost-stress manifest/input及统计代码指纹绑定，结果不可变、幂等、原件查询/重放；嵌套源由既有原件读者校验。不存在新依赖/拟合/SEALED/网络/真实资金/资格/前向动作。

验收：

- api-red.log：404，1 failed/20.78s。
- api-green.log：1 PASS/24.80s，常数10000元CASH/收益0/暴露0，候选原NAV和差值、完整日历缺4/未知5不补值、归档/幂等/重启重放。
- api-final.log：1 PASS/28.88s，另以公开迁移/后继冻结/费用链建立非空初始lot，现金控制409 NO_ASSUMED_LIQUIDATION，未改变原状态/账户。
- api-adverse.log：已观察暴露突破原上限、完整收益仍未知时保留MAXIMUM_EXPOSURE_EXCEEDED硬FAIL。
- browser-green.log：Chrome1 PASS/30.9s，保存CASH/明确风险未匹配/差值与暴露/重放/重载/390px；同链时间三段与费用报告仍通过。
- build.log：TypeScript/Vite通过；双轴审查开放发现0，未追加任何真实调用。
- preservation.json：15原现场文件无差异；model-preservation.json：12旧模型依赖不变；旧四个冻结模块git diff为空。

剩余START_HOLD/MA5_MA20需保留各自旧登记规则，不能把v1观察后20会话退出改成v2新lot入场后20会话而声称相同。源仍METHOD，不能关闭真实输入、共同风险匹配/独立统计、余下延迟/邻域/迁移或完整冻结要求。
