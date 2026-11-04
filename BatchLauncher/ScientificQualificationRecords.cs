using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

// L0-L3 records describe only the named inventory or probe that passed in this run.
// The file is written once; History derives current status without changing it.
public static class ScientificQualificationRecords
{
    private static string Digest(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static JsonObject? Manifest(string runtimeId, string sourceRoot, string installedRoot, string? expectedHash)
    {
        var installed = Path.Combine(installedRoot, "runtimes", runtimeId, "runtime.json");
        var path = File.Exists(installed) ? installed : Path.Combine(sourceRoot, "runtimes", runtimeId, "runtime.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 1048576) return null;
        var actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        if (!string.Equals(actual, expectedHash, StringComparison.OrdinalIgnoreCase)) return null;
        return JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
    }

    private static JsonObject Record(string runId, string runtimeId, string capabilityId, string level,
        string evidenceId, string fingerprintSha256, string suiteRevisionSha256, JsonObject contract,
        string? evidenceSha256 = null)
    {
        var record = new JsonObject
        {
            ["schemaVersion"] = 1, ["runId"] = runId, ["runtimeId"] = runtimeId,
            ["capabilityId"] = capabilityId, ["level"] = level, ["evidenceId"] = evidenceId,
            ["runFingerprintSha256"] = fingerprintSha256, ["suiteRevisionSha256"] = suiteRevisionSha256,
            ["contract"] = contract.DeepClone()
        };
        if (evidenceSha256 != null) record["evidenceSha256"] = evidenceSha256;
        record["recordId"] = Digest(record.ToJsonString());
        return record;
    }

    private static string[] Arguments(JsonNode? step) => step?["arguments"] is JsonArray values
        ? values.Select(item => item?.GetValue<string>() ?? "").ToArray() : Array.Empty<string>();

    private static bool HasArgument(string[] arguments, string option, string value)
    {
        for (var index = 0; index < arguments.Length - 1; index++)
            if (arguments[index] == option && string.Equals(arguments[index + 1], value, StringComparison.OrdinalIgnoreCase))
                return true;
        return false;
    }

    private static string? CompileLinkHash(string directory, string sourceRoot, string runtimeId,
        JsonObject result, JsonObject components)
    {
        if (runtimeId is not ("cgal-win-conda" or "vtk-win-conda")
            || result["steps"] is not JsonArray steps || steps.Count != 2
            || result["compileLink"] is not JsonObject buildEvidence
            || components["worker"]?["executedFiles"] is not JsonArray executed
            || components["environment"]?["toolchain"]?["cmake"]?["state"]?.GetValue<string>() != "recorded"
            || components["environment"]?["toolchain"]?["msvcCompiler"]?["state"]?.GetValue<string>() != "recorded"
            || string.IsNullOrWhiteSpace(result["versions"]?["msvc"]?.GetValue<string>())) return null;
        var kind = runtimeId.StartsWith("cgal", StringComparison.Ordinal) ? "cgal" : "vtk";
        var build = Path.Combine(directory, "build");
        var source = Path.Combine(sourceRoot, "scientific", "smoke", kind);
        var configure = steps[0]; var compile = steps[1];
        var configureArguments = Arguments(configure); var compileArguments = Arguments(compile);
        if (configure?["stage"]?.GetValue<string>() != "configure" || compile?["stage"]?.GetValue<string>() != "build"
            || configure["exitCode"]?.GetValue<int>() != 0 || compile["exitCode"]?.GetValue<int>() != 0
            || !HasArgument(configureArguments, "-S", source) || !HasArgument(configureArguments, "-B", build)
            || !HasArgument(compileArguments, "--build", build) || !HasArgument(compileArguments, "--config", "Release")) return null;
        var cmake = components["environment"]?["toolchain"]?["cmake"]?["sha256"]?.GetValue<string>();
        if (!string.Equals(configure["executable"]?.GetValue<string>(), compile["executable"]?.GetValue<string>(), StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetFileName(configure["executable"]?.GetValue<string>()), "cmake.exe", StringComparison.OrdinalIgnoreCase)
            || !executed.Any(item => item?["role"]?.GetValue<string>() == "executable"
                && item?["name"]?.GetValue<string>() == "cmake.exe" && item?["sha256"]?.GetValue<string>() == cmake)) return null;
        var binaryName = "devshell_" + kind + "_smoke.exe";
        var hash = buildEvidence["sha256"]?.GetValue<string>();
        var binary = Path.Combine(build, "Release", binaryName);
        if (buildEvidence["binaryName"]?.GetValue<string>() != binaryName || hash?.Length != 64 || !File.Exists(binary)) return null;
        var actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(binary))).ToLowerInvariant();
        return string.Equals(actual, hash, StringComparison.OrdinalIgnoreCase)
            && executed.Any(item => item?["role"]?.GetValue<string>() == "linked-binary"
                && item?["name"]?.GetValue<string>() == binaryName
                && string.Equals(item?["sha256"]?.GetValue<string>(), hash, StringComparison.OrdinalIgnoreCase))
            ? hash : null;
    }

