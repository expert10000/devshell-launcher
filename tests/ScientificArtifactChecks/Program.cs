using BatchLauncher;
using System.Text.Json;
using System.Text.Json.Nodes;

var directory = Path.Combine(Path.GetTempPath(), "devshell-scientific-artifacts-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(Path.Combine(directory, "render"));
File.WriteAllText(Path.Combine(directory, "sphere.vtp"), "<VTKFile/>\n");
var png = Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=");
File.WriteAllBytes(Path.Combine(directory, "render", "vtk-offscreen.png"), png);
int count = 0;
void Check(bool condition, string label) { if (!condition) throw new Exception(label); count++; Console.WriteLine("PASS: " + label); }
void Reject(Action action, string label)
{
    try { action(); } catch (Exception exception) when (exception is InvalidOperationException or ArgumentException or IOException or InvalidDataException) { Check(true, label); return; }
    throw new Exception(label);
}
JsonElement Element(JsonNode node) => JsonSerializer.SerializeToElement(node);
var legacy = new JsonObject {
    ["runId"] = new string('a', 32), ["profileId"] = "test-profile", ["runtimeId"] = "vtk-win-conda", ["recipeId"] = "test-all",
    ["state"] = "succeeded", ["artifact"] = "sphere.vtp", ["artifacts"] = new JsonArray(),
    ["rendering"] = new JsonObject { ["state"] = "succeeded", ["artifact"] = "vtk-offscreen.png" }
};
var request = new JsonObject {
    ["runId"] = new string('a', 32), ["profileId"] = "test-profile", ["runtimeId"] = "vtk-win-conda", ["recipeId"] = "test-all", ["outputArtifacts"] = new JsonArray()
};
void SaveRequest() => File.WriteAllText(Path.Combine(directory, "request.json"), request.ToJsonString());
SaveRequest();
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "test-all").SequenceEqual(new[] { "sphere.vtp", "render/vtk-offscreen.png" }), "VTK test-all declares mesh and PNG");
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "run").SequenceEqual(new[] { "sphere.vtp" }), "VTK run declares only its mesh");
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "configure").Length == 0 && ScientificArtifactFiles.SmokeOutputs("cgal-win-conda", "test-all").Length == 0, "other recipes do not acquire VTK outputs");
var artifacts = new JsonArray(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "test-all").Select(path => (JsonNode?)ScientificArtifactFiles.Describe(directory, path)).ToArray());
Check(artifacts.Count == 2 && artifacts[1]!["mediaType"]!.GetValue<string>() == "image/png", "fresh output records have correct media types");
Check(artifacts[0]!["bytes"]!.GetValue<long>() > 0 && artifacts[0]!["sha256"]!.GetValue<string>().Length == 64, "output size and SHA-256 recorded");
var current = (JsonObject)legacy.DeepClone(); current["artifacts"] = artifacts;
Check(ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp").EndsWith("sphere.vtp"), "registered mesh resolves for open/reveal");
var preview = ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png");
Check(preview.MimeType == "image/png" && Convert.FromBase64String(preview.DataUrl.Split(',')[1]).SequenceEqual(png), "registered PNG reaches inline preview unchanged");
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "sphere.vtp"), "mesh cannot masquerade as PNG");
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "request.json"), "unregistered file rejected");
var escaped = (JsonObject)current.DeepClone(); escaped["artifacts"] = new JsonArray(new JsonObject { ["path"] = "../outside.png" });
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(escaped), "../outside.png"), "registered path cannot escape run directory");
File.AppendAllText(Path.Combine(directory, "sphere.vtp"), "changed");
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp"), "changed mesh rejected");
File.WriteAllText(Path.Combine(directory, "sphere.vtp"), "<VTKFile/>\n");
File.Move(Path.Combine(directory, "sphere.vtp"), Path.Combine(directory, "saved.vtp"));
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp"), "missing output rejected");
File.Move(Path.Combine(directory, "saved.vtp"), Path.Combine(directory, "sphere.vtp"));
var recovered = ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy));
Check(recovered.GetProperty("artifacts").GetArrayLength() == 2 && recovered.GetProperty("artifacts")[0].GetProperty("recoveredFromLegacyRun").GetBoolean(), "legacy successful VTK outputs recovered and labelled");
Check(legacy["artifacts"]!.AsArray().Count == 0, "legacy result source remains unchanged");
foreach (var state in new[] { "failed", "cancelled", "timed-out" })
{
    var failed = (JsonObject)legacy.DeepClone(); failed["state"] = state;
    Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(failed)).GetProperty("artifacts").GetArrayLength() == 0, state + " run does not advertise output files");
    failed["artifacts"] = artifacts.DeepClone();
    Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(failed), "sphere.vtp"), state + " run cannot open successful output");
}
var noEvidence = (JsonObject)legacy.DeepClone(); noEvidence.Remove("artifact"); noEvidence.Remove("rendering");
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(noEvidence)).GetProperty("artifacts").GetArrayLength() == 0, "files without legacy worker evidence not discovered");
request["outputArtifacts"] = new JsonArray(new JsonObject { ["path"] = "sphere.vtp" }); SaveRequest();
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy)).GetProperty("artifacts").GetArrayLength() == 0, "new request cannot acquire outputs through legacy fallback");
request["outputArtifacts"] = new JsonArray(); request["profileId"] = "other-profile"; SaveRequest();
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy)).GetProperty("artifacts").GetArrayLength() == 0, "mismatched legacy request not recovered");
File.WriteAllText(Path.Combine(directory, "render", "vtk-offscreen.png"), "not a PNG");
current["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(directory, "render/vtk-offscreen.png"));
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png"), "wrong PNG signature rejected even with matching hash");
using (var file = File.Create(Path.Combine(directory, "render", "vtk-offscreen.png"))) file.SetLength(WorkspaceFiles.MaxImageBytes + 1L);
current["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(directory, "render/vtk-offscreen.png"));
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png"), "oversized image rejected");
var dataRoot = Path.Combine(directory, "preparation");
var mathRoot = Path.Combine(directory, "Math3D");
var source = Path.Combine(mathRoot, "tests", "assets", "meshes", "basic", "02_cube.obj");
Directory.CreateDirectory(Path.GetDirectoryName(source)!);
File.WriteAllText(source, "cube source fixture");
var sourceHash = ScientificArtifactFiles.Hash(source);
var datasetId = ScientificMath3DPreparation.DatasetIds[1];
ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, datasetId);
var manifestPath = Path.Combine(dataRoot, "datasets", "manifest.json");
var manifest = JsonNode.Parse(File.ReadAllText(manifestPath))!;
manifest["entries"]!.AsArray().Add(new JsonObject { ["id"] = "unrelated", ["path"] = "retained.obj" });
File.WriteAllText(manifestPath, manifest.ToJsonString());
ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, datasetId);
manifest = JsonNode.Parse(File.ReadAllText(manifestPath))!;
Check(manifest["entries"]!.AsArray().Count == 2 && ScientificArtifactFiles.Hash(source) == sourceHash, "fixture preparation preserves unrelated datasets and source files");
var input = new JsonObject { ["datasetId"] = datasetId, ["path"] = Path.Combine(dataRoot, "datasets", datasetId), ["sha256"] = sourceHash };
var prefix = Path.Combine(directory, "dedicated-cgal");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "missing validation baseline requires preparation");
var baselineFolder = Path.Combine(dataRoot, "runs", new string('b', 32));
Directory.CreateDirectory(baselineFolder);
File.WriteAllText(Path.Combine(baselineFolder, "validated.obj"), "validated fixture");
var baseline = new JsonObject { ["runId"] = new string('b', 32), ["profileId"] = "laptop", ["runtimeId"] = "cgal-win-conda", ["recipeId"] = "cgal.validate", ["state"] = "succeeded",
    ["diagnostics"] = new JsonArray(), ["inputArtifacts"] = new JsonArray(input.DeepClone()), ["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(baselineFolder, "validated.obj")),
    ["steps"] = new JsonArray(new JsonObject { ["stage"] = "configure", ["executable"] = Path.Combine(prefix, "Library", "bin", "cmake.exe") }) };
void SaveBaseline() => File.WriteAllText(Path.Combine(baselineFolder, "results.json"), baseline.ToJsonString());
SaveBaseline();
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) != null, "matching verified baseline reused");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "other-profile", prefix, input) == null, "baseline from another profile not reused");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix + "-changed", input) == null, "baseline from another environment not reused");
var changedInput = (JsonObject)input.DeepClone(); changedInput["sha256"] = new string('0', 64);
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, changedInput) == null, "baseline for a changed input not reused");
File.AppendAllText(Path.Combine(baselineFolder, "validated.obj"), "tampered");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "changed baseline output forces validation again");
baseline["state"] = "cancelled"; SaveBaseline();
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "cancelled preparation never supplies a baseline");
Reject(() => ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, "../unsafe.obj"), "preparation accepts only the registered integration fixtures");
var booleanRequest = new JsonObject { ["inputAId"] = "cube-a.obj", ["inputBId"] = "cube-b.obj", ["operation"] = "difference", ["outputName"] = "result.m3dm", ["scaleB"] = 0.5,
    ["translateB"] = new JsonArray(0, 0, 0) };
