# 08.5 实际本地命令（未启动外部模型）

在专用 rv-ticket08 工作树执行。Python为原仓库虚拟环境；所有basetemp在原仓库.scratch下新目录。METHOD进程使用假auth文件，无真实OpenAI调用。PowerShell输出重定向至同目录对应txt；失败原样保留。

```powershell
$env:PYTHONPATH='backend/src;backend/tests/application'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_substance.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red29
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_substance.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green29
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py backend/tests/company_research/test_report_substance.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red30
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green30
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red31
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green31
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green31b
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py::test_accepted_source_observations_and_price_series_reach_summary_without_rewriting_core -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red32
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py::test_accepted_source_observations_and_price_series_reach_summary_without_rewriting_core -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green32
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_summary.py backend/tests/company_research/test_report_substance.py backend/tests/company_research/test_report_revisions.py backend/tests/company_research/test_report_coverage.py backend/tests/company_research/test_report_pipeline.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-regression33
```

日志编号与失败原因见local-08.5-validation.md。已运行的red/green29在新增peer用例前为五项，red30七项substance加一项summary；历史选择器体现运行时版本，不用当前测试数量改写旧结果。

最后数值覆盖slice及纯本地冻结/恢复：

```powershell
$env:PYTHONPATH='backend/src;backend/tests/application'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_substance.py -k 'label or five_distinct' -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-red34
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe -m pytest backend/tests/company_research/test_report_substance.py backend/tests/company_research/test_report_summary.py -q --basetemp D:/dsh-proj/Roll/.scratch/rv08-green34
$env:PYTHONPATH='backend/src'
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/start_host_revision05.py --data-directory D:/dsh-proj/Roll/.scratch/rv08-real02 --old-host-receipt .scratch/roll-research-valuation/evidence/08/host-revision04.json --old-audit-directory .scratch/roll-research-valuation/evidence/08/preview-host04 --output .scratch/roll-research-valuation/evidence/08/host-revision05.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/audit_local_payload.py --data-directory D:/dsh-proj/Roll/.scratch/rv08-real02 --job-id cf414530-5dee-45d3-af28-0e7e3f9321ae --output-directory .scratch/roll-research-valuation/evidence/08/preview-host05
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/restore_host_revision.py --source D:/dsh-proj/Roll/.scratch/rv08-real02 --target D:/dsh-proj/Roll/.scratch/rv08-queued-restored05 --job-id cf414530-5dee-45d3-af28-0e7e3f9321ae --output .scratch/roll-research-valuation/evidence/08/queued-restore05.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/revalidate_existing_offline05.py
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/preview_existing_offline05.py
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/verify_host_wire05.py
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/restore_host_revision.py --source D:/dsh-proj/Roll/.scratch/rv08-real02 --target D:/dsh-proj/Roll/.scratch/rv08-revalidated-restored05 --job-id cf414530-5dee-45d3-af28-0e7e3f9321ae --output .scratch/roll-research-valuation/evidence/08/revalidated-restore05.json
& D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe .scratch/roll-research-valuation/evidence/08/verify_source_bytes.py
```

实际结果和目录不可覆盖条件见checkpoint05.md、host-revision05/host05-wire-verification/queued-restore05/revalidated-restore05 JSON及相应txt。