    public static string? Save(string directory, JsonObject result, string sourceRoot, string installedRoot)
    {
        if (result["state"]?.GetValue<string>() != "succeeded") return null;
        var runId = result["runId"]?.GetValue<string>();
        var runtimeId = result["runtimeId"]?.GetValue<string>();
        var fingerprintSha256 = result["runFingerprintSha256"]?.GetValue<string>();
        if (runId == null || runtimeId == null || fingerprintSha256 == null) return null;
        ScientificRunFingerprint.Verify(directory, fingerprintSha256);
        var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var components = fingerprint?["components"] as JsonObject;
        var suiteRevision = components?["suite"]?["revisionSha256"]?.GetValue<string>();
        var contract = components?["contract"] as JsonObject;
        var manifestHash = contract?["runtimeManifest"]?["sha256"]?.GetValue<string>();
        if (suiteRevision?.Length != 64 || manifestHash?.Length != 64 || contract == null
            || contract["providerRegistryVersion"]?.GetValue<int>() != ScientificProviderRegistry.ContractVersion)
            return null;
        var manifest = Manifest(runtimeId, sourceRoot, installedRoot, manifestHash);
        if (manifest == null) return null;
        var environment = components?["environment"];
        var packagesRecorded = environment?["condaPackageRecords"]?["state"]?.GetValue<string>() == "recorded"
            || environment?["systemPackageRecords"]?["state"]?.GetValue<string>() == "recorded";
        if (!packagesRecorded || components?["worker"]?["executedFiles"] is not JsonArray workers || workers.Count == 0)
            return null;
        var records = new List<JsonObject>();
        void Add(string capability, string level, string evidence, string? evidenceHash = null)
        {
            if (records.Any(item => item["capabilityId"]?.GetValue<string>() == capability
                && item["level"]?.GetValue<string>() == level)) return;
            records.Add(Record(runId, runtimeId, capability, level, evidence, fingerprintSha256, suiteRevision, contract, evidenceHash));
        }
        Add("runtime.inventory", "L0", "fingerprint.environment");
        var recipeId = result["recipeId"]?.GetValue<string>();
        if (recipeId == "lab.probe" && result["probeResults"] is JsonArray probeResults
            && manifest["probes"] is JsonArray declared)
        {
            var declarations = declared.OfType<JsonObject>().ToDictionary(item => item["id"]!.GetValue<string>(), StringComparer.Ordinal);
            var observations = probeResults.OfType<JsonObject>().ToArray();
            if (observations.Length == declarations.Count
                && observations.Select(item => item["id"]?.GetValue<string>()).Distinct(StringComparer.Ordinal).Count() == declarations.Count
                && observations.All(item => item["status"]?.GetValue<string>() == "passed"
                    && item["exitCode"]?.GetValue<int>() == 0
                    && declarations.ContainsKey(item["id"]?.GetValue<string>() ?? "")))
                foreach (var observation in observations)
                {
                    var id = observation["id"]!.GetValue<string>();
                    var declaration = declarations[id];
                    var level = declaration["readinessLevel"]?.GetValue<string>();
                    if (level is not ("L1" or "L2" or "L3") || observation["readinessLevel"]?.GetValue<string>() != level)
                        continue;
                    Add(declaration["capability"]?.GetValue<string>() ?? id, level, id);
                }
        }
        else if (runtimeId == "sage-wsl" && recipeId == "sage.version"
            && !string.IsNullOrWhiteSpace(result["versions"]?["sage"]?.GetValue<string>()))
            Add("runtime.executable", "L1", "sage.version");
        else if (runtimeId == "sage-wsl" && recipeId == "sage.factor-smoke"
            && result["validatedCapabilities"] is JsonArray capabilities
            && capabilities.Any(item => item?.GetValue<string>() == "math.symbolic")
            && result["evidence"]?["output"]?.GetValue<string>() == "verified: (x - 1) * (x + 1)")
        {
            Add("sage.python.binding", "L2", "sage.factor-smoke");
            Add("math.symbolic", "L3", "sage.factor-smoke");
        }
        else if (recipeId == "compile-link" && manifest["qualificationRecipes"] is JsonArray recipes)
        {
            var declaration = recipes.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "compile-link"
                && item["readinessLevel"]?.GetValue<string>() == "L4");
            var expectedCapability = runtimeId == "cgal-win-conda" ? "cgal.cpp.compile-link"
                : runtimeId == "vtk-win-conda" ? "vtk.cpp.compile-link" : null;
            var hash = CompileLinkHash(directory, sourceRoot, runtimeId, result, components!);
            if (declaration?["capability"]?.GetValue<string>() == expectedCapability && hash != null)
                Add(expectedCapability!, "L4", "compile-link", hash);
        }
        var document = new JsonObject
        {
            ["schemaVersion"] = 1, ["runId"] = runId, ["runtimeId"] = runtimeId,
            ["runFingerprintSha256"] = fingerprintSha256,
            ["records"] = new JsonArray(records.Select(item => (JsonNode?)item).ToArray())
        };
        var text = document.ToJsonString();
        var target = Path.Combine(directory, "qualifications.json");
        var temporary = Path.Combine(directory, $".qualifications-{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporary, text, new UTF8Encoding(false));
            File.Move(temporary, target);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
        return Digest(text);
    }

