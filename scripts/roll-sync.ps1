$project = Join-Path (Split-Path $PSScriptRoot -Parent) 'backend'
& uv run --project $project --locked roll sync @args
exit $LASTEXITCODE
