using System.Globalization;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    // Independent, fixed-fixture gate. This does not qualify arbitrary repair inputs.
    internal static bool CgalRepairOutputValid(string path)
    {
        if (!File.Exists(path) || new FileInfo(path).Length is <= 0 or > 1048576) return false;
        var points = new List<double[]>();
        var faces = new List<int[]>();
        foreach (var line in File.ReadLines(path))
        {
            var tokens = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length == 0 || tokens[0].StartsWith('#')) continue;
            if (tokens[0] == "v")
            {
                if (tokens.Length != 4 || points.Count == 4) return false;
                var point = new double[3];
                for (var i = 0; i < 3; i++)
                    if (!double.TryParse(tokens[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out point[i])
                        || !double.IsFinite(point[i])) return false;
                points.Add(point);
            }
            else if (tokens[0] == "f")
            {
                if (tokens.Length != 4 || faces.Count == 4) return false;
                var face = new int[3];
                for (var i = 0; i < 3; i++)
                    if (!int.TryParse(tokens[i + 1].Split('/')[0], NumberStyles.None, CultureInfo.InvariantCulture, out face[i])
                        || face[i] is < 1 or > 4) return false;
                if (face.Distinct().Count() != 3) return false;
                faces.Add(face);
            }
            else return false;
        }
        if (points.Count != 4 || faces.Count != 4) return false;
        var expected = new[] { new[] { 0d, 0d, 0d }, new[] { 1d, 0d, 0d },
            new[] { 0d, 1d, 0d }, new[] { 0d, 0d, 1d } };
        if (points.Where(point => expected.Any(reference => Enumerable.Range(0, 3)
                .All(i => Math.Abs(point[i] - reference[i]) <= 1e-12))).Count() != 4
            || expected.Any(reference => points.Count(point => Enumerable.Range(0, 3)
                .All(i => Math.Abs(point[i] - reference[i]) <= 1e-12)) != 1)) return false;
        var edges = new Dictionary<(int, int), int>();
        var directed = new HashSet<(int, int)>();
        double volume = 0;
        foreach (var face in faces)
        {
            for (var i = 0; i < 3; i++)
            {
                var a = Math.Min(face[i], face[(i + 1) % 3]);
                var b = Math.Max(face[i], face[(i + 1) % 3]);
                edges[(a, b)] = edges.GetValueOrDefault((a, b)) + 1;
                if (!directed.Add((face[i], face[(i + 1) % 3]))) return false;
            }
            var a0 = points[face[0] - 1]; var b0 = points[face[1] - 1]; var c0 = points[face[2] - 1];
            volume += (a0[0] * (b0[1] * c0[2] - b0[2] * c0[1])
                + a0[1] * (b0[2] * c0[0] - b0[0] * c0[2])
                + a0[2] * (b0[0] * c0[1] - b0[1] * c0[0])) / 6;
        }
        return edges.Count == 6 && edges.Values.All(count => count == 2)
            && directed.All(edge => directed.Contains((edge.Item2, edge.Item1)))
            && Math.Abs(volume - 1d / 6d) <= 1e-12;
    }
}
