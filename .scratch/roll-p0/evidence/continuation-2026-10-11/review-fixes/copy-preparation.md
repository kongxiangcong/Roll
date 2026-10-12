# 审阅修复：实际资料副本准备（2026-10-11）

授权范围仅为把23已停止的根 `actual-current-copy` 复制到全新根 `.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy`。源为既有研究一致副本，不是原19。通过[helper](copy-actual-corrected.py)执行SQLite只读online backup及已登记归档逐件SHA/长度复制；不打开应用、不解析归档语义、不复制未登记文件或凭据。

预检通过：无命令行引用精确源profile的关联进程，源WAL为0字节。源以 `mode=ro&immutable=1` 打开，既有DB/SHM/WAL均前后核对SHA及长度，目标SQLite integrity_check和所有表行数必须一致。目标或报告已存在、链接路径、非空源WAL、归档缺失或指纹差异均拒绝继续，不覆盖既有结果。

最终执行exit 0，**PASS**：3841份已登记归档、702,438,979字节，复制差异0；SQLite完整性ok、全部表行数一致，源DB及SHM/WAL的SHA/长度前后相同。源DB SHA256为 `e4a2d0dbafac0319d4e565c4b77c6b60fdc11855fb9c4ada29265bd4d4ff10e0`。逐件结果记录于[manifest](actual-corrected-copy-manifest.json)。此前23初始副本3822归档的历史收据仍保留；本次按当前已登记3841归档复制，包含其后新增的历史材料，不覆盖旧记录。

本阶段未追加冻结、拟合、验证、审阅或前向，未增加预算/账户状态；旧freeze/forecast/validation/material作为历史保存。复制时模型3、预测6、completefreeze1、validation3、material1、technical review runs0等全部表行数与源相同。后续仅在修复源码稳定并获得父代理具体通知后，追加新的completefreeze、复用同模型与historical CAL forecast作新诊断和纯本地review material。不能复用旧源码freeze冒充修复后冻结，不能改写旧档。

旧23provider审批packet保留为历史。由于分红登记日snapshot修复将改变shadow.py，旧packet不得作为当前接续材料执行；本阶段没有外发或真实provider调用。新的冻结/诊断/本地材料与任何真实外发授权分别取证，23仍partial。
