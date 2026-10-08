using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private Task HandleWorkspaceTabsAsync(JsonElement payload)
    {
        var profileId = payload.GetProperty("profileId").GetString();
        var requestId = payload.TryGetProperty("requestId", out var request) ? request.GetString() : null;
        if (profileId != _activeWorkspaceProfileId) return Task.CompletedTask;
        string? action = null;
        try
        {
            action = payload.GetProperty("action").GetString();
            if (action == "load")
                SendMessage(new { type = "workspace.tabs.loaded", profileId, requestId, state = WorkspaceTabsStore.Load(profileId!, _workspace) });
            else if (action == "save")
            {
                var json = payload.GetProperty("state").GetRawText();
                if (json.Length > 128000) throw new ArgumentException("Workspace tab descriptors are too large.");
                var state = JsonSerializer.Deserialize<WorkspaceTabsState>(json, _jsonOptions) ?? new();
                WorkspaceTabsStore.Save(profileId!, state, _workspace);
            }
            else if (action is "layouts-load" or "layouts-save" or "layouts-delete")
            {
                var layouts = WorkspaceLayoutStore.Load(profileId!, _workspace); string? savedId = null;
                if (action == "layouts-save")
                {
                    var json = payload.GetProperty("layout").GetRawText();
                    if (json.Length > 32768) throw new ArgumentException("Layout descriptors are too large.");
                    var layout = JsonSerializer.Deserialize<WorkspaceNamedLayout>(json, _jsonOptions) ?? throw new ArgumentException("Provide a named split layout.");
                    var existing = layouts.FirstOrDefault(item => item.Name.Equals((layout.Name ?? "").Trim(), StringComparison.OrdinalIgnoreCase));
                    layout.Id = existing?.Id ?? Guid.NewGuid().ToString();
                    layout = WorkspaceLayoutStore.Normalize(layout, _workspace) ?? throw new ArgumentException("Use a name up to 48 characters and two distinct, configured workspace views.");
                    if (existing == null && layouts.Count >= WorkspaceLayoutStore.MaxLayouts) throw new InvalidOperationException("Delete a saved layout first (limit: 12 per profile).");
                    layouts.RemoveAll(item => item.Id == layout.Id); layouts.Add(layout); savedId = layout.Id;
                    WorkspaceLayoutStore.Save(profileId!, layouts, _workspace);
                }
                else if (action == "layouts-delete")
                {
                    var id = payload.GetProperty("layoutId").GetString();
                    layouts.RemoveAll(item => item.Id == id); WorkspaceLayoutStore.Save(profileId!, layouts, _workspace);
                }
                SendMessage(new { type = "workspace.layouts.result", profileId, requestId, layouts, savedId });
            }
        }
        catch (Exception error)
        {
            if (action?.StartsWith("layouts-", StringComparison.Ordinal) == true) SendMessage(new { type = "workspace.layouts.result", profileId, requestId, error = error.Message });
            else SendMessage(new { type = "workspace.tabs.error", profileId, requestId, message = error.Message });
        }
        return Task.CompletedTask;
    }
}
