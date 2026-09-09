param(
    [Parameter(Mandatory = $true)][string]$RepositoryUrl,
    [Parameter(Mandatory = $true)][string]$Destination
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function Assert-GitSuccess([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (git exit code $LASTEXITCODE)." }
}

function Normalize-Origin([string]$Url) {
    return ($Url.Trim().TrimEnd('/') -replace '\.git$', '')
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is not installed or not on PATH.' }
    if ($RepositoryUrl -notmatch '^https://[^/]+/.+') { throw 'An HTTPS repository URL is required.' }
    if (-not [IO.Path]::IsPathRooted($Destination)) { throw 'An absolute destination path is required.' }
    $path = [IO.Path]::GetFullPath($Destination).TrimEnd('\', '/')
    Write-Host ("[sync] {0} | {1}" -f (Get-Date -Format o), $path)
    if (Test-Path -LiteralPath $path) {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw 'Destination is not a directory.' }
        if (-not (Test-Path -LiteralPath (Join-Path $path '.git'))) {
            if (Get-ChildItem -LiteralPath $path -Force | Select-Object -First 1) {
                throw 'Destination is nonempty and is not a Git checkout. Nothing was overwritten.'
            }
            $clone = $true
        } else { $clone = $false }
    } else { $clone = $true }

    if ($clone) {
        $parent = Split-Path -Parent $path
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Write-Host "[sync] Cloning $RepositoryUrl"
        & git clone --progress -- $RepositoryUrl $path
        Assert-GitSuccess 'Clone'
    } else {
        $top = & git -C $path rev-parse --show-toplevel
        Assert-GitSuccess 'Locate checkout'
        if ([IO.Path]::GetFullPath($top).TrimEnd('\', '/') -ne $path) { throw 'Destination is not the checkout root.' }
        $origin = & git -C $path remote get-url origin
        Assert-GitSuccess 'Read origin'
        if ((Normalize-Origin $origin) -cne (Normalize-Origin $RepositoryUrl)) { throw "Unexpected origin: $origin" }
        $changes = & git -C $path status --porcelain --untracked-files=normal
        Assert-GitSuccess 'Read working tree status'
        if ($changes) { throw 'Local changes or untracked files exist. Commit, stash, or move them before updating.' }
        $branch = & git -C $path symbolic-ref --quiet --short HEAD
        Assert-GitSuccess 'Read branch (detached HEAD cannot be updated)'
        $remote = & git -C $path config --get "branch.$branch.remote"
        Assert-GitSuccess 'Read upstream remote'
        if ($remote -ne 'origin') { throw 'The current branch must track origin. No branch was changed.' }
        Write-Host "[sync] Pulling $branch (fast-forward only)"
        & git -C $path pull --ff-only --no-rebase --progress
        Assert-GitSuccess 'Pull'
    }
    Write-Host '[sync] SUCCEEDED' -ForegroundColor Green
} catch {
    Write-Host ("[sync] FAILED: " + $_.Exception.Message) -ForegroundColor Red
    throw
}
