$ErrorActionPreference='Continue'
cd D:\dsh-proj\Roll\backend
$env:PYTHONPATH='src'
$env:PYTHONIOENCODING='utf-8'
$log='D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\13-observation\real-observation.log'
"STARTED=$(Get-Date -Format o)" | Out-File -FilePath $log -Encoding utf8
& '.venv\Scripts\python.exe' -c "import runpy;runpy.run_path(r'D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\13-observation\run_real_observation.py',run_name='__main__')" *>> $log
"EXIT=$LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8
