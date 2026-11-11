param(
    [Parameter(Mandatory=$true)][ValidateSet('Repair', 'GmshVolume', 'Remesh', 'Orientation', 'VtkRead')][string]$Scenario,
    [int]$CdpPort = 9244,
    [string]$Math3DCheckout = $env:MATH3D_CHECKOUT,
    [string]$ExistingWorktree,
    [ValidateSet('L0', 'L5', 'L6', 'L7', 'L8', 'L9')][string]$ResumeFrom = 'L0',
    [switch]$UseRunningApp,
    [switch]$SkipBuild,
    [switch]$BootOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$previousArgs = [Environment]::GetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', 'Process')
$previousUrl = [Environment]::GetEnvironmentVariable('DEVSHELL_CDP_URL', 'Process')
$previousCheckout = [Environment]::GetEnvironmentVariable('MATH3D_CHECKOUT', 'Process')
$previousRuns = [Environment]::GetEnvironmentVariable('DEVSHELL_SCIENTIFIC_RUNS_ROOT', 'Process')
$previousResume = [Environment]::GetEnvironmentVariable('DEVSHELL_REPAIR_RESUME_FROM', 'Process')
$previousVolumeOnly = [Environment]::GetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_ONLY', 'Process')
$previousVolumeResume = [Environment]::GetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_RESUME', 'Process')
$ownedApp = $null
$worktree = $root
$cdpUrl = "http://127.0.0.1:$CdpPort"

try {
    if ($UseRunningApp -and !$SkipBuild) { throw 'UseRunningApp requires SkipBuild.' }
    if ($ExistingWorktree -and !$SkipBuild) {
        throw 'ExistingWorktree requires SkipBuild; rebuilding changes runtime-lab identity and stales saved support.'
    }
    if ($Scenario -eq 'GmshVolume' -and $ResumeFrom -notin @('L0', 'L7')) {
        throw 'Gmsh volume acceptance supports L0 or L7 resume.'
    }
    if ([string]::IsNullOrWhiteSpace($Math3DCheckout) -or
        !(Test-Path -LiteralPath (Join-Path $Math3DCheckout 'renderer\src\mesh\surfaceMesh.ts'))) {
        throw 'Pass -Math3DCheckout with a MATH3D checkout that has the Mesh importer.'
    }
    if (!$UseRunningApp -and !$ExistingWorktree) {
        # MSVC's CMake scratch projects exceed MAX_PATH when nested under OneDrive.
        $session = [guid]::NewGuid().ToString('N').Substring(0, 12)
        $worktree = Join-Path $env:SystemDrive "dsr-$session"
        & git -C $root worktree add --detach $worktree HEAD
        if ($LASTEXITCODE -ne 0) { throw 'Could not create an isolated scientific acceptance worktree.' }
        Write-Host "WORKTREE=$worktree"
        $scientific = Join-Path $worktree '.scientific'
        New-Item -ItemType Directory -Path $scientific -Force | Out-Null
        $inventory = Join-Path $root '.scientific\runtime-report.json'
        if (Test-Path -LiteralPath $inventory) {
            Copy-Item -LiteralPath $inventory -Destination (Join-Path $scientific 'runtime-report.json')
        }
    }
    elseif ($ExistingWorktree) {
        $worktree = (Resolve-Path -LiteralPath $ExistingWorktree).Path
        if (!(Test-Path -LiteralPath (Join-Path $worktree '.git')) -or
            !(Test-Path -LiteralPath (Join-Path $worktree 'BatchLauncher\BatchLauncher.csproj'))) {
            throw 'ExistingWorktree must be a DevShell Git worktree.'
        }
        Write-Host "WORKTREE=$worktree"
    }
    if ($worktree.Length -gt 90) { throw 'Acceptance worktree path is too long for the CGAL CMake build.' }
    New-Item -ItemType Directory -Path (Join-Path $worktree '.scientific\runs') -Force | Out-Null
    $frontend = Join-Path $worktree 'DevShell\ui\dev-ui-react'
    $project = Join-Path $worktree 'BatchLauncher\BatchLauncher.csproj'
    $app = Join-Path $worktree 'BatchLauncher\bin\Release\net8.0-windows\BatchLauncher.exe'
    if (!$SkipBuild) {
        Push-Location $frontend
        try {
            if (!(Test-Path 'node_modules\playwright-core')) {
                & npm ci --ignore-scripts
                if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed to install.' }
            }
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
        & dotnet build $project -c Release
        if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    }
    if (!(Test-Path -LiteralPath $app)) { throw "Desktop executable is unavailable: $app" }
    [Environment]::SetEnvironmentVariable('MATH3D_CHECKOUT', $Math3DCheckout, 'Process')
    if (!$UseRunningApp) {
        [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS',
            "--remote-debugging-port=$CdpPort", 'Process')
        $ownedApp = Start-Process -FilePath $app -WorkingDirectory (Split-Path -Parent $app) `
            -WindowStyle Hidden -PassThru
    }
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $cdpUrl, 'Process')
    [Environment]::SetEnvironmentVariable('MATH3D_CHECKOUT', $Math3DCheckout, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_SCIENTIFIC_RUNS_ROOT',
        (Join-Path $worktree '.scientific\runs'), 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_REPAIR_RESUME_FROM', $ResumeFrom, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_ONLY',
        $(if ($Scenario -eq 'GmshVolume' -and $ResumeFrom -eq 'L0') { '1' } else { $null }), 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_RESUME',
        $(if ($Scenario -eq 'GmshVolume' -and $ResumeFrom -eq 'L7') { '1' } else { $null }), 'Process')
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($ownedApp -and $ownedApp.HasExited) { throw 'Isolated DevShell exited before WebView2 was ready.' }
        try {
            $targets = Invoke-RestMethod "$cdpUrl/json/list" -TimeoutSec 2
            if (@($targets | Where-Object { $_.url -like '*app.local*' }).Count -gt 0) {
                $ready = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (!$ready) { throw "Isolated DevShell WebView2 did not appear at $cdpUrl." }
    if (!$BootOnly) {
        $script = if ($Scenario -eq 'Repair') { 'scientific-cgal-repair-managed-ui-checks.mjs' }
            elseif ($Scenario -eq 'Remesh') { 'scientific-cgal-remesh-managed-ui-checks.mjs' }
            elseif ($Scenario -eq 'Orientation') { 'scientific-cgal-orientation-managed-ui-checks.mjs' }
            elseif ($Scenario -eq 'VtkRead') { 'scientific-vtk-read-managed-ui-checks.mjs' }
            else { 'scientific-gmsh-managed-ui-checks.mjs' }
        & node (Join-Path $root "tests\$script")
        if ($LASTEXITCODE -ne 0) { throw "Managed $Scenario acceptance failed." }
    }
    Write-Host "PASS: isolated $Scenario acceptance session"
}
finally {
    [Environment]::SetEnvironmentVariable('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', $previousArgs, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_CDP_URL', $previousUrl, 'Process')
    [Environment]::SetEnvironmentVariable('MATH3D_CHECKOUT', $previousCheckout, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_SCIENTIFIC_RUNS_ROOT', $previousRuns, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_REPAIR_RESUME_FROM', $previousResume, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_ONLY', $previousVolumeOnly, 'Process')
    [Environment]::SetEnvironmentVariable('DEVSHELL_GMSH_VOLUME_RESUME', $previousVolumeResume, 'Process')
    if ($ownedApp -and !$ownedApp.HasExited) {
        $null = $ownedApp.CloseMainWindow()
        if (!$ownedApp.WaitForExit(10000)) { Stop-Process -Id $ownedApp.Id -Force }
    }
}
