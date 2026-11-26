$backend = Join-Path (Split-Path $PSScriptRoot -Parent) 'backend'
$cliArgs = @($args)
if ($cliArgs.Count -eq 0) { $cliArgs = @('serve') }
& uv run --project $backend --locked roll @cliArgs
exit $LASTEXITCODE
