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
        var required = new[] { "runtime.inventory", "python.version", "cgal.python.import",
            "geometry.point3", "cgal.cpp.compile-link", "mesh.repair", "mesh.repair",
            "mesh.repair", "mesh.repair", "mesh.repair" };
        var levels = new JsonArray();
        for (var index = 0; index < required.Length; index++)
        {
            var level = "L" + index;
            var selected = runs.SelectMany(run => (run["qualifications"]?.AsArray().OfType<JsonObject>() ?? [])
                    .Where(record => record["level"]?.GetValue<string>() == level
                        && record["capabilityId"]?.GetValue<string>() == required[index])
                    .Select(record => (Run: run, Record: record)))
                .OrderByDescending(item => item.Record["status"]?.GetValue<string>() == "current")
                .ThenByDescending(item => item.Run["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                .FirstOrDefault();
            levels.Add(new JsonObject { ["level"] = level, ["capabilityId"] = required[index],
                ["status"] = selected.Record?["status"]?.GetValue<string>() ?? "missing",
                ["runId"] = selected.Run?["runId"]?.DeepClone(),
                ["recordId"] = selected.Record?["recordId"]?.DeepClone(),
                ["reasons"] = selected.Record?["staleReasons"]?.DeepClone() ?? new JsonArray() });
        }
        var earliest = Enumerable.Range(0, 10).FirstOrDefault(index =>
            levels[index]?["status"]?.GetValue<string>() != "current", 10);
        var recipes = current.Length > 0 ? Array.Empty<string>() : earliest <= 4 ? RepairRecipes
            : RepairRecipes.Skip(Math.Min(earliest - 3, RepairRecipes.Length)).ToArray();
        return new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.cgal-repair-export-audit",
            ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.repair", ["profileId"] = profile,
            ["verifiedRunCount"] = runs.Count, ["consumerFilesAvailable"] = RepairSourceFiles(math3d) != null,
            ["capabilityDeclared"] = ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.repair"),
            ["eligible"] = current.Length > 0, ["currentRunId"] = current.FirstOrDefault()?["runId"]?.DeepClone(),
            ["currentRecordId"] = current.FirstOrDefault()?["recordId"]?.DeepClone(),
            ["mode"] = current.Length > 0 ? "current" : earliest <= 4 ? "full" : "resume",
            ["earliestRequiredLevel"] = current.Length > 0 ? null : "L" + earliest,
            ["levels"] = levels,
            ["recipes"] = new JsonArray(recipes.Select(item => (JsonNode?)JsonValue.Create(item)).ToArray()),
            ["exportReason"] = current.Length > 0 ? null : "No current repair qualification at L" + earliest,
            ["candidates"] = candidates,
            ["rejectedL9Runs"] = new JsonArray(rejected.Select(item => (JsonNode?)item).ToArray()) };
    }

    static JsonObject? ExportRepair(string repo, string installed, string math3d, string profile)
    {
        if (!ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.repair")) return null;
        var files = RepairSourceFiles(math3d);
        if (files == null) return null;
        JsonObject contract;
        try { contract = ScientificRepairProductContract.Load(repo); }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException) { return null; }
        var runs = RepairRuns(repo, installed, math3d, profile);
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var currentIds = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.repair")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var evidence = result["repairProductEvidence"];
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (evidence?["productContractSha256"]?.GetValue<string>() != Digest(contract)
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(files)
                || lower is not { Count: 9 }
                || lower.Where((item, index) => item?["level"]?.GetValue<string>() != "L" + index
                    || item?["recordId"]?.GetValue<string>() is not { } id || !currentIds.Contains(id)).Any()) continue;
            var cases = evidence["cases"] as JsonArray;
            var fixtures = ScientificRepairFixtures.Manifest(repo)["fixtures"]!.AsArray();
            if (cases?.Count != 4) continue;
            var references = new JsonArray();
            var valid = true;
            for (var index = 0; index < 4; index++)
            {
                var item = cases[index];
                var fixture = fixtures[index];
                var id = fixture?["caseId"]?.GetValue<string>();
                var source = Path.Combine(repo, fixture!["path"]!.GetValue<string>().Replace('/', Path.DirectorySeparatorChar));
                var output = Path.Combine(directory, "cases", id!, "repaired.obj");
                if (item is not JsonObject caseItem || caseItem["caseId"]?.GetValue<string>() != id
                    || caseItem["recipeId"]?.GetValue<string>() != fixture["recipeId"]?.GetValue<string>()
                    || !File.Exists(source) || !File.Exists(output)
                    || HashFile(source) != fixture["sha256"]?.GetValue<string>()
                    || HashFile(output) != caseItem["outputSha256"]?.GetValue<string>()
                    || caseItem["inputSha256"]?.GetValue<string>() != fixture["sha256"]?.GetValue<string>())
                { valid = false; break; }
                references.Add(new JsonObject { ["caseId"] = id, ["recipeId"] = caseItem["recipeId"]?.DeepClone(),
                    ["inputSha256"] = fixture["sha256"]?.DeepClone(),
                    ["outputSha256"] = caseItem["outputSha256"]?.DeepClone(),
                    ["m3dmSha256"] = caseItem["artifactHashes"]?["product/repaired.m3dm"]?.DeepClone() });
            }
            if (!valid) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var binary = fingerprint["components"]?["worker"]?["executedFiles"]?.AsArray().OfType<JsonObject>()
                .FirstOrDefault(item => item["role"]?.GetValue<string>() == "cgal-hole-repair-worker");
            var binaryHash = binary?["sha256"]?.GetValue<string>();
            if (binaryHash is not { Length: 64 }) continue;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.repair",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            return new JsonObject { ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.repair",
                ["level"] = "L9", ["scope"] = "four pinned public CGAL hole-repair fixtures",
                ["sourceRunId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-cgal-hole-repair-worker.py")),
                ["workerBinarySha256"] = binaryHash,
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = Digest(contract),
                ["consumerSources"] = files, ["consumerSourceSha256"] = Digest(files),
                ["fixtureManifestSha256"] = contract["fixtureManifestSha256"]?.DeepClone(),
                ["referenceCases"] = references, ["referenceInputSha256"] = references[0]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = references[0]?["outputSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceL8RunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceL8RecordId"]?.DeepClone(),
                ["supportingRecords"] = support };
        }
        return null;
    }
}
