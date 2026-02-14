namespace BatchLauncher;

internal static class AppPaths
{
    private static readonly string AppBasePath = ResolveAppBasePath();

    public static string ConfigDirectory => AppBasePath;

    public static string ScriptsPath => Path.Combine(AppBasePath, "scripts.json");

    public static string ProfilesPath => Path.Combine(AppBasePath, "profile.json");

    public static string LegacyProfilesPath => Path.Combine(AppBasePath, "profiles.json");

    public static string LegacyProfilesPathAlt => Path.Combine(AppBasePath, "profile.json");

    public static string LegacyProfilesPathAlt2 => Path.Combine(AppBasePath, "profiles.json");

    public static string StatePath => Path.Combine(AppBasePath, "state.json");

    public static void EnsureConfigDirectory()
    {
        Directory.CreateDirectory(AppBasePath);
    }

    public static void EnsureProfilesDirectory()
    {
        Directory.CreateDirectory(AppBasePath);
    }

    private static string ResolveAppBasePath()
    {
        var baseDir = AppContext.BaseDirectory;
        var isBinOutput = baseDir.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}");
        if (!isBinOutput &&
            (File.Exists(Path.Combine(baseDir, "scripts.json")) ||
             File.Exists(Path.Combine(baseDir, "profile.json"))))
        {
            return baseDir;
        }

        var current = new DirectoryInfo(baseDir);
        for (var i = 0; i < 5 && current.Parent != null; i++)
        {
            current = current.Parent;
            if (File.Exists(Path.Combine(current.FullName, "scripts.json")) ||
                File.Exists(Path.Combine(current.FullName, "profile.json")))
            {
                return current.FullName;
            }
        }

        return baseDir;
    }
}
