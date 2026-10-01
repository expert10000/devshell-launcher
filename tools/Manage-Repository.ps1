param(
    [Parameter(Mandatory)][ValidateSet('commit','push')][string]$Action,
    [Parameter(Mandatory)][string]$Destination,
    [Parameter(Mandatory)][string]$ExpectedBranch,
    [Parameter(Mandatory)][string]$ExpectedHead,
    [string]$ExpectedIndexHash,
    [string]$Message,
    [string]$Remote,
    [string]$RemoteRef,
    [string]$ExpectedRemoteHash
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'
if (-not [IO.Path]::IsPathFullyQualified($Destination)) { throw 'An absolute repository path is required.' }
$path = [IO.Path]::GetFullPath($Destination).TrimEnd('\','/')
$prefix = @('-c', ('safe.directory=' + $path.Replace('\','/')), '-C', $path)
function Read-Git([string[]]$Arguments) {
    $result = & git @prefix @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Git state check failed (exit $LASTEXITCODE). Refresh and retry." }
    return $result
}
function Fingerprint([string]$Text) { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($Text))) }
$root = (Read-Git @('rev-parse','--show-toplevel')) -join "`n"
if ([IO.Path]::GetFullPath($root).TrimEnd('\','/') -ne $path) { throw 'Destination is not the repository root.' }
$branch = (Read-Git @('symbolic-ref','--quiet','--short','HEAD')) -join "`n"
$head = (& git @prefix rev-parse --verify HEAD 2>$null) -join "`n"
if ($LASTEXITCODE -ne 0) { $head = '(unborn)' }
if ($branch -cne $ExpectedBranch -or $head -cne $ExpectedHead) { throw 'The branch or HEAD changed since confirmation. Nothing was written; refresh and retry.' }
foreach ($operation in @('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply')) {
    $marker = (Read-Git @('rev-parse','--git-path',$operation)) -join "`n"
    if (-not [IO.Path]::IsPathRooted($marker)) { $marker = Join-Path $path $marker }
    if (Test-Path -LiteralPath $marker) { throw 'Finish the current merge/rebase/cherry-pick/revert first.' }
}
if ($Action -eq 'commit') {
    if ([string]::IsNullOrWhiteSpace($Message) -or $Message.Length -gt 4000) { throw 'A commit message of 1-4000 characters is required.' }
    $index = (Read-Git @('ls-files','--stage','-z')) -join "`n"
    if (-not $ExpectedIndexHash -or (Fingerprint $index) -cne $ExpectedIndexHash) { throw 'Staged files changed since confirmation. Nothing was committed; review and retry.' }
    & git @prefix diff --cached --quiet --exit-code --no-ext-diff --no-textconv
    if ($LASTEXITCODE -eq 0) { throw 'No staged changes.' }
    if ($LASTEXITCODE -ne 1) { throw 'Cannot inspect staged changes.' }
    Write-Host "[commit] Committing staged changes on $branch (no automatic staging)."
    & git @prefix commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Commit failed (exit $LASTEXITCODE)." }
} else {
    if ($ExpectedHead -eq '(unborn)') { throw 'There is no commit to push.' }
    $upstream = ((Read-Git @('for-each-ref','--format=%(upstream:remotename)%00%(upstream:remoteref)',('refs/heads/' + $branch))) -join "`n") -split "`0"
    if ($upstream.Count -ne 2 -or $upstream[0] -cne $Remote -or $upstream[1] -cne $RemoteRef -or $Remote -eq '.' -or -not $RemoteRef.StartsWith('refs/heads/')) { throw 'The upstream destination changed since confirmation. Nothing was pushed.' }
    $urls = @(Read-Git @('remote','get-url','--push','--all',$Remote))
    if ($urls.Count -ne 1 -or (Fingerprint $urls[0]) -cne $ExpectedRemoteHash) { throw 'The remote URL changed since confirmation. Nothing was pushed.' }
    Write-Host "[push] Pushing confirmed commit to $Remote / $RemoteRef (no force, tags, or submodule pushes)."
    & git @prefix -c "remote.$Remote.mirror=false" -c push.followTags=false push --porcelain --no-force --no-follow-tags --recurse-submodules=no -- $Remote "${ExpectedHead}:$RemoteRef"
    if ($LASTEXITCODE -ne 0) { throw "Push failed (exit $LASTEXITCODE). Fetch and inspect divergence or authentication before retrying." }
}
Write-Host "[$Action] SUCCEEDED"
