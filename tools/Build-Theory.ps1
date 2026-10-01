param(
    [string]$RepositoryPath = (Get-Location).Path,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath 'main.tex') -PathType Leaf)) {
    throw "Theory main.tex was not found in $RepositoryPath"
}
Push-Location -LiteralPath $RepositoryPath
try {
    $version = (& pdflatex --version 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to run pdflatex.' }
    $arguments = @('-pdf', '-interaction=nonstopmode', '-halt-on-error')
    if ($Force) { $arguments += '-g' }
    if ($version -match 'MiKTeX') {
        # Scoped to this build; no changes to the user's MiKTeX configuration.
        $arguments += '-pdflatex=pdflatex --disable-installer -pool-size=16000000 -extra-mem-top=10000000 -extra-mem-bot=10000000 %O %S'
        # Git's Perl may identify as MSYS even when the TeX tools are native Windows.
        $root = (Get-Location).Path.Replace('\', '/').Replace("'", "\'")
        $arguments += @('-e', ('$ENV{''BIBINPUTS''} = ''' + $root + '/bibliography;' + $root + ';'';'))
        Write-Host '[Theory] MiKTeX: increased string pool and memory for this build.'
    }
    $arguments += 'main.tex'
    & latexmk @arguments
    if ($LASTEXITCODE -ne 0) { throw "Theory PDF build failed (exit $LASTEXITCODE). See build/main.log." }
    Write-Host ('[Theory] PDF build succeeded: ' + (Join-Path (Get-Location).Path 'build/main.pdf'))
}
finally { Pop-Location }
