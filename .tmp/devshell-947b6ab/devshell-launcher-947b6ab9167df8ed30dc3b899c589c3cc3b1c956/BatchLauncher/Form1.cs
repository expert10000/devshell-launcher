using Microsoft.Web.WebView2.Core;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Collections;
using System.Collections.Concurrent;
using System.Text;
using System.Diagnostics;

namespace BatchLauncher;

public partial class Form1 : Form
{
    private const string VirtualHost = "app.local";
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };
    private readonly List<TerminalProfile> _profiles;
    private readonly TerminalManager _terminalManager;
    private readonly ConcurrentDictionary<string, OutputBuffer> _outputBuffers = new();
    private readonly Dictionary<string, FileStream> _fileTransfers = new();
    private readonly Dictionary<string, StreamWriter> _sessionLogs = new();
    private readonly object _logLock = new();
    private readonly WorkspaceConfig _workspace;
    private readonly Dictionary<string, string> _environment;
    private AppState _latestState;
    private readonly string _scriptsPath;

    public Form1()
    {
        InitializeComponent();
        _scriptsPath = AppPaths.ScriptsPath;
        _profiles = ProfileStore.LoadProfiles();
        _terminalManager = new TerminalManager(_profiles);
        _terminalManager.Output += HandleSessionOutput;
        _terminalManager.Exited += HandleSessionExit;
        _terminalManager.Error += HandleSessionError;
        _workspace = WorkspaceStore.LoadWorkspace();
        _environment = BuildEnvironmentSnapshot();
        _latestState = AppStateStore.Load();
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

        var baseDir = AppContext.BaseDirectory;
        var isBinOutput = baseDir.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}");
        if (isBinOutput && Directory.Exists(devUi))
        {
            return devUi;
        }

        var configUi = Path.Combine(AppPaths.ConfigDirectory, "ui");
        if (Directory.Exists(configUi))
        {
            return configUi;
        }

        var baseUi = Path.Combine(baseDir, "ui");
        if (Directory.Exists(baseUi))
        {
            return baseUi;
        }

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
            SendMessage(new
            {
                type = "error",
                sessionId = (string?)null,
                message = ex.Message
            });
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
            "app.ready" => HandleAppReadyAsync(),
            "app.state" => HandleAppStateAsync(doc.RootElement),
            "profiles.request" => HandleProfilesRequestAsync(),
            "profiles.save" => HandleProfilesSaveAsync(doc.RootElement),
            "projects.request" => HandleProjectsRequestAsync(),
            "tasks.request" => HandleTasksRequestAsync(),
            "task.run" => HandleTaskRunAsync(doc.RootElement),
            "session.attach" => HandleSessionAttachAsync(doc.RootElement),
            "logging.start" => HandleLoggingStartAsync(doc.RootElement),
            "logging.stop" => HandleLoggingStopAsync(doc.RootElement),
            "file.upload.start" => HandleFileUploadStartAsync(doc.RootElement),
            "file.upload.chunk" => HandleFileUploadChunkAsync(doc.RootElement),
            "file.upload.end" => HandleFileUploadEndAsync(doc.RootElement),
            "file.upload.abort" => HandleFileUploadAbortAsync(doc.RootElement),
            "folder.pick" => HandleFolderPickAsync(doc.RootElement),
            "folder.explorer" => HandleFolderExplorerAsync(doc.RootElement),
            "folder.request" => HandleFolderListAsync(doc.RootElement),
            "terminal.start" => HandleTerminalStartAsync(doc.RootElement),
            "start" => HandleTerminalStartAsync(doc.RootElement),
            "terminal.stdin" => HandleTerminalStdinAsync(doc.RootElement),
            "input" => HandleTerminalStdinAsync(doc.RootElement),
            "terminal.kill" => HandleTerminalKillAsync(doc.RootElement),
            "kill" => HandleTerminalKillAsync(doc.RootElement),
            "terminal.resize" => HandleTerminalResizeAsync(doc.RootElement),
            "resize" => HandleTerminalResizeAsync(doc.RootElement),
            _ => Task.CompletedTask
        };
    }

    private Task HandleAppReadyAsync()
    {
        SendInitPayload();
        return Task.CompletedTask;
    }

    private Task HandleProfilesRequestAsync()
    {
        SendProfiles();
        return Task.CompletedTask;
    }

    private Task HandleProjectsRequestAsync()
    {
        SendProjects();
        return Task.CompletedTask;
    }

    private Task HandleProfilesSaveAsync(JsonElement root)
    {
        if (!root.TryGetProperty("profile", out var profileElement))
        {
            return Task.CompletedTask;
        }

        var profile = profileElement.Deserialize<TerminalProfile>(_jsonOptions);
        if (profile == null || string.IsNullOrWhiteSpace(profile.Id))
        {
            return Task.CompletedTask;
        }

        var existing = _profiles.FirstOrDefault(p => p.Id.Equals(profile.Id, StringComparison.OrdinalIgnoreCase));
        if (existing != null)
        {
            var index = _profiles.IndexOf(existing);
            _profiles[index] = profile;
        }
        else
        {
            _profiles.Add(profile);
        }

        ProfileStore.SaveProfiles(_profiles);
        _terminalManager.ReplaceProfiles(_profiles);
        SendProfiles();
        return Task.CompletedTask;
    }

    private Task HandleTasksRequestAsync()
    {
        SendTasks();
        return Task.CompletedTask;
    }

    private Task HandleTaskRunAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out var sessionId))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("task", out var taskElement))
        {
            return Task.CompletedTask;
        }

        var task = taskElement.Deserialize<ScriptEntry>(_jsonOptions);
        if (task == null || (string.IsNullOrWhiteSpace(task.Path) && string.IsNullOrWhiteSpace(task.Command)))
        {
            return Task.CompletedTask;
        }

        var command = BuildTaskCommand(session.ProfileId, task);
        if (string.IsNullOrWhiteSpace(command))
        {
            return Task.CompletedTask;
        }
        SendMessage(new
        {
            type = "output",
            sessionId,
            data = $"\r\n[task] sending: {command}"
        });
        return session.WriteAsync(command);
    }

    private Task HandleSessionAttachAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out var sessionId))
        {
            return Task.CompletedTask;
        }

        var clientId = root.TryGetProperty("clientId", out var clientElement)
            ? clientElement.GetString()
            : null;

        SendMessage(new { type = "ready", sessionId, profileId = session.ProfileId, clientId });
        SendMessage(new { type = "status", sessionId, state = "running" });
        return Task.CompletedTask;
    }

    private Task HandleLoggingStartAsync(JsonElement root)
    {
        if (!TryGetSession(root, out var session, out var sessionId))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("path", out var pathElement))
        {
            return Task.CompletedTask;
        }

        var path = pathElement.GetString();
        if (string.IsNullOrWhiteSpace(path))
        {
            return Task.CompletedTask;
        }

        lock (_logLock)
        {
            if (_sessionLogs.TryGetValue(sessionId, out var existing))
            {
                existing.Dispose();
                _sessionLogs.Remove(sessionId);
            }

            var directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var writer = new StreamWriter(new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read))
            {
                AutoFlush = true
            };
            _sessionLogs[sessionId] = writer;
        }

        SendMessage(new { type = "logging.status", sessionId, enabled = true, path });
        return Task.CompletedTask;
    }

    private Task HandleLoggingStopAsync(JsonElement root)
    {
        if (!TryGetSession(root, out _, out var sessionId))
        {
            return Task.CompletedTask;
        }

        lock (_logLock)
        {
            if (_sessionLogs.TryGetValue(sessionId, out var writer))
            {
                writer.Dispose();
                _sessionLogs.Remove(sessionId);
            }
        }

        SendMessage(new { type = "logging.status", sessionId, enabled = false });
        return Task.CompletedTask;
    }

    private Task HandleFileUploadStartAsync(JsonElement root)
    {
        if (!root.TryGetProperty("transferId", out var transferElement))
        {
            return Task.CompletedTask;
        }

        var transferId = transferElement.GetString();
        if (string.IsNullOrWhiteSpace(transferId))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("targetPath", out var targetElement))
        {
            return Task.CompletedTask;
        }

        var targetPath = targetElement.GetString();
        if (string.IsNullOrWhiteSpace(targetPath))
        {
            return Task.CompletedTask;
        }

        try
        {
            var directory = Path.GetDirectoryName(targetPath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var stream = new FileStream(targetPath, FileMode.Create, FileAccess.Write, FileShare.Read);
            _fileTransfers[transferId] = stream;
            SendMessage(new { type = "file.status", transferId, state = "started", path = targetPath });
        }
        catch (Exception ex)
        {
            SendMessage(new { type = "file.status", transferId, state = "error", message = ex.Message });
        }

        return Task.CompletedTask;
    }

    private Task HandleFileUploadChunkAsync(JsonElement root)
    {
        if (!root.TryGetProperty("transferId", out var transferElement) ||
            !root.TryGetProperty("data", out var dataElement))
        {
            return Task.CompletedTask;
        }

        var transferId = transferElement.GetString();
        var data = dataElement.GetString();
        if (string.IsNullOrWhiteSpace(transferId) || string.IsNullOrWhiteSpace(data))
        {
            return Task.CompletedTask;
        }

        if (!_fileTransfers.TryGetValue(transferId, out var stream))
        {
            return Task.CompletedTask;
        }

        try
        {
            var buffer = Convert.FromBase64String(data);
            stream.Write(buffer, 0, buffer.Length);
        }
        catch (Exception ex)
        {
            SendMessage(new { type = "file.status", transferId, state = "error", message = ex.Message });
        }

        return Task.CompletedTask;
    }

    private Task HandleFileUploadEndAsync(JsonElement root)
    {
        if (!root.TryGetProperty("transferId", out var transferElement))
        {
            return Task.CompletedTask;
        }

        var transferId = transferElement.GetString();
        if (string.IsNullOrWhiteSpace(transferId))
        {
            return Task.CompletedTask;
        }

        if (_fileTransfers.TryGetValue(transferId, out var stream))
        {
            stream.Dispose();
            _fileTransfers.Remove(transferId);
        }

        SendMessage(new { type = "file.status", transferId, state = "completed" });
        return Task.CompletedTask;
    }

    private Task HandleFileUploadAbortAsync(JsonElement root)
    {
        if (!root.TryGetProperty("transferId", out var transferElement))
        {
            return Task.CompletedTask;
        }

        var transferId = transferElement.GetString();
        if (string.IsNullOrWhiteSpace(transferId))
        {
            return Task.CompletedTask;
        }

        if (_fileTransfers.TryGetValue(transferId, out var stream))
        {
            stream.Dispose();
            _fileTransfers.Remove(transferId);
        }

        SendMessage(new { type = "file.status", transferId, state = "aborted" });
        return Task.CompletedTask;
    }

    private Task HandleAppStateAsync(JsonElement root)
    {
        if (!root.TryGetProperty("state", out var stateElement))
        {
            return Task.CompletedTask;
        }

        var state = stateElement.Deserialize<AppState>(_jsonOptions);
        if (state != null)
        {
            _latestState = state;
        }

        return Task.CompletedTask;
    }

    private Task HandleFolderPickAsync(JsonElement root)
    {
        if (!root.TryGetProperty("sessionId", out var sessionElement))
        {
            return Task.CompletedTask;
        }

        var sessionId = sessionElement.GetString() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            return Task.CompletedTask;
        }

        var initialPath = root.TryGetProperty("path", out var pathElement)
            ? pathElement.GetString()
            : null;

        if (InvokeRequired)
        {
            BeginInvoke(() => HandleFolderPick(sessionId, initialPath));
            return Task.CompletedTask;
        }

        HandleFolderPick(sessionId, initialPath);
        return Task.CompletedTask;
    }

    private Task HandleFolderExplorerAsync(JsonElement root)
    {
        if (!root.TryGetProperty("sessionId", out var sessionElement))
        {
            return Task.CompletedTask;
        }

        var sessionId = sessionElement.GetString() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            return Task.CompletedTask;
        }

        if (!root.TryGetProperty("path", out var pathElement))
        {
            return Task.CompletedTask;
        }

        var path = pathElement.GetString();
        if (string.IsNullOrWhiteSpace(path))
        {
            return Task.CompletedTask;
        }

        try
        {
            Process.Start(new ProcessStartInfo("explorer.exe", path) { UseShellExecute = true });
        }
        catch
        {
            // Ignore explorer failures.
        }

        return Task.CompletedTask;
    }

    private Task HandleFolderListAsync(JsonElement root)
    {
        var sessionId = root.TryGetProperty("sessionId", out var sessionElement)
            ? sessionElement.GetString()
            : null;
        var path = root.TryGetProperty("path", out var pathElement)
            ? pathElement.GetString()
            : null;

        var result = BuildFolderListing(path);
        SendMessage(new
        {
            type = "folder.list",
            sessionId,
            path = result.Path,
            parent = result.Parent,
            entries = result.Entries,
            error = result.Error
        });

        return Task.CompletedTask;
    }

    private Task HandleTerminalStartAsync(JsonElement root)
    {
        var profileId = root.TryGetProperty("profileId", out var profileElement)
            ? profileElement.GetString()
            : root.TryGetProperty("shell", out var shellElement)
                ? shellElement.GetString()
                : "powershell";

        var sessionId = Guid.NewGuid().ToString("N");
        var clientId = root.TryGetProperty("clientId", out var clientElement)
            ? clientElement.GetString()
            : null;
        try
        {
            var options = new SessionStartOptions
            {
                Cols = root.TryGetProperty("cols", out var colsElement) ? colsElement.GetInt32() : null,
                Rows = root.TryGetProperty("rows", out var rowsElement) ? rowsElement.GetInt32() : null,
                WorkingDirectory = root.TryGetProperty("cwd", out var cwdElement) ? cwdElement.GetString() : null
            };

            _terminalManager.StartSession(sessionId, profileId ?? "powershell", options);
            SendMessage(new { type = "ready", sessionId, profileId, clientId });
            SendMessage(new { type = "status", sessionId, state = "running" });
        }
        catch (Exception ex)
        {
            SendMessage(new { type = "error", sessionId, clientId, message = ex.Message });
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
        if (!TryGetSession(root, out _, out var sessionId))
        {
            return Task.CompletedTask;
        }

        _terminalManager.Kill(sessionId);
        CloseSessionLog(sessionId);
        return Task.CompletedTask;
    }

    private Task HandleTerminalResizeAsync(JsonElement root)
    {
        if (!TryGetSession(root, out _, out var sessionId))
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

        _terminalManager.Resize(sessionId, cols, rows);
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

        return _terminalManager.TryGetSession(sessionId, out session);
    }

    private void HandleSessionOutput(TerminalSession session, string data)
    {
        WriteSessionLog(session.SessionId, data);
        var buffer = _outputBuffers.GetOrAdd(session.SessionId, _ => new OutputBuffer());
        buffer.Append(data, chunk =>
        {
            SendMessage(new { type = "output", sessionId = session.SessionId, data = chunk });
        });
    }

    private void HandleSessionExit(TerminalSession session, int exitCode)
    {
        _outputBuffers.TryRemove(session.SessionId, out _);
        CloseSessionLog(session.SessionId);
        SendMessage(new { type = "exit", sessionId = session.SessionId, code = exitCode });
        SendMessage(new { type = "status", sessionId = session.SessionId, state = "exited" });
    }

    private void HandleSessionError(TerminalSession session, string message)
    {
        SendMessage(new { type = "error", sessionId = session.SessionId, message });
    }

    private void SendMessage(object payload)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => SendMessage(payload));
            return;
        }

        if (webView.CoreWebView2 == null)
        {
            return;
        }

        var json = JsonSerializer.Serialize(payload, _jsonOptions);
        webView.CoreWebView2.PostWebMessageAsString(json);
    }

    private void StopAllSessions()
    {
        _terminalManager.Dispose();
        foreach (var stream in _fileTransfers.Values)
        {
            stream.Dispose();
        }

        _fileTransfers.Clear();
        CloseAllLogs();
        if (_latestState != null)
        {
            AppStateStore.Save(_latestState);
        }
    }

    private void SendInitPayload()
    {
        RefreshProfileAvailability();
        SendMessage(new
        {
            type = "app.init",
            profiles = _profiles,
            statePayload = _latestState,
            workspace = _workspace,
            environment = _environment,
            projects = _workspace.Projects ?? new List<WorkspaceProject>(),
            scriptsPath = _scriptsPath,
            sessions = _terminalManager.Sessions.Select(session => new
            {
                sessionId = session.SessionId,
                profileId = session.ProfileId,
                state = "running"
            })
        });
    }

    private void SendProfiles()
    {
        RefreshProfileAvailability();
        SendMessage(new
        {
            type = "profiles.list",
            profiles = _profiles
        });
    }

    private void SendProjects()
    {
        SendMessage(new
        {
            type = "projects.list",
            workspace = _workspace,
            projects = _workspace.Projects ?? new List<WorkspaceProject>()
        });
    }

    private void SendTasks()
    {
        SendMessage(new
        {
            type = "tasks.list",
            workspace = _workspace
        });
    }

    private static Dictionary<string, string> BuildEnvironmentSnapshot()
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (DictionaryEntry entry in Environment.GetEnvironmentVariables())
        {
            var key = entry.Key?.ToString();
            if (string.IsNullOrWhiteSpace(key))
            {
                continue;
            }

            var value = entry.Value?.ToString();
            if (value == null)
            {
                continue;
            }

            result[key] = value;
        }

        return result;
    }

    private void RefreshProfileAvailability()
    {
        foreach (var profile in _profiles)
        {
            if (profile.IsTemplate)
            {
                profile.IsAvailable = true;
                continue;
            }

            _terminalManager.TryResolveProfileCommand(profile, out _);
        }
    }

    private void WriteSessionLog(string sessionId, string data)
    {
        lock (_logLock)
        {
            if (_sessionLogs.TryGetValue(sessionId, out var writer))
            {
                writer.Write(data);
            }
        }
    }

    private void CloseSessionLog(string sessionId)
    {
        lock (_logLock)
        {
            if (_sessionLogs.TryGetValue(sessionId, out var writer))
            {
                writer.Dispose();
                _sessionLogs.Remove(sessionId);
            }
        }
    }

    private void CloseAllLogs()
    {
        lock (_logLock)
        {
            foreach (var writer in _sessionLogs.Values)
            {
                writer.Dispose();
            }

            _sessionLogs.Clear();
        }
    }

    private void HandleFolderPick(string sessionId, string? initialPath)
    {
        if (!_terminalManager.TryGetSession(sessionId, out var session))
        {
            return;
        }

        if (!TryPickFolder(this, initialPath, out var selected))
        {
            return;
        }
        if (string.IsNullOrWhiteSpace(selected))
        {
            return;
        }

        var kind = ResolveShellKind(session.ProfileId);
        var cdCommand = BuildChangeDirectoryCommand(kind, selected);
        if (string.IsNullOrWhiteSpace(cdCommand))
        {
            return;
        }

        _ = session.WriteAsync($"{cdCommand}\r\n");
        SendMessage(new { type = "folder.changed", sessionId, path = selected });
    }

    private static bool TryPickFolder(IWin32Window owner, string? initialPath, out string selected)
    {
        selected = string.Empty;
        var safeInitial = !string.IsNullOrWhiteSpace(initialPath) && Directory.Exists(initialPath)
            ? initialPath
            : null;

        var openFolderType = Type.GetType("System.Windows.Forms.OpenFolderDialog, System.Windows.Forms");
        if (openFolderType != null)
        {
            using var dialog = (IDisposable)Activator.CreateInstance(openFolderType)!;
            openFolderType.GetProperty("Title")?.SetValue(dialog, "Select working directory");
            openFolderType.GetProperty("Multiselect")?.SetValue(dialog, false);
            if (safeInitial != null)
            {
                openFolderType.GetProperty("InitialDirectory")?.SetValue(dialog, safeInitial);
            }

            var showDialog = openFolderType.GetMethod("ShowDialog", new[] { typeof(IWin32Window) });
            if (showDialog?.Invoke(dialog, new object[] { owner }) is DialogResult result &&
                result == DialogResult.OK)
            {
                var folderName = openFolderType.GetProperty("FolderName")?.GetValue(dialog) as string;
                if (!string.IsNullOrWhiteSpace(folderName))
                {
                    selected = folderName;
                    return true;
                }
            }
        }

        using var fallback = new FolderBrowserDialog
        {
            Description = "Select working directory",
            UseDescriptionForTitle = true,
            ShowNewFolderButton = true
        };
        if (safeInitial != null)
        {
            fallback.SelectedPath = safeInitial;
        }

        if (fallback.ShowDialog(owner) != DialogResult.OK)
        {
            return false;
        }

        selected = fallback.SelectedPath;
        return !string.IsNullOrWhiteSpace(selected);
    }

    private static FolderListingResult BuildFolderListing(string? path)
    {
        var normalized = path?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return new FolderListingResult
            {
                Path = string.Empty,
                Parent = null,
                Entries = DriveInfo.GetDrives()
                    .Where(drive => drive.IsReady)
                    .Select(drive => new FolderEntry
                    {
                        Name = drive.Name,
                        Path = drive.RootDirectory.FullName,
                        Kind = "drive"
                    })
                    .ToList(),
                Error = null
            };
        }

        if (!Directory.Exists(normalized))
        {
            return new FolderListingResult
            {
                Path = normalized,
                Parent = GetParentPath(normalized),
                Entries = new List<FolderEntry>(),
                Error = "Folder not found."
            };
        }

        try
        {
            var entries = Directory.EnumerateDirectories(normalized)
                .Select(folder => new FolderEntry
                {
                    Name = Path.GetFileName(folder),
                    Path = folder,
                    Kind = "folder"
                })
                .OrderBy(entry => entry.Name, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return new FolderListingResult
            {
                Path = normalized,
                Parent = GetParentPath(normalized),
                Entries = entries,
                Error = null
            };
        }
        catch (UnauthorizedAccessException)
        {
            return new FolderListingResult
            {
                Path = normalized,
                Parent = GetParentPath(normalized),
                Entries = new List<FolderEntry>(),
                Error = "Access denied."
            };
        }
        catch (Exception ex)
        {
            return new FolderListingResult
            {
                Path = normalized,
                Parent = GetParentPath(normalized),
                Entries = new List<FolderEntry>(),
                Error = ex.Message
            };
        }
    }

    private static string? GetParentPath(string path)
    {
        var trimmed = path.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            return null;
        }

        var parent = Directory.GetParent(trimmed);
        return parent?.FullName;
    }

    private string BuildTaskCommand(string profileId, ScriptEntry task)
    {
        var kind = ResolveShellKind(profileId);
        var command = ResolveTaskCommand(kind, task);
        if (string.IsNullOrWhiteSpace(command))
        {
            return string.Empty;
        }

        var workingDirectory = !string.IsNullOrWhiteSpace(task.WorkingDirectory)
            ? task.WorkingDirectory
            : task.Cwd;
        if (!string.IsNullOrWhiteSpace(workingDirectory))
        {
            var cwd = workingDirectory;
            var cdCommand = kind switch
            {
                ShellKind.PowerShell => $"Set-Location -Path {QuotePowerShell(cwd)}",
                ShellKind.Cmd => $"cd /d {QuoteCmd(cwd)}",
                _ => $"cd {QuoteBash(cwd)}"
            };

            return $"{cdCommand}\r\n{command}\r\n";
        }

        return $"{command}\r\n";
    }

    private string BuildChangeDirectoryCommand(ShellKind kind, string path)
    {
        return kind switch
        {
            ShellKind.PowerShell => $"Set-Location -Path {QuotePowerShell(path)}",
            ShellKind.Cmd => $"cd /d {QuoteCmd(path)}",
            _ => $"cd {QuoteBash(path)}"
        };
    }

    private string ResolveTaskCommand(ShellKind kind, ScriptEntry task)
    {
        if (!string.IsNullOrWhiteSpace(task.Command))
        {
            return task.Command!;
        }

        if (string.IsNullOrWhiteSpace(task.Path))
        {
            return string.Empty;
        }

        return BuildExecutableCommand(kind, task.Path, task.Args);
    }

    private ShellKind ResolveShellKind(string profileId)
    {
        var profile = _terminalManager.GetProfile(profileId);
        var command = profile?.ResolvedCommand ?? profile?.Command ?? string.Empty;
        var name = Path.GetFileName(command).ToLowerInvariant();
        if (name.Contains("cmd"))
        {
            return ShellKind.Cmd;
        }

        if (name.Contains("pwsh") || name.Contains("powershell"))
        {
            return ShellKind.PowerShell;
        }

        if (name.Contains("bash") || name.Contains("wsl"))
        {
            return ShellKind.Bash;
        }

        return ShellKind.PowerShell;
    }

    private string BuildExecutableCommand(ShellKind kind, string path, string? args)
    {
        var hasArgs = !string.IsNullOrWhiteSpace(args);
        var trimmedArgs = hasArgs ? args!.Trim() : string.Empty;
        var needsQuote = path.Contains(' ');

        return kind switch
        {
            ShellKind.PowerShell => hasArgs
                ? needsQuote
                    ? $"& {QuotePowerShell(path)} {trimmedArgs}"
                    : $"{path} {trimmedArgs}"
                : needsQuote ? $"& {QuotePowerShell(path)}" : path,
            ShellKind.Cmd => hasArgs
                ? $"{(needsQuote ? QuoteCmd(path) : path)} {trimmedArgs}"
                : needsQuote ? QuoteCmd(path) : path,
            _ => hasArgs
                ? $"{(needsQuote ? QuoteBash(path) : path)} {trimmedArgs}"
                : needsQuote ? QuoteBash(path) : path
        };
    }

    private static string QuotePowerShell(string value)
    {
        return $"\"{value.Replace("\"", "`\"")}\"";
    }

    private static string QuoteCmd(string value)
    {
        return $"\"{value.Replace("\"", "\"\"")}\"";
    }

    private static string QuoteBash(string value)
    {
        return $"\"{value.Replace("\"", "\\\"")}\"";
    }

    private sealed class FolderListingResult
    {
        public string Path { get; init; } = string.Empty;
        public string? Parent { get; init; }
        public List<FolderEntry> Entries { get; init; } = new();
        public string? Error { get; init; }
    }

    private sealed class FolderEntry
    {
        public string Name { get; init; } = string.Empty;
        public string Path { get; init; } = string.Empty;
        public string Kind { get; init; } = "folder";
    }

    private enum ShellKind
    {
        PowerShell,
        Cmd,
        Bash
    }

    private sealed class OutputBuffer
    {
        private const int ChunkSize = 8192;
        private readonly object _sync = new();
        private readonly StringBuilder _buffer = new();
        private bool _flushing;

        public void Append(string data, Action<string> sendChunk)
        {
            lock (_sync)
            {
                _buffer.Append(data);
                if (_flushing)
                {
                    return;
                }

                _flushing = true;
            }

            _ = Task.Run(async () =>
            {
                while (true)
                {
                    string? chunk = null;
                    lock (_sync)
                    {
                        if (_buffer.Length == 0)
                        {
                            _flushing = false;
                            return;
                        }

                        var length = Math.Min(ChunkSize, _buffer.Length);
                        chunk = _buffer.ToString(0, length);
                        _buffer.Remove(0, length);
                    }

                    sendChunk(chunk);
                    await Task.Delay(10);
                }
            });
        }
    }
}
