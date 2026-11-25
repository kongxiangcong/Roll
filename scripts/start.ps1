$projectRoot = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $projectRoot 'backend'
$frontend = Join-Path $projectRoot 'frontend'
$cliArgs = @($args)
if ($cliArgs.Count -eq 0) { $cliArgs = @('serve') }
if ($cliArgs -contains 'serve') {
    if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules/.bin/vite.cmd'))) {
        & npm.cmd --prefix $frontend ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    # Rebuild from the checkout even when a previous version left an ignored dist directory.
    & npm.cmd --prefix $frontend run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& uv run --project $backend --locked roll @cliArgs
exit $LASTEXITCODE
