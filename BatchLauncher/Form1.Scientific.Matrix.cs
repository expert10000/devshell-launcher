using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private sealed record ScientificMatrixCase(string Id, string DatasetId, string Name, string Expected, string Reason);

    private static ScientificMatrixCase[] ScientificMatrixCases()
    {
        var path=Path.Combine(AppContext.BaseDirectory,"runtimes","cgal-win-conda","runtime.json");
        if(!File.Exists(path)||new FileInfo(path).Length>65536)throw new InvalidOperationException("CGAL Test Matrix manifest is unavailable.");
        using var document=JsonDocument.Parse(File.ReadAllText(path));
        var cases=document.RootElement.GetProperty("testMatrix").EnumerateArray().Select(item=>new ScientificMatrixCase(
            item.GetProperty("id").GetString()??"",item.GetProperty("datasetId").GetString()??"",
            item.GetProperty("name").GetString()??"",item.GetProperty("expected").GetString()??"",
            item.GetProperty("reason").GetString()??"")).ToArray();
        if(cases.Length is <1 or >16||cases.Select(item=>item.Id).Distinct(StringComparer.Ordinal).Count()!=cases.Length
            ||cases.Any(item=>!Regex.IsMatch(item.Id,"^[a-z0-9][a-z0-9-]{0,40}$")
                ||string.IsNullOrWhiteSpace(item.Name)||item.Expected is not ("succeeded" or "rejected")
                ||item.Expected=="rejected"&&string.IsNullOrWhiteSpace(item.Reason)))
            throw new InvalidOperationException("CGAL Test Matrix manifest contains an invalid case.");
        foreach(var item in cases)ScientificScopedFile(Path.Combine(ScientificDataRoot,"datasets"),item.DatasetId);
        return cases;
    }

    private object ScientificMatrixStart(string profileId,string runtimeId)
    {
        if(runtimeId!="cgal-win-conda")throw new InvalidOperationException("The registered Test Matrix requires Windows Native CGAL.");
        var prefix=ScientificPrefix(runtimeId);
        var cases=ScientificMatrixCases();
        foreach(var item in cases)ScientificDatasetArtifact(item.DatasetId);
        if(!_scientificGate.Wait(0))throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory=Path.Combine(ScientificDataRoot,"runs",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);
            var job=new ScientificJob{ProfileId=profileId,RuntimeId=runtimeId,RecipeId="matrix.cgal.validation",Directory=directory};
            ScientificWriteRequest(job,JsonSerializer.SerializeToElement(new{suiteId="cgal-validation-v1",caseCount=cases.Length},ScientificJson));
            _scientificJobs[profileId+":"+runtimeId]=job;
            ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(job)});
            _=ScientificMatrixRunAsync(job,prefix,cases);
            return ScientificJobSnapshot(job);
        }
        catch{_scientificGate.Release();throw;}
    }

    private async Task ScientificMatrixRunAsync(ScientificJob suite,string prefix,ScientificMatrixCase[] cases)
    {
        var timer=Stopwatch.StartNew();
        var outcomes=new List<object>();
        var passed=0;
        try
        {
            foreach(var test in cases)
            {
                suite.Cancellation.Token.ThrowIfCancellationRequested();
                suite.Stage="case: "+test.Id;
                var directory=Path.Combine(ScientificDataRoot,"runs",Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);
                var job=new ScientificJob{ProfileId=suite.ProfileId,RuntimeId=suite.RuntimeId,RecipeId="cgal.validate",Directory=directory,Cancellation=suite.Cancellation};
                var output="matrix-"+test.Id+".obj";
                var parameters=JsonSerializer.SerializeToElement(new{inputId=test.DatasetId,outputName=output,testCaseId=test.Id},ScientificJson);
                ScientificWriteRequest(job,parameters,ScientificDatasetArtifact(test.DatasetId),output);
                _scientificJobs[suite.ProfileId+":"+suite.RuntimeId]=job;
                ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(job)});
                var caseTimer=Stopwatch.StartNew();
                try
                {
                    await ScientificCgalExecuteAsync(job,prefix);
                    job.State="succeeded";job.Stage="completed";
                }
                catch(OperationCanceledException){job.State="cancelled";job.Error="The owned matrix was stopped.";}
                catch(TimeoutException exception){job.State="timed-out";job.Error=exception.Message;}
                catch(Exception exception){job.State="failed";job.Error=exception.Message;}
                finally
                {
                    job.DurationMs=caseTimer.ElapsedMilliseconds;
                    ScientificFinish(job);
                    ScientificLog(job,$"\n[{job.State}] {job.DurationMs} ms {job.Error}\n");
                    _scientificJobs[suite.ProfileId+":"+suite.RuntimeId]=suite;
                }
                var result=job.Result!.Value;
                var accepted=test.Expected=="succeeded"
                    ? job.State=="succeeded"&&result.GetProperty("artifacts").EnumerateArray().Any(item=>item.GetProperty("path").GetString()==output&&item.TryGetProperty("sha256",out var hash)&&!string.IsNullOrEmpty(hash.GetString()))
                        &&result.GetProperty("validatedCapabilities").EnumerateArray().Any(item=>item.GetString()=="mesh.validate")
                    : job.State=="failed"&&result.GetProperty("diagnostics").EnumerateArray().Any(item=>item.GetProperty("message").GetString()?.Contains(test.Reason,StringComparison.OrdinalIgnoreCase)==true);
                if(accepted)passed++;
                outcomes.Add(new{caseId=test.Id,runId=job.Id,expected=test.Expected,observed=job.State,verdict=accepted?"pass":"fail",durationMs=job.DurationMs});
                ScientificLog(suite,$"\n{test.Name}: {(accepted?"PASS":"FAIL")} ({job.State}), run {job.Id}\n");
                if(job.State=="cancelled")suite.Cancellation.Token.ThrowIfCancellationRequested();
            }
            suite.State=passed==cases.Length?"succeeded":"failed";
            suite.Stage="completed";
            if(suite.State=="failed")suite.Error=$"{passed}/{cases.Length} matrix cases passed.";
        }
        catch(OperationCanceledException){suite.State="cancelled";suite.Stage="stopped";suite.Error="The owned matrix was stopped.";}
        catch(Exception exception){suite.State="failed";suite.Stage="failed";suite.Error=exception.Message;}
        finally
        {
            suite.DurationMs=timer.ElapsedMilliseconds;
            try
            {
                File.WriteAllText(Path.Combine(suite.Directory,"results.json"),JsonSerializer.Serialize(new{matrixSummary=new{suiteId="cgal-validation-v1",total=cases.Length,passed,cases=outcomes}},ScientificJson),new UTF8Encoding(false));
                ScientificFinish(suite);
                ScientificLog(suite,$"\n[{suite.State}] {passed}/{cases.Length} passed in {suite.DurationMs} ms\n");
            }
            catch(Exception exception){Debug.WriteLine($"CGAL matrix final log failed: {exception}");}
            finally
            {
                _scientificJobs[suite.ProfileId+":"+suite.RuntimeId]=suite;
                ScientificSend(new{type="scientific.runtime.job",job=ScientificJobSnapshot(suite)});
                _scientificGate.Release();
            }
        }
    }
}
