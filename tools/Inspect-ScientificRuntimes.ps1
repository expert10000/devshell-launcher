[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) '.scientific/runtime-report.json'),
    [switch]$PublishToLauncher
)
$ErrorActionPreference = 'Stop'
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$probe = Join-Path $PSScriptRoot 'scientific-runtime-probe.py'
$results = @()
foreach ($kind in @('cgal', 'vtk')) {
    $prefix = Join-Path $RuntimeRoot "devshell-$kind"
    $python = Join-Path $prefix 'python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $results += [ordered]@{ id="$kind-win-conda"; kind=$kind; name=$kind.ToUpperInvariant(); execution='windows-native'; environmentRoot=$prefix; executable=$python; version=$null; state='missing'; packages=@(); checks=@(@{id="$kind.environment"; name='Local environment'; state='missing'; detail='Not installed'; durationMs=0}); validatedCapabilities=@() }
        continue
    }
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $python
    $start.ArgumentList.Add($probe)
    $start.ArgumentList.Add('--kind')
    $start.ArgumentList.Add($kind)
    $start.WorkingDirectory = $prefix
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $start.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
    # Conda's DLL search directories belong to this child only; never mutate system PATH.
    $start.Environment['PATH'] = "$prefix;$prefix\Library\bin;$prefix\Library\usr\bin;$prefix\Scripts;" + $env:PATH
    $start.Environment['PYTHONIOENCODING'] = 'utf-8'
    $start.Environment['PYTHONNOUSERSITE'] = '1'
    $start.Environment.Remove('PYTHONPATH') | Out-Null
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw "Could not start $kind probe" }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(60000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw "$kind inventory timed out after 60 seconds"
        }
        $output = $stdout.GetAwaiter().GetResult()
        $errorOutput = $stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw "$kind probe exited $($process.ExitCode): $($errorOutput.Substring(0, [Math]::Min(2000, $errorOutput.Length)))" }
        if ($output.Length -gt 1048576) { throw "$kind report exceeds 1 MiB" }
        $results += ($output | ConvertFrom-Json)
    } finally { $process.Dispose() }
}
$compiler = [ordered]@{ state='missing'; installation=$null; version=$null; path=$null; compilation='not-tested' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (Test-Path -LiteralPath $vswhere) {
    $installation = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if ($installation) {
        $tools = Get-ChildItem -LiteralPath (Join-Path $installation 'VC/Tools/MSVC') -Directory | Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
        if ($tools) {
            $cl = Join-Path $tools.FullName 'bin/Hostx64/x64/cl.exe'
            if (Test-Path -LiteralPath $cl) { $compiler = [ordered]@{ state='installed'; installation=$installation; version=(Get-Item -LiteralPath $cl).VersionInfo.ProductVersion; toolsetVersion=$tools.Name; path=$cl; compilation='not-tested' } }
        }
    }
}
$report = [ordered]@{ schemaVersion=1; generatedAt=[DateTime]::UtcNow.ToString('o'); runtimeRoot=$RuntimeRoot; compiler=$compiler; runtimes=@($results); notes=@('Explicit imports and local file/tool inventory only. No C++ compile/link or rendering tests were run.', 'Partial readiness is intentional: installation is not capability validation.', 'Existing MATH3D environments and system PATH were not changed.') }
$json = $report | ConvertTo-Json -Depth 20
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
[System.IO.Directory]::CreateDirectory((Split-Path $OutputPath -Parent)) | Out-Null
[System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
if ($PublishToLauncher) {
    $repository = Split-Path $PSScriptRoot -Parent
    foreach ($folder in @('BatchLauncher/ui', 'BatchLauncher/bin/Debug/net8.0-windows/ui', 'BatchLauncher/bin/Managed/ui')) {
        $target = Join-Path $repository $folder
        if (Test-Path -LiteralPath $target -PathType Container) {
            [System.IO.File]::WriteAllText((Join-Path $target 'scientific-runtime-report.json'), $json, [System.Text.UTF8Encoding]::new($false))
        }
    }
}
Write-Host "Report: $OutputPath"
foreach ($runtime in $results) { Write-Host "$($runtime.name): $($runtime.state); version $($runtime.version); $($runtime.environmentRoot)" }
Write-Host "MSVC: $($compiler.state) $($compiler.version). C++ compilation/linking and rendering remain untested."
