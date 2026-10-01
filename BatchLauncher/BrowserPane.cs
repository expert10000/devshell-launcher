using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Diagnostics;

namespace BatchLauncher;

// Every web tab is isolated from the launcher's message bridge and host objects.
internal sealed class BrowserPane : UserControl
{
    private sealed class BrowserTab
    {
        public string Id = Guid.NewGuid().ToString("N");
        public readonly TabPage Page = new("New tab");
        public readonly WebView2 View = new() { Dock = DockStyle.Fill, Visible = false };
        public readonly Label Welcome = new()
        {
            Dock = DockStyle.Fill,
            Text = "Browser\r\n\r\nEnter a URL above, or open a GitHub or Jupyter task in DevShell.",
            TextAlign = ContentAlignment.MiddleCenter,
            BackColor = Color.FromArgb(245, 239, 226),
            ForeColor = Color.FromArgb(23, 33, 43)
        };
        public string? Url, TokenParameter, TokenOrigin;
        public string Title = "New tab";
        public bool Loading;
        public Task? Initialization;
    }

    private readonly TabControl _tabs = new() { Dock = DockStyle.Fill, ShowToolTips = true };
    private readonly List<BrowserTab> _pages = new();
    private readonly ToolStrip _navigation = new() { GripStyle = ToolStripGripStyle.Hidden, Dock = DockStyle.Top };
    private readonly ToolStripTextBox _address = new() { AutoSize = false, Width = 240 };
    private readonly ToolStripButton _back = new("Back") { Enabled = false };
    private readonly ToolStripButton _forward = new("Forward") { Enabled = false };
    private readonly ToolStripButton _reload = new("Reload");
    private readonly ToolStripStatusLabel _status = new() { Spring = true, TextAlign = ContentAlignment.MiddleLeft };
    private readonly System.Windows.Forms.Timer _saveTimer = new() { Interval = 500 };
    private CoreWebView2Environment? _environment;
    private string? _statePath;
    private bool _restoring, _workspaceVisible, _disposing;
    private BrowserTab? ActiveTab => _pages.FirstOrDefault(tab => tab.Page == _tabs.SelectedTab);

    public event EventHandler? CloseRequested;
    public event EventHandler? HideRequested;

    public BrowserPane()
    {
        Dock = DockStyle.Fill;
        var go = new ToolStripButton("Go");
        var newTab = new ToolStripButton("New tab");
        var closeTab = new ToolStripButton("Close tab");
        var external = new ToolStripButton("Open externally");
        var hide = new ToolStripButton("Hide") { ToolTipText = "Hide the browser without closing its tabs" };
        var close = new ToolStripButton("Close pane");
        _navigation.Items.AddRange(new ToolStripItem[] { _back, _forward, _reload, _address, go, newTab, closeTab, external, hide, close });
        var statusBar = new StatusStrip();
        statusBar.Items.Add(_status);
        Controls.Add(_tabs);
        Controls.Add(statusBar);
        Controls.Add(_navigation);
        _tabs.AccessibleName = "Browser tabs";
        _address.AccessibleName = "Browser address";
        _address.ToolTipText = "Enter an HTTP or HTTPS URL";
        _back.Click += (_, _) => { if (ActiveTab?.View.CanGoBack == true) ActiveTab.View.GoBack(); };
        _forward.Click += (_, _) => { if (ActiveTab?.View.CanGoForward == true) ActiveTab.View.GoForward(); };
        _reload.Click += (_, _) =>
        {
            var tab = ActiveTab;
            if (tab == null) return;
            if (tab.Loading) tab.View.CoreWebView2?.Stop(); else tab.View.CoreWebView2?.Reload();
        };
        go.Click += async (_, _) => await NavigateFromAddressAsync();
        _address.KeyDown += async (_, e) =>
        {
            if (e.KeyCode != Keys.Enter) return;
            e.SuppressKeyPress = true;
            await NavigateFromAddressAsync();
        };
        newTab.Click += async (_, _) =>
        {
            try { var tab = AddTab(null); _tabs.SelectedTab = tab.Page; await EnsureTabAsync(tab); _address.Focus(); }
            catch (Exception error) { if (!IsDisposed) _status.Text = error.Message; }
        };
        closeTab.Click += (_, _) => CloseActiveTab();
        external.Click += (_, _) => OpenExternally();
        hide.Click += (_, _) => HideRequested?.Invoke(this, EventArgs.Empty);
        close.Click += (_, _) => CloseRequested?.Invoke(this, EventArgs.Empty);
        _tabs.SelectedIndexChanged += async (_, _) =>
        {
            if (_restoring || _disposing || ActiveTab is not { } tab) return;
            UpdateNavigation(tab);
            ScheduleSave();
            try { await EnsureTabAsync(tab); }
            catch (Exception error) { if (!IsDisposed) _status.Text = error.Message; }
        };
        _saveTimer.Tick += (_, _) => { _saveTimer.Stop(); SaveWorkspace(); };
        _navigation.SizeChanged += (_, _) =>
        {
            var buttons = _navigation.Items.Cast<ToolStripItem>().Where(item => item != _address).Sum(item => item.Width + item.Margin.Horizontal);
            _address.Width = Math.Max(110, _navigation.ClientSize.Width - buttons - 24);
        };
    }

