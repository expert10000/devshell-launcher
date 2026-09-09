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
    }

    private Task HandleBrowserToggleAsync()
    {
        if (_browserHost.Panel2Collapsed)
            return ShowBrowserAsync(null, _activeWorkspaceProfileId);
        HideBrowserPane();
        return Task.CompletedTask;
    }

    private void HideBrowserPane()
    {
        if (_browserHost.Panel2Collapsed) return;
        var length = _browserHost.Orientation == Orientation.Vertical ? _browserHost.Width : _browserHost.Height;
        if (length > 0) _browserSplitRatio = (double)_browserHost.SplitterDistance / length;
        _browserHost.Panel2Collapsed = true;
        webView.Focus();
    }

    private Task HandleBrowserOpenAsync(JsonElement message)
    {
        var url = message.TryGetProperty("url", out var value) ? value.GetString() : null;
        if (url != null && !BrowserPane.IsWebUrl(url))
            throw new ArgumentException("Browser tasks require an HTTP or HTTPS URL.");
        return ShowBrowserAsync(url, _activeWorkspaceProfileId);
    }

    private async Task ShowBrowserAsync(string? url, string profileId)
    {
        await _browserGate.WaitAsync();
        BrowserPane? pane = null;
        try
        {
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            if (_browserHost.Panel2Collapsed)
            {
                _browserHost.Orientation = ClientSize.Width < 1100 ? Orientation.Horizontal : Orientation.Vertical;
                _browserHost.Panel2Collapsed = false;
                var length = _browserHost.Orientation == Orientation.Vertical ? _browserHost.Width : _browserHost.Height;
                var min = _browserHost.Panel1MinSize;
                var max = Math.Max(min, length - _browserHost.SplitterWidth - _browserHost.Panel2MinSize);
                _browserHost.SplitterDistance = Math.Clamp((int)(length * _browserSplitRatio), min, max);
            }
            if (_browserPane == null)
            {
                pane = new BrowserPane();
                _browserPane = pane;
                pane.CloseRequested += (_, _) => ResetBrowserPane();
                pane.HideRequested += (_, _) => HideBrowserPane();
                _browserHost.Panel2.Controls.Add(pane);
                var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId)));
                var storage = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "DevShellLauncher", "browser", key);
                await pane.InitializeAsync(storage);
            }
            pane = _browserPane;
            if (pane == null || pane.IsDisposed || profileId != _activeWorkspaceProfileId) return;
            if (url != null) pane.Navigate(url);
            if (!_browserHost.Panel2Collapsed) pane.Focus();
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
        var pane = _browserPane;
        _browserPane = null;
        pane?.Dispose();
        _browserHost.Panel2Collapsed = true;
    }
}
