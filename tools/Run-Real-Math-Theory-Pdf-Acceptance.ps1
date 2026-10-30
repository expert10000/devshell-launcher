param([switch]$SkipBuild, [int]$CdpPort = 9237)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$app = Join-Path $repo 'BatchLauncher\bin\Release\net8.0-windows\BatchLauncher.exe'
$profile = Get-Content -LiteralPath (Join-Path $repo 'BatchLauncher\profiles\profile-laptop.json') -Raw | ConvertFrom-Json
$workspaceRoot = $profile.globals.workspaceRoot
$local = Join-Path $env:LOCALAPPDATA 'DevShellLauncher'
$sha = [System.Security.Cryptography.SHA256]::Create()
$hash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes('profile-laptop'))).Replace('-', '')
$sha.Dispose()
$paths = @(
    (Join-Path $local 'workspace-profile.json'),
    (Join-Path (Join-Path $local 'workspace-tabs') "$hash.json"),
    (Join-Path $repo 'BatchLauncher\state.json')
)
$saved = @{}
foreach ($path in $paths) {
    $saved[$path] = if (Test-Path -LiteralPath $path) { [System.IO.File]::ReadAllBytes($path) } else { $null }
}
$previousArgs = [Environment]::GetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', 'Process')
$previousCdp = [Environment]::GetEnvironmentVariable('DEVSHELL_CDP_URL', 'Process')
$previousRoot = [Environment]::GetEnvironmentVariable('DEVSHELL_REAL_PDF_ROOT', 'Process')
$ownedApp = $null

function Start-CheckApp {
    $script:ownedApp = Start-Process -FilePath $app -WorkingDirectory (Split-Path -Parent $app) -WindowStyle Normal -PassThru
    $cdpUrl = "http://127.0.0.1:$CdpPort"
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($script:ownedApp.HasExited) { throw 'DevShell exited before WebView2 was ready.' }
        try {
            $targets = Invoke-RestMethod "$cdpUrl/json/list" -TimeoutSec 2
            if (@($targets | Where-Object { $_.url -like '*app.local*' }).Count -gt 0) { return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw "DevShell WebView2 did not appear at $cdpUrl."
}

function Stop-CheckApp {
    if ($script:ownedApp -and !$script:ownedApp.HasExited) {
        $null = $script:ownedApp.CloseMainWindow()
        if (!$script:ownedApp.WaitForExit(10000)) { Stop-Process -Id $script:ownedApp.Id -Force }
    }
    $script:ownedApp = $null
    $cdpUrl = "http://127.0.0.1:$CdpPort"
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try {
            $targets = Invoke-RestMethod "$cdpUrl/json/list" -TimeoutSec 1
            if (@($targets | Where-Object { $_.url -like '*app.local*' }).Count -eq 0) { break }
        } catch { break }
        Start-Sleep -Milliseconds 250
    }
}

try {
    if (Get-Process BatchLauncher -ErrorAction SilentlyContinue) { throw 'Close DevShell before this acceptance check.' }
    if (!(Test-Path -LiteralPath (Join-Path $workspaceRoot 'theory\release\v1.0.0\final_pdfs\Master\Theory_of_Quantum_Mechanics_COMPLETE_v1.0.0.pdf')) -or
        !(Test-Path -LiteralPath (Join-Path $workspaceRoot 'math\content\theory-of-real-analysis.pdf'))) {
        throw 'The real Theory and Math PDF fixtures are not present.'
    }
    if (!$SkipBuild) {
        Push-Location (Join-Path $repo 'DevShell\ui\dev-ui-react')
        try { & npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
        finally { Pop-Location }
        & dotnet build (Join-Path $repo 'BatchLauncher\BatchLauncher.csproj') -c Release --no-restore
        if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    }
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', "--remote-debugging-port=$CdpPort", 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', "http://127.0.0.1:$CdpPort", 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_REAL_PDF_ROOT', $workspaceRoot, 'Process')
    Start-CheckApp
    & node (Join-Path $repo 'tests\real-math-theory-pdf-ui-checks.mjs') prepare
    if ($LASTEXITCODE -ne 0) { throw 'Real PDF prepare phase failed.' }
    Stop-CheckApp
    Start-CheckApp
    & node (Join-Path $repo 'tests\real-math-theory-pdf-ui-checks.mjs') verify
    if ($LASTEXITCODE -ne 0) { throw 'Real PDF restart verification failed.' }
    Write-Host 'PASS: real Math/Theory PDF acceptance checks'
}
finally {
    Stop-CheckApp
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', $previousArgs, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $previousCdp, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_REAL_PDF_ROOT', $previousRoot, 'Process')
    foreach ($path in $paths) {
        if ($null -ne $saved[$path]) {
            $parent = Split-Path -Parent $path
            if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            [System.IO.File]::WriteAllBytes($path, $saved[$path])
        } elseif (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }
}