Check(ScientificBooleanParameters.Parse(Element(booleanRequest)).ScaleB == 0.5, "Boolean parameters retain operation and placement");
foreach (var invalid in new[] { "../result.m3dm", "operand-a.m3dm", "result.obj", "C:/result.m3dm" })
{
    var invalidOutput = (JsonObject)booleanRequest.DeepClone(); invalidOutput["outputName"] = invalid;
    Reject(() => ScientificBooleanParameters.Parse(Element(invalidOutput)), "unsafe/reserved Boolean output rejected: " + invalid);
}
var invalidScale = (JsonObject)booleanRequest.DeepClone(); invalidScale["scaleB"] = -1;
Reject(() => ScientificBooleanParameters.Parse(Element(invalidScale)), "negative Boolean scale rejected");
var invalidTranslation = (JsonObject)booleanRequest.DeepClone(); invalidTranslation["translateB"] = new JsonArray(0, 0);
Reject(() => ScientificBooleanParameters.Parse(Element(invalidTranslation)), "incomplete Boolean placement rejected");

var progressRecords = new JsonArray(new JsonObject { ["name"] = "cube.obj", ["state"] = "validating" });
var importProgress = ScientificMeshImports.Progress(new string('e',32), "laptop", progressRecords);
Check(importProgress["validatedCapabilities"]!.AsArray().Count == 0 && importProgress["artifacts"]!.AsArray().Count == 0 && importProgress["state"]!.GetValue<string>() == "running", "import progress uses a complete result envelope without claiming capabilities or artifacts");
progressRecords[0]!["state"] = "passed";
Check(importProgress["imports"]![0]!["state"]!.GetValue<string>() == "validating", "published import progress snapshots remain immutable");
var importRoot = Path.Combine(directory, "user-imports");
var userMesh = Path.Combine(directory, "my cube.obj");
File.WriteAllText(userMesh, "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n");
var originalBytes = File.ReadAllBytes(userMesh);
var imported = ScientificMeshImports.Import(importRoot, userMesh);
var importedId = imported["id"]!.GetValue<string>();
var importedPath = ScientificArtifactFiles.ScopedFile(Path.Combine(importRoot, "datasets"), importedId);
Check(File.ReadAllBytes(importedPath).SequenceEqual(originalBytes) && File.ReadAllBytes(userMesh).SequenceEqual(originalBytes), "mesh import copies exact bytes without changing the source");
Check(imported["sha256"]!.GetValue<string>() == ScientificArtifactFiles.Hash(userMesh) && importedId.EndsWith("mesh-my_cube.obj"), "import registers a hash and safe content-addressed filename");
ScientificMeshImports.Import(importRoot, userMesh);
Check(ScientificMeshImports.ReadManifest(importRoot)["entries"]!.AsArray().Count == 1, "importing identical bytes and filename reuses the registered copy");
ScientificMeshImports.SaveValidation(importRoot, importedId, imported["sha256"]!.GetValue<string>(), new JsonObject { ["state"] = "open", ["closed"] = false });
Check(ScientificMeshImports.ReadManifest(importRoot)["entries"]![0]!["validation"]!["state"]!.GetValue<string>() == "open", "validation status is recorded against the registered identity");
Reject(() => ScientificMeshImports.SaveValidation(importRoot, importedId, new string('0',64), new JsonObject()), "validation cannot attach to different input bytes");
File.AppendAllText(userMesh, "# new version\n");
var newer = ScientificMeshImports.Import(importRoot, userMesh);
Check(newer["id"]!.GetValue<string>() != importedId && File.ReadAllBytes(importedPath).SequenceEqual(originalBytes), "a changed source creates a new copy and preserves the old operand");
Check(ScientificMeshImports.ReadManifest(importRoot)["entries"]!.AsArray().Count == 2, "new imports preserve existing registrations and validation metadata");
File.WriteAllText(importedPath, "changed local copy");
var sameOriginal = Path.Combine(directory, "original-source", "my cube.obj");
Directory.CreateDirectory(Path.GetDirectoryName(sameOriginal)!); File.WriteAllBytes(sameOriginal, originalBytes);
Reject(() => ScientificMeshImports.Import(importRoot, sameOriginal), "a modified registered copy cannot be silently overwritten");
foreach(var extension in new[]{".stl", ".ply", ".off"})
{
    var file = Path.Combine(directory,"mesh"+extension); File.WriteAllText(file,"fixture");
    Check(ScientificMeshImports.Import(importRoot,file)["path"]!.GetValue<string>().EndsWith(extension), "import supports " + extension);
}
var unsupported = Path.Combine(directory,"unsafe.exe"); File.WriteAllText(unsupported,"fixture");
Reject(() => ScientificMeshImports.Import(importRoot,unsupported), "unsupported import types rejected");
var oversized = Path.Combine(directory,"large.obj"); using(var file=File.Create(oversized)) file.SetLength(ScientificMeshImports.MaxBytes+1);
Reject(() => ScientificMeshImports.Import(importRoot,oversized), "oversized mesh rejected before copying");
var empty = Path.Combine(directory,"empty.obj");File.WriteAllText(empty,"");
Reject(() => ScientificMeshImports.Import(importRoot,empty), "empty input rejected");
using(var stopped=new CancellationTokenSource())
{
    stopped.Cancel();var rejected=false;
    try { ScientificMeshImports.Import(importRoot,userMesh,stopped.Token); } catch(OperationCanceledException) { rejected=true; }
    Check(rejected,"cancelled import does not start copying");
}
var replayId=new string('c',32);
var recordedInput=new JsonObject { ["datasetId"]="cube-a.obj", ["sha256"]=new string('a',64), ["bytes"]=42L };
var recordedSecond=(JsonObject)recordedInput.DeepClone();recordedSecond["datasetId"]="cube-b.obj";
var replayRequest=new JsonObject { ["runId"]=replayId, ["profileId"]="laptop", ["runtimeId"]="cgal-win-conda", ["recipeId"]="cgal.boolean",
    ["parameters"]=booleanRequest.DeepClone(), ["inputArtifacts"]=new JsonArray(recordedInput.DeepClone(),recordedSecond.DeepClone()) };
