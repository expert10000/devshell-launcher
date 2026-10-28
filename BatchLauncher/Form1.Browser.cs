using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private SplitContainer _browserHost = null!;
    private BrowserPane? _browserPane;
    private double _browserSplitRatio = 0.55;
    private readonly SemaphoreSlim _browserGate = new(1, 1);
    private sealed record CenterBrowserSlot(string Key, Rectangle Bounds);
    private CenterBrowserSlot? _centerBrowserSlot;
    private readonly Dictionary<string, string> _browserTabBindings = new(StringComparer.Ordinal);
    private bool _browserEmbedded, _centerBrowserHidden;

    private void InitializeBrowserHost()
    {
        _browserHost = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Size = ClientSize,
            Panel2Collapsed = true,
            SplitterWidth = 7
        };
        Controls.Remove(webView);
        _browserHost.Panel1.Controls.Add(webView);
        Controls.Add(_browserHost);
        Shown += async (_, _) => await RestoreBrowserWorkspaceAsync();
    }

    private Task HandleBrowserToggleAsync()
    {
        if (_centerBrowserSlot is { } slot && _browserPane != null && _browserTabBindings.ContainsKey(slot.Key))
        {
            _centerBrowserHidden = !_centerBrowserHidden;
            if (_centerBrowserHidden) HideBrowserPane(); else PlaceBrowserInCenter();
            return Task.CompletedTask;
        }
        if (_browserHost.Panel2Collapsed)
        {
            if (_pdfPaneActive && _pdfPane != null) { ExpandBrowserHost(); return Task.CompletedTask; }
            return ShowBrowserAsync(null, _activeWorkspaceProfileId);
        }
        HideBrowserPane();
        return Task.CompletedTask;
    }

    private void HideBrowserPane()
    {
        if (_browserEmbedded)
        {
            _centerBrowserHidden = true;
            _browserPane?.SetWorkspaceVisible(false);
            if (_browserPane != null) _browserPane.Visible = false;
            _browserEmbedded = false;
            webView.Focus();
            return;
        }
        if (_browserHost.Panel2Collapsed) return;
        _browserPane?.SetWorkspaceVisible(false);
        var length = _browserHost.Orientation == Orientation.Vertical ? _browserHost.Width : _browserHost.Height;
        if (length > 0) _browserSplitRatio = (double)_browserHost.SplitterDistance / length;
        _browserHost.Panel2Collapsed = true;
        webView.Focus();
    }

    private Task HandleBrowserOpenAsync(JsonElement message)
    {
        var url = message.TryGetProperty("url", out var value) ? value.GetString() : null;
        var projectId = message.TryGetProperty("projectId", out var project) ? project.GetString() : null;
        var repositoryId = message.TryGetProperty("repositoryId", out var repository) ? repository.GetString() : null;
        if (url != null && !BrowserPane.IsWebUrl(url))
            throw new ArgumentException("Browser tasks require an HTTP or HTTPS URL.");
        return ShowBrowserAsync(url, _activeWorkspaceProfileId, "browser", projectId, repositoryId);
    }

    private void ExpandBrowserHost()
    {
        if (!_browserHost.Panel2Collapsed) return;
        _browserHost.Orientation = ClientSize.Width < 1100 ? Orientation.Horizontal : Orientation.Vertical;
        _browserHost.Panel2Collapsed = false;
        var length = _browserHost.Orientation == Orientation.Vertical ? _browserHost.Width : _browserHost.Height;
        var min = _browserHost.Panel1MinSize;
        var max = Math.Max(min, length - _browserHost.SplitterWidth - _browserHost.Panel2MinSize);
        _browserHost.SplitterDistance = Math.Clamp((int)(length * _browserSplitRatio), min, max);
    }

    private static string? WorkspaceBrowserKey(string? kind, string? projectId, string? servicePath, string? url)
    {
        if (kind == "jupyter") return projectId == null ? null : $"jupyter:{projectId}:{servicePath ?? ""}";
        var clean = WorkspaceTabsStore.CleanWebUrl(url);
        return kind == "browser" && clean != null ? "browser:" + clean : null;
    }

    private Task HandleWorkspaceBrowserSlotAsync(JsonElement message)
    {
        if (message.TryGetProperty("profileId", out var profile) && profile.GetString() != _activeWorkspaceProfileId)
            return Task.CompletedTask;
        if (message.TryGetProperty("action", out var statusAction) && statusAction.GetString() == "status")
        {
            var requestId = message.TryGetProperty("requestId", out var request) ? request.GetString() : null;
            SendMessage(new { type = "workspace.browser.slot.state", profileId = _activeWorkspaceProfileId, requestId,
                mode = _browserEmbedded ? "center" : _browserHost.Panel2Collapsed ? "hidden" : "side",
                bounds = _browserEmbedded ? _browserPane?.Bounds : null });
            return Task.CompletedTask;
        }
        if (!message.TryGetProperty("action", out var action) || action.GetString() != "show")
        {
            _centerBrowserSlot = null;
            ReleaseCenterBrowser();
            return Task.CompletedTask;
        }
        var kind = message.TryGetProperty("kind", out var kindValue) ? kindValue.GetString() : null;
        var projectId = message.TryGetProperty("projectId", out var project) ? project.GetString() : null;
        var servicePath = message.TryGetProperty("servicePath", out var service) ? service.GetString() : null;
        var url = message.TryGetProperty("url", out var address) ? address.GetString() : null;
        var key = WorkspaceBrowserKey(kind, projectId, servicePath, url);
        if (key == null || !TryNumber(message, "x", out var x) || !TryNumber(message, "y", out var y) ||
            !TryNumber(message, "width", out var width) || !TryNumber(message, "height", out var height) ||
            !TryNumber(message, "viewportWidth", out var viewportWidth) || !TryNumber(message, "viewportHeight", out var viewportHeight) ||
            viewportWidth <= 0 || viewportHeight <= 0 || width <= 0 || height <= 0)
        {
            _centerBrowserSlot = null;
            ReleaseCenterBrowser();
            return Task.CompletedTask;
        }
        var scaleX = (double)webView.ClientSize.Width / viewportWidth;
        var scaleY = (double)webView.ClientSize.Height / viewportHeight;
        var bounds = Rectangle.Intersect(new Rectangle((int)Math.Round(x * scaleX), (int)Math.Round(y * scaleY),
            (int)Math.Round(width * scaleX), (int)Math.Round(height * scaleY)), webView.ClientRectangle);
        _centerBrowserSlot = bounds.Width >= 120 && bounds.Height >= 100 ? new(key, bounds) : null;
        if (!PlaceBrowserInCenter()) ReleaseCenterBrowser();
        return Task.CompletedTask;
    }

    private static bool TryNumber(JsonElement message, string name, out double value)
    {
        value = 0;
        return message.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.Number &&
            property.TryGetDouble(out value) && double.IsFinite(value) && Math.Abs(value) < 1000000;
    }

    private bool PlaceBrowserInCenter()
    {
        if (_centerBrowserHidden || _centerBrowserSlot is not { } slot || _browserPane is not { } pane ||
            !_browserTabBindings.TryGetValue(slot.Key, out var nativeId) || !pane.TrySelectInitializedTab(nativeId)) return false;
        if (pane.Parent != _browserHost.Panel1)
        {
            pane.Parent?.Controls.Remove(pane);
            _browserHost.Panel1.Controls.Add(pane);
        }
        pane.Dock = DockStyle.None;
        pane.Bounds = slot.Bounds;
        _browserHost.Panel2Collapsed = true;
        pane.SetWorkspaceVisible(false); // Center restoration remains a passive workspace descriptor.
        pane.Visible = true;
        pane.BringToFront();
        _browserEmbedded = true;
        return true;
    }

    private void ReleaseCenterBrowser()
    {
        if (!_browserEmbedded || _browserPane == null) return;
        _browserPane.Visible = false;
        _browserPane.SetWorkspaceVisible(false);
        _browserEmbedded = false;
    }

    private void PlaceBrowserInSide(BrowserPane pane)
    {
        if (pane.Parent != _browserHost.Panel2)
        {
            pane.Visible = false;
            pane.Parent?.Controls.Remove(pane);
            _browserHost.Panel2.Controls.Add(pane);
        }
        pane.Dock = DockStyle.Fill;
        ExpandBrowserHost();
        pane.Visible = true;
        pane.BringToFront();
        pane.SetWorkspaceVisible(true);
        _browserEmbedded = false;
    }

    private async Task ShowBrowserAsync(string? url, string profileId, string? workspaceKind = null,
        string? projectId = null, string? repositoryId = null, string? servicePath = null)
    {
        await _browserGate.WaitAsync();
        BrowserPane? pane = null;
        try
        {
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            if (_browserPane == null)
            {
                ExpandBrowserHost();
                pane = new BrowserPane();
                _browserPane = pane;
                pane.CloseRequested += (_, _) => { pane.SetWorkspaceVisible(false); ResetBrowserPane(); };
                pane.HideRequested += (_, _) => HideBrowserPane();
                _browserHost.Panel2.Controls.Add(pane);
                await pane.InitializeAsync(BrowserStoragePath(profileId));
            }
            pane = _browserPane;
            if (pane == null || pane.IsDisposed || profileId != _activeWorkspaceProfileId) return;
            _pdfPaneActive = false;
            if (_pdfPane != null) _pdfPane.Visible = false;
            if (url != null)
            {
                await pane.OpenTabAsync(url);
                var key = WorkspaceBrowserKey(workspaceKind, projectId, servicePath, url);
                if (key != null && pane.ActiveTabId != null) _browserTabBindings[key] = pane.ActiveTabId;
                if (profileId == _activeWorkspaceProfileId && !IsDisposed && !pane.IsDisposed)
                    SendMessage(new { type = "workspace.browser.opened", profileId, kind = workspaceKind ?? "browser", projectId, repositoryId,
                        servicePath, url = workspaceKind == "jupyter" ? null : WorkspaceTabsStore.CleanWebUrl(url) });
            }
            if (url != null) _centerBrowserHidden = false;
            if (!PlaceBrowserInCenter()) PlaceBrowserInSide(pane);
            if (pane.Visible) pane.Focus();
        }
        catch (Exception) when (IsDisposed || profileId != _activeWorkspaceProfileId || pane?.IsDisposed == true)
        {
            // A closed pane or switched profile must not reopen after initialization.
        }
        catch
        {
            ResetBrowserPane();
            throw;
        }
        finally { _browserGate.Release(); }
    }

    private void ResetBrowserPane()
    {
        _centerBrowserSlot = null;
        _browserTabBindings.Clear();
        _browserEmbedded = false;
        _centerBrowserHidden = false;
        var pane = _browserPane;
        _browserPane = null;
        pane?.Dispose();
        _pdfPane?.Dispose(); _pdfPane = null; _pdfPaneActive = false;
        _browserHost.Panel2Collapsed = true;
    }

    private static string BrowserStoragePath(string profileId)
    {
        var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId)));
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "browser", key);
    }

    private async Task RestoreBrowserWorkspaceAsync()
    {
        var profileId = _activeWorkspaceProfileId;
        if (!BrowserWorkspaceStore.Load(Path.Combine(BrowserStoragePath(profileId), "tabs.json")).Visible) return;
        try { await ShowBrowserAsync(null, profileId); }
        catch (Exception error) { System.Diagnostics.Trace.WriteLine("Could not restore browser workspace: " + error.Message); }
    }
}
