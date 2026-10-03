using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace BatchLauncher;

// A document-only WebView: no host objects, launcher bridge, directory mappings, or arbitrary URLs.
internal sealed class PdfPane : UserControl
{
    private readonly WebView2 _view = new() { Dock = DockStyle.Fill };
    private readonly ToolStripLabel _title = new("PDF");
    private readonly ToolStripStatusLabel _status = new() { Spring = true, TextAlign = ContentAlignment.MiddleLeft };
    private readonly List<Stream> _responses = new();
    private CoreWebView2Environment? _environment;
    private Task? _initialization;
    private string? _documentUrl, _root;
    public string? ProjectId { get; private set; }
    public string? RepositoryId { get; private set; }
    public string? FilePath { get; private set; }
    public int Page { get; private set; } = 1;
    public event Action<string>? ActionRequested;
    public event Action<string>? Failed;
    public event EventHandler? HideRequested;
    public event EventHandler? CloseRequested;

    public PdfPane()
    {
        Dock = DockStyle.Fill;
        var toolbar = new ToolStrip { Dock = DockStyle.Top, GripStyle = ToolStripGripStyle.Hidden };
        var refresh = new ToolStripButton("Refresh PDF");
        var external = new ToolStripButton("Open externally");
        var hide = new ToolStripButton("Hide");
        var close = new ToolStripButton("Close PDF");
        toolbar.Items.AddRange(new ToolStripItem[] { _title, refresh, external, hide, close });
        var statusBar = new StatusStrip(); statusBar.Items.Add(_status);
        Controls.Add(_view); Controls.Add(statusBar); Controls.Add(toolbar);
        refresh.Click += (_, _) => ActionRequested?.Invoke("refresh");
        external.Click += (_, _) => ActionRequested?.Invoke("external");
        hide.Click += (_, _) => HideRequested?.Invoke(this, EventArgs.Empty);
        close.Click += (_, _) => CloseRequested?.Invoke(this, EventArgs.Empty);
        AccessibleName = "Workspace PDF viewer";
    }

    private async Task InitializeAsync(string storagePath)
    {
        _environment = await CoreWebView2Environment.CreateAsync(userDataFolder: storagePath);
        if (IsDisposed) return;
        await _view.EnsureCoreWebView2Async(_environment);
        if (IsDisposed) return;
        var core = _view.CoreWebView2;
        core.Settings.IsWebMessageEnabled = false;
        core.Settings.AreHostObjectsAllowed = false;
        core.Settings.AreDefaultContextMenusEnabled = false;
        core.NewWindowRequested += (_, e) => { e.Handled = true; _status.Text = "Document links are blocked. Use Open externally to follow them."; };
        core.DownloadStarting += (_, e) => e.Cancel = true;
        core.PermissionRequested += (_, e) => e.State = CoreWebView2PermissionState.Deny;
        core.NavigationStarting += (_, e) =>
        {
            if (e.Uri != "about:blank" && !IsDocumentUrl(e.Uri))
            { e.Cancel = true; _status.Text = "Only the selected PDF can be opened in this viewer."; }
        };
        core.NavigationCompleted += (_, e) =>
        {
            if (IsDisposed) return;
            _status.Text = e.IsSuccess ? "PDF / use the document toolbar for page navigation, zoom, and search" : "PDF navigation failed: " + e.WebErrorStatus;
            if (!e.IsSuccess) Failed?.Invoke(_status.Text);
        };
        // Serve exactly one validated file. Never map its directory to a web origin.
        core.AddWebResourceRequestedFilter("http*://*", CoreWebView2WebResourceContext.All);
        core.AddWebResourceRequestedFilter("file://*", CoreWebView2WebResourceContext.All);
        core.WebResourceRequested += (_, e) =>
        {
            try
            {
                if (_root == null || FilePath == null || !IsDocumentUrl(e.Request.Uri) || e.Request.Method != "GET")
                { e.Response = _environment.CreateWebResourceResponse(null, 403, "Forbidden", "Cache-Control: no-store"); return; }
                var path = PdfFile.Resolve(_root, FilePath);
                var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
                _responses.Add(stream);
                e.Response = _environment.CreateWebResourceResponse(stream, 200, "OK",
                    $"Content-Type: application/pdf\r\nContent-Length: {stream.Length}\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff");
            }
            catch (Exception error)
            {
                _status.Text = error.Message; Failed?.Invoke(error.Message);
                e.Response = _environment.CreateWebResourceResponse(null, 404, "PDF unavailable", "Cache-Control: no-store");
            }
        };
    }

    private bool IsDocumentUrl(string value) => Uri.TryCreate(value, UriKind.Absolute, out var uri) &&
        uri.GetLeftPart(UriPartial.Path) == _documentUrl && string.IsNullOrEmpty(uri.Query);

    public async Task OpenAsync(string storagePath, string projectId, string repositoryId, string root, string relativePath, int page)
    {
        await (_initialization ??= InitializeAsync(storagePath));
        if (IsDisposed) return;
        PdfFile.Resolve(root, relativePath);
        _view.CoreWebView2.Stop();
        // A fresh endpoint avoids reopening a cached pre-build PDF. No bytes are persisted by this app.
        _root = root; ProjectId = projectId; RepositoryId = repositoryId; FilePath = relativePath; Page = page;
        _documentUrl = "https://devshell-pdf.invalid/" + Guid.NewGuid().ToString("N") + "/document.pdf";
        _title.Text = Path.GetFileName(relativePath); _status.Text = "Loading PDF...";
        _view.CoreWebView2.Navigate(_documentUrl + "#page=" + page);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _view.Dispose();
            foreach (var stream in _responses) stream.Dispose();
            _responses.Clear();
        }
        base.Dispose(disposing);
    }
}