var replayResult=new JsonObject { ["runId"]=replayId, ["profileId"]="laptop", ["runtimeId"]="cgal-win-conda", ["recipeId"]="cgal.boolean", ["state"]="cancelled", ["inputArtifacts"]=replayRequest["inputArtifacts"]!.DeepClone() };
var beforeReplay=replayRequest.ToJsonString();
var restored=ScientificBooleanReplay.Read(Element(replayRequest),Element(replayResult),"laptop");
Check(restored.InputAId=="cube-a.obj" && restored.InputBId=="cube-b.obj" && restored.Operation=="difference" && restored.ScaleB==0.5 && restored.TranslateB.SequenceEqual(new[]{0.0,0,0}),"rerun restores both operands, operation, scale, and translation even for a stopped run");
Check(replayRequest.ToJsonString()==beforeReplay,"preparing a rerun preserves the saved request");
ScientificBooleanReplay.VerifyInput(Element(recordedInput),recordedInput);
Check(true,"rerun accepts matching registered input size and hash");
var changedReplay=(JsonObject)recordedInput.DeepClone();changedReplay["sha256"]=new string('b',64);
Reject(()=>ScientificBooleanReplay.VerifyInput(Element(recordedInput),changedReplay),"rerun rejects changed operand hashes");
changedReplay=(JsonObject)recordedInput.DeepClone();changedReplay["bytes"]=43L;
Reject(()=>ScientificBooleanReplay.VerifyInput(Element(recordedInput),changedReplay),"rerun rejects changed operand sizes");
Reject(()=>ScientificBooleanReplay.Read(Element(replayRequest),Element(replayResult),"other-profile"),"rerun cannot cross profile boundaries");
var mismatch=(JsonObject)replayResult.DeepClone();mismatch["runId"]=new string('d',32);
Reject(()=>ScientificBooleanReplay.Read(Element(replayRequest),Element(mismatch),"laptop"),"rerun rejects mismatched saved request and result");
var changedRecord=(JsonObject)replayResult.DeepClone();changedRecord["inputArtifacts"]![0]!["sha256"]=new string('f',64);
Reject(()=>ScientificBooleanReplay.Read(Element(replayRequest),Element(changedRecord),"laptop"),"rerun rejects different operand evidence in the saved result");
var swapped=(JsonObject)replayRequest.DeepClone();swapped["inputArtifacts"]![0]!["datasetId"]="cube-b.obj";
Reject(()=>ScientificBooleanReplay.Read(Element(swapped),Element(replayResult),"laptop"),"rerun rejects operand order mismatch");

