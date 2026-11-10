using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    // The older CGAL interoperability check deliberately fixes a four-point tetrahedron.
    // Repair outputs have different topology, so compare each consumer with its own
    // independently parsed OBJ and keep the malformed-input rejection in scope.
    public static bool ValidRepairInteropSemantics(JsonObject source, JsonObject vtk, JsonObject math3d,
        JsonObject rejection, string malformedSha256, string vtkReaderSha256, string importerSha256)
    {
        var points = source["points"]?.GetValue<int>() ?? 0;
        var triangles = source["triangles"]?.GetValue<int>() ?? 0;
        var hash = source["artifactSha256"]?.GetValue<string>();
        if (source["format"]?.GetValue<string>() != "obj" || points < 4 || triangles < 4
            || hash is not { Length: 64 } || source["closed"]?.GetValue<bool>() != true
            || source["boundaryEdges"]?.GetValue<int>() != 0
            || source["nonManifoldEdges"]?.GetValue<int>() != 0
            || source["bounds"] is not JsonArray bounds || bounds.Count != 6
            || rejection["state"]?.GetValue<string>() != "rejected"
            || rejection["inputObjSha256"]?.GetValue<string>() != malformedSha256
            || rejection["readerSourceSha256"]?.GetValue<string>() != vtkReaderSha256
            || rejection["reason"]?.GetValue<string>()?.Contains("invalid face indices", StringComparison.Ordinal) != true)
            return false;
        var sourceVolume = source["signedVolume"]?.GetValue<double>() ?? double.NaN;
        var sourceArea = source["surfaceArea"]?.GetValue<double>() ?? double.NaN;
        if (!double.IsFinite(sourceVolume) || sourceVolume <= 0
            || !double.IsFinite(sourceArea) || sourceArea <= 0) return false;
        foreach (var (consumer, name, sourceField, expectedSource) in new[] {
            (vtk, "VTK vtkOBJReader", "readerSourceSha256", vtkReaderSha256),
            (math3d, "MATH3D desktop loadSurfaceMeshFromFile", "importerSourceSha256", importerSha256) })
        {
            if (consumer["consumer"]?.GetValue<string>() != name
                || consumer[sourceField]?.GetValue<string>() != expectedSource
                || consumer["inputObjSha256"]?.GetValue<string>() != hash
                || consumer["points"]?.GetValue<int>() != points
                || consumer["triangles"]?.GetValue<int>() != triangles
                || consumer["boundaryEdges"]?.GetValue<int>() != 0
                || consumer["nonManifoldEdges"]?.GetValue<int>() != 0
                || consumer["closed"]?.GetValue<bool>() != true
                || consumer["bounds"] is not JsonArray comparedBounds || comparedBounds.Count != 6)
                return false;
            for (var i = 0; i < 6; i++)
            {
                var expected = bounds[i]?.GetValue<double>() ?? double.NaN;
                var actual = comparedBounds[i]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(expected) || !double.IsFinite(actual)
                    || Math.Abs(expected - actual) > 1e-6) return false;
            }
            foreach (var (field, expected) in new[] { ("signedVolume", sourceVolume), ("surfaceArea", sourceArea) })
            {
                var actual = consumer[field]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(actual) || Math.Abs(actual - expected) > 1e-6) return false;
            }
        }
        return true;
    }
}
