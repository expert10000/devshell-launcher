[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspaceRoot,
    [Parameter(Mandatory=$true)][string]$CondaExecutable,
    [ValidateSet('cgal', 'vtk', 'both')][string]$Kind = 'both',
    [switch]$PublishToLauncher
)
$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$CondaExecutable = [System.IO.Path]::GetFullPath($CondaExecutable)
if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) { throw 'Workspace root must already exist.' }
if (-not (Test-Path -LiteralPath $CondaExecutable -PathType Leaf)) { throw 'Conda executable missing.' }
$runtimeRoot = Join-Path $WorkspaceRoot '.conda'
$kinds = if ($Kind -eq 'both') { @('cgal', 'vtk') } else { @($Kind) }
foreach ($runtimeKind in $kinds) {
    $prefix = Join-Path $runtimeRoot "devshell-$runtimeKind"
    $packages = if ($runtimeKind -eq 'cgal') { @('python=3.11', 'cgal', 'cgal-cpp', 'cmake', 'ninja', 'eigen', 'numpy', 'scipy') } else { @('python=3.11', 'vtk', 'cmake', 'ninja', 'numpy', 'scipy') }
    $exists = Test-Path -LiteralPath (Join-Path $prefix 'conda-meta/history') -PathType Leaf
    if ((Test-Path -LiteralPath $prefix) -and -not $exists) { throw "Refusing to modify non-Conda directory: $prefix" }
    if ($exists) {
        $inventory = & $CondaExecutable list --prefix $prefix --json
        if ($LASTEXITCODE -ne 0) { throw "Cannot inventory $prefix" }
        $installed = @($inventory | ConvertFrom-Json | ForEach-Object { $_.name })
        $missing = @($packages | Where-Object { ($_ -split '=')[0] -notin $installed })
        if ($missing.Count -eq 0) { Write-Host "$runtimeKind required packages already present; no update performed."; continue }
        $action = 'install'
    } else { $action = 'create' }
    Write-Host "Installing missing $runtimeKind components into $prefix. Existing MATH3D environments are not modified."
    & $CondaExecutable $action --yes --override-channels --channel conda-forge --prefix $prefix @packages
    if ($LASTEXITCODE -ne 0) { throw "$runtimeKind installation failed with exit $LASTEXITCODE" }
}
& (Join-Path $PSScriptRoot 'Inspect-ScientificRuntimes.ps1') -RuntimeRoot $runtimeRoot -PublishToLauncher:$PublishToLauncher
