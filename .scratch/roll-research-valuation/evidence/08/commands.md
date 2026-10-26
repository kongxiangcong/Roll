# 当前可复现命令与实际状态

工作目录`D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket08`；Python固定`D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe`。所有basetemp在原workspace `.scratch/rv08-*`，不放stage；TestClient/METHOD child需要escalated，未使用真实key/MODEL的工程测试与实际章分账。

以下为本轮实际执行的选择器（文件保存全部原失败，不以修后结果覆盖）：

```powershell
$env:PYTHONPATH='backend/src;backend/tests/application'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red18
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green18
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -k revision_keeps -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red19
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -k revision_keeps -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green19
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-review20
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-review20b
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py backend/tests/company_research/test_report_pipeline.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-revision21
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py backend/tests/company_research/test_report_pipeline.py::test_public_report_refresh_collects_financial_facts_and_binds_new_partial_shared_snapshot -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-revision22
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py::test_fresh_report_preview_includes_only_its_fixed_model_and_typed_host_tables -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red23
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py backend/tests/company_research/test_report_pipeline.py::test_economic_coverage_distinguishes_explicit_baseline_and_valid_method_non_applicability backend/tests/company_research/test_report_pipeline.py::test_missing_sources_produce_ten_sections_and_explicit_partial_gates -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green23
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_revisions.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-final24
```

red18/green18当时未带application PYTHONPATH，使用此文件自身fixture不受影响。revision21当时仅目录默认导入路径，29passed/1个application sibling import缺失；revision22明确加该路径且只重跑失败项与新修订8项，未改生产语义变绿。review20 sandbox不能启METHOD进程（UNAVAILABLE）；review20b同选择器escalated7passed。final24是在最终冻结16源码上8passed52.33s。之后仅文档/非冻结API换行整理，算法源字节不再改。

实际离线新任务及审计：

```powershell
$env:PYTHONPATH='backend/src'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/start_host_revision.py --data-directory D:/dsh-proj/Roll/.scratch/rv08-real02 --original-plan .scratch/roll-research-valuation/evidence/08/frozen-command-plan.json --output .scratch/roll-research-valuation/evidence/08/host-revision03.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/audit_local_payload.py --data-directory D:/dsh-proj/Roll/.scratch/rv08-real02 --job-id 91a7cc25-2cde-4633-bb23-2113bac5acf4 --output-directory .scratch/roll-research-valuation/evidence/08/preview-host03
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/verify_host_wire.py
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/revalidate_existing_offline.py
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/restore_host_revision.py --source D:/dsh-proj/Roll/.scratch/rv08-real02 --target D:/dsh-proj/Roll/.scratch/rv08-queued-restored03 --job-id 91a7cc25-2cde-4633-bb23-2113bac5acf4 --output .scratch/roll-research-valuation/evidence/08/queued-restore03.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/restore_host_revision.py --source D:/dsh-proj/Roll/.scratch/rv08-real02 --target D:/dsh-proj/Roll/.scratch/rv08-revalidated-restored03 --job-id 91a7cc25-2cde-4633-bb23-2113bac5acf4 --output .scratch/roll-research-valuation/evidence/08/revalidated-restore03.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/verify_source_bytes.py
```

这组命令全部model/network/auth读取0。两个restore target已存在，不可原样重跑去覆盖；后续证明应选择全新命名目标。revalidate_existing_offline严格检查next sid在reusable8中，遇9立即退出，不可改成任意advance循环。

恢复入口：现存job91a7cc25、revision05b8b25b、input33ee7a98/core37b71966；8章在CHAPTERS检查点，待4新章。人类明确授权及同一auto-review通过前禁止启worker。合法授权到达后保持16源码与4wire SHA不变，用原Reviews/launcher继续独立8028/5208；先核第9实际model/provider/tools/commandSHA，再推进余章。不得为了完成率另起prompt或把旧失败改成功。