var fingerprintRoot=Path.Combine(directory,"fingerprint-source");
var manifestFolder=Path.Combine(fingerprintRoot,"runtimes","vtk-win-conda");Directory.CreateDirectory(manifestFolder);
var manifestFile=Path.Combine(manifestFolder,"runtime.json");File.WriteAllText(manifestFile,"{\"schemaVersion\":1}");
var fingerprintA=ScientificRunFingerprint.Capture("vtk-win-conda","laptop",fingerprintRoot,fingerprintRoot);
var runA=Path.Combine(directory,"fingerprint-a");var runB=Path.Combine(directory,"fingerprint-b");Directory.CreateDirectory(runA);Directory.CreateDirectory(runB);
var workerFile=Path.Combine(directory,"worker.exe");File.WriteAllText(workerFile,"worker version one");
var executed=new[]{ScientificRunFingerprint.ExecutedFile(workerFile,"executable")};
var digestA=ScientificRunFingerprint.Save(runA,fingerprintA,executed);
var digestB=ScientificRunFingerprint.Save(runB,fingerprintA,executed);
Check(digestA==digestB && digestA.Length==64,"identical run inputs share a stable fingerprint across run folders");
ScientificRunFingerprint.Verify(runA,digestA);
Check(true,"saved fingerprint verifies against its result digest");
Reject(()=>ScientificRunFingerprint.Save(runA,fingerprintA,executed),"saved fingerprint cannot be overwritten");
var fingerprintText=File.ReadAllText(Path.Combine(runA,"fingerprint.json"));
Check(!fingerprintText.Contains(directory,StringComparison.OrdinalIgnoreCase) && fingerprintText.Contains("\"runtimeManifest\""),"portable fingerprint records manifest identity without local paths");
File.WriteAllText(workerFile,"worker version two");
var runC=Path.Combine(directory,"fingerprint-c");Directory.CreateDirectory(runC);
Check(ScientificRunFingerprint.Save(runC,fingerprintA,new[]{ScientificRunFingerprint.ExecutedFile(workerFile,"executable")})!=digestA,"worker change invalidates run fingerprint");
File.AppendAllText(Path.Combine(runB,"fingerprint.json")," ");
ScientificRunFingerprint.Verify(runB,digestB);
var altered=File.ReadAllText(Path.Combine(runB,"fingerprint.json")).Replace("vtk-win-conda","vtk-other");
File.WriteAllText(Path.Combine(runB,"fingerprint.json"),altered);
Reject(()=>ScientificRunFingerprint.Verify(runB,digestB),"altered fingerprint is rejected");
File.WriteAllText(manifestFile,"{\"schemaVersion\":2}");
var runD=Path.Combine(directory,"fingerprint-d");Directory.CreateDirectory(runD);
Check(ScientificRunFingerprint.Save(runD,ScientificRunFingerprint.Capture("vtk-win-conda","laptop",fingerprintRoot,fingerprintRoot),executed)!=digestA,"contract manifest change invalidates run fingerprint");
var sageFingerprint=ScientificRunFingerprint.Capture("sage-wsl","laptop",fingerprintRoot,fingerprintRoot,wslDistro:"Ubuntu");
Check(sageFingerprint["environment"]?["wslProviderBinary"]?.GetValue<string>()=="unavailable from Windows host","WSL provider hash is explicitly unavailable from Windows");
Check(ScientificRunFingerprint.CommandIdentity("sage.factor-smoke","command one")["sha256"]?.GetValue<string>() != ScientificRunFingerprint.CommandIdentity("sage.factor-smoke","command two")["sha256"]?.GetValue<string>(),"Sage command change invalidates worker identity");
var wslFiles=new List<JsonObject>();
var sageHash=new string('a',64);var historyHash=new string('b',64);var packageHash=new string('c',64);var shellHash=new string('d',64);var systemHash=new string('e',64);
ScientificRunFingerprint.RecordWslEvidence(sageFingerprint,wslFiles,$"[fingerprint] sage={sageHash}\n[fingerprint] condaHistory={historyHash}\n[fingerprint] condaPackages={packageHash}\n[fingerprint] systemPackages={systemHash}\n[fingerprint] wslShell={shellHash}\n");
Check(sageFingerprint["environment"]?["wslProviderBinary"]?["sha256"]?.GetValue<string>()==sageHash
    && sageFingerprint["environment"]?["condaHistory"]?["sha256"]?.GetValue<string>()==historyHash
    && sageFingerprint["environment"]?["condaPackageRecords"]?["sha256"]?.GetValue<string>()==packageHash
    && sageFingerprint["environment"]?["systemPackageRecords"]?["sha256"]?.GetValue<string>()==systemHash
    && sageFingerprint["environment"]?["toolchain"]?["wslShell"]?["sha256"]?.GetValue<string>()==shellHash
    && wslFiles.Count==1 && wslFiles[0]["sha256"]?.GetValue<string>()==sageHash,
    "WSL provider, Conda packages, and shell hashes join the immutable run fingerprint");
