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
$report = Join-Path $repo '.scientific\runtime-report.json'
$brokerProject = Join-Path $repo 'tools\scientific-broker\ScientificBroker.csproj'
$brokerRoot = Join-Path $repo 'tools\scientific-broker'
$deployment = Join-Path $repo ".scientific\broker\release-$ReleaseTag"
$manifest = Join-Path $deployment 'certified-capabilities.json'
$config = Join-Path $deployment 'repair-config.json'
if (!(Test-Path -LiteralPath $installed)) { throw 'Run desktop repair acceptance before release.' }
if (Test-Path -LiteralPath $deployment) { throw "Release deployment already exists: $deployment" }
$inventory = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
& (Join-Path $repo 'tools\Inspect-ScientificRuntimes.ps1') `
    -RuntimeRoot $inventory.runtimeRoot -OutputPath $report
$auditText = & dotnet run --project $brokerProject -- audit-repair $repo $installed $math3d desktop-five
if ($LASTEXITCODE -ne 0) { throw 'Repair qualification audit failed.' }
$audit = $auditText | ConvertFrom-Json
if (!$audit.eligible) { throw "Repair chain is not current at $($audit.earliestRequiredLevel): $($audit.exportReason)" }
New-Item -ItemType Directory -Path $deployment -Force | Out-Null
& dotnet run --project $brokerProject -- export $repo $installed $math3d desktop-five $manifest
if ($LASTEXITCODE -ne 0) { throw 'Repair capability export failed.' }
& (Join-Path $PSScriptRoot 'New-CgalRepair-BrokerProfile.ps1') -Worktree $repo `
    -Math3DCheckout $math3d -Manifest $manifest -Output $config -BrokerPython $python
$smokeText = & $python (Join-Path $brokerRoot 'repair_smoke.py') run --config $config
if ($LASTEXITCODE -ne 0) { throw "Four-case repair smoke failed: $smokeText" }
$smoke = $smokeText | ConvertFrom-Json
if ($smoke.verdict -ne 'passed' -or !(Test-Path -LiteralPath $smoke.record)) {
    throw 'Four-case repair smoke did not save a passing record.'
}
$releaseText = & $python (Join-Path $brokerRoot 'release_certification.py') certify `
    --config $config --installed-root $installed --profile-id desktop-five `
    --release-tag $ReleaseTag --smoke-record $smoke.record `
    --output-root (Join-Path $repo '.scientific\releases')
if ($LASTEXITCODE -ne 0) { throw "Repair release certification failed: $releaseText" }
$release = $releaseText | ConvertFrom-Json
if ($release.verdict -ne 'qualified') { throw "Repair release is $($release.verdict): $($release.reasons)" }
& $python (Join-Path $brokerRoot 'release_certification.py') verify --config $config --report $release.report
if ($LASTEXITCODE -ne 0) { throw 'Repair release verification failed.' }
Write-Host "CONFIG=$config"
Write-Host "SMOKE=$($smoke.record)"
Write-Host "REPORT=$($release.report)"
