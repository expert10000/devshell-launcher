param(
    [Parameter(Mandatory=$true)][string]$Worktree,
    [Parameter(Mandatory=$true)][string]$Math3DCheckout,
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$BrokerPython = (Get-Command python -ErrorAction Stop).Source
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $Worktree).Path
$math3d = (Resolve-Path -LiteralPath $Math3DCheckout).Path
$manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$brokerExecutable = (Resolve-Path -LiteralPath $BrokerPython).Path
$outputPath = [System.IO.Path]::GetFullPath($Output)
$manifestData = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$entries = @($manifestData.certifiedCapabilities | Where-Object {
    $_.runtimeId -eq 'gmsh-win-conda' -and $_.capabilityId -eq 'mesh.generate3d' -and $_.level -eq 'L9'
})
if ($entries.Count -ne 1) { throw 'The candidate manifest needs one current mesh.generate3d@L9 entry.' }
$entry = $entries[0]
$report = Get-Content -LiteralPath (Join-Path $repo '.scientific\runtime-report.json') -Raw | ConvertFrom-Json
$runtime = @($report.runtimes | Where-Object { $_.id -eq 'gmsh-win-conda' })
if ($runtime.Count -ne 1) { throw 'Gmsh runtime inventory is missing.' }
$prefix = $runtime[0].environmentRoot
$adapter = Join-Path $repo 'tools\scientific-broker\gmsh_volume_adapter.py'
$worker = Join-Path $repo 'tools\scientific-gmsh-volume-worker.py'
$broker = Join-Path $repo 'tools\scientific-broker\broker.py'
$exporter = Join-Path $repo 'tools\scientific-gmsh-tetmesh-export.py'
foreach ($item in @(@($adapter,$entry.adapterSha256), @($worker,$entry.workerBinarySha256),
        @($broker,$entry.brokerSha256), @($exporter,$entry.exporterSha256))) {
    $actual = (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $item[1]) { throw "Candidate source differs: $($item[0])" }
}
& $brokerExecutable -c 'import psutil'
if ($LASTEXITCODE -ne 0) { throw 'The broker Python needs psutil for process-tree cleanup verification.' }
if (Test-Path -LiteralPath $outputPath) { throw "Broker profile already exists: $outputPath" }
$config = [ordered]@{
    schemaVersion = 1
    runtimeId = 'gmsh-win-conda'
    capabilityId = 'mesh.generate3d'
    manifest = $manifestPath
    runtimeManifest = (Join-Path $repo 'runtimes\gmsh-win-conda\runtime.json')
    adapter = $adapter
    workerContract = (Join-Path $repo 'tools\scientific_worker_contract.py')
    python = (Join-Path $prefix 'python.exe')
    worker = $worker
    prefix = $prefix
    datasetRoot = (Join-Path $repo '.scientific\datasets')
    jobsRoot = (Join-Path (Split-Path -Parent $outputPath) 'jobs')
    math3dRoot = $math3d
    sourceRoot = $repo
    maxConcurrentJobs = 4
    memoryLimitMiB = 2048
}
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $outputPath -Encoding utf8NoBOM
& $brokerExecutable $broker verify --config $outputPath
if ($LASTEXITCODE -ne 0) { throw 'Candidate volume broker profile verification failed.' }
Write-Host "CONFIG=$outputPath"
Write-Host "BROKER_PYTHON=$brokerExecutable"
