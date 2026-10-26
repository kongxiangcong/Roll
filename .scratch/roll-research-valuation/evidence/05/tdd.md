# 05 公共边界红绿记录

用户已经确认研究服务/API、计算器、网页与备份恢复边界；05只在服务/API/Backups开展测试，没有mock内部模块。METHOD数据和真实来源/代理分账，模型调用0。

基础命令（每轮选择test_economic_review.py对应行为，用唯一隔离basetemp）：

```powershell
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests/company_research/test_economic_review.py -q -k <selector> --basetemp=D:/dsh-proj/Roll/.scratch/rv05-<unique-round>
```

API/TestClient在Windows sandbox内挂起，实际red05b/green05与最后回归使用获准相同边界的sandbox外执行。只停止已确认两个rv05-red05进程；未扩大为终止全部Python。空red05.txt不是测试结果。

切片/选择器/真实观察见README表和red01–red13/greenNN输出。green01首次规范归档错误、真实脚本前三次源输入失败、旧经济门误把审核缺失放行、验证脚本str/Path错误均保留。red12中scope首次因同序列冲突头本已保留而通过，后来改独立事实序列，scope-regression验证父链保护；没有将通过项伪写red失败。

最终覆盖22个新增测试：FCFF桥、正常化、来源/假设、ROIC/资本时序、经济重复桥、周期/集团/金融、四态、旧值隐藏、当前读取时点/新增披露、快照一致、备份与重放、经济数值域和损失税处理。最终一次受影响回归94 passed、5 subtests passed in412.24s；原始final-regression.txt为准。代码完成后未重复扩大测试。真实案例/隔离恢复使用独立脚本，不把METHOD测试当真实模型/浏览器验收。
