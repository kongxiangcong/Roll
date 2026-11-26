$project = Join-Path (Split-Path $PSScriptRoot -Parent) 'backend'
& uv run --project $project --locked roll market sync @args
exit $LASTEXITCODE
