param([string]$RuntimeRoot='G:\master\.conda')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$datasets=Join-Path $root '.scientific/datasets'
$manifest=Get-Content -LiteralPath (Join-Path $datasets 'manifest.json') -Raw | ConvertFrom-Json
$suite=Join-Path $root ('.scientific/tests/mesh-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
[void](New-Item -ItemType Directory -Path $suite)
$checks=[System.Collections.Generic.List[object]]::new()
$before=@{}
foreach($entry in $manifest.entries){$before[$entry.id]=(Get-FileHash -LiteralPath (Join-Path $datasets $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant()}
function Invoke-Case([string]$Id,[string]$Kind,[string]$Operation,[string]$InputId,[hashtable]$Parameters,[bool]$Success){
    $directory=Join-Path $suite $Id;[void](New-Item -ItemType Directory -Path $directory)
    $prefix=Join-Path $RuntimeRoot ('devshell-'+$Kind)
    $inputFile=Join-Path $datasets $InputId
    $info=[System.Diagnostics.ProcessStartInfo]::new()
    $info.WorkingDirectory=$directory;$info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $info.StandardOutputEncoding=[Text.Encoding]::UTF8;$info.StandardErrorEncoding=[Text.Encoding]::UTF8
    $info.Environment['PATH']="$prefix;$prefix\Library\bin;$prefix\Scripts;"+$env:PATH
    $info.Environment['PYTHONNOUSERSITE']='1';$info.Environment['PYTHONIOENCODING']='utf-8'
    [void]$info.Environment.Remove('PYTHONPATH')
    if($Kind -eq 'cgal'){
        $info.FileName=Join-Path $root '.scientific/builds/cgal-worker-prebuild/Release/devshell_cgal_worker.exe'
        foreach($argument in @($Operation,$inputFile,(Join-Path $directory 'output.obj'),[string]$Parameters.targetEdge,[string]$Parameters.iterations,[string]$Parameters.preserveBoundary)){$info.ArgumentList.Add($argument)}
    }else{
        $info.FileName=Join-Path $prefix 'python.exe'
        $request=@{schemaVersion=1;runId=$Id;runtimeId='vtk-win-conda';recipeId=('mesh.'+$Operation);datasetRoot=$datasets;workingDirectory=$directory;parameters=$Parameters;inputArtifacts=@(@{path=$inputFile});outputArtifacts=@(@{path='output.vtp'})}
        $requestPath=Join-Path $directory 'request.json'
        $request | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $requestPath -Encoding utf8
        $info.ArgumentList.Add((Join-Path $root 'tools/scientific-mesh-worker.py'));$info.ArgumentList.Add('--request');$info.ArgumentList.Add($requestPath)
    }
    $process=[System.Diagnostics.Process]::new();$process.StartInfo=$info
    try{
        [void]$process.Start();$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(120000)){$process.Kill($true);$process.WaitForExit();throw "Owned test $Id timed out"}
        $out=$stdout.GetAwaiter().GetResult();$err=$stderr.GetAwaiter().GetResult()
        $out | Set-Content -LiteralPath (Join-Path $directory 'stdout.log') -Encoding utf8
        $err | Set-Content -LiteralPath (Join-Path $directory 'stderr.log') -Encoding utf8
        $resultPath=Join-Path $directory 'results.json';$result=$null
        if(Test-Path -LiteralPath $resultPath){$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json}
        $artifact=Join-Path $directory $(if($Kind -eq 'cgal'){'output.obj'}else{'output.vtp'})
        $passed=if($Success){$process.ExitCode -eq 0 -and $result.state -eq 'succeeded' -and (Test-Path -LiteralPath $artifact) -and (Get-Item -LiteralPath $artifact).Length -gt 0}else{$process.ExitCode -ne 0}
        if(-not $Success){
            $reason=if($Kind -eq 'cgal'){$result.error}else{$err}
            $expectedReason=switch($Id){
                'cgal-reject-degenerate' {'degenerate|not a readable manifold'}
                'cgal-reject-budget' {'conservative laboratory budget'}
                'vtk-reject-open-auto-orient' {'Auto orientation requires a closed manifold surface'}
                'vtk-reject-truncated-ply' {'Reader failed or surface is empty|Operation failed or surface is empty'}
                default {'(?!)'}
            }
            $passed=$passed -and $reason -match $expectedReason -and -not(Test-Path -LiteralPath $artifact)
        }
        if($passed -and $Success -and $Operation -eq 'simplify'){$passed=$result.after.triangles -le $result.before.triangles}
        if($passed -and $Success -and $Kind -eq 'cgal' -and $Operation -eq 'remesh'){$passed=$result.after.faces -gt 0 -and $result.versions.cgal}
        $checks.Add([pscustomobject]@{id=$Id;passed=[bool]$passed;expectedSuccess=$Success;exitCode=$process.ExitCode;result=$result;error=$err;directory=$directory})
        Write-Output ("{0}: {1} (exit {2})" -f $Id,$(if($passed){'PASS'}else{'FAIL'}),$process.ExitCode)
    }finally{$process.Dispose()}
}
$cgal=@{targetEdge='0.25';iterations='1';preserveBoundary='1'}
Invoke-Case 'cgal-validate-cube' cgal validate 'math3d/basic/02_cube.obj' $cgal $true
Invoke-Case 'cgal-remesh-tetrahedron' cgal remesh 'math3d/basic/01_tetrahedron.obj' $cgal $true
Invoke-Case 'cgal-reject-degenerate' cgal validate 'math3d/problematic/18_degenerate_faces.obj' $cgal $false
Invoke-Case 'cgal-reject-budget' cgal remesh 'math3d/basic/01_tetrahedron.obj' @{targetEdge='0.000001';iterations='1';preserveBoundary='1'} $false
Invoke-Case 'vtk-inspect-tetrahedron' vtk inspect 'math3d/basic/01_tetrahedron.obj' @{} $true
Invoke-Case 'vtk-simplify-torus' vtk simplify 'math3d/basic/05_torus.obj' @{targetReduction=0.5;preserveTopology=$true;preserveBoundary=$true} $true
Invoke-Case 'vtk-normals-cube' vtk normals 'math3d/basic/02_cube.obj' @{featureAngle=30;autoOrient=$false} $true
Invoke-Case 'vtk-reject-open-auto-orient' vtk normals 'math3d/import/triangle.obj' @{featureAngle=30;autoOrient=$true} $false
Invoke-Case 'vtk-reject-truncated-ply' vtk inspect 'math3d/import/truncated-ascii.ply' @{} $false
$unchanged=$true;$provenance=$true
foreach($entry in $manifest.entries){
    $hash=(Get-FileHash -LiteralPath (Join-Path $datasets $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant()
    if($hash -ne $before[$entry.id] -or $hash -ne $entry.sha256){$unchanged=$false}
    $sourceHash=(Get-FileHash -LiteralPath (Join-Path $entry.sourceRoot $entry.sourcePath) -Algorithm SHA256).Hash.ToLowerInvariant()
    if($sourceHash -ne $entry.sha256){$provenance=$false}
}
$checks.Add([pscustomobject]@{id='all-16-copies-unchanged';passed=$unchanged})
$checks.Add([pscustomobject]@{id='all-16-source-hashes-match';passed=$provenance})
$failed=@($checks | Where-Object {-not $_.passed})
$report=@{schemaVersion=1;generatedAt=[DateTime]::UtcNow.ToString('o');checks=$checks.ToArray();passed=($checks.Count-$failed.Count);failed=$failed.Count}
$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $suite 'test-report.json') -Encoding utf8
Write-Output ("Suite: {0}; passed {1}/{2}" -f $suite,$report.passed,$checks.Count)
if($failed.Count){exit 1}