    public async Task InitializeAsync(string storagePath)
    {
        _environment = await CoreWebView2Environment.CreateAsync(userDataFolder: storagePath);
        if (IsDisposed) return;
        _statePath = Path.Combine(storagePath, "tabs.json");
        var state = BrowserWorkspaceStore.Load(_statePath);
        _workspaceVisible = state.Visible;
        _restoring = true;
        try
        {
            foreach (var saved in state.Tabs.Take(BrowserWorkspaceStore.MaxTabs))
            {
                if (saved.Url != null && !IsWebUrl(saved.Url)) continue;
                AddTab(saved.Url, saved.Id, saved.Title);
            }
            if (_pages.Count == 0) AddTab(null);
            _tabs.SelectedTab = (_pages.FirstOrDefault(tab => tab.Id == state.ActiveTabId) ?? _pages[0]).Page;
        }
        finally { _restoring = false; }
        if (ActiveTab is { } active) { UpdateNavigation(active); await EnsureTabAsync(active); }
    }

    internal static bool IsWebUrl(string value) => Uri.TryCreate(value, UriKind.Absolute, out var uri) &&
        uri.Scheme is "http" or "https" && string.IsNullOrEmpty(uri.UserInfo);

    public void SetWorkspaceVisible(bool visible) { _workspaceVisible = visible; ScheduleSave(); }

    // Tasks reuse an identical URL, otherwise open a new tab; address-bar navigation stays in its tab.
    public async Task OpenTabAsync(string url)
    {
        if (!IsWebUrl(url)) throw new ArgumentException("Enter a valid HTTP or HTTPS URL without embedded credentials.");
        var clean = BrowserWorkspaceStore.CleanUrl(url);
        var tab = _pages.FirstOrDefault(page => page.Url != null && BrowserWorkspaceStore.CleanUrl(page.Url) == clean)
            ?? (ActiveTab?.Url == null ? ActiveTab : null) ?? AddTab(url);
        var initialized = tab.View.CoreWebView2 != null;
        var previous = tab.Url;
        tab.Url = url;
        _tabs.SelectedTab = tab.Page;
        await EnsureTabAsync(tab);
        if (IsDisposed || tab.Page.IsDisposed) return;
        if (initialized && (previous != url || tab.View.Source == null)) NavigateTab(tab, url);
        UpdateNavigation(tab);
        ScheduleSave();
    }

    public void Navigate(string url) => _ = OpenSafelyAsync(url);

    private async Task OpenSafelyAsync(string url)
    {
        try { await OpenTabAsync(url); }
        catch (Exception error) { if (!IsDisposed) _status.Text = error.Message; }
    }

    private BrowserTab AddTab(string? url, string? id = null, string? title = null)
    {
        if (_pages.Count >= BrowserWorkspaceStore.MaxTabs) throw new InvalidOperationException("Close a browser tab before opening another (limit: 24).");
        var tab = new BrowserTab { Url = url, Id = string.IsNullOrWhiteSpace(id) ? Guid.NewGuid().ToString("N") : id, Title = title ?? "New tab" };
        if (tab.Title == "New tab" && url != null) tab.Title = new Uri(url).Host;
        tab.Page.Text = ShortTitle(tab.Title);
        tab.Page.ToolTipText = url == null ? "New tab" : BrowserWorkspaceStore.CleanUrl(url);
        tab.Page.Controls.Add(tab.View);
        tab.Page.Controls.Add(tab.Welcome);
        _pages.Add(tab);
        _tabs.TabPages.Add(tab.Page);
        ScheduleSave();
        return tab;
    }

    private Task EnsureTabAsync(BrowserTab tab) => tab.Initialization ??= InitializeTabAsync(tab);

    private async Task InitializeTabAsync(BrowserTab tab)
    {
        if (_environment == null || IsDisposed || tab.Page.IsDisposed) return;
        await tab.View.EnsureCoreWebView2Async(_environment);
        if (IsDisposed || tab.Page.IsDisposed) return;
        var core = tab.View.CoreWebView2;
        core.Settings.IsWebMessageEnabled = false;
        core.Settings.AreHostObjectsAllowed = false;
        core.NavigationStarting += (_, e) =>
        {
            if (e.Uri != "about:blank" && !IsWebUrl(e.Uri))
            {
                e.Cancel = true;
                if (tab == ActiveTab) _status.Text = "Only HTTP and HTTPS links can be opened here.";
                return;
            }
            CaptureToken(tab, e.Uri);
            tab.Loading = true;
            if (tab == ActiveTab) UpdateNavigation(tab);
        };
        core.NavigationCompleted += (_, e) =>
        {
            tab.Loading = false;
            if (tab == ActiveTab)
            {
                UpdateNavigation(tab);
                if (!e.IsSuccess) _status.Text = "Navigation failed: " + e.WebErrorStatus;
            }
        };
        core.SourceChanged += (_, _) =>
        {
            if (IsWebUrl(core.Source)) { tab.Url = core.Source; CaptureToken(tab, core.Source); }
            UpdateNavigation(tab);
            ScheduleSave();
        };
        core.HistoryChanged += (_, _) => UpdateNavigation(tab);
        core.DocumentTitleChanged += (_, _) =>
        {
            tab.Title = string.IsNullOrWhiteSpace(core.DocumentTitle) ? (tab.Url == null ? "New tab" : new Uri(tab.Url).Host) : core.DocumentTitle;
            tab.Page.Text = ShortTitle(tab.Title);
            UpdateNavigation(tab);
            ScheduleSave();
        };
        core.NewWindowRequested += (_, e) => { e.Handled = true; if (IsWebUrl(e.Uri)) _ = OpenSafelyAsync(e.Uri); };
        if (tab.Url != null) NavigateTab(tab, tab.Url);
    }

