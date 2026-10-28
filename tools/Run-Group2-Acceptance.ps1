param([switch]$SkipBuild, [int]$CdpPort = 9237)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$app = Join-Path $root 'BatchLauncher\bin\Release\net8.0-windows\BatchLauncher.exe'
$profiles = Join-Path $root 'BatchLauncher\profiles'
$selection = Join-Path $env:LOCALAPPDATA 'DevShellLauncher\workspace-profile.json'
$state = Join-Path $root 'BatchLauncher\state.json'
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
$profileId = "profile-group2-acceptance-$suffix"
$otherId = "profile-group2-empty-$suffix"
$profilePath = Join-Path $profiles "$profileId.json"
$otherPath = Join-Path $profiles "$otherId.json"
$session = Join-Path ([System.IO.Path]::GetTempPath()) "devshell-group2-$suffix"
$fixture = Join-Path $session 'repo'
$previousArgs = [Environment]::GetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', 'Process')
$previousCdp = [Environment]::GetEnvironmentVariable('DEVSHELL_CDP_URL', 'Process')
$previousFixture = [Environment]::GetEnvironmentVariable('DEVSHELL_GROUP2_FIXTURE_ROOT', 'Process')
$previousProfile = [Environment]::GetEnvironmentVariable('DEVSHELL_GROUP2_PROFILE_ID', 'Process')
$previousOther = [Environment]::GetEnvironmentVariable('DEVSHELL_GROUP2_OTHER_PROFILE_ID', 'Process')
$selectionBytes = if (Test-Path -LiteralPath $selection) { [System.IO.File]::ReadAllBytes($selection) } else { $null }
$stateBytes = if (Test-Path -LiteralPath $state) { [System.IO.File]::ReadAllBytes($state) } else { $null }
$ownedApp = $null
$passed = $false

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
}

try {
    if (Get-Process BatchLauncher -ErrorAction SilentlyContinue) {
        throw 'Close DevShell before the isolated acceptance check.'
    }
    New-Item -ItemType Directory -Path $fixture -Force | Out-Null
    & git -C $fixture init -q
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize disposable repository.' }
    $config = @{
        version = 2
        globals = @{ defaultShell = 'pwsh'; workspaceRoot = $fixture; autoDetectTools = $false }
        projects = @(@{
            id = 'acceptance'; name = 'Group 2 Acceptance'; root = $fixture
            tasks = @{ 'Fixture - Build' = @{ shell = 'pwsh'; cwd = $fixture; steps = @(@{ run = "Write-Output 'GROUP2_JOB_READY'; Start-Sleep -Seconds 120" }) } }
            repositories = @(@{ id = 'fixture'; name = 'Fixture'; path = $fixture; buildTask = 'Fixture - Build'; pdfPath = 'docs/sample.pdf'; pdfDirectory = 'docs' })
        })
    }
    $empty = @{ version = 2; globals = @{ defaultShell = 'pwsh'; workspaceRoot = $fixture; autoDetectTools = $false }; projects = @() }
    $config | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $profilePath -Encoding utf8
    $empty | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $otherPath -Encoding utf8
    if (!$SkipBuild) {
        Push-Location (Join-Path $root 'DevShell\ui\dev-ui-react')
        try { & npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
        finally { Pop-Location }
        & dotnet build (Join-Path $root 'BatchLauncher\BatchLauncher.csproj') -c Release --no-restore
        if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    }
    if (!(Test-Path -LiteralPath $app)) { throw "Desktop executable missing: $app" }
    [System.IO.File]::WriteAllText($selection, ('{"activeProfileId":"' + $profileId + '"}'))
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', "--remote-debugging-port=$CdpPort", 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', "http://127.0.0.1:$CdpPort", 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_FIXTURE_ROOT', $fixture, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_PROFILE_ID', $profileId, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_OTHER_PROFILE_ID', $otherId, 'Process')
    Start-CheckApp
    & node (Join-Path $root 'tests\group2-acceptance-ui-checks.mjs') prepare
    if ($LASTEXITCODE -ne 0) { throw 'Group 2 prepare phase failed.' }
    Stop-CheckApp
    Start-CheckApp
    & node (Join-Path $root 'tests\group2-acceptance-ui-checks.mjs') verify
    if ($LASTEXITCODE -ne 0) { throw 'Group 2 restart verification failed.' }
    $passed = $true
    Write-Host 'PASS: Group 2 PDF/Files and real Logs Stop acceptance checks'
}
finally {
    Stop-CheckApp
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', $previousArgs, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $previousCdp, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_FIXTURE_ROOT', $previousFixture, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_PROFILE_ID', $previousProfile, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GROUP2_OTHER_PROFILE_ID', $previousOther, 'Process')
    foreach ($path in @($profilePath, $otherPath)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }
    if ($selectionBytes) { [System.IO.File]::WriteAllBytes($selection, $selectionBytes) }
    elseif (Test-Path -LiteralPath $selection) { Remove-Item -LiteralPath $selection -Force }
    if ($stateBytes) { [System.IO.File]::WriteAllBytes($state, $stateBytes) }
    elseif (Test-Path -LiteralPath $state) { Remove-Item -LiteralPath $state -Force }
    if ($passed) {
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
        $target = [System.IO.Path]::GetFullPath($session)
        if ([System.IO.Path]::GetDirectoryName($target) -ne $tempRoot -or !([System.IO.Path]::GetFileName($target).StartsWith('devshell-group2-'))) {
            throw "Refusing to remove unexpected fixture path: $target"
        }
        Remove-Item -LiteralPath $target -Recurse -Force
    } else {
        Write-Warning "Fixture retained for debugging: $session"
    }
}
