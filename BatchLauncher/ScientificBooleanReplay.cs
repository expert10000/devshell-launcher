using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal static class ScientificBooleanReplay
{
    internal static ScientificBooleanParameters Read(JsonElement request, JsonElement result, string profileId)
    {
        foreach (var key in new[] { "runId", "profileId", "runtimeId", "recipeId" })
            if (request.GetProperty(key).GetString() != result.GetProperty(key).GetString()) throw new InvalidOperationException("Saved request and result do not match.");
        if (request.GetProperty("profileId").GetString() != profileId || request.GetProperty("runtimeId").GetString() != "cgal-win-conda"
            || request.GetProperty("recipeId").GetString() != "cgal.boolean" || !Regex.IsMatch(request.GetProperty("runId").GetString() ?? "", "^[0-9a-f]{32}$"))
            throw new InvalidOperationException("Select a saved Boolean run in this profile.");
        var parameters = ScientificBooleanParameters.Parse(request.GetProperty("parameters"));
        var inputs = request.GetProperty("inputArtifacts");
        if (inputs.GetArrayLength() != 2 || inputs[0].GetProperty("datasetId").GetString() != parameters.InputAId
            || inputs[1].GetProperty("datasetId").GetString() != parameters.InputBId) throw new InvalidOperationException("Saved operands do not match the Boolean parameters.");
        var recorded = result.GetProperty("inputArtifacts");
        if (recorded.GetArrayLength() != 2) throw new InvalidOperationException("Saved result is missing its two operand identities.");
        for (var index = 0; index < 2; index++) VerifyInput(inputs[index], (JsonObject)JsonNode.Parse(recorded[index].GetRawText())!);
        return parameters;
    }

    internal static void VerifyInput(JsonElement original, JsonObject current)
    {
        if (original.GetProperty("datasetId").GetString() != current["datasetId"]?.GetValue<string>()
            || original.GetProperty("sha256").GetString() != current["sha256"]?.GetValue<string>()
            || original.GetProperty("bytes").GetInt64() != current["bytes"]?.GetValue<long>())
            throw new InvalidOperationException("A saved operand has changed. Import it as a new mesh and start a new operation; rerun never substitutes different bytes silently.");
    }
}
