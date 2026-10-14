[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Math3DPath, [string]$Destination=(Join-Path (Split-Path $PSScriptRoot -Parent) '.scientific/datasets'))
$ErrorActionPreference='Stop'
$Math3DPath=[IO.Path]::GetFullPath($Math3DPath)
$Destination=[IO.Path]::GetFullPath($Destination)
if (-not (Test-Path -LiteralPath $Math3DPath -PathType Container)) { throw 'MATH3D checkout missing.' }
if ($Destination.StartsWith($Math3DPath.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Destination must be outside the original checkout.' }
$files=@('tests/assets/meshes/basic/01_tetrahedron.obj','tests/assets/meshes/basic/02_cube.obj','tests/assets/meshes/basic/03_cube_ascii.stl','tests/assets/meshes/basic/04_cylinder.obj','tests/assets/meshes/basic/05_torus.obj','tests/assets/meshes/standard/08_stanford_bunny.obj','tests/assets/meshes/problematic/15_open_boundary.obj','tests/assets/meshes/problematic/16_non_manifold_edge.obj','tests/assets/meshes/problematic/17_disconnected_components.obj','tests/assets/meshes/problematic/18_degenerate_faces.obj','tests/assets/meshes/problematic/19_inconsistent_normals.obj','tests/assets/meshes/problematic/20_self_intersection.obj','tests/assets/mobile-mesh-import/triangle.obj','tests/assets/mobile-mesh-import/triangle-ascii.stl','tests/assets/mobile-mesh-import/triangle-ascii.ply','tests/assets/mobile-mesh-import/truncated-ascii.ply')
[IO.Directory]::CreateDirectory($Destination)|Out-Null
$entries=@()
foreach($relative in $files){
    $source=Join-Path $Math3DPath $relative
    if(-not(Test-Path -LiteralPath $source -PathType Leaf)){continue}
    $item=Get-Item -LiteralPath $source
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint)-or $item.Length -gt 33554432){throw "Unsafe/oversized dataset: $relative"}
    $category=if($relative -match '/problematic/'){'problematic'}elseif($relative -match '/standard/'){'standard'}elseif($relative -match '/mobile-mesh-import/'){'import'}else{'basic'}
    $local='math3d/'+$category+'/'+$item.Name
    $target=Join-Path $Destination $local
    [IO.Directory]::CreateDirectory((Split-Path $target -Parent))|Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
    $entries += [ordered]@{id=$local;name=$item.Name;category=$category;path=$local;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant();sourcePath=$relative;sourceRoot=$Math3DPath;expectedProblem=($category -eq 'problematic'-or $item.Name -eq 'truncated-ascii.ply')}
}
$provenance=Join-Path $Destination 'provenance'
[IO.Directory]::CreateDirectory($provenance)|Out-Null
foreach($relative in @('LICENSE','tests/assets/meshes/README.md','tests/assets/meshes/manifest.json','tests/assets/meshes/registry.json')){
    $source=Join-Path $Math3DPath $relative
    if(Test-Path -LiteralPath $source -PathType Leaf){Copy-Item -LiteralPath $source -Destination (Join-Path $provenance ([IO.Path]::GetFileName($source))) -Force}
}
$manifest=[ordered]@{schemaVersion=1;importedAt=[DateTime]::UtcNow.ToString('o');source='MATH3D local duplicates';note='Originals unchanged. Local copies only; upstream source/license terms still apply. No automatic test execution or redistribution.';entries=@($entries)}
[IO.File]::WriteAllText((Join-Path $Destination 'manifest.json'),($manifest|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Host "Duplicated $($entries.Count) datasets into $Destination. Originals unchanged; no tests run."
