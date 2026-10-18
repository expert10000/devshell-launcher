param([Parameter(Mandatory = $true)][string]$PlanJson)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$plan = $PlanJson | ConvertFrom-Json
$tools = @{}
$plan.tools.PSObject.Properties | ForEach-Object { $tools[$_.Name] = $_.Value }
$managerRoot = Join-Path $plan.root '.tools\package-managers'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

function Invoke-Native([string]$Executable, [string[]]$Arguments) {
    Write-Host ('[setup] Command: ' + $Executable + ' ' + ($Arguments -join ' '))
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed with exit code ' + $LASTEXITCODE) }
}
function Refresh-ToolPaths {
    $env:PATH = $managerRoot + ';' + (Join-Path $managerRoot 'node_modules\.bin') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + $env:PATH
}
function Resolve-Tool([string]$Name) {
    if ($tools.ContainsKey($Name) -and (Test-Path -LiteralPath $tools[$Name] -PathType Leaf)) { return $tools[$Name] }
    Refresh-ToolPaths
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source -and $command.Source -notlike '*\WindowsApps\python*') { $tools[$Name] = $command.Source; return $command.Source }
    $candidates = switch ($Name) {
        'node' { Join-Path $env:ProgramFiles 'nodejs\node.exe' }
        'git' { Join-Path $env:ProgramFiles 'Git\cmd\git.exe' }
        'pwsh' { Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe' }
        'dotnet' { Join-Path $env:ProgramFiles 'dotnet\dotnet.exe' }
        'python' { Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Directory -Filter 'Python*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'python.exe' } }
    }
    foreach ($candidate in $candidates) { if (Test-Path -LiteralPath $candidate -PathType Leaf) { $tools[$Name] = $candidate; return $candidate } }
    return $null
}
function Install-Tool([string]$Name, [int]$MinimumMajor = 8) {
    $packages = @{ node = 'OpenJS.NodeJS.LTS'; npm = 'OpenJS.NodeJS.LTS'; python = 'Python.Python.3.12'; dotnet = 'Microsoft.DotNet.SDK.8'; git = 'Git.Git'; pwsh = 'Microsoft.PowerShell'; code = 'Microsoft.VisualStudioCode' }
    if ($Name -eq 'dotnet' -and $MinimumMajor -gt 8) { $packages.dotnet = 'Microsoft.DotNet.SDK.' + $MinimumMajor }
    if (-not $packages.ContainsKey($Name)) { throw ('Install ' + $Name + ' manually, then run Setup again.') }
    $winget = Resolve-Tool 'winget'
    if (-not $winget) { throw ('WinGet is unavailable. Install ' + $Name + ' and run Setup again.') }
    Invoke-Native $winget @('install', '--id', $packages[$Name], '--exact', '--source', 'winget', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
    $tools.Remove($Name)
    if ($Name -in @('node', 'npm')) { $tools.Remove('npmCli') }
    if (-not (Resolve-Tool $Name)) { throw ('Installed ' + $Name + ', but its command is unavailable. Restart DevShell and run Setup again.') }
}
function Npm([string[]]$Arguments) {
    $node = Resolve-Tool 'node'
    if (-not $node) { Install-Tool 'node'; $node = Resolve-Tool 'node' }
    $npmCli = $tools['npmCli']
    if (-not $npmCli -or -not (Test-Path -LiteralPath $npmCli)) { $npmCli = Join-Path (Split-Path -Parent $node) 'node_modules\npm\bin\npm-cli.js' }
    if (Test-Path -LiteralPath $npmCli) { Invoke-Native $node (@($npmCli) + $Arguments) }
    else { $npm = Resolve-Tool 'npm'; if (-not $npm) { throw 'npm is missing. Install Node.js with npm, then run Setup again.' }; Invoke-Native $npm $Arguments }
}
function Node-Compatible([string]$Node, [string]$Range, [int]$MinimumMajor) {
    $version = & $Node --version
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the Node.js version.' }
    if ($MinimumMajor -and [int]($version.TrimStart('v').Split('.')[0]) -lt $MinimumMajor) { return $false }
    if ($Range) {
        $semver = Join-Path (Split-Path -Parent $Node) 'node_modules\npm\node_modules\semver'
        if ($tools['npmCli'] -and (Test-Path -LiteralPath $tools['npmCli'])) { $npmSemver = Join-Path (Split-Path -Parent (Split-Path -Parent $tools['npmCli'])) 'node_modules\semver'; if (Test-Path -LiteralPath $npmSemver) { $semver = $npmSemver } }
        if (-not (Test-Path -LiteralPath $semver)) { throw 'Cannot verify the Node version range. Install npm with Node.js, then retry.' }
        & $Node -e 'const s=require(process.argv[1]); if(!s.validRange(process.argv[2])) process.exit(2); process.exit(s.satisfies(process.argv[3].replace(/^v/, ""),process.argv[2])?0:1);' $semver $Range $version
        if ($LASTEXITCODE -eq 2) { throw 'The project declares an invalid Node.js version range.' }
        return $LASTEXITCODE -eq 0
    }
    return $true
}
function Environment-Python([string]$Directory) {
    foreach ($relative in @('Scripts\python.exe', 'python.exe')) { $candidate = Join-Path $Directory $relative; if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate } }
    return $null
}

try {
    for ($i = 0; $i -lt $plan.steps.Count; $i++) {
        $step = $plan.steps[$i]
        Write-Host ('[setup] STEP ' + ($i + 1) + '/' + $plan.steps.Count + ': ' + $step.name)
        Set-Location -LiteralPath $step.directory
        switch ($step.kind) {
            'tool' { if (-not (Resolve-Tool $step.tool)) { Install-Tool $step.tool } }
            'node' {
                $node = Resolve-Tool 'node'
                if (-not $node) { Install-Tool 'node'; $node = Resolve-Tool 'node' }
                if (-not (Node-Compatible $node $step.nodeRange $step.minimumMajor)) {
                    Write-Host ('[setup] This project requires Node.js ' + $step.nodeRange)
                    Install-Tool 'node'; $node = Resolve-Tool 'node'
                    if (-not (Node-Compatible $node $step.nodeRange $step.minimumMajor)) { throw 'The installed Node.js version still does not meet this project requirement.' }
                }
                $stepManagerRoot = if ($step.managerVersion) { Join-Path $managerRoot ($step.manager + '-' + $step.managerVersion) } else { $managerRoot }
                $managedPath = if ($step.manager -eq 'npm') { Join-Path $stepManagerRoot 'node_modules\npm\bin\npm-cli.js' } else { Join-Path $stepManagerRoot ($step.manager + '.cmd') }
                $manager = if (Test-Path -LiteralPath $managedPath -PathType Leaf) { $managedPath } else { Resolve-Tool $step.manager }
                if ($step.manager -eq 'npm' -and $manager -and -not $manager.EndsWith('.js')) { $npmCli = if ($tools['npmCli']) { $tools['npmCli'] } else { Join-Path (Split-Path -Parent $node) 'node_modules\npm\bin\npm-cli.js' }; if (Test-Path -LiteralPath $npmCli) { $manager = $npmCli } }
                if ($manager -and $step.managerVersion) {
                    $managerVersion = if ($manager.EndsWith('.js')) { & $node $manager --version } else { & $manager --version }
                    if ($LASTEXITCODE -ne 0 -or $managerVersion.Trim() -ne $step.managerVersion) { $manager = $null }
                }
                if (-not $manager -and ($step.manager -ne 'npm' -or $step.managerVersion)) {
                    $package = $step.manager + $(if ($step.managerVersion) { '@' + $step.managerVersion } else { '' })
                    Npm @('install', '--global', '--prefix', $stepManagerRoot, $package, '--no-audit', '--no-fund')
                    $manager = $managedPath
                    if (-not (Test-Path -LiteralPath $manager -PathType Leaf)) { throw ('Cannot find installed ' + $step.manager) }
                }
                if ($step.manager -eq 'npm') {
                    if ($manager -and $manager.EndsWith('.js')) { Invoke-Native $node (@($manager) + $step.arguments) }
                    else { Npm $step.arguments }
                } else { Invoke-Native $manager $step.arguments }
            }
            'python-create' {
                if (-not (Environment-Python $step.environment)) {
                    if ((Test-Path -LiteralPath $step.environment) -and (Get-ChildItem -LiteralPath $step.environment -Force | Select-Object -First 1) -and -not (Test-Path -LiteralPath (Join-Path $step.environment 'pyvenv.cfg'))) { throw ('Environment folder is nonempty and is not a Python environment: ' + $step.environment) }
                    $python = Resolve-Tool 'python'; if (-not $python) { Install-Tool 'python'; $python = Resolve-Tool 'python' }
                    Invoke-Native $python @('-m', 'venv', $step.environment)
                }
                if (-not (Environment-Python $step.environment)) { throw 'Python environment was not created.' }
            }
            'python-install' { if (Test-Path -LiteralPath (Join-Path $step.environment 'conda-meta')) { $env:CONDA_PREFIX = $step.environment; $env:PATH = $step.environment + ';' + (Join-Path $step.environment 'Library\bin') + ';' + (Join-Path $step.environment 'Scripts') + ';' + $env:PATH }; $python = Environment-Python $step.environment; if (-not $python) { throw 'Python environment is missing.' }; Invoke-Native $python $step.arguments }
            'command' {
                $tool = Resolve-Tool $step.tool
                if (-not $tool) { Install-Tool $step.tool $step.minimumMajor; $tool = Resolve-Tool $step.tool }
                if ($step.tool -eq 'dotnet') {
                    $sdks = & $tool --list-sdks
                    if ($LASTEXITCODE -ne 0 -or -not ($sdks | Where-Object { $_ -match '^(\d+)\.' -and [int]$Matches[1] -ge $step.minimumMajor })) {
                        Install-Tool 'dotnet' $step.minimumMajor; $tool = Resolve-Tool 'dotnet'
                        $sdks = & $tool --list-sdks
                        if ($LASTEXITCODE -ne 0 -or -not ($sdks | Where-Object { $_ -match '^(\d+)\.' -and [int]$Matches[1] -ge $step.minimumMajor })) { throw 'The required .NET SDK is still unavailable.' }
                    }
                }
                Invoke-Native $tool $step.arguments
            }
            'note' { Write-Host '[setup] No dependency installation is required.' }
            default { throw ('Unknown setup step: ' + $step.kind) }
        }
        Write-Host ('[setup] DONE ' + ($i + 1) + '/' + $plan.steps.Count)
    }
    Write-Host '[setup] SUCCEEDED'
} catch { Write-Host ('[setup] FAILED: ' + $_.Exception.Message); throw }
