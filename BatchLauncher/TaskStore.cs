using System.Text.Json;

namespace BatchLauncher;

internal static class TaskStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static List<ScriptEntry> LoadTasks()
    {
        var path = AppPaths.ScriptsPath;
        if (!File.Exists(path))
        {
            return new List<ScriptEntry>();
        }

        try
        {
            var json = File.ReadAllText(path);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.ValueKind == JsonValueKind.Array)
            {
                return JsonSerializer.Deserialize<List<ScriptEntry>>(json, Options) ?? new List<ScriptEntry>();
            }

            if (doc.RootElement.ValueKind == JsonValueKind.Object)
            {
                if (doc.RootElement.TryGetProperty("tasks", out var tasksElement))
                {
                    if (tasksElement.ValueKind == JsonValueKind.Array)
                    {
                        return JsonSerializer.Deserialize<List<ScriptEntry>>(tasksElement.GetRawText(), Options)
                            ?? new List<ScriptEntry>();
                    }

                    if (tasksElement.ValueKind == JsonValueKind.Object)
                    {
                        var singleTask = JsonSerializer.Deserialize<ScriptEntry>(
                            tasksElement.GetRawText(),
                            Options);
                        return singleTask != null ? new List<ScriptEntry> { singleTask } : new List<ScriptEntry>();
                    }
                }

                var single = JsonSerializer.Deserialize<ScriptEntry>(json, Options);
                return single != null ? new List<ScriptEntry> { single } : new List<ScriptEntry>();
            }
        }
        catch
        {
        }

        return new List<ScriptEntry>();
    }
}