Check(!sageFingerprint.ToJsonString().Contains("/home/",StringComparison.Ordinal),"WSL fingerprint omits private provider paths");
var providers=ScientificProviderRegistry.Providers;
Check(providers.Count==5 && providers.Select(item=>item.RuntimeId).Distinct().Count()==5,"five unique native provider registrations");
foreach(var provider in providers)
{
    using var manifestDocument=JsonDocument.Parse(File.ReadAllText(Path.Combine("runtimes",provider.RuntimeId,"runtime.json")));
    var registered=manifestDocument.RootElement;
    Check(registered.GetProperty("schemaVersion").GetInt32()==ScientificProviderRegistry.ContractVersion
        && registered.GetProperty("id").GetString()==provider.RuntimeId
        && registered.GetProperty("execution").GetString()==provider.Backend,
        "native registry matches "+provider.RuntimeId+" manifest contract");
    Check(ScientificProviderRegistry.RequireAction(provider.RuntimeId,"lab-probe")==provider,"registered provider accepts its own probe");
}
Reject(()=>ScientificProviderRegistry.RequireAction("vtk-win-conda","boolean-recipe"),"VTK rejects CGAL Boolean action");
Reject(()=>ScientificProviderRegistry.RequireAction("cgal-win-conda","sage-recipe"),"CGAL rejects Sage action");
Reject(()=>ScientificProviderRegistry.RequireAction("gmsh-win-conda","recipe"),"Gmsh rejects unmanaged recipe action");
Reject(()=>ScientificProviderRegistry.RequireAction("sage-wsl","import-meshes"),"Sage rejects CGAL import action");
foreach(var name in new[]{"tools/scientific_worker_contract.py","tools/runtime-lab/Program.cs",
    "BatchLauncher/ScientificProviderRegistry.cs","BatchLauncher/ScientificRunFingerprint.cs",
    "tools/scientific-mesh-worker.py","tools/scientific-vtk-render-check.py",
    "BatchLauncher/Form1.Scientific.cs","BatchLauncher/Form1.Scientific.Artifacts.cs",
    "BatchLauncher/ScientificArtifactFiles.cs","BatchLauncher/Form1.Scientific.VtkRejections.cs"})
{
    var file=Path.Combine(fingerprintRoot,name.Replace('/',Path.DirectorySeparatorChar));
    Directory.CreateDirectory(Path.GetDirectoryName(file)!);File.WriteAllText(file,name);
}
var prefixRoot=Path.Combine(directory,"environment");var condaMeta=Path.Combine(prefixRoot,"conda-meta");Directory.CreateDirectory(condaMeta);
File.WriteAllText(Path.Combine(condaMeta,"history"),"conda history");
File.WriteAllText(Path.Combine(condaMeta,"vtk-9.json"),"{\"version\":\"9\"}");
File.WriteAllText(Path.Combine(condaMeta,"numpy-2.json"),"{\"version\":\"2\"}");
var cmake=Path.Combine(prefixRoot,"Library","bin","cmake.exe");Directory.CreateDirectory(Path.GetDirectoryName(cmake)!);File.WriteAllText(cmake,"cmake binary");
var ninja=Path.Combine(prefixRoot,"Library","bin","ninja.exe");File.WriteAllText(ninja,"ninja binary");
File.WriteAllText(Path.Combine(prefixRoot,"python.exe"),"python binary");
var runtimeLab=Path.Combine(fingerprintRoot,"runtime-lab","runtime-lab.exe");Directory.CreateDirectory(Path.GetDirectoryName(runtimeLab)!);File.WriteAllText(runtimeLab,"runtime-lab binary");
var wslQualified=ScientificRunFingerprint.Capture("sage-wsl","laptop",fingerprintRoot,fingerprintRoot,wslDistro:"Ubuntu",recipeId:"sage.version");
var wslEvidence=$"[fingerprint] sage={sageHash}\n[fingerprint] systemPackages={systemHash}\n[fingerprint] wslShell={shellHash}\n[fingerprint] wslTimeout={historyHash}\n";
ScientificRunFingerprint.RecordWslEvidence(wslQualified,new List<JsonObject>(),wslEvidence);
var wslQualifiedRun=Path.Combine(directory,"wsl-qualified-run");Directory.CreateDirectory(wslQualifiedRun);
ScientificRunFingerprint.Save(wslQualifiedRun,wslQualified,Array.Empty<JsonObject>());
Check(ScientificRunFingerprint.AssessEnvironmentDrift(wslQualifiedRun,fingerprintRoot,null,"Ubuntu",wslEvidence)["state"]?.GetValue<string>()=="current",
    "matching WSL system packages, provider, and toolchain are current");
