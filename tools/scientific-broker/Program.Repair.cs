using System.Text.Json.Nodes;
using BatchLauncher;

static partial class BrokerManifest
{
    static readonly string[] RepairRecipes = ["lab.probe", "compile-link", "l5.cgal-repair",
        "l6.cgal-repair", "l7.cgal-repair", "l8.cgal-repair", "l9.cgal-repair"];

    static JsonObject? RepairSourceFiles(string root)
    {
        var files = new JsonObject();
        foreach (var name in ScientificRepairProductContract.ConsumerSources)
        {
            var path = Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            files[name] = HashFile(path);
        }
        return files;
    }

    static List<JsonObject> RepairRuns(string repo, string installed, string math3d, string profile,
        List<JsonObject>? rejected = null)
    {
        var runs = ReadRuns(repo, installed, profile, "cgal-win-conda", rejected);
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        var importer = Path.Combine(math3d, "renderer", "src", "mesh", "surfaceMesh.ts");
        string? vtkEnvironment = null;
        try
        {
            var captured = ScientificRunFingerprint.Capture("vtk-win-conda", profile, repo, installed,
                Path.Combine(repo, ".scientific", "runtime-report.json"));
            if (captured["environment"]?["condaPackageRecords"]?["state"]?.GetValue<string>() == "recorded")
                vtkEnvironment = Digest(captured["environment"]);
        }
        catch (Exception) { }
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids, includeL8: false, includeL9: false);
                ScientificQualificationRecords.AssessL7Consumer(records,
                    File.Exists(importer) ? HashFile(importer) : null, vtkEnvironment);
            }
        ids.UnionWith(CurrentIds(runs, "L7"));
        AssessDependencies(runs, ids, l9: false);
        ids.UnionWith(CurrentIds(runs, "L8"));
        var files = RepairSourceFiles(math3d);
        string? contractHash = null;
        try { contractHash = Digest(ScientificRepairProductContract.Load(repo)); }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException) { }
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids);
                ScientificQualificationRecords.AssessRepairL9Consumer(records,
                    files is null ? null : Digest(files), contractHash);
            }
        return runs;
    }

    static JsonObject AuditRepair(string repo, string installed, string math3d, string profile)
    {
        var rejected = new List<JsonObject>();
        var runs = RepairRuns(repo, installed, math3d, profile, rejected);
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var current = summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.repair")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal).ToArray();
        var byId = Records(runs).Where(item => item["recordId"]?.GetValue<string>() != null)
            .GroupBy(item => item["recordId"]!.GetValue<string>(), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
        var candidates = new JsonArray();
        foreach (var run in runs.OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            foreach (var record in run["qualifications"]?.AsArray().OfType<JsonObject>() ?? [])
            {
                if (record["evidenceId"]?.GetValue<string>() != "l9.cgal-repair") continue;
                var support = new JsonArray();
                foreach (var item in record["lowerQualification"]?["records"]?.AsArray() ?? [])
                {
                    var id = item?["recordId"]?.GetValue<string>();
                    var found = id != null && byId.TryGetValue(id, out var existing) ? existing : null;
                    support.Add(new JsonObject { ["level"] = item?["level"]?.DeepClone(), ["recordId"] = id,
                        ["status"] = found?["status"]?.DeepClone(),
                        ["reasons"] = found?["staleReasons"]?.DeepClone() });
                }
                candidates.Add(new JsonObject { ["runId"] = run["runId"]?.DeepClone(),
                    ["recordId"] = record["recordId"]?.DeepClone(), ["status"] = record["status"]?.DeepClone(),
                    ["reasons"] = record["staleReasons"]?.DeepClone(), ["support"] = support });
                if (candidates.Count >= 20) break;
            }
            if (candidates.Count >= 20) break;
        }
        var earliest = 0;
        if (candidates.FirstOrDefault()?["support"] is JsonArray chain && chain.Count == 9)
            earliest = Enumerable.Range(0, 9).FirstOrDefault(index =>
                chain[index]?["level"]?.GetValue<string>() != "L" + index
                || chain[index]?["status"]?.GetValue<string>() != "current", 9);
        var recipes = current.Length > 0 ? Array.Empty<string>() : earliest <= 4 ? RepairRecipes
            : RepairRecipes.Skip(earliest - 3).ToArray();
        return new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.cgal-repair-export-audit",
            ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.repair", ["profileId"] = profile,
            ["verifiedRunCount"] = runs.Count, ["consumerFilesAvailable"] = RepairSourceFiles(math3d) != null,
            ["capabilityDeclared"] = ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.repair"),
            ["eligible"] = current.Length > 0, ["currentRunId"] = current.FirstOrDefault()?["runId"]?.DeepClone(),
            ["currentRecordId"] = current.FirstOrDefault()?["recordId"]?.DeepClone(),
            ["mode"] = current.Length > 0 ? "current" : earliest <= 4 ? "full" : "resume",
            ["recipes"] = new JsonArray(recipes.Select(item => (JsonNode?)JsonValue.Create(item)).ToArray()),
            ["exportReason"] = current.Length > 0 ? null : "No current four-case repair L9 qualification chain",
            ["candidates"] = candidates,
            ["rejectedL9Runs"] = new JsonArray(rejected.Select(item => (JsonNode?)item).ToArray()) };
    }
}
