using System.Text.Json;

namespace BatchLauncher;

internal static class AppStateStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public static AppState Load()
    {
        AppPaths.EnsureConfigDirectory();
        if (!File.Exists(AppPaths.StatePath))
        {
            return new AppState { RestoreSessions = false };
        }

        try
        {
            var json = File.ReadAllText(AppPaths.StatePath);
            var state = JsonSerializer.Deserialize<AppState>(json, Options) ?? new AppState();
            state.Tabs.Clear();
            state.ActiveTabId = null;
            state.RestoreSessions = false;
            return state;
        }
        catch
        {
            return new AppState { RestoreSessions = false };
        }
    }

    public static void Save(AppState state)
    {
        AppPaths.EnsureConfigDirectory();
        state.Tabs.Clear();
        state.ActiveTabId = null;
        state.RestoreSessions = false;
        var json = JsonSerializer.Serialize(state, Options);
        File.WriteAllText(AppPaths.StatePath, json);
    }
}
