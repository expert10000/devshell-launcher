param([string]$Root = 'G:\master')
$ErrorActionPreference = 'Stop'
$repositories = [ordered]@{
    'Math3D' = 'https://github.com/expert10000/Math3D.git'
    'theory' = 'https://github.com/expert10000/theory.git'
    'math' = 'https://github.com/expert10000/math.git'
    'devshell-launcher' = 'https://github.com/expert10000/devshell-launcher.git'
    'Browser-AI' = 'https://github.com/expert10000/Browser-AI.git'
}
$failures = @()
foreach ($entry in $repositories.GetEnumerator()) {
    $path = Join-Path $Root $entry.Key
    try { & (Join-Path $PSScriptRoot 'Sync-Repository.ps1') -RepositoryUrl $entry.Value -Destination $path }
    catch { $failures += $entry.Key; Write-Warning $_.Exception.Message }
}
if ($failures.Count) { throw ('Repositories needing attention: ' + ($failures -join ', ')) }
Write-Host 'All master repositories updated.'
