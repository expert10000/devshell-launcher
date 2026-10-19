using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal sealed record ScientificBooleanParameters(string InputAId, string InputBId, string Operation, string OutputName, double ScaleB, double[] TranslateB)
{
    internal static ScientificBooleanParameters Parse(JsonElement value)
    {
        var a = value.GetProperty("inputAId").GetString() ?? "";
        var b = value.GetProperty("inputBId").GetString() ?? "";
        var operation = value.GetProperty("operation").GetString() ?? "";
        var output = value.GetProperty("outputName").GetString() ?? "";
        var scale = value.GetProperty("scaleB").GetDouble();
        var translate = value.GetProperty("translateB").EnumerateArray().Select(item => item.GetDouble()).ToArray();
        if (a.Length is 0 or > 256 || b.Length is 0 or > 256) throw new InvalidOperationException("Select two registered meshes.");
        if (operation is not ("union" or "intersection" or "difference")) throw new InvalidOperationException("Choose Union, Intersection, or Difference A minus B.");
        if (!Regex.IsMatch(output, @"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.m3dm$") || output.Equals("operand-a.m3dm", StringComparison.OrdinalIgnoreCase) || output.Equals("operand-b.m3dm", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Choose a safe M3DM output filename; operand-a and operand-b are reserved for input snapshots.");
        if (!double.IsFinite(scale) || scale < 0.000001 || scale > 1000 || translate.Length != 3 || translate.Any(item => !double.IsFinite(item) || Math.Abs(item) > 1000000))
            throw new InvalidOperationException("Use a positive mesh B scale between 0.000001 and 1000, and finite translation coordinates within +/-1000000.");
        return new(a, b, operation, output, scale, translate);
    }
}
