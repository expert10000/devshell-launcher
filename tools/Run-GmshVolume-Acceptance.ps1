param(
    [int]$CdpPort = 9244,
    [string]$Math3DCheckout = $env:MATH3D_CHECKOUT,
    [string]$ExistingWorktree,
    [ValidateSet('L0', 'L7')][string]$ResumeFrom = 'L0',
    [switch]$UseRunningApp,
    [switch]$SkipBuild,
    [switch]$BootOnly
)

& (Join-Path $PSScriptRoot 'Run-Scientific-Desktop-Acceptance.ps1') -Scenario GmshVolume `
    -CdpPort $CdpPort -Math3DCheckout $Math3DCheckout -ExistingWorktree $ExistingWorktree `
    -ResumeFrom $ResumeFrom -UseRunningApp:$UseRunningApp -SkipBuild:$SkipBuild -BootOnly:$BootOnly