    private static string ShortTitle(string title) => title.Length > 28 ? title[..25] + "..." : title;

    private static void CaptureToken(BrowserTab tab, string url)
    {
        if (!IsWebUrl(url)) return;
        var uri = new Uri(url);
        var token = uri.Query.TrimStart('?').Split('&').FirstOrDefault(part => part.StartsWith("token=", StringComparison.OrdinalIgnoreCase));
        if (token != null) { tab.TokenParameter = token; tab.TokenOrigin = uri.GetLeftPart(UriPartial.Authority); }
    }

    private void NavigateTab(BrowserTab tab, string url)
    {
        tab.Url = url;
        CaptureToken(tab, url);
        tab.Welcome.Visible = false;
        tab.View.Visible = true;
        tab.View.CoreWebView2.Navigate(url);
    }

    private async Task NavigateFromAddressAsync()
    {
        var url = _address.Text.Trim();
        if (!url.Contains("://")) url = "https://" + url;
        try
        {
            if (!IsWebUrl(url)) throw new ArgumentException("Enter a valid HTTP or HTTPS URL.");
            var tab = ActiveTab ?? AddTab(null);
            await EnsureTabAsync(tab);
            if (!IsDisposed && !tab.Page.IsDisposed) NavigateTab(tab, url);
            ScheduleSave();
        }
        catch (Exception error) { if (!IsDisposed) _status.Text = error.Message; }
    }

    private void UpdateNavigation(BrowserTab tab)
    {
        if (IsDisposed || tab.Page.IsDisposed) return;
        tab.Page.ToolTipText = tab.Url == null ? "New tab" : BrowserWorkspaceStore.CleanUrl(tab.Url);
        if (tab != ActiveTab) return;
        _back.Enabled = tab.View.CanGoBack;
        _forward.Enabled = tab.View.CanGoForward;
        _reload.Text = tab.Loading ? "Stop" : "Reload";
        _address.Text = tab.Url == null ? "" : BrowserWorkspaceStore.CleanUrl(tab.Url);
        _status.Text = tab.Loading ? "Loading..." : tab.Url == null ? "Ready. Enter a URL or open a browser task." : tab.Title;
    }

    private void CloseActiveTab()
    {
        if (ActiveTab is not { } tab) return;
        _pages.Remove(tab);
        _tabs.TabPages.Remove(tab.Page);
        tab.Page.Dispose();
        if (_pages.Count == 0) AddTab(null);
        if (ActiveTab is { } active) UpdateNavigation(active);
        ScheduleSave();
    }

    private void OpenExternally()
    {
        var tab = ActiveTab;
        if (tab?.Url == null || !IsWebUrl(tab.Url)) return;
        var source = new Uri(tab.Url);
        var target = new UriBuilder(source);
        if (tab.TokenParameter != null && source.GetLeftPart(UriPartial.Authority) == tab.TokenOrigin &&
            !source.Query.TrimStart('?').Split('&').Any(part => part.StartsWith("token=", StringComparison.OrdinalIgnoreCase)))
            target.Query = string.IsNullOrEmpty(source.Query) ? tab.TokenParameter : source.Query.TrimStart('?') + "&" + tab.TokenParameter;
        try { Process.Start(new ProcessStartInfo(target.Uri.AbsoluteUri) { UseShellExecute = true }); }
        catch (Exception error) { _status.Text = error.Message; }
    }

    private void ScheduleSave()
    {
        if (_restoring || _disposing || _statePath == null) return;
        _saveTimer.Stop();
        _saveTimer.Start();
    }

    private void SaveWorkspace()
    {
        if (_statePath == null) return;
        try
        {
            BrowserWorkspaceStore.Save(_statePath, new BrowserWorkspaceState
            {
                Visible = _workspaceVisible,
                ActiveTabId = ActiveTab?.Id,
                Tabs = _pages.Select(tab => new PersistedBrowserTab { Id = tab.Id, Title = tab.Title,
                    Url = tab.Url == null ? null : BrowserWorkspaceStore.CleanUrl(tab.Url) }).ToList()
            });
        }
        catch (Exception error) { Trace.WriteLine("Could not save browser tabs: " + error.Message); }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing && !_disposing)
        {
            _disposing = true;
            _saveTimer.Stop();
            SaveWorkspace();
            _saveTimer.Dispose();
        }
        base.Dispose(disposing);
    }
}