Check(ScientificRunFingerprint.AssessEnvironmentDrift(wslQualifiedRun,fingerprintRoot,null,"Ubuntu",wslEvidence.Replace(systemHash,new string('f',64)))["state"]?.GetValue<string>()=="stale",
    "changed WSL system packages mark saved environment stale");
var compilerFile=Path.Combine(directory,"cl.exe");File.WriteAllText(compilerFile,"compiler binary");
var reportFile=Path.Combine(fingerprintRoot,"report.json");
File.WriteAllText(reportFile,JsonSerializer.Serialize(new { compiler=new { path=compilerFile }, runtimes=new[]{new { id="vtk-win-conda",environmentRoot=prefixRoot }} }));
var qualified=ScientificRunFingerprint.Capture("vtk-win-conda","laptop",fingerprintRoot,fingerprintRoot,reportFile,recipeId:"matrix.vtk.rejections");
Check(qualified["environment"]?["condaPackageRecords"]?["count"]?.GetValue<int>()==2
    && qualified["environment"]?["toolchain"]?["cmake"]?["state"]?.GetValue<string>()=="recorded"
    && qualified["environment"]?["toolchain"]?["ninja"]?["state"]?.GetValue<string>()=="recorded"
    && qualified["environment"]?["toolchain"]?["msvcCompiler"]?["state"]?.GetValue<string>()=="recorded",
    "package inventory and toolchain hashes recorded");
