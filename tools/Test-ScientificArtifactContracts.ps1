[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$data = Join-Path $root '.scientific/datasets'
$manifest = Get-Content -LiteralPath (Join-Path $data 'manifest.json') -Raw | ConvertFrom-Json
$suite = Join-Path $root ('.scientific/tests/contracts-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[System.IO.Directory]::CreateDirectory($suite) | Out-Null
$compiler = Join-Path $root '.scientific/builds/cgal-worker-prebuild/Release/devshell_cgal_worker.exe'
$python = @{ cgal='G:\master\.conda\devshell-cgal\python.exe'; vtk='G:\master\.conda\devshell-vtk\python.exe' }
$records = [System.Collections.Generic.List[object]]::new()

function Invoke-Child([string]$Kind, [string[]]$Arguments, [string]$Directory) {
    $prefix = Split-Path $python[$Kind] -Parent
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $python[$Kind]
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false; $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $start.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
    $start.Environment['PATH'] = "$prefix;$prefix\Library\bin;$prefix\Scripts;" + $env:PATH
    $start.Environment['PYTHONNOUSERSITE'] = '1'; $start.Environment['PYTHONIOENCODING'] = 'utf-8'
    $start.Environment.Remove('PYTHONPATH') | Out-Null
    $process = [System.Diagnostics.Process]::new(); $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Child did not start' }
        $output = $process.StandardOutput.ReadToEndAsync(); $errors = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(150000)) { $process.Kill($true); $process.WaitForExit(); throw 'Test child exceeded 150 seconds' }
        $stdout = $output.GetAwaiter().GetResult(); $stderr = $errors.GetAwaiter().GetResult()
        [System.IO.File]::WriteAllText((Join-Path $Directory 'stdout.log'), $stdout)
        [System.IO.File]::WriteAllText((Join-Path $Directory 'stderr.log'), $stderr)
        return @{ exitCode=$process.ExitCode; stdout=$stdout; stderr=$stderr }
    } finally { $process.Dispose() }
}
function Check([string]$CheckName, [scriptblock]$Test) {
    try { & $Test; $records.Add(@{name=$CheckName; passed=$true}); Write-Host "$CheckName`: PASS" }
    catch { $records.Add(@{name=$CheckName; passed=$false; error=$_.Exception.Message}); Write-Host "$CheckName`: FAIL / $($_.Exception.Message)" }
}
function Require([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Run-Mesh([string]$Name, [string]$Kind, [string]$Recipe, [string]$InputId, [hashtable]$Parameters, [string]$FailurePattern = '', [switch]$WrongHash) {
    $entry = $manifest.entries | Where-Object id -EQ $InputId | Select-Object -First 1
    if (-not $entry) { throw "Fixture missing: $InputId" }
    $input = Join-Path $data $entry.path
    $directory = Join-Path $suite $Name
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    $runId = [guid]::NewGuid().ToString('N')
    $extension = if ($Kind -eq 'cgal') { 'obj' } else { 'vtp' }
    $outputName = "mesh.$extension"
    $request = @{schemaVersion=1; runId=$runId; runtimeId="$Kind-win-conda"; recipeId=$Recipe; operation=$Recipe; parameters=$Parameters; workingDirectory=$directory; datasetRoot=$data; timeoutSeconds=120;
        inputArtifacts=@(@{path=$input; mediaType='application/octet-stream'; sha256=$(if ($WrongHash) {'0' * 64} else {$entry.sha256}); bytes=$entry.bytes; datasetId=$entry.id; sourceRoot=$entry.sourceRoot; sourcePath=$entry.sourcePath});
        outputArtifacts=@(@{path=$outputName; mediaType=$(if ($Kind -eq 'cgal') {'model/obj'} else {'application/vnd.vtk.vtp'})}); provenance=@{inputPolicy='Registered copied fixtures'}}
    $file = Join-Path $directory 'request.json'
    [System.IO.File]::WriteAllText($file, ($request | ConvertTo-Json -Depth 20), [System.Text.UTF8Encoding]::new($false))
    $arguments = if ($Kind -eq 'cgal') { @((Join-Path $root 'tools/scientific-cgal-worker.py'), '--request', $file, '--worker', $compiler) } else { @((Join-Path $root 'tools/scientific-mesh-worker.py'), '--request', $file) }
    $child = Invoke-Child $Kind $arguments $directory
    $result = Get-Content -LiteralPath (Join-Path $directory 'results.json') -Raw | ConvertFrom-Json
    Require ($result.schemaVersion -eq 1 -and $result.runId -eq $runId -and $result.runtimeId -eq "$Kind-win-conda" -and $result.recipeId -eq $Recipe) 'Result identity does not match the request'
    foreach ($field in @('state', 'exitCode', 'durationMs', 'versions', 'validatedCapabilities', 'diagnostics', 'logReference', 'artifacts', 'inputArtifacts', 'provenance', 'before', 'after')) {
        Require ($result.PSObject.Properties.Name -contains $field) "Missing result field: $field"
    }
    if ($FailurePattern) {
        Require ($child.exitCode -ne 0 -and $result.state -eq 'failed' -and $result.artifacts.Count -eq 0) 'Expected a failed result without successful artifacts'
        Require (($result.diagnostics | ConvertTo-Json -Depth 10) -match $FailurePattern) 'Expected rejection reason missing from structured diagnostics'
        Require (-not (Test-Path -LiteralPath (Join-Path $directory $outputName))) 'Rejected input produced geometry'
    } else {
        Require ($child.exitCode -eq 0 -and $result.state -eq 'succeeded') "Worker failed: $($child.stderr)"
        $artifact = $result.artifacts | Select-Object -First 1
        $output = Join-Path $directory $artifact.path
        Require ((Get-Item -LiteralPath $output).Length -gt 0) 'Output is empty'
        Require ((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant() -eq $artifact.sha256) 'Output hash mismatch'
        Require ($result.inputArtifacts[0].sha256 -eq $entry.sha256) 'Input provenance hash mismatch'
        Require ($result.after.points -gt 0 -and $result.after.triangles -gt 0) 'Normalized geometry statistics missing'
    }
    return @{directory=$directory; input=$input; output=(Join-Path $directory $outputName); result=$result}
}
$cases = @{}
Check 'cgal-json-validate' { $cases.validate = Run-Mesh 'cgal-json-validate' 'cgal' 'cgal.validate' 'math3d/basic/02_cube.obj' @{} }
Check 'cgal-json-remesh' { $cases.remesh = Run-Mesh 'cgal-json-remesh' 'cgal' 'cgal.remesh' 'math3d/basic/02_cube.obj' @{targetEdge=0.02; iterations=1; preserveBoundary=$true} }
Check 'vtk-json-inspect' { $cases.inspect = Run-Mesh 'vtk-json-inspect' 'vtk' 'mesh.inspect' 'math3d/basic/01_tetrahedron.obj' @{} }
Check 'vtk-json-simplify' { $cases.simplify = Run-Mesh 'vtk-json-simplify' 'vtk' 'mesh.simplify' 'math3d/basic/05_torus.obj' @{targetReduction=0.5; preserveTopology=$true; preserveBoundary=$true} }
Check 'vtk-json-normals' { $cases.normals = Run-Mesh 'vtk-json-normals' 'vtk' 'mesh.normals' 'math3d/basic/02_cube.obj' @{featureAngle=30; autoOrient=$false} }
Check 'cgal-json-reject-degenerate' { $null = Run-Mesh 'cgal-json-reject-degenerate' 'cgal' 'cgal.validate' 'math3d/problematic/18_degenerate_faces.obj' @{} 'degenerate|not a readable manifold polygon mesh' }
Check 'vtk-json-reject-open-orientation' { $null = Run-Mesh 'vtk-json-reject-open-orientation' 'vtk' 'mesh.normals' 'math3d/problematic/15_open_boundary.obj' @{featureAngle=30; autoOrient=$true} 'closed manifold' }
Check 'reject-changed-input-hash' { $null = Run-Mesh 'reject-changed-input-hash' 'vtk' 'mesh.inspect' 'math3d/basic/01_tetrahedron.obj' @{} 'hash changed' -WrongHash }
foreach ($name in @('inspect', 'remesh')) {
    Check "preview-$name" {
        $case = $cases[$name]; if (-not $case) { throw 'Prerequisite worker case failed' }
        $directory = Join-Path $suite "preview-$name"; [System.IO.Directory]::CreateDirectory($directory) | Out-Null
        $child = Invoke-Child 'vtk' @((Join-Path $root 'tools/scientific-artifact-preview.py'), '--before', $case.input, '--after', $case.output) $directory
        Require ($child.exitCode -eq 0) "Preview failed: $($child.stderr)"
        $preview = $child.stdout | ConvertFrom-Json
        foreach ($mesh in @($preview.before, $preview.after)) {
            Require ($mesh.points -gt 0 -and $mesh.previewTriangles -gt 0 -and $mesh.previewTriangles -le 12000) 'Preview size/statistics invalid'
            Require ($mesh.positions.Count -eq $mesh.previewTriangles * 9 -and $mesh.bounds.Count -eq 6) 'Preview array shape invalid'
        }
        if ($name -eq 'remesh') { Require ($preview.after.sampled -eq $true -and $preview.after.triangles -gt 12000) 'Dense output was not labelled as sampled' }
        else { Require ($preview.after.sampled -eq $false -and $preview.after.triangles -eq 4) 'Small tetrahedron preview was altered' }
    }
}
Check 'copied-fixtures-unchanged' {
    foreach ($entry in $manifest.entries) { Require ((Get-FileHash -LiteralPath (Join-Path $data $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $entry.sha256) "Fixture changed: $($entry.id)" }
}
$passed = @($records | Where-Object passed).Count
[System.IO.File]::WriteAllText((Join-Path $suite 'test-report.json'), (@{generatedAt=[DateTime]::UtcNow.ToString('o'); passed=$passed; total=$records.Count; cases=@($records)} | ConvertTo-Json -Depth 20))
Write-Host "$passed/$($records.Count) passed; report $suite/test-report.json"
if ($passed -ne $records.Count) { exit 1 }
