[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [string]$OutputRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) '.scientific/smoke'),
    [switch]$PublishToLauncher
)
$ErrorActionPreference = 'Stop'
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
$OutputRoot = Join-Path ([System.IO.Path]::GetFullPath($OutputRoot)) ([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
[System.IO.Directory]::CreateDirectory($OutputRoot) | Out-Null
$repository = Split-Path $PSScriptRoot -Parent
$checks = @()

function Invoke-OwnedCheck {
    param([string]$Executable, [string[]]$Arguments, [string]$Directory, [string]$Prefix, [string]$LogPath, [int]$TimeoutSeconds = 180)
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.Environment['PATH'] = "$Prefix;$Prefix\Library\bin;$Prefix\Scripts;" + $env:PATH
    $start.Environment['PYTHONIOENCODING'] = 'utf-8'
    $start.Environment['PYTHONNOUSERSITE'] = '1'
    $start.Environment.Remove('PYTHONPATH') | Out-Null
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $process.Start()) { throw "Could not start $Executable" }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
        if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
        $text = $stdout.GetAwaiter().GetResult() + "`n" + $stderr.GetAwaiter().GetResult()
        [System.IO.File]::WriteAllText($LogPath, $text, [System.Text.UTF8Encoding]::new($false))
        if ($timedOut) { throw "Timeout after $TimeoutSeconds seconds; log $LogPath" }
        if ($process.ExitCode -ne 0) { throw "Exit $($process.ExitCode); log $LogPath`n$($text.Substring(0, [Math]::Min(8000, $text.Length)))" }
        return $timer.ElapsedMilliseconds
    } finally {
        if ($process.Id -and -not $process.HasExited) { $process.Kill($true); $process.WaitForExit() }
        $process.Dispose()
    }
}

foreach ($kind in @('cgal', 'vtk')) {
    $prefix = Join-Path $RuntimeRoot "devshell-$kind"
    $cmake = Join-Path $prefix 'Library/bin/cmake.exe'
    $source = Join-Path $repository "scientific/smoke/$kind"
    $directory = Join-Path $OutputRoot $kind
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    $build = Join-Path $directory 'build'
    Write-Host "$kind configure / build / run -> $directory"
    $elapsed = Invoke-OwnedCheck -Executable $cmake -Arguments @('-S', $source, '-B', $build, '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DCMAKE_PREFIX_PATH=$prefix\Library") -Directory $directory -Prefix $prefix -LogPath (Join-Path $directory 'configure.log')
    $checks += @{ runtimeId="$kind-win-conda"; id="$kind.configure"; name='CMake configure / dependency discovery'; state='passed'; durationMs=$elapsed; detail=(Join-Path $directory 'configure.log') }
    $elapsed = Invoke-OwnedCheck -Executable $cmake -Arguments @('--build', $build, '--config', 'Release', '--parallel', '2') -Directory $directory -Prefix $prefix -LogPath (Join-Path $directory 'build.log')
    $checks += @{ runtimeId="$kind-win-conda"; id="$kind.compile-link"; name='C++ compile / link'; state='passed'; durationMs=$elapsed; detail=(Join-Path $directory 'build.log') }
    $exe = Join-Path $build "Release/devshell_${kind}_smoke.exe"
    $elapsed = Invoke-OwnedCheck -Executable $exe -Arguments @() -Directory $directory -Prefix $prefix -LogPath (Join-Path $directory 'run.log') -TimeoutSeconds 30
    $checks += @{ runtimeId="$kind-win-conda"; id="$kind.geometry"; name='C++ geometry smoke / artifact'; state='passed'; durationMs=$elapsed; detail=(Join-Path $directory 'results.json') }
}
$vtkPrefix = Join-Path $RuntimeRoot 'devshell-vtk'
$renderDirectory = Join-Path $OutputRoot 'vtk-render'
[System.IO.Directory]::CreateDirectory($renderDirectory) | Out-Null
$elapsed = Invoke-OwnedCheck -Executable (Join-Path $vtkPrefix 'python.exe') -Arguments @((Join-Path $PSScriptRoot 'scientific-vtk-render-check.py')) -Directory $renderDirectory -Prefix $vtkPrefix -LogPath (Join-Path $renderDirectory 'render.log') -TimeoutSeconds 60
$checks += @{ runtimeId='vtk-win-conda'; id='vtk.offscreen'; name='VTK offscreen render / nonblank PNG'; state='passed'; durationMs=$elapsed; detail=(Join-Path $renderDirectory 'results.json') }
$reportPath = Join-Path $repository '.scientific/runtime-report.json'
& (Join-Path $PSScriptRoot 'Inspect-ScientificRuntimes.ps1') -RuntimeRoot $RuntimeRoot -OutputPath $reportPath
$report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
foreach ($runtime in $report.runtimes) {
    $runtime.checks = @($runtime.checks) + @($checks | Where-Object { $_.runtimeId -eq $runtime.id } | ForEach-Object { @{id=$_.id; name=$_.name; state=$_.state; durationMs=$_.durationMs; detail=$_.detail} })
    $runtime.sdk.compilation = 'passed'
    $runtime.sdk.linking = 'passed'
    if ($runtime.kind -eq 'vtk') { $runtime.sdk.rendering = 'passed'; $runtime.validatedCapabilities = @('geometry.polydata', 'mesh.read.vtp', 'mesh.write.vtp', 'render.offscreen') }
    else { $runtime.validatedCapabilities = @('geometry.surface-mesh') }
    $runtime.state = 'partial'
}
$report.notes = @('Explicit C++ smoke builds/linking/geometry and VTK offscreen rendering passed. Other declared algorithms and interactive rendering remain untested.', "Run artifacts and logs: $OutputRoot")
$json = $report | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($reportPath, $json, [System.Text.UTF8Encoding]::new($false))
if ($PublishToLauncher) {
    foreach ($folder in @('BatchLauncher/ui', 'BatchLauncher/bin/Debug/net8.0-windows/ui', 'BatchLauncher/bin/Managed/ui')) {
        $target = Join-Path $repository $folder
        if (Test-Path -LiteralPath $target -PathType Container) { [System.IO.File]::WriteAllText((Join-Path $target 'scientific-runtime-report.json'), $json, [System.Text.UTF8Encoding]::new($false)) }
    }
}
Write-Host "All 7 scientific smoke checks passed. Artifacts: $OutputRoot"
