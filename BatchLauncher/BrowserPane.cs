using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Diagnostics;

namespace BatchLauncher;

// Web content never receives the launcher's message bridge or host objects.
internal sealed class BrowserPane : UserControl
{
    private readonly WebView2 _view = new() { Dock = DockStyle.Fill };
    private readonly ToolStrip _navigation = new() { GripStyle = ToolStripGripStyle.Hidden, Dock = DockStyle.Top };
    private readonly ToolStripTextBox _address = new() { AutoSize = false, Width = 240 };
    private readonly ToolStripButton _back = new("Back") { Enabled = false };
    private readonly ToolStripButton _forward = new("Forward") { Enabled = false };
    private readonly ToolStripButton _reload = new("Reload");
    private readonly ToolStripStatusLabel _status = new() { Spring = true, TextAlign = ContentAlignment.MiddleLeft };
    private string? _tokenParameter;
    private string? _tokenOrigin;
    private bool _loading;

    public event EventHandler? CloseRequested;
    public event EventHandler? HideRequested;

    public BrowserPane()
    {
        Dock = DockStyle.Fill;
        var go = new ToolStripButton("Go");
        var external = new ToolStripButton("Open externally");
        var close = new ToolStripButton("Close");
        var hide = new ToolStripButton("Hide") { ToolTipText = "Hide the browser without closing the page" };
        _navigation.Items.AddRange(new ToolStripItem[] { _back, _forward, _reload, _address, go, external, hide, close });
        var statusBar = new StatusStrip();
        statusBar.Items.Add(_status);
        Controls.Add(_view);
        Controls.Add(statusBar);
        Controls.Add(_navigation);
        _address.AccessibleName = "Browser address";
        _address.ToolTipText = "Enter an HTTP or HTTPS URL";
        _back.Click += (_, _) => { if (_view.CanGoBack) _view.GoBack(); };
        _forward.Click += (_, _) => { if (_view.CanGoForward) _view.GoForward(); };
        _reload.Click += (_, _) => { if (_loading) _view.CoreWebView2?.Stop(); else _view.CoreWebView2?.Reload(); };
        go.Click += (_, _) => NavigateFromAddress();
        _address.KeyDown += (_, e) =>
        {
            if (e.KeyCode != Keys.Enter) return;
            e.SuppressKeyPress = true;
            NavigateFromAddress();
        };
        external.Click += (_, _) => OpenExternally();
        close.Click += (_, _) => CloseRequested?.Invoke(this, EventArgs.Empty);
        hide.Click += (_, _) => HideRequested?.Invoke(this, EventArgs.Empty);
        _navigation.SizeChanged += (_, _) =>
        {
            var buttons = _navigation.Items.Cast<ToolStripItem>().Where(item => item != _address)
                .Sum(item => item.Width + item.Margin.Horizontal);
            _address.Width = Math.Max(110, _navigation.ClientSize.Width - buttons - 24);
        };
    }

    public async Task InitializeAsync(string storagePath)
    {
        var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: storagePath);
        if (IsDisposed) return;
        await _view.EnsureCoreWebView2Async(environment);
        if (IsDisposed) return;
        var core = _view.CoreWebView2;
        core.Settings.IsWebMessageEnabled = false;
        core.Settings.AreHostObjectsAllowed = false;
        core.NavigationStarting += (_, e) =>
        {
            if (e.Uri != "about:blank" && !IsWebUrl(e.Uri))
            {
                e.Cancel = true;
                _status.Text = "Only HTTP and HTTPS links can be opened here.";
                return;
            }
            _loading = true;
            _reload.Text = "Stop";
            _status.Text = "Loading...";
        };
        core.NavigationCompleted += (_, e) =>
        {
            _loading = false;
            _reload.Text = "Reload";
            _status.Text = e.IsSuccess ? core.DocumentTitle : "Navigation failed: " + e.WebErrorStatus;
            UpdateNavigation();
        };
        core.SourceChanged += (_, _) => UpdateNavigation();
        core.HistoryChanged += (_, _) => UpdateNavigation();
        core.DocumentTitleChanged += (_, _) => { if (!_loading) _status.Text = core.DocumentTitle; };
        core.NewWindowRequested += (_, e) =>
        {
            e.Handled = true;
            if (IsWebUrl(e.Uri)) Navigate(e.Uri);
        };
        core.NavigateToString("<!doctype html><html><body style='font:18px Georgia;padding:40px;background:#f5efe2;color:#17212b'><h1>Browser</h1><p>Enter a URL above, or open a GitHub or Jupyter task in DevShell.</p></body></html>");
    }

    internal static bool IsWebUrl(string value) =>
        Uri.TryCreate(value, UriKind.Absolute, out var uri) &&
        (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps);

    public void Navigate(string url)
    {
        if (!IsWebUrl(url)) throw new ArgumentException("Enter a valid HTTP or HTTPS URL.");
        var uri = new Uri(url);
        var token = uri.Query.TrimStart('?').Split('&').FirstOrDefault(part =>
            part.StartsWith("token=", StringComparison.OrdinalIgnoreCase));
        if (token != null)
        {
            _tokenParameter = token;
            _tokenOrigin = uri.GetLeftPart(UriPartial.Authority);
        }
        _view.CoreWebView2.Navigate(url);
    }

    private void NavigateFromAddress()
    {
        var url = _address.Text.Trim();
        if (!url.Contains("://")) url = "https://" + url;
        try { Navigate(url); }
        catch (Exception ex) { _status.Text = ex.Message; }
    }

    private void UpdateNavigation()
    {
        _back.Enabled = _view.CanGoBack;
        _forward.Enabled = _view.CanGoForward;
        var source = _view.Source;
        if (source == null || !IsWebUrl(source.AbsoluteUri)) return;
        // Do not display an authentication token in the address field.
        var clean = new UriBuilder(source)
        {
            Query = string.Join("&", source.Query.TrimStart('?').Split('&')
                .Where(part => !part.StartsWith("token=", StringComparison.OrdinalIgnoreCase)))
        };
        _address.Text = clean.Uri.AbsoluteUri;
    }

    private void OpenExternally()
    {
        var source = _view.Source;
        if (source == null || !IsWebUrl(source.AbsoluteUri)) return;
        var target = new UriBuilder(source);
        if (_tokenParameter != null && source.GetLeftPart(UriPartial.Authority) == _tokenOrigin &&
            !source.Query.TrimStart('?').Split('&').Any(part => part.StartsWith("token=", StringComparison.OrdinalIgnoreCase)))
            target.Query = string.IsNullOrEmpty(source.Query) ? _tokenParameter : source.Query.TrimStart('?') + "&" + _tokenParameter;
        try { Process.Start(new ProcessStartInfo(target.Uri.AbsoluteUri) { UseShellExecute = true }); }
        catch (Exception ex) { _status.Text = ex.Message; }
    }
}