    public static JsonArray Verify(string directory, JsonElement result)
    {
        if (!result.TryGetProperty("qualificationSha256", out var expectedValue)
            || expectedValue.GetString() is not { Length: 64 } expected)
            throw new InvalidDataException("Qualification reference is missing.");
        var path = Path.Combine(directory, "qualifications.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 262144)
            throw new InvalidDataException("Qualification record is missing or too large.");
        var text = File.ReadAllText(path);
        if (!string.Equals(Digest(text), expected, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Qualification record does not match saved evidence.");
        var document = JsonNode.Parse(text) as JsonObject;
        var records = document?["records"] as JsonArray;
        var runId = result.GetProperty("runId").GetString();
        var runtimeId = result.GetProperty("runtimeId").GetString();
        var fingerprintSha256 = result.GetProperty("runFingerprintSha256").GetString();
        if (document?["schemaVersion"]?.GetValue<int>() != 1 || records == null || records.Count == 0
            || document["runId"]?.GetValue<string>() != runId
            || document["runtimeId"]?.GetValue<string>() != runtimeId
            || document["runFingerprintSha256"]?.GetValue<string>() != fingerprintSha256
            || result.GetProperty("state").GetString() != "succeeded")
            throw new InvalidDataException("Qualification identity is invalid.");
        var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var suiteRevision = fingerprint?["components"]?["suite"]?["revisionSha256"]?.GetValue<string>();
        var contract = fingerprint?["components"]?["contract"] as JsonObject;
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var item in records)
        {
            if (item is not JsonObject record) throw new InvalidDataException("Invalid qualification entry.");
            var copy = (JsonObject)record.DeepClone();
            var recordId = copy["recordId"]?.GetValue<string>();
            copy.Remove("recordId");
            if (recordId == null || !ids.Add(recordId) || Digest(copy.ToJsonString()) != recordId
                || record["schemaVersion"]?.GetValue<int>() != 1
                || record["runId"]?.GetValue<string>() != runId
                || record["runtimeId"]?.GetValue<string>() != runtimeId
                || record["runFingerprintSha256"]?.GetValue<string>() != fingerprintSha256
                || record["suiteRevisionSha256"]?.GetValue<string>() != suiteRevision
                || record["contract"]?.ToJsonString() != contract?.ToJsonString()
                || record["level"]?.GetValue<string>() is not ("L0" or "L1" or "L2" or "L3" or "L4"))
                throw new InvalidDataException("Qualification entry does not match its run.");
            if (record["level"]?.GetValue<string>() == "L4")
            {
                var kind = runtimeId == "cgal-win-conda" ? "cgal" : runtimeId == "vtk-win-conda" ? "vtk" : null;
                var binaryName = kind == null ? null : "devshell_" + kind + "_smoke.exe";
                var binary = binaryName == null ? null : Path.Combine(directory, "build", "Release", binaryName);
                if (binary == null || !File.Exists(binary)
                    || record["capabilityId"]?.GetValue<string>() != kind + ".cpp.compile-link"
                    || record["evidenceId"]?.GetValue<string>() != "compile-link"
                    || !string.Equals(record["evidenceSha256"]?.GetValue<string>(),
                        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(binary))).ToLowerInvariant(), StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Compiled qualification binary has changed.");
            }
        }
        return records;
    }

    public static JsonArray Assess(JsonArray records, JsonObject sourceDrift, JsonObject environmentDrift)
    {
        var source = sourceDrift["state"]?.GetValue<string>();
        var environment = environmentDrift["state"]?.GetValue<string>();
        var contractChanged = records.Any(item => item?["contract"]?["providerRegistryVersion"]?.GetValue<int>()
            != ScientificProviderRegistry.ContractVersion
            || item?["contract"]?["requestSchemaVersion"]?.GetValue<int>() != 1
            || item?["contract"]?["resultSchemaVersion"]?.GetValue<int>() != 1);
        var state = source == "stale" || environment == "stale" || contractChanged ? "stale"
            : source == "unknown" || environment == "unknown" ? "unknown" : "current";
        var reasons = new JsonArray();
        if (source != "current") reasons.Add("source " + source);
        if (environment != "current") reasons.Add("environment " + environment);
        if (contractChanged) reasons.Add("contract version changed");
        foreach (var reason in sourceDrift["reasons"]?.AsArray() ?? new JsonArray()) reasons.Add(reason?.DeepClone());
        foreach (var reason in environmentDrift["reasons"]?.AsArray() ?? new JsonArray()) reasons.Add(reason?.DeepClone());
        return new JsonArray(records.Select(item =>
        {
            var view = (JsonObject)item!.DeepClone();
            view["status"] = state;
            view["staleReasons"] = reasons.DeepClone();
            return (JsonNode?)view;
        }).ToArray());
    }

    public static JsonObject Summarize(string runtimeId, IEnumerable<JsonObject> runs)
    {
        var current = new Dictionary<string, List<(int Level, JsonObject Run)>>(StringComparer.Ordinal);
        var excludedFailed = 0;
        var excludedStale = 0;
        var excludedUnknown = 0;
        foreach (var run in runs)
        {
            if (run["runtimeId"]?.GetValue<string>() != runtimeId) continue;
            if (run["state"]?.GetValue<string>() != "succeeded") { excludedFailed++; continue; }
            if (run["qualifications"] is not JsonArray records) continue;
            foreach (var record in records.OfType<JsonObject>())
            {
                var status = record["status"]?.GetValue<string>();
                if (status == "stale") { excludedStale++; continue; }
                if (status != "current") { excludedUnknown++; continue; }
                var capability = record["capabilityId"]?.GetValue<string>();
                var level = record["level"]?.GetValue<string>();
                if (capability == null || level?.Length != 2 || level[0] != 'L' || !int.TryParse(level[1..], out var number))
                    continue;
                if (!current.TryGetValue(capability, out var candidates))
                    current[capability] = candidates = new List<(int, JsonObject)>();
                candidates.Add((number, new JsonObject
                {
                    ["runId"] = run["runId"]?.GetValue<string>(),
                    ["recordId"] = record["recordId"]?.GetValue<string>(),
                    ["recipeId"] = run["recipeId"]?.GetValue<string>(),
                    ["finishedAtUtc"] = run["finishedAtUtc"]?.GetValue<string>()
                }));
            }
        }
        var capabilities = new JsonArray();
        foreach (var (capability, candidates) in current.OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            var highest = candidates.Max(item => item.Level);
            capabilities.Add(new JsonObject
            {
                ["capabilityId"] = capability,
                ["highestLevel"] = "L" + highest,
                ["supportingRuns"] = new JsonArray(candidates.Where(item => item.Level == highest)
                    .OrderByDescending(item => item.Run["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                    .Select(item => (JsonNode?)item.Run).ToArray())
            });
        }
        return new JsonObject { ["runtimeId"] = runtimeId, ["capabilities"] = capabilities,
            ["excludedFailedRuns"] = excludedFailed, ["excludedStaleRecords"] = excludedStale,
            ["excludedUnknownRecords"] = excludedUnknown };
    }
}
