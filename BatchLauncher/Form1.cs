using Microsoft.Web.WebView2.Core;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace BatchLauncher;

public partial class Form1 : Form
{
    private const string VirtualHost = "app.local";
    private readonly Dictionary<string, TerminalSession> _sessions = new();
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public Form1()
    {
        InitializeComponent();
        Shown += async (_, _) => await InitializeWebViewAsync();
        FormClosing += (_, _) => StopAllSessions();
    }

    private async Task InitializeWebViewAsync()
    {
        await webView.EnsureCoreWebView2Async();

        var uiPath = ResolveUiPath();
        if (string.IsNullOrWhiteSpace(uiPath))
        {
            webView.CoreWebView2.NavigateToString("<html><body>Missing UI build output.</body></html>");
            return;
        }

        webView.CoreWebView2.SetVirtualHostNameToFolderMapping(
            VirtualHost,
            uiPath,
            CoreWebView2HostResourceAccessKind.Allow);

        webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
        webView.CoreWebView2.Navigate($"https://{VirtualHost}/index.html");
    }

    private string? ResolveUiPath()
    {
        var baseUi = Path.Combine(AppContext.BaseDirectory, "ui");
        if (Directory.Exists(baseUi))
        {
            return baseUi;
        }

        var devUi = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "DevShell",
            "ui",
            "dev-ui-react",
            "dist"));

        return Directory.Exists(devUi) ? devUi : null;
    }

    private async void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        try
        {
            var message = e.WebMessageAsJson;
            if (!string.IsNullOrWhiteSpace(message))
            {
                await HandleWebMessageAsync(message);
            }
        }
        catch (Exception ex)
        {
            SendMessage("terminal.error", sessionId: null, message: ex.Message);
        }
    }

    private Task HandleWebMessageAsync(string payload)
    {
        using var doc = JsonDocument.Parse(payload);
        if (!doc.RootElement.TryGetProperty("type", out var typeElement))
        {
            return Task.CompletedTask;
        }

        var type = typeElement.GetString();
        if (string.IsNullOrWhiteSpace(type))
        {
            return Task.CompletedTask;
        }

        return type switch
        {
            "terminal.start" => HandleTerminalStartAsync(doc.RootElement),
            "terminal.stdin" => HandleTerminalStdinAsync(doc.RootElement),
            "terminal.kill" => HandleTerminalKillAsync(doc.RootElement),
            "terminal.resize" => HandleTerminalResizeAsync(doc.RootElement),
            _ => Task.CompletedTask
        };
    }

    private Task HandleTerminalStartAsync(JsonElement root)
    {
        var shell = root.TryGetProperty("shell", out var shellElement)
            ? shellElement.GetString()
            : "powershell";

        var sessionId = Guid.NewGuid().ToString("N");
        try
        {
            var session = TerminalSession.Start(sessionId, shell ?? "powershell");
            session.Output += HandleSessionOutput;
            session.Exited += HandleSessionExit;
            session.Error += HandleSessionError;
            _sessions[sessionId] = session;

            SendMessage("terminal.ready", sessionId);
        }
        catch (Exception ex)
        {
            SendMessage("terminal.error", sessionId, message: ex.Message);
        }

        return Task.CompletedTask;
    }

    private Task HandleTerminalStdinAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out var sessionId))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("data", out var dataElement))
        {
            return Task.CompletedTask;
        }

        var data = dataElement.GetString();
        if (string.IsNullOrEmpty(data))
        {
            return Task.CompletedTask;
        }

        return session.WriteAsync(data);
    }

    private Task HandleTerminalKillAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out _))
        {
            return Task.CompletedTask;
        }

        session.Kill();
        return Task.CompletedTask;
    }

    private Task HandleTerminalResizeAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out _))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("cols", out var colsElement) ||
            !root.TryGetProperty("rows", out var rowsElement))
        {
            return Task.CompletedTask;
        }

        var cols = colsElement.GetInt32();
        var rows = rowsElement.GetInt32();
        if (cols <= 0 || rows <= 0)
        {
            return Task.CompletedTask;
        }

        session.Resize(cols, rows);
        return Task.CompletedTask;
    }

    private bool TryGetSession(JsonElement root, out TerminalSession session, out string sessionId)
    {
        session = null!;
        sessionId = string.Empty;

        if (!root.TryGetProperty("sessionId", out var sessionElement))
        {
            return false;
        }

        sessionId = sessionElement.GetString() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            return false;
        }

        return _sessions.TryGetValue(sessionId, out session);
    }

    private void HandleSessionOutput(TerminalSession session, string data)
    {
        SendMessage("terminal.stdout", session.SessionId, data);
    }

    private void HandleSessionExit(TerminalSession session, int exitCode)
    {
        _sessions.Remove(session.SessionId);
        SendMessage("terminal.exit", session.SessionId, exitCode: exitCode);
    }

    private void HandleSessionError(TerminalSession session, string message)
    {
        SendMessage("terminal.error", session.SessionId, message: message);
    }

    private void SendMessage(string type, string? sessionId, string? data = null, int? exitCode = null, string? message = null)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => SendMessage(type, sessionId, data, exitCode, message));
            return;
        }

        if (webView.CoreWebView2 == null)
        {
            return;
        }

        var payload = new
        {
            type,
            sessionId,
            data,
            exitCode,
            message
        };

        var json = JsonSerializer.Serialize(payload, _jsonOptions);
        webView.CoreWebView2.PostWebMessageAsString(json);
    }

    private void StopAllSessions()
    {
        foreach (var session in _sessions.Values)
        {
            session.Kill();
        }

        _sessions.Clear();
    }
}