Check(qualified["suite"]?["recipeId"]?.GetValue<string>()=="matrix.vtk.rejections"
    && qualified["suite"]?["revisionSha256"]?.GetValue<string>()?.Length==64,"suite revision is pinned to recipe source");
var qualifiedRun=Path.Combine(directory,"qualified-run");Directory.CreateDirectory(qualifiedRun);
var qualifiedDigest=ScientificRunFingerprint.Save(qualifiedRun,qualified,executed);
ScientificRunFingerprint.Verify(qualifiedRun,qualifiedDigest);
Check(ScientificRunFingerprint.AssessSourceDrift(qualifiedRun,fingerprintRoot,fingerprintRoot)["state"]?.GetValue<string>()=="current",
    "matching saved source and suite are current");
Check(ScientificRunFingerprint.AssessEnvironmentDrift(qualifiedRun,fingerprintRoot,reportFile)["state"]?.GetValue<string>()=="current",
    "matching packages and toolchain are current");
File.AppendAllText(Path.Combine(fingerprintRoot,"BatchLauncher","Form1.Scientific.VtkRejections.cs"),"changed");
var drift=ScientificRunFingerprint.AssessSourceDrift(qualifiedRun,fingerprintRoot,fingerprintRoot);
Check(drift["state"]?.GetValue<string>()=="stale" && drift["reasons"]?.ToJsonString().Contains("VtkRejections",StringComparison.Ordinal)==true,
    "changed suite source marks the saved run stale without rewriting it");
File.AppendAllText(Path.Combine(condaMeta,"vtk-9.json"),"changed");
var packageDrift=ScientificRunFingerprint.AssessEnvironmentDrift(qualifiedRun,fingerprintRoot,reportFile);
Check(packageDrift["state"]?.GetValue<string>()=="stale" && packageDrift["reasons"]?.ToJsonString().Contains("condaPackageRecords",StringComparison.Ordinal)==true,
    "changed package inventory marks saved environment stale");
var changedEnvironment=ScientificRunFingerprint.Capture("vtk-win-conda","laptop",fingerprintRoot,fingerprintRoot,reportFile,recipeId:"matrix.vtk.rejections");
Check(changedEnvironment["environment"]?["condaPackageRecords"]?["sha256"]?.GetValue<string>()
    !=qualified["environment"]?["condaPackageRecords"]?["sha256"]?.GetValue<string>(),
    "package record change invalidates environment identity");
File.AppendAllText(cmake,"changed");
var toolchainDrift=ScientificRunFingerprint.AssessEnvironmentDrift(qualifiedRun,fingerprintRoot,reportFile);
Check(toolchainDrift["state"]?.GetValue<string>()=="stale" && toolchainDrift["reasons"]?.ToJsonString().Contains("toolchain cmake",StringComparison.Ordinal)==true,
    "changed toolchain marks saved environment stale");
Check(ScientificRunFingerprint.AssessEnvironmentDrift(qualifiedRun,fingerprintRoot,Path.Combine(directory,"missing-report.json"))["state"]?.GetValue<string>()=="unknown",
    "missing runtime report leaves environment drift unknown");
