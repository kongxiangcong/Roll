# 05 原迁移lot/范围验收

基线84d8736，方法先保存method-before-derivation.json。只消费保存frozen迁移、范围、原/新lot和BUY事件；旧引擎、模型与注册模块不改，不重跑执行，不授跨证券/市场/时期迁移能力。

公开API先404失败1项/20.03s；首绿1 PASS/22.14s。规格审查发现P2逐帧未核对position_id，已补原位置身份、新lot初始BUY订单身份及剩余数量不可回涨。最终 **1 PASS/22.88s**（api-final.log）。其中公开正向：原100股不可卖lot截止3、5次观察保持原期限，新增100股实际3入场、截止23，原迁移active分别false/true/true/true/true；保存幂等、查询/重启/后来帧不改变旧重放、嵌套源损坏409并还原、账户/影子不变。

另有明确的纯METHOD derive负向：拷贝内存输入后分别替换baseline位置身份、新lot首帧位置身份，均报告INCONSISTENT；数量50回涨100报告差异。未改归档源，不能称作公开篡改源被接纳；G5仍INCONCLUSIVE，结构差异不冒充统计失败。

修复后Chrome **1 PASS/61.85s**（体41.5s，browser-final.log/browser-results.json）：保存、读取、重放、刷新恢复、空原持仓迁移不适用但新lot审计继续、390px无溢出截图mobile.png。隔离profile `.scratch/r05mb2`、8166/5266。TypeScript/Vite通过，双审查P2复核关闭，见对应review.md。15原脏文件0差异、12旧模型依赖不变。

只证明METHOD绑定/期限/范围工程一致性；原行情/独立支持、其他regime、拟合邻域工件与完整冻结仍缺。NOT_GRANTED，真实前向未启动，05保持partial。下一离线前沿为版本化工程完成检查，统一验证已绑定消费者及仍缺的真实/工件条件，不回写旧冻结或要求成熟G7先于启运。
