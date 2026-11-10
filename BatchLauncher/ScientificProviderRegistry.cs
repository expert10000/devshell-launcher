namespace BatchLauncher;

// The native boundary admits only actions declared for the selected provider.
// Manifest probes and recipes remain in runtimes/<id>/runtime.json.
public sealed record ScientificProvider(
    string RuntimeId, string Backend, string EnvironmentName, bool NativeManaged,
    bool LabProbe, string[] Actions);

public static class ScientificProviderRegistry
{
    public const int ContractVersion = 1;

    public static IReadOnlyList<ScientificProvider> Providers { get; } = new[]
    {
        new ScientificProvider("cgal-win-conda", "windows-native", "devshell-cgal", true, true,
            new[] { "import-meshes", "repair-fixtures", "test-matrix", "math3d-readiness", "environment", "terminal", "export", "test-hold", "recipe", "boolean-recipe", "cgal-recipe", "run-matrix", "real-mesh-suite", "math3d-integration", "math3d-prepare-run", "l5-worker", "l5-cgal-repair", "l6-reproduce", "l6-cgal-repair", "l7-cgal-vtk-math3d", "l8-resilience", "l9-math3d-product" }),
        new ScientificProvider("vtk-win-conda", "windows-native", "devshell-vtk", true, true,
            new[] { "environment", "terminal", "export", "test-hold", "recipe", "vtk-rejections", "l5-worker", "l6-reproduce", "l7-math3d-import" }),
        new ScientificProvider("gmsh-win-conda", "windows-native", "devshell-scientific", true, true,
            new[] { "install-runtime", "environment", "terminal", "recipe", "l5-worker", "l6-reproduce", "l7-gmsh-interop", "l8-gmsh-resilience", "l9-gmsh-product", "l5-gmsh-volume", "l6-gmsh-volume", "l7-gmsh-volume", "l8-gmsh-volume", "gmsh-volume-product-readiness", "l9-gmsh-volume" }),
        new ScientificProvider("python-win-conda", "windows-native", "devshell-scientific", false, true,
            Array.Empty<string>()),
        new ScientificProvider("sage-wsl", "wsl", "", false, true,
            new[] { "sage-recipe" })
    };

    public static ScientificProvider Get(string runtimeId) => Providers.SingleOrDefault(provider => provider.RuntimeId == runtimeId)
        ?? throw new InvalidOperationException("No provider is registered for this runtime.");

    public static ScientificProvider RequireAction(string runtimeId, string action)
    {
        var provider = Get(runtimeId);
        if (!(action == "lab-probe" && provider.LabProbe)
            && !provider.Actions.Contains(action, StringComparer.Ordinal))
            throw new InvalidOperationException($"{action} is not registered for {runtimeId}.");
        return provider;
    }
}
