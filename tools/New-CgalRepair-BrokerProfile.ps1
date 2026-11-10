param(
    [Parameter(Mandatory=$true)][string]$Worktree,
    [Parameter(Mandatory=$true)][string]$Math3DCheckout,
    [string]$Manifest,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $Worktree).Path
$math3d = (Resolve-Path -LiteralPath $Math3DCheckout).Path
if (!$Manifest) { $Manifest = Join-Path $repo '.scientific\broker\repair-manifest.json' }
if (!$Output) { $Output = Join-Path $repo '.scientific\broker\repair-config.json' }
$manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$manifestData = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$entries = @($manifestData.certifiedCapabilities | Where-Object {
    $_.runtimeId -eq 'cgal-win-conda' -and $_.capabilityId -eq 'mesh.repair' -and $_.level -eq 'L9'
})
if ($entries.Count -ne 1) { throw 'The manifest needs exactly one certified mesh.repair@L9 entry.' }
if ($entries[0].referenceCases.Count -ne 4) { throw 'The repair entry needs four reference cases.' }
$report = Get-Content -LiteralPath (Join-Path $repo '.scientific\runtime-report.json') -Raw | ConvertFrom-Json
$runtime = @($report.runtimes | Where-Object { $_.id -eq 'cgal-win-conda' })
if ($runtime.Count -ne 1) { throw 'CGAL runtime inventory is missing.' }
$prefix = $runtime[0].environmentRoot
$workerHash = $entries[0].workerBinarySha256
$workers = @(Get-ChildItem -LiteralPath (Join-Path $repo '.scientific\builds') `
    -Filter devshell_cgal_hole_repair.exe -Recurse -File | Where-Object {
        (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $workerHash
    })
if ($workers.Count -ne 1) { throw "Expected one built repair worker matching $workerHash; found $($workers.Count)." }
$config = [ordered]@{
    schemaVersion = 1
    runtimeId = 'cgal-win-conda'
    capabilityId = 'mesh.repair'
    manifest = $manifestPath
    runtimeManifest = (Join-Path $repo 'runtimes\cgal-win-conda\runtime.json')
    adapter = (Join-Path $repo 'tools\scientific-cgal-hole-repair-worker.py')
    workerContract = (Join-Path $repo 'tools\scientific_worker_contract.py')
    python = (Join-Path $prefix 'python.exe')
    worker = $workers[0].FullName
    prefix = $prefix
    datasetRoot = (Join-Path $repo '.scientific\datasets')
    jobsRoot = (Join-Path $repo '.scientific\broker\repair-jobs')
    math3dRoot = $math3d
    sourceRoot = $repo
    maxConcurrentJobs = 4
    memoryLimitMiB = 2048
}
$outputPath = [System.IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
if (Test-Path -LiteralPath $outputPath) { throw "Broker profile already exists: $outputPath" }
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $outputPath -Encoding utf8NoBOM
& (Join-Path $prefix 'python.exe') (Join-Path $repo 'tools\scientific-broker\broker.py') verify --config $outputPath
if ($LASTEXITCODE -ne 0) { throw 'Repair broker profile verification failed.' }
Write-Host "CONFIG=$outputPath"
