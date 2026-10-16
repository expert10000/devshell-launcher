using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificCgalStart(string profileId, string runtimeId, JsonElement request)
    {
        if(runtimeId!="cgal-win-conda")throw new InvalidOperationException("Select the installed Windows Native CGAL profile.");
        var prefix=ScientificPrefix(runtimeId);
        var recipe=request.GetProperty("recipeId").GetString();
        if(recipe is not ("cgal.validate" or "cgal.remesh"))throw new InvalidOperationException("CGAL recipe is not registered.");
        var parameters=request.GetProperty("parameters");
        if(parameters.TryGetProperty("testCaseId",out var testCase))
        {
            var registered=ScientificMatrixCases().FirstOrDefault(item=>item.Id==testCase.GetString());
            if(testCase.ValueKind!=JsonValueKind.String || registered==null
                || request.GetProperty("recipeId").GetString()!="cgal.validate"
                || registered.DatasetId!=parameters.GetProperty("inputId").GetString()
                || $"matrix-{registered.Id}.obj"!=parameters.GetProperty("outputName").GetString())
                throw new InvalidOperationException("Test Matrix case does not match the registered manifest.");
        }
        var inputId=parameters.GetProperty("inputId").GetString()??"";
        var datasets=Path.Combine(ScientificDataRoot,"datasets");
        using(var manifest=JsonDocument.Parse(File.ReadAllText(Path.Combine(datasets,"manifest.json"))))
        {
            if(!manifest.RootElement.GetProperty("entries").EnumerateArray().Any(entry=>entry.GetProperty("id").GetString()==inputId))
                throw new InvalidOperationException("Select a registered duplicated dataset.");
        }
        var input=ScientificScopedFile(datasets,inputId);
        if(!File.Exists(input)||new FileInfo(input).Length>32*1024*1024||!new[]{".obj",".stl",".ply",".off"}.Contains(Path.GetExtension(input).ToLowerInvariant()))
            throw new InvalidOperationException("CGAL input must be an OBJ/STL/PLY/OFF fixture up to 32 MiB.");
        var output=parameters.GetProperty("outputName").GetString()??"";
        if(!Regex.IsMatch(output,@"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.obj$"))throw new InvalidOperationException("Output must be a safe OBJ filename.");
        var edge=recipe=="cgal.remesh"?parameters.GetProperty("targetEdge").GetDouble():0.1;
        var iterations=recipe=="cgal.remesh"?parameters.GetProperty("iterations").GetInt32():1;
        var boundary=recipe=="cgal.remesh"&&parameters.GetProperty("preserveBoundary").GetBoolean();
        if(!double.IsFinite(edge)||edge<=0||edge>1000000||iterations<1||iterations>10)throw new InvalidOperationException("Invalid remesh parameters.");
        if(!_scientificGate.Wait(0))throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory=Path.Combine(ScientificDataRoot,"runs",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);
            var job=new ScientificJob{ProfileId=profileId,RuntimeId=runtimeId,RecipeId=recipe,Directory=directory};
            ScientificWriteRequest(job,parameters,ScientificDatasetArtifact(inputId),output);
            _scientificJobs[profileId+":"+runtimeId]=job;
            ScientificSend(new{type="scientific.runtime.job",profileId,job=ScientificJobSnapshot(job)});
            _=ScientificCgalRunAsync(job,prefix,input,output,edge,iterations,boundary);
            return ScientificJobSnapshot(job);
        }
        catch{_scientificGate.Release();throw;}
    }

    private async Task ScientificCgalRunAsync(ScientificJob job,string prefix,string input,string output,double edge,int iterations,bool boundary)
    {
        var timer=Stopwatch.StartNew();
        try
        {
            await ScientificCgalExecuteAsync(job,prefix);
            job.State="succeeded";
            job.Stage="completed";
        }
        catch(OperationCanceledException){job.State="cancelled";job.Error="Only this owned job was stopped.";}
        catch(TimeoutException exception){job.State="timed-out";job.Error=exception.Message;}
        catch(Exception exception){job.State="failed";job.Error=exception.Message;}
        finally
        {
            job.DurationMs=timer.ElapsedMilliseconds;
            try{ScientificFinish(job);ScientificLog(job,$"\n[{job.State}] {job.DurationMs} ms {job.Error}\n");}
            catch(Exception exception){Debug.WriteLine($"CGAL final log failed: {exception}");}
            finally{ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(job)});_scientificGate.Release();}
        }
    }

    private async Task ScientificCgalExecuteAsync(ScientificJob job,string prefix)
    {
        var key=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(job.ProfileId+"|"+prefix))).Substring(0,12);
        var build=Path.Combine(ScientificDataRoot,"builds",key,"cgal-worker");
        var cmake=Path.Combine(prefix,"Library","bin","cmake.exe");
        await ScientificProcessAsync(job,prefix,cmake,new[]{"-S",Path.Combine(ScientificSourceRoot,"scientific","cgal-worker"),"-B",build,"-G","Visual Studio 17 2022","-A","x64","-DCMAKE_PREFIX_PATH="+Path.Combine(prefix,"Library")},job.Directory,180);
        await ScientificProcessAsync(job,prefix,cmake,new[]{"--build",build,"--config","Release","--parallel","1"},job.Directory,180);
        var worker=Path.Combine(build,"Release","devshell_cgal_worker.exe");
        var adapter=Path.Combine(ScientificSourceRoot,"tools","scientific-cgal-worker.py");
        var condaHistory=Path.Combine(prefix,"conda-meta","history");
        job.EnvironmentFingerprint=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            ScientificHash(condaHistory)+"|"+ScientificHash(worker)+"|"+ScientificHash(adapter)))).ToLowerInvariant();
        if(job.RecipeId=="cgal.validate")
        {
            var lab=Path.Combine(AppContext.BaseDirectory,"runtime-lab","runtime-lab.exe");
            var args=new[]{"run",job.RuntimeId,"--manifest-root",Path.Combine(AppContext.BaseDirectory,"runtimes"),
                "--prefix",prefix,"--run-id",job.Id,"--output",job.Directory,"--source-root",ScientificSourceRoot,
                "--request",Path.Combine(job.Directory,"request.json"),"--worker",worker};
            await ScientificProcessAsync(job,prefix,lab,args,job.Directory,150);
        }
        else
        {
            var args=new[]{adapter,"--request",Path.Combine(job.Directory,"request.json"),"--worker",worker};
            await ScientificProcessAsync(job,prefix,Path.Combine(prefix,"python.exe"),args,job.Directory,120);
        }
    }
}
