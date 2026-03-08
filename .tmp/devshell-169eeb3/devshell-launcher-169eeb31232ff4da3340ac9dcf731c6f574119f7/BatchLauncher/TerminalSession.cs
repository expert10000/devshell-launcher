using System.Text;
using System.IO;

namespace BatchLauncher;

public sealed class TerminalSession : IDisposable
{
    private readonly ConPtyProcess _process;
    private readonly FileStream _inputStream;
    private readonly FileStream _outputStream;
    private readonly CancellationTokenSource _cts = new();
    private readonly Decoder _decoder = Encoding.UTF8.GetDecoder();
    private readonly object _writeLock = new();
    private int _exitRaised;
    private bool _disposed;

    public string SessionId { get; }
    public string ProfileId { get; }

    public event Action<TerminalSession, string>? Output;
    public event Action<TerminalSession, int>? Exited;
    public event Action<TerminalSession, string>? Error;

    private TerminalSession(string sessionId, string profileId, ConPtyProcess process)
    {
        SessionId = sessionId;
        ProfileId = profileId;
        _process = process;
        _inputStream = new FileStream(_process.InputWrite, FileAccess.Write, 4096, isAsync: false);
        _outputStream = new FileStream(_process.OutputRead, FileAccess.Read, 4096, isAsync: false);

        _ = Task.Run(() => ReadOutputLoop(_cts.Token));
        _ = Task.Run(() => WaitForExitAsync(_cts.Token));
    }

    public static TerminalSession Start(
        string sessionId,
        TerminalProfile profile,
        TerminalManager.ShellCommand command,
        SessionStartOptions options)
    {
        var cols = options.Cols ?? profile.DefaultCols ?? 80;
        var rows = options.Rows ?? profile.DefaultRows ?? 24;
        var workingDir = options.WorkingDirectory ?? profile.WorkingDirectory;
        var hasWorkingDir = !string.IsNullOrWhiteSpace(workingDir);
        if (hasWorkingDir && !Directory.Exists(workingDir))
        {
            workingDir = null;
            hasWorkingDir = false;
        }
        var env = MergeEnvironment(profile.Environment, options.Environment);
        var arguments = string.IsNullOrWhiteSpace(options.Arguments)
            ? command.Arguments
            : string.IsNullOrWhiteSpace(command.Arguments)
                ? options.Arguments
                : $"{command.Arguments} {options.Arguments}";

        var resolved = new TerminalManager.ShellCommand(command.Application, arguments);
        ConPtyProcess process;
        try
        {
            process = ConPtyProcess.Start(
                resolved.Application,
                resolved.Arguments,
                cols,
                rows,
                workingDir,
                env);
        }
        catch (InvalidOperationException ex) when (hasWorkingDir &&
                                                   ex.Message.Contains("CreateProcess failed: 5", StringComparison.OrdinalIgnoreCase))
        {
            process = ConPtyProcess.Start(
                resolved.Application,
                resolved.Arguments,
                cols,
                rows,
                null,
                env);
        }
        return new TerminalSession(sessionId, profile.Id, process);
    }

    public Task WriteAsync(string data)
    {
        if (_disposed)
        {
            return Task.CompletedTask;
        }

        var buffer = Encoding.UTF8.GetBytes(data);
        return Task.Run(() => WriteAndFlush(buffer), _cts.Token);
    }

    public void Resize(int cols, int rows)
    {
        if (_disposed)
        {
            return;
        }

        _process.Resize(cols, rows);
    }

    public void Kill()
    {
        Dispose();
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _cts.Cancel();
        _inputStream.Dispose();
        _outputStream.Dispose();
        _process.Dispose();
        _cts.Dispose();
    }

    private void ReadOutputLoop(CancellationToken token)
    {
        var buffer = new byte[4096];
        try
        {
            while (!token.IsCancellationRequested)
            {
                var read = _outputStream.Read(buffer, 0, buffer.Length);
                if (read <= 0)
                {
                    break;
                }

                var charCount = _decoder.GetCharCount(buffer, 0, read, false);
                var chars = new char[charCount];
                _decoder.GetChars(buffer, 0, read, chars, 0, false);
                Output?.Invoke(this, new string(chars));
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (ObjectDisposedException)
        {
        }
        catch (Exception ex)
        {
            Error?.Invoke(this, ex.Message);
        }
    }

    private Task WaitForExitAsync(CancellationToken token)
    {
        try
        {
            var exitCode = _process.WaitForExit(token);
            RaiseExit(exitCode);
        }
        catch (Exception ex)
        {
            Error?.Invoke(this, ex.Message);
        }

        return Task.CompletedTask;
    }

    private void RaiseExit(int exitCode)
    {
        if (Interlocked.Exchange(ref _exitRaised, 1) == 0)
        {
            Exited?.Invoke(this, exitCode);
        }
    }

    private static Dictionary<string, string>? MergeEnvironment(
        Dictionary<string, string>? baseEnv,
        Dictionary<string, string>? overrides)
    {
        if (baseEnv == null && overrides == null)
        {
            return null;
        }

        var merged = baseEnv != null
            ? new Dictionary<string, string>(baseEnv, StringComparer.OrdinalIgnoreCase)
            : new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        if (overrides != null)
        {
            foreach (var pair in overrides)
            {
                merged[pair.Key] = pair.Value;
            }
        }

        return merged;
    }

    private void WriteAndFlush(byte[] buffer)
    {
        lock (_writeLock)
        {
            _inputStream.Write(buffer, 0, buffer.Length);
            _inputStream.Flush();
        }
    }
}
