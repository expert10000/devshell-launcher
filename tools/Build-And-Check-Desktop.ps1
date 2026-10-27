param(
    [switch]$UseRunningApp,
    [switch]$SkipBuild,
    [int]$CdpPort = 9237
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'DevShell\ui\dev-ui-react'
$project = Join-Path $root 'BatchLauncher\BatchLauncher.csproj'
$app = Join-Path $root 'BatchLauncher\bin\Release\net8.0-windows\BatchLauncher.exe'
$cdpUrl = "http://127.0.0.1:$CdpPort"
$previousCdpArgs = [Environment]::GetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', 'Process')
$previousCdpUrl = [Environment]::GetEnvironmentVariable('DEVSHELL_CDP_URL', 'Process')
$ownedApp = $null

try {
    if ($UseRunningApp -and !$SkipBuild) {
        throw 'UseRunningApp requires SkipBuild; a running app would not include the newly built files.'
    }
    if (!$UseRunningApp -and (Get-Process BatchLauncher -ErrorAction SilentlyContinue)) {
        throw 'Close the running DevShell app before this check, or use -UseRunningApp -SkipBuild.'
    }
    if (!$SkipBuild) {
        if (!(Test-Path (Join-Path $frontend 'node_modules\playwright-core'))) {
            Push-Location $frontend
            try { & npm ci --ignore-scripts; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' } }
            finally { Pop-Location }
        }
        Push-Location $frontend
        try { & npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
        finally { Pop-Location }
        & dotnet build $project -c Release
        if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    }
    if (!$UseRunningApp) {
        if (!(Test-Path $app)) { throw "Desktop executable is missing: $app" }
        [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', "--remote-debugging-port=$CdpPort", 'Process')
        # WinForms initializes WebView2 on Shown; hidden or minimized launch can skip it.
        $ownedApp = Start-Process -FilePath $app -WorkingDirectory (Split-Path -Parent $app) -WindowStyle Normal -PassThru
    }
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $cdpUrl, 'Process')
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $targets = Invoke-RestMethod "$cdpUrl/json/list" -TimeoutSec 2
            if (@($targets | Where-Object { $_.url -like '*app.local*' }).Count -gt 0) { $ready = $true; break }
        } catch { }
        if ($ownedApp -and $ownedApp.HasExited) { throw 'DevShell exited before its WebView2 page was ready.' }
        Start-Sleep -Seconds 1
    }
    if (!$ready) { throw "DevShell WebView2 did not appear at $cdpUrl." }

    & node (Join-Path $root 'tests\shell-preflight-ui-checks.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Missing-shell Playwright check failed.' }
    & node (Join-Path $root 'tests\jupyter-studio-ui-checks.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Jupyter Playwright check failed.' }
    Write-Host 'PASS: desktop build and both Playwright UI checks'
}
finally {
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', $previousCdpArgs, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $previousCdpUrl, 'Process')
    if ($ownedApp -and !$ownedApp.HasExited) {
        $null = $ownedApp.CloseMainWindow()
        if (!$ownedApp.WaitForExit(10000)) {
            Stop-Process -Id $ownedApp.Id -Force
        }
    }
}