ScientificRunFingerprint.Verify(qualifiedRun,qualifiedDigest);
var changedToolchain=ScientificRunFingerprint.Capture("vtk-win-conda","laptop",fingerprintRoot,fingerprintRoot,reportFile,recipeId:"matrix.vtk.rejections");
Check(changedToolchain["environment"]?["toolchain"]?["cmake"]?["sha256"]?.GetValue<string>()
    !=changedEnvironment["environment"]?["toolchain"]?["cmake"]?["sha256"]?.GetValue<string>(),
    "toolchain binary change invalidates environment identity");
Check(changedToolchain["suite"]?["revisionSha256"]?.GetValue<string>()
    !=qualified["suite"]?["revisionSha256"]?.GetValue<string>(),
    "suite source change invalidates its revision hash");


if (args.Length == 4)
{
    // Optional real importer/CGAL adapter check, with owned processes and disposable copies.
    var nativeRoot=Path.Combine(directory,"native-import");
    foreach(var name in new[]{"cube.obj","cube.stl","cube.off","open-triangle.ply","invalid.obj"})
    {
        var entry=ScientificMeshImports.Import(nativeRoot,Path.Combine(args[0],name));
        var id=entry["id"]!.GetValue<string>();
        var runId=Guid.NewGuid().ToString("N");
        var outputDirectory=Path.Combine(nativeRoot,"runs",runId);Directory.CreateDirectory(outputDirectory);
        var inputArtifact=new JsonObject { ["datasetId"]=id,["path"]=ScientificArtifactFiles.ScopedFile(Path.Combine(nativeRoot,"datasets"),id),["sha256"]=entry["sha256"]!.DeepClone(),["bytes"]=entry["bytes"]!.DeepClone(),["mediaType"]=ScientificArtifactFiles.MediaType(name) };
        var nativeRequest=new JsonObject { ["schemaVersion"]=1,["runId"]=runId,["profileId"]="import-check",["runtimeId"]="cgal-win-conda",["recipeId"]="cgal.validate",["operation"]="cgal.validate",
            ["parameters"]=new JsonObject { ["inputId"]=id,["outputName"]="validated.obj" },["inputArtifacts"]=new JsonArray(inputArtifact),["outputArtifacts"]=new JsonArray(new JsonObject { ["path"]="validated.obj",["mediaType"]="model/obj" }),
            ["workingDirectory"]=outputDirectory,["datasetRoot"]=Path.Combine(nativeRoot,"datasets"),["timeoutSeconds"]=60,["provenance"]=new JsonObject() };
        var nativeRequestPath=Path.Combine(outputDirectory,"request.json");File.WriteAllText(nativeRequestPath,nativeRequest.ToJsonString());
        var start=new System.Diagnostics.ProcessStartInfo(args[1]) { UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=outputDirectory };
        foreach(var argument in new[]{"run","cgal-win-conda","--manifest-root",Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(args[1]))!,"runtimes"),"--prefix",args[2],"--run-id",runId,"--output",outputDirectory,"--source-root",Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,"../../../../../")),"--request",nativeRequestPath,"--worker",args[3]})start.ArgumentList.Add(argument);
        using var process=System.Diagnostics.Process.Start(start)!;
        var stdout=process.StandardOutput.ReadToEndAsync();var stderr=process.StandardError.ReadToEndAsync();
        if(!process.WaitForExit(90000)) { process.Kill(true);throw new Exception("Native import check timed out: "+name); }
        Task.WaitAll(stdout,stderr);File.WriteAllText(Path.Combine(outputDirectory,"full.log"),stdout.Result+stderr.Result);
        using var resultDocument=JsonDocument.Parse(File.ReadAllText(Path.Combine(outputDirectory,"results.json")));
        var actual=resultDocument.RootElement;
        if(name=="invalid.obj")Check(process.ExitCode!=0 && actual.GetProperty("state").GetString()=="failed","native validation reports malformed imported OBJ");
        else
        {
            Check(process.ExitCode==0 && actual.GetProperty("state").GetString()=="succeeded","native CGAL validates imported "+name);
            Check(actual.GetProperty("after").GetProperty("closed").GetBoolean()==(name!="open-triangle.ply"),"native validation distinguishes solid/open input for "+name);
        }
        Check(ScientificArtifactFiles.Hash(inputArtifact["path"]!.GetValue<string>())==entry["sha256"]!.GetValue<string>(),"native validation preserves registered bytes for "+name);
    }
}

Console.WriteLine($"{count} checks passed. Fixtures retained at {directory}");
