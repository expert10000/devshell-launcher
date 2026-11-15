using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal static class ScientificWorkbenchOperationCatalog
{
    internal const int Version = 1;
    private const string RelativePath = "schemas/scientific-workbench-operations.v1.json";
    internal static void Validate(string sourceRoot, string runtimeId, string recipeId, JsonElement parameters, string inputPath)
    {
        var path = Path.Combine(sourceRoot, RelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(path) || new FileInfo(path).Length > 65536)
            throw new InvalidOperationException("Workbench operation catalog is missing or too large.");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var catalog = document.RootElement;
        if (catalog.GetProperty("schemaVersion").GetInt32() != Version)
            throw new InvalidOperationException("Unsupported Workbench operation catalog version.");
        var operation = catalog.GetProperty("operations").EnumerateArray()
            .FirstOrDefault(item => item.GetProperty("id").GetString() == recipeId);
        if (operation.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("Operation is not in the Workbench catalog.");
        var provider = runtimeId switch { "cgal-win-conda" => "cgal", "vtk-win-conda" => "vtk", _ => "" };
        if (operation.GetProperty("provider").GetString() != provider)
            throw new InvalidOperationException("Operation does not belong to the selected provider.");
        var extension = Path.GetExtension(inputPath).TrimStart('.').ToLowerInvariant();
        if (!operation.GetProperty("inputExtensions").EnumerateArray().Any(item => item.GetString() == extension))
            throw new InvalidOperationException($"{recipeId} does not accept .{extension} input.");
        var output = parameters.GetProperty("outputName").GetString() ?? "";
        var suffix = operation.GetProperty("output").GetString() ?? "";
        if (!Regex.IsMatch(output, $"^[a-zA-Z0-9][a-zA-Z0-9_.-]{{0,99}}\\.{Regex.Escape(suffix)}$"))
            throw new InvalidOperationException($"Output must be a safe .{suffix} filename.");
        var fields = operation.GetProperty("fields").EnumerateArray().ToDictionary(item => item.GetProperty("id").GetString()!, StringComparer.Ordinal);
        foreach (var parameter in parameters.EnumerateObject())
        {
            if (parameter.Name is "inputId" or "outputName") continue;
            if (recipeId == "cgal.validate" && parameter.Name == "testCaseId") continue;
            if (!fields.TryGetValue(parameter.Name, out var field))
                throw new InvalidOperationException($"Unknown {recipeId} parameter: {parameter.Name}.");
            if (field.GetProperty("kind").GetString() == "boolean")
            {
                if (parameter.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new InvalidOperationException($"{parameter.Name} must be boolean.");
                continue;
            }
            if (parameter.Value.ValueKind != JsonValueKind.Number || !parameter.Value.TryGetDouble(out var number)
                || !double.IsFinite(number) || number < field.GetProperty("min").GetDouble()
                || number > field.GetProperty("max").GetDouble()
                || field.TryGetProperty("integer", out var integer) && integer.GetBoolean() && number != Math.Truncate(number))
                throw new InvalidOperationException($"{parameter.Name} is outside the catalog limits.");
        }
        foreach (var field in fields)
            if (!parameters.TryGetProperty(field.Key, out _))
                throw new InvalidOperationException($"Missing {recipeId} parameter: {field.Key}.");
    }
}
