using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private Task HandleWorkspaceTabsAsync(JsonElement payload)
    {
        var profileId = payload.GetProperty("profileId").GetString();
        var requestId = payload.TryGetProperty("requestId", out var request) ? request.GetString() : null;
        if (profileId != _activeWorkspaceProfileId) return Task.CompletedTask;
        try
        {
            var action = payload.GetProperty("action").GetString();
            if (action == "load")
                SendMessage(new { type = "workspace.tabs.loaded", profileId, requestId, state = WorkspaceTabsStore.Load(profileId!, _workspace) });
            else if (action == "save")
            {
                var json = payload.GetProperty("state").GetRawText();
                if (json.Length > 128000) throw new ArgumentException("Workspace tab descriptors are too large.");
                var state = JsonSerializer.Deserialize<WorkspaceTabsState>(json, _jsonOptions) ?? new();
                WorkspaceTabsStore.Save(profileId!, state, _workspace);
            }
        }
        catch (Exception error) { SendMessage(new { type = "workspace.tabs.error", profileId, requestId, message = error.Message }); }
        return Task.CompletedTask;
    }
}
