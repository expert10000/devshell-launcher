param(
    [Parameter(Mandatory=$true)][string]$Worktree,
    [Parameter(Mandatory=$true)][string]$Math3DCheckout,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')][string]$ReleaseTag,
    [string]$BrokerPython = (Get-Command python -ErrorAction Stop).Source
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $Worktree).Path
$math3d = (Resolve-Path -LiteralPath $Math3DCheckout).Path
$python = (Resolve-Path -LiteralPath $BrokerPython).Path
$installed = Join-Path $repo 'BatchLauncher\bin\Release\net8.0-windows'
$brokerProject = Join-Path $repo 'tools\scientific-broker\ScientificBroker.csproj'
$brokerRoot = Join-Path $repo 'tools\scientific-broker'
$inventorySource = Join-Path $repo '.scientific\runtime-report.json'
$deployment = Join-Path $repo ".scientific\broker\volume-release-$ReleaseTag"
$inventory = Join-Path $deployment 'runtime-inventory.json'
$manifest = Join-Path $deployment 'certified-capabilities.json'
$config = Join-Path $deployment 'broker-config.json'
$published = Join-Path $deployment 'qualified.json'
if (!(Test-Path -LiteralPath $installed)) { throw 'Run isolated Gmsh volume acceptance before release.' }
if (Test-Path -LiteralPath $deployment) { throw "Volume release directory already exists: $deployment" }
$runtimeRoot = (Get-Content -LiteralPath $inventorySource -Raw | ConvertFrom-Json).runtimeRoot
New-Item -ItemType Directory -Path $deployment -Force | Out-Null
& (Join-Path $repo 'tools\Inspect-ScientificRuntimes.ps1') -RuntimeRoot $runtimeRoot -OutputPath $inventory
$auditText = & dotnet run --project $brokerProject -- audit-volume $repo $installed $math3d desktop-five
if ($LASTEXITCODE -ne 0) { throw 'Volume qualification audit failed.' }
$audit = $auditText | ConvertFrom-Json
if (!$audit.eligible) { throw "Volume chain is not current: $($audit.exportReason)" }
& dotnet run --project $brokerProject -- export $repo $installed $math3d desktop-five $manifest
if ($LASTEXITCODE -ne 0) { throw 'Volume candidate export failed.' }
$volumeEntry = @((Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).certifiedCapabilities |
    Where-Object { $_.runtimeId -eq 'gmsh-win-conda' -and $_.capabilityId -eq 'mesh.generate3d' })
if ($volumeEntry.Count -ne 1) { throw 'Candidate export lacks one current fixed-cube volume capability.' }
& (Join-Path $PSScriptRoot 'New-GmshVolume-BrokerProfile.ps1') -Worktree $repo `
    -Math3DCheckout $math3d -Manifest $manifest -Output $config -BrokerPython $python
$smokeText = & $python (Join-Path $brokerRoot 'gmsh_volume_smoke.py') run --config $config
if ($LASTEXITCODE -ne 0) { throw "Volume broker/MATH3D smoke failed: $smokeText" }
$smoke = ($smokeText | Select-Object -Last 1) | ConvertFrom-Json
if ($smoke.verdict -ne 'passed') { throw 'Volume broker/MATH3D smoke did not pass.' }
$releaseText = & $python (Join-Path $brokerRoot 'release_certification.py') certify `
    --config $config --installed-root $installed --profile-id desktop-five `
    --release-tag $ReleaseTag --inventory $inventory --smoke-record $smoke.record `
    --output-root (Join-Path $deployment 'releases')
if ($LASTEXITCODE -ne 0) { throw "Volume release certification failed: $releaseText" }
$release = ($releaseText | Select-Object -Last 1) | ConvertFrom-Json
if ($release.verdict -ne 'qualified') { throw "Volume release is $($release.verdict): $($release.reasons)" }
& $python (Join-Path $brokerRoot 'release_certification.py') verify --config $config --report $release.report
if ($LASTEXITCODE -ne 0) { throw 'Volume release verification failed.' }
$hash = { param($path) (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
$marker = [ordered]@{
    schemaVersion = 1
    kind = 'scientific.gmsh-volume-published-release'
    releaseTag = $ReleaseTag
    sourceCommit = (& git -C $repo rev-parse HEAD).Trim()
    recordId = $volumeEntry[0].recordId
    manifest = @{ path = $manifest; sha256 = (& $hash $manifest) }
    config = @{ path = $config; sha256 = (& $hash $config) }
    inventory = @{ path = $inventory; sha256 = (& $hash $inventory) }
    smoke = @{ path = $smoke.record; sha256 = (& $hash $smoke.record) }
    report = @{ path = $release.report; sha256 = (& $hash $release.report) }
}
$marker | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $published -Encoding utf8NoBOM
(& $hash $published) | Set-Content -LiteralPath "$published.sha256" -Encoding ascii
Write-Host "PUBLISHED=$published"
Write-Host "REPORT=$($release.report)"
