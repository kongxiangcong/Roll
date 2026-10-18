# 16 工程标准审查：接手复核与评测纠正

- 权限：仅公开元数据读取；新attempt02—06逐个预登记并CLOSED_NO_RETRY。02沙箱ProxyError/零字节；03—06宿主合计22请求、126160字节，含GitHub403及Riverise README404；未重开旧预算、未下载候选权重、未执行远程源码或发送私有材料。
- 新指标函数只读混淆统计；验证标签和计数，拒判保留在真实类别分母，其他类别误判保留为FP。无支持类别recall为null；不将未知填零或将拒判当中性。二类macro-F1明确命名，非伪造四类能力。
- 原始标签/推理/混淆/评测报告未变；纠正报告绑定旧混淆报告SHA256，新reference绑定纠正报告SHA256和被替代reference摘要。旧运行包保持原引用；真实API复核新包写入后旧包查询值完全相同。
- 运行只用 `.scratch/r16-takeover-20261018`，来源为`.scratch/r15real`的新副本。真实账户库、来源预算、冻结模型与旧前向状态未写。新旧分类包均RESEARCH_LIMITED/NOT_GRANTED；账户0→0。
- 浏览器测试允许显式设置截图路径，CLI覆盖reporter/output以免覆盖旧browser-results.json/mobile.png；新端口18216/15216及18217/15217，不复用已有服务。
- 失败保留：初次沙箱pytest无输出后中止；宿主基线5通过；纠正后首次测试5失败/5通过，均因深层basetemp使Windows临时原件路径超过限制，改用新短目录`.scratch/r16cg`复跑，不改业务取证逻辑。
- 评测变更后重新运行相关pytest、构建、真实本地模型和Chrome；不以修改前的绿色代替修改后检查。最终结果见acceptance.md。
