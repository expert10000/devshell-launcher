using System.Diagnostics;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.Web.WebView2.WinForms;

namespace BatchLauncher;

public partial class Form1
{
    private readonly ConcurrentDictionary<string, ScientificJob> _scientificJobs = new(StringComparer.Ordinal);
    private readonly SemaphoreSlim _scientificGate = new(1, 1);
    private bool _scientificCloseHook;
    private sealed class ScientificJob
    {
        public string Id { get; init; } = Guid.NewGuid().ToString("N");
        public required string ProfileId { get; init; }
        public required string RuntimeId { get; init; }
        public required string RecipeId { get; init; }
        public required string Directory { get; init; }
        public DateTimeOffset StartedAtUtc { get; } = DateTimeOffset.UtcNow;
        public string State { get; set; } = "running";
        public string? Error { get; set; }
        public long DurationMs { get; set; }
        public string Stage { get; set; } = "queued";
        public int? ExitCode { get; set; }
        public string? CompilerVersion { get; set; }
        public string? EnvironmentFingerprint { get; set; }
        public JsonObject? FingerprintComponents { get; set; }
        public JsonObject? SourceSnapshot { get; set; }
        public List<JsonObject> ExecutedFiles { get; } = new();
        public JsonElement? Request { get; set; }
        public JsonElement? Result { get; set; }
        public List<object> Steps { get; } = new();
        public CancellationTokenSource Cancellation { get; init; } = new();
        public StringBuilder Log { get; } = new();
        public object Sync { get; } = new();
    }
    private static readonly JsonSerializerOptions ScientificJson = new() { PropertyNamingPolicy=JsonNamingPolicy.CamelCase };
    private static string ScientificRepositoryRoot()
    {
        for(var directory=new DirectoryInfo(AppContext.BaseDirectory);directory!=null;directory=directory.Parent)
            if(File.Exists(Path.Combine(directory.FullName,"BatchLauncher","BatchLauncher.csproj"))) return directory.FullName;
        return AppContext.BaseDirectory;
    }
    private static string ScientificDataRoot=>Path.Combine(ScientificRepositoryRoot(),".scientific");
    private static string ScientificSourceRoot=>File.Exists(Path.Combine(ScientificRepositoryRoot(),"tools","scientific-runtime-probe.py"))?ScientificRepositoryRoot():AppContext.BaseDirectory;
    private static string ScientificReportPath()
    {
        var path=Path.Combine(ScientificDataRoot,"runtime-report.json");
        return File.Exists(path)?path:Path.Combine(AppContext.BaseDirectory,"ui","scientific-runtime-report.json");
    }
    private static JsonElement ScientificReport()
    {
        var path=ScientificReportPath();
        if(!File.Exists(path)||new FileInfo(path).Length>1048576) throw new InvalidOperationException("Install/inspect local environments first.");
        using var document=JsonDocument.Parse(File.ReadAllText(path)); return document.RootElement.Clone();
    }
    private string ScientificPrefix(string runtimeId)
    {
        var provider = ScientificProviderRegistry.Get(runtimeId);
        if (!provider.NativeManaged) throw new InvalidOperationException("Only installed Windows-native scientific adapters execute.");
        var prefix = Path.Combine(ScientificRuntimeRoot(), provider.EnvironmentName);
        var expected=provider.EnvironmentName;
        if(!Path.IsPathFullyQualified(prefix)||Path.GetFileName(prefix.TrimEnd(Path.DirectorySeparatorChar))!=expected||!File.Exists(Path.Combine(prefix,"conda-meta","history"))) throw new InvalidOperationException($"{expected} is not installed for this workspace. Use Install / repair in Scientific Runtimes.");
        return Path.GetFullPath(prefix);
    }
    private static Dictionary<string,string> ScientificEnvironment(string prefix)=>new()
    {
        ["CMAKE_PREFIX_PATH"]=Path.Combine(prefix,"Library"),
        ["PATH"]=prefix+";"+Path.Combine(prefix,"Library","bin")+";"+Path.Combine(prefix,"Scripts")+";"+(Environment.GetEnvironmentVariable("PATH")??""),
        ["PYTHONNOUSERSITE"]="1",["PYTHONIOENCODING"]="utf-8"
    };
    private static string ScientificScopedFile(string root,string relative) => ScientificArtifactFiles.ScopedFile(root, relative);
    private static IEnumerable<Control> ScientificControls(Control parent)
    {
        foreach(Control child in parent.Controls){yield return child;foreach(var nested in ScientificControls(child))yield return nested;}
    }
    private void ScientificSend(object message)
    {
        if(IsDisposed||Disposing)return;
        if(InvokeRequired){try{BeginInvoke(new Action(()=>ScientificSend(message)));}catch(InvalidOperationException){}return;}
        var view=ScientificControls(this).OfType<WebView2>().FirstOrDefault(item=>item.CoreWebView2?.Source.StartsWith("https://app.local/",StringComparison.OrdinalIgnoreCase)==true);
        view?.CoreWebView2?.PostWebMessageAsJson(JsonSerializer.Serialize(message,ScientificJson));
    }
    private static object ScientificJobSnapshot(ScientificJob job)
    {
        lock(job.Sync)return new{jobId=job.Id,profileId=job.ProfileId,runtimeId=job.RuntimeId,recipeId=job.RecipeId,state=job.State,stage=job.Stage,startedAtUtc=job.StartedAtUtc,durationMs=job.DurationMs,error=job.Error,log=job.Log.ToString(),outputDirectory=job.Directory,request=job.Request,result=job.Result};
    }
    private void ScientificLog(ScientificJob job,string text)
    {
        lock(job.Sync)
        {
            job.Log.Append(text);if(job.Log.Length>65536)job.Log.Remove(0,job.Log.Length-65536);
            var compiler=Regex.Match(job.Log.ToString(),@"(?:MSVC |CXX compiler identification is MSVC )(?<version>19\.\d+\.\d+(?:\.\d+)?)");
            if(compiler.Success)job.CompilerVersion=compiler.Groups["version"].Value;
            var path=Path.Combine(job.Directory,"full.log");if(!File.Exists(path)||new FileInfo(path).Length<16777216)File.AppendAllText(path,text,Encoding.UTF8);
        }
        // Internal resilience probes own processes but do not replace the managed parent in the UI.
        if (_scientificJobs.TryGetValue(job.ProfileId + ":" + job.RuntimeId, out var current)
            && ReferenceEquals(current, job))
            ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(job)});
    }
    private async Task ScientificProcessAsync(ScientificJob job,string prefix,string executable,string[] arguments,string directory,int timeoutSeconds,string? extraPath=null,long? memoryLimitBytes=null,Action<long>? peakMemory=null,Action<string>? stdoutCapture=null)
    {
        job.Cancellation.Token.ThrowIfCancellationRequested();
        job.Stage=arguments.Contains("--build")?"build":arguments.Contains("-S")?"configure":executable.EndsWith("python.exe",StringComparison.OrdinalIgnoreCase)?"worker":"run";
        var stepTimer=Stopwatch.StartNew();
        var start=new ProcessStartInfo(executable){WorkingDirectory=directory,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
        foreach(var argument in arguments)start.ArgumentList.Add(argument);
        job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(executable, "executable"));
        foreach (var argument in arguments)
            if (File.Exists(argument) && new[] { ".exe", ".dll", ".py", ".mjs" }.Contains(Path.GetExtension(argument).ToLowerInvariant())
                && !Path.GetFullPath(argument).StartsWith(job.Directory.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(argument, "argument"));
        foreach(var pair in ScientificEnvironment(prefix))start.Environment[pair.Key]=pair.Value;
        if(extraPath!=null)start.Environment["PATH"]=extraPath+Path.PathSeparator+start.Environment["PATH"];
        start.Environment.Remove("PYTHONPATH");
        ScientificLog(job,"$ "+executable+" "+string.Join(" ",arguments.Select(argument=>JsonSerializer.Serialize(argument)))+"\n");
        using var process=new Process{StartInfo=start};using var owner=new OwnedProcessJob(memoryLimitBytes);
        using var cancellation=CancellationTokenSource.CreateLinkedTokenSource(job.Cancellation.Token);cancellation.CancelAfter(TimeSpan.FromSeconds(timeoutSeconds));
        if(!process.Start())throw new InvalidOperationException("Could not start registered command.");
        try
        {
            owner.Add(process);
            async Task Drain(StreamReader reader,Action<string>? capture){var buffer=new char[4096];int count;while((count=await reader.ReadAsync(buffer.AsMemory()))>0){var chunk=new string(buffer,0,count);capture?.Invoke(chunk);ScientificLog(job,chunk);}}
            var output=Drain(process.StandardOutput,stdoutCapture);var errors=Drain(process.StandardError,null);
            try{await process.WaitForExitAsync(cancellation.Token);}
            catch(OperationCanceledException){owner.Stop();await process.WaitForExitAsync();await Task.WhenAll(output,errors);if(job.Cancellation.IsCancellationRequested)throw;throw new TimeoutException($"Step exceeded {timeoutSeconds} seconds.");}
            await Task.WhenAll(output,errors);job.ExitCode=process.ExitCode;
            peakMemory?.Invoke(owner.PeakProcessMemoryBytes);
            if(process.ExitCode!=0)throw new InvalidOperationException($"Registered command exited {process.ExitCode}. See full log.");
        }
        finally{owner.Stop();job.Steps.Add(new{stage=job.Stage,executable,arguments,durationMs=stepTimer.ElapsedMilliseconds,exitCode=process.HasExited?(int?)process.ExitCode:null});}
    }
    private async Task ScientificRunAsync(ScientificJob job,string prefix,JsonElement request)
    {
        var timer=Stopwatch.StartNew();
        try
        {
            var kind=job.RuntimeId.StartsWith("cgal",StringComparison.Ordinal)?"cgal":
                job.RuntimeId.StartsWith("gmsh",StringComparison.Ordinal)?"gmsh":"vtk";
            var hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(job.ProfileId)))[..12];
            var build=job.RecipeId=="compile-link"?Path.Combine(job.Directory,"build")
                :Path.Combine(ScientificDataRoot,"builds",hash,kind);var cmake=ScientificRunFingerprint.CmakePath(prefix, job.RuntimeId);
            if(job.RecipeId=="diagnostics")await ScientificProcessAsync(job,prefix,ScientificExecutable("pwsh.exe"),new[]{"-NoProfile","-File",Path.Combine(ScientificSourceRoot,"tools","Inspect-ScientificRuntimes.ps1"),"-RuntimeRoot",Path.GetDirectoryName(prefix)!,"-OutputPath",Path.Combine(ScientificDataRoot,"runtime-report.json"),"-PublishToLauncher"},job.Directory,150);
            else if(job.RecipeId=="version")await ScientificProcessAsync(job,prefix,Path.Combine(prefix,"python.exe"),new[]{Path.Combine(ScientificSourceRoot,"tools","scientific-runtime-probe.py"),"--kind",kind},job.Directory,60);
            else if(job.RecipeId.StartsWith("mesh.",StringComparison.Ordinal))
            {
                if(kind!="vtk")throw new InvalidOperationException("CGAL mesh workers are not implemented by this adapter.");
                var inputId=request.GetProperty("parameters").GetProperty("inputId").GetString()??"";
                var inputArtifact=ScientificDatasetArtifact(inputId);var input=inputArtifact["path"]!.GetValue<string>();
                if(!File.Exists(input)||new FileInfo(input).Length>33554432||!new[]{".obj",".stl",".ply",".vtp"}.Contains(Path.GetExtension(input).ToLowerInvariant()))throw new InvalidOperationException("Select a supported bounded dataset copy.");
                var output=request.GetProperty("parameters").GetProperty("outputName").GetString()??"";
                if(!Regex.IsMatch(output,"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\\.vtp$"))throw new InvalidOperationException("Output must be a safe VTP basename.");
                ScientificWriteRequest(job,request.GetProperty("parameters"),inputArtifact,output);
                var file=Path.Combine(job.Directory,"request.json");
                await ScientificProcessAsync(job,prefix,Path.Combine(prefix,"python.exe"),new[]{Path.Combine(ScientificSourceRoot,"tools","scientific-mesh-worker.py"),"--request",file},job.Directory,120);
            }
            else
            {
                if(job.RecipeId is "configure" or "test-all" or "compile-link")await ScientificProcessAsync(job,prefix,cmake,new[]{"-S",Path.Combine(ScientificSourceRoot,"scientific","smoke",kind),"-B",build,"-G","Visual Studio 17 2022","-A","x64","-DCMAKE_PREFIX_PATH="+Path.Combine(prefix,"Library")},job.Directory,180);
                if(job.RecipeId is "build" or "test-all" or "compile-link")await ScientificProcessAsync(job,prefix,cmake,new[]{"--build",build,"--config","Release","--parallel","2"},job.Directory,180);
                if(job.RecipeId=="compile-link")
                {
                    var binary=Path.Combine(build,"Release","devshell_"+kind+"_smoke.exe");
                    if(!File.Exists(binary))throw new FileNotFoundException("Compiled smoke executable is missing.",binary);
                    job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(binary,"linked-binary"));
                }
                if(job.RecipeId is "run" or "test-all")await ScientificProcessAsync(job,prefix,Path.Combine(build,"Release","devshell_"+kind+"_smoke.exe"),Array.Empty<string>(),job.Directory,30);
                if(kind=="vtk"&&job.RecipeId=="test-all"){var render=Path.Combine(job.Directory,"render");Directory.CreateDirectory(render);await ScientificProcessAsync(job,prefix,Path.Combine(prefix,"python.exe"),new[]{Path.Combine(ScientificSourceRoot,"tools","scientific-vtk-render-check.py")},render,60);}
            }
            job.State="succeeded";
            job.Stage="completed";
        }
        catch(OperationCanceledException){job.State="cancelled";job.Error="Only this owned job was stopped.";}
        catch(TimeoutException exception){job.State="timed-out";job.Error=exception.Message;}
        catch(Exception exception){job.State="failed";job.Error=exception.Message;}
        finally
        {
            job.DurationMs=timer.ElapsedMilliseconds;
            try
            {
                ScientificFinish(job);
                ScientificLog(job,$"\n[{job.State}] {job.DurationMs} ms {job.Error}\n");
            }
            catch(Exception exception)
            {
                System.Diagnostics.Debug.WriteLine($"Scientific recipe final log failed: {exception}");
            }
            finally
            {
                ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(job)});
                _scientificGate.Release();
            }
        }
    }
    private static string ScientificExecutable(string name)
    {
        foreach(var folder in(Environment.GetEnvironmentVariable("PATH")??"").Split(';',StringSplitOptions.RemoveEmptyEntries)){var path=Path.Combine(folder.Trim('"'),name);if(File.Exists(path))return path;}
        if(name=="pwsh.exe"){var path=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"PowerShell","7",name);if(File.Exists(path))return path;}
        throw new FileNotFoundException(name+" is required by this action.");
    }
    private async Task HandleScientificRuntimeAsync(JsonElement source)
    {
        var request=source.Clone();var profileId=request.TryGetProperty("profileId",out var profile)?profile.GetString()??"":"";
        var requestId=request.TryGetProperty("requestId",out var identifier)?identifier.GetString():null;
        var action=request.TryGetProperty("action",out var operation)?operation.GetString()??"":"";
        var runtimeId=request.TryGetProperty("runtimeId",out var runtime)?runtime.GetString()??"":"";
        object? data=null;string? error=null;
        try
        {
            if(profileId.Length is 0 or >128)throw new InvalidOperationException("Select a workspace profile.");
            if(!_scientificCloseHook){_scientificCloseHook=true;FormClosed+=(_,_)=>{_scientificLifetime.Cancel();foreach(var job in _scientificJobs.Values)if(job.State=="running")job.Cancellation.Cancel();};}
            if(action=="status")data=_scientificJobs.Values.Where(job=>job.ProfileId==profileId).Select(ScientificJobSnapshot).ToArray();
            else if(action=="history")data=ScientificHistoryList(profileId);
            else if(action=="qualification-summary")data=runtimeId=="sage-wsl"
                ? await Task.Run(()=>ScientificQualificationSummary(profileId,runtimeId)) : ScientificQualificationSummary(profileId,runtimeId);
            else if(action=="ci-matrix")data=ScientificCiMatrix();
            else if(action=="retest-plan")data=await Task.Run(()=>ScientificRetestPlan(profileId,request));
            else if(action=="retest-status")data=ScientificRetestStatus(profileId,request.GetProperty("planId").GetString()??"");
            else if(action=="retest-start")data=ScientificRetestStart(profileId,request.GetProperty("planId").GetString()??"");
            else if(action=="retest-stop")data=ScientificRetestStop(profileId,request.GetProperty("planId").GetString()??"");
            else if(action=="capabilities")data=new{schemaVersion=ScientificCapabilityRegistry.SchemaVersion,capabilities=ScientificCapabilityRegistry.Discover(runtimeId)};
            else if(action=="history-result")data=runtimeId=="sage-wsl"
                ? await Task.Run(()=>ScientificHistoryResult(profileId,request.GetProperty("jobId").GetString()??""))
                : ScientificHistoryResult(profileId,request.GetProperty("jobId").GetString()??"");
            else if(action=="history-repair-math3d-handoff")data=ScientificCgalRepairHandoffStart(profileId,runtimeId,request.GetProperty("jobId").GetString()??"");
            else if(action=="history-drift-diagnose")data=runtimeId=="sage-wsl"
                ? await Task.Run(()=>ScientificDriftDiagnosis(profileId,runtimeId,request.GetProperty("jobId").GetString()??""))
                : ScientificDriftDiagnosis(profileId,runtimeId,request.GetProperty("jobId").GetString()??"");
            else if(action=="history-boolean-draft")data=ScientificBooleanDraft(profileId,request.GetProperty("jobId").GetString()??"");
            else if(action=="import-meshes"){ScientificProviderRegistry.RequireAction(runtimeId,action);data=ScientificMeshImportStart(profileId,runtimeId);}
            else if(action=="test-matrix"){ScientificProviderRegistry.RequireAction(runtimeId,action);data=ScientificMatrixCases();}
            else if(action=="history-thumbnail")data=ScientificHistoryThumbnail(profileId,request);
            else if(action=="history-image-preview")data=ScientificHistoryImagePreview(profileId,request);
            else if(action=="history-preview")data=await ScientificHistoryPreviewAsync(profileId,request);
            else if(action is "history-open-log" or "history-open-output" or "history-reveal-artifact" or "history-open-artifact")data=ScientificHistoryOpen(profileId,request,action);
            else if(action=="report")data=ScientificReport();
            else if(action=="install-runtime")data=ScientificInstallStart(profileId,runtimeId);
            else if(action=="sage-recipe"){ScientificProviderRegistry.RequireAction(runtimeId,action);data=ScientificSageStart(profileId,runtimeId,request);}
            else if(action=="math3d-readiness"){ScientificProviderRegistry.RequireAction(runtimeId,action);data=ScientificMath3DReadiness(profileId);}
            else if(action=="inspect-selection-preview")data=ScientificInspectPreviewStart(profileId,request);
            else if(action=="inspect-selection-run")data=ScientificInspectSelectionStart(profileId,request);
            else if(action=="datasets")
            {
                data=ScientificMeshImports.ReadManifest(ScientificDataRoot);
            }
            else if(action=="repair-fixtures")
            {
                ScientificProviderRegistry.RequireAction(runtimeId,action);
                if(!_scientificGate.Wait(0))throw new InvalidOperationException("A Scientific job is already running.");
                try{data=ScientificRepairFixtures.Load(ScientificSourceRoot,ScientificDataRoot,_scientificLifetime.Token);}
                finally{_scientificGate.Release();}
            }
            else if(action is "open-log" or "open-output" or "stop" or "artifacts")
            {
                if(!_scientificJobs.TryGetValue(profileId+":"+runtimeId,out var job)||request.GetProperty("jobId").GetString()!=job.Id)throw new InvalidOperationException("Job is no longer current.");
                if(action=="artifacts")data=await ScientificPreviewAsync(job,request);
                else if(action=="stop"){job.Cancellation.Cancel();data=ScientificJobSnapshot(job);}
                else{var path=action=="open-log"?Path.Combine(job.Directory,"full.log"):job.Directory;var start=new ProcessStartInfo(action=="open-log"?"notepad.exe":"explorer.exe"){UseShellExecute=true};start.ArgumentList.Add(path);Process.Start(start);data=new{path};}
            }
            else if(action=="lab-probe") {ScientificProviderRegistry.RequireAction(runtimeId,action);data=ScientificLabProbeStart(profileId,runtimeId);}
            else if(action=="l5-worker")data=ScientificL5Start(profileId,runtimeId);
            else if(action=="l5-cgal-repair")data=ScientificCgalRepairL5Start(profileId,runtimeId);
            else if(action=="l5-cgal-orientation")data=ScientificL5OrientationStart(profileId,runtimeId);
            else if(action=="l6-cgal-repair")data=ScientificCgalRepairL6Start(profileId,runtimeId);
            else if(action=="l7-cgal-repair")data=ScientificCgalRepairL7Start(profileId,runtimeId);
            else if(action=="l8-cgal-repair")data=ScientificCgalRepairL8Start(profileId,runtimeId);
            else if(action=="l9-cgal-repair")data=ScientificCgalRepairL9Start(profileId,runtimeId);
            else if(action is "l5-cgal-remesh" or "l6-cgal-remesh" or "l7-cgal-remesh" or "l8-cgal-remesh" or "l9-cgal-remesh")
                data=ScientificCgalRemeshLevelStart(profileId,runtimeId,action[1]-'0');
            else if(action is "l5-cgal-inspect" or "l6-cgal-inspect" or "l7-cgal-inspect" or "l8-cgal-inspect" or "l9-cgal-inspect")
                data=ScientificCgalInspectLevelStart(profileId,runtimeId,action[1]-'0');
            else if(action is "l5-cgal-orient" or "l6-cgal-orient" or "l7-cgal-orient" or "l8-cgal-orient" or "l9-cgal-orient")
                data=ScientificCgalOrientationLevelStart(profileId,runtimeId,action[1]-'0');
            else if(action is "l5-vtk-read" or "l6-vtk-read" or "l7-vtk-read" or "l8-vtk-read" or "l9-vtk-read")
                data=ScientificVtkReadLevelStart(profileId,runtimeId,action[1]-'0');
            else if(action=="l6-reproduce")data=ScientificL6Start(profileId,runtimeId);
            else if(action=="l6-cgal-orientation")data=ScientificL6OrientationStart(profileId,runtimeId);
            else if(action=="l7-math3d-import")data=ScientificL7Start(profileId,runtimeId);
            else if(action=="l7-cgal-vtk-math3d")data=ScientificL7InteropStart(profileId,runtimeId);
            else if(action=="l7-gmsh-interop")data=ScientificGmshL7Start(profileId,runtimeId);
            else if(action=="l8-resilience")data=ScientificL8Start(profileId,runtimeId);
            else if(action=="l8-gmsh-resilience")data=ScientificGmshL8Start(profileId,runtimeId);
            else if(action=="l9-math3d-product")data=ScientificL9Start(profileId,runtimeId);
            else if(action=="l9-gmsh-product")data=ScientificGmshL9Start(profileId,runtimeId);
            else if(action=="l5-gmsh-volume")data=ScientificGmshVolumeStart(profileId,runtimeId,"L5");
            else if(action=="l6-gmsh-volume")data=ScientificGmshVolumeStart(profileId,runtimeId,"L6");
            else if(action=="l7-gmsh-volume")data=ScientificGmshVolumeStart(profileId,runtimeId,"L7");
            else if(action=="l8-gmsh-volume")data=ScientificGmshVolumeL8Start(profileId,runtimeId);
            else if(action=="gmsh-volume-product-readiness")data=ScientificGmshVolumeProductReadinessStart(profileId,runtimeId);
            else if(action=="l9-gmsh-volume")data=ScientificGmshVolumeL9Start(profileId,runtimeId);
            else
            {
                ScientificProviderRegistry.RequireAction(runtimeId,action);
                var prefix=ScientificPrefix(runtimeId);
                if(action=="environment")
                {
                    var vcpkg=Environment.GetEnvironmentVariable("VCPKG_ROOT");var inferred=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),"vcpkg");
                    data=new{environment=ScientificEnvironment(prefix),vcpkgRoot=vcpkg,installedVcpkg=File.Exists(Path.Combine(inferred,"vcpkg.exe"))?inferred:null,vcpkgUsed=false,report=ScientificReport(),evidence=ScientificEvidence(profileId,runtimeId)};
                }
                else if(action=="terminal")
                {
                    var start=new ProcessStartInfo(ScientificExecutable("pwsh.exe")){UseShellExecute=false,CreateNoWindow=false,WorkingDirectory=prefix};
                    foreach(var pair in ScientificEnvironment(prefix))start.Environment[pair.Key]=pair.Value;
                    start.Environment.Remove("PYTHONPATH");start.ArgumentList.Add("-NoLogo");start.ArgumentList.Add("-NoExit");Process.Start(start);data=new{note="External scientific PowerShell opened; runtime environment, not a VS developer shell."};
                }
                else if(action=="export")
                {
                    using var dialog=new SaveFileDialog{Filter="Runtime profile (*.json)|*.json",DefaultExt="json",FileName=runtimeId+".json",AddExtension=true,OverwritePrompt=true};
                    if(dialog.ShowDialog(this)==DialogResult.OK){var definition=new{schemaVersion=1,id=runtimeId,kind=runtimeId.StartsWith("cgal",StringComparison.Ordinal)?"cgal":"vtk",execution="windows-native",environmentRoot=prefix,executable=Path.Combine(prefix,"python.exe"),cmake=Path.Combine(prefix,"Library","bin","cmake.exe"),sdkRoot=Path.Combine(prefix,"Library"),environment=new Dictionary<string,string>{["CMAKE_PREFIX_PATH"]=Path.Combine(prefix,"Library"),["PYTHONNOUSERSITE"]="1"},readiness="not-checked",note="Definition only; no host secrets, captured job contents, or readiness evidence."};File.WriteAllText(dialog.FileName,JsonSerializer.Serialize(definition,new JsonSerializerOptions(ScientificJson){WriteIndented=true}),Encoding.UTF8);data=new{path=dialog.FileName};}else data=new{cancelled=true};
                }
                else if(action=="test-hold")data=ScientificStopTestStart(profileId,runtimeId);
                else if(action=="recipe")
                {
                    var recipe=request.GetProperty("recipeId").GetString()??"";
                    if(!new[]{"version","configure","build","run","test-all","compile-link","diagnostics","mesh.inspect","mesh.simplify","mesh.normals"}.Contains(recipe))throw new InvalidOperationException("Recipe not registered.");
                    if(!_scientificGate.Wait(0))throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
                    try
                    {
                        var directory=Path.Combine(ScientificDataRoot,"runs",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);
                        var job=new ScientificJob{ProfileId=profileId,RuntimeId=runtimeId,RecipeId=recipe,Directory=directory};_scientificJobs[profileId+":"+runtimeId]=job;data=ScientificJobSnapshot(job);
                        ScientificWriteRequest(job,request.TryGetProperty("parameters",out var parameters)?parameters:null);
                        _=ScientificRunAsync(job,prefix,request);
                    }
                    catch{_scientificGate.Release();throw;}
                }
                else if(action=="boolean-recipe")data=ScientificBooleanStart(profileId,runtimeId,request);
                else if(action=="cgal-recipe")data=ScientificCgalStart(profileId,runtimeId,request);
                else if(action=="run-matrix")data=ScientificMatrixStart(profileId,runtimeId);
                else if(action=="vtk-rejections")data=ScientificVtkRejectionsStart(profileId,runtimeId);
                else if(action=="real-mesh-suite")data=ScientificRealMeshStart(profileId,runtimeId,request);
                else if(action is "math3d-integration" or "math3d-prepare-run")data=ScientificMath3DIntegrationStart(profileId,runtimeId,action=="math3d-prepare-run");
                else throw new InvalidOperationException("Unknown Scientific action.");
            }
        }
        catch(Exception exception){error=exception.Message;}
        ScientificSend(new{type="scientific.runtime.result",profileId,requestId,action,runtimeId,data,error});await Task.CompletedTask;
    }
}
