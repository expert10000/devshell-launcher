using System.Collections.Concurrent;

namespace BatchLauncher;

public sealed class TerminalManager : IDisposable
{
    private readonly ConcurrentDictionary<string, TerminalSession> _sessions = new();
    private Dictionary<string, TerminalProfile> _profiles;

    public TerminalManager(IEnumerable<TerminalProfile> profiles)
    {
        _profiles = profiles.ToDictionary(p => p.Id, StringComparer.OrdinalIgnoreCase);
    }

    public event Action<TerminalSession, string>? Output;
    public event Action<TerminalSession, int>? Exited;
    public event Action<TerminalSession, string>? Error;

    public IReadOnlyCollection<TerminalSession> Sessions => _sessions.Values.ToList();

    public TerminalProfile? GetProfile(string profileId)
    {
        return _profiles.TryGetValue(profileId, out var profile) ? profile : null;
    }

    public IReadOnlyCollection<TerminalProfile> Profiles => _profiles.Values.ToList();

    public void ReplaceProfiles(IEnumerable<TerminalProfile> profiles)
    {
        _profiles = profiles.ToDictionary(p => p.Id, StringComparer.OrdinalIgnoreCase);
    }

    public TerminalSession StartSession(string sessionId, string profileId, SessionStartOptions options)
    {
        var profile = ResolveProfile(profileId);
        var resolved = ResolveProfileCommand(profile);
        profile.ResolvedCommand = resolved.Application;

        var session = TerminalSession.Start(sessionId, profile, resolved, options);
        session.Output += (s, data) => Output?.Invoke(s, data);
        session.Error += (s, message) => Error?.Invoke(s, message);
        session.Exited += (s, exitCode) =>
        {
            _sessions.TryRemove(s.SessionId, out _);
            Exited?.Invoke(s, exitCode);
        };

        _sessions[sessionId] = session;
        return session;
    }

    public bool TryGetSession(string sessionId, out TerminalSession session)
    {
        return _sessions.TryGetValue(sessionId, out session!);
    }

    public void Kill(string sessionId)
    {
        if (_sessions.TryRemove(sessionId, out var session))
        {
            session.Dispose();
        }
    }

    public void Resize(string sessionId, int cols, int rows)
    {
        if (_sessions.TryGetValue(sessionId, out var session))
        {
            session.Resize(cols, rows);
        }
    }

    public void Dispose()
    {
        foreach (var session in _sessions.Values)
        {
            session.Dispose();
        }

        _sessions.Clear();
    }

    private TerminalProfile ResolveProfile(string profileId)
    {
        if (_profiles.TryGetValue(profileId, out var profile))
        {
            return profile;
        }

        if (_profiles.TryGetValue("powershell", out var fallback))
        {
            return fallback;
        }

        return _profiles.Values.First();
    }

    private static ShellCommand ResolveProfileCommand(TerminalProfile profile)
    {
        if (string.IsNullOrWhiteSpace(profile.Command))
        {
            throw new InvalidOperationException($"Profile \"{profile.Name}\" has no command configured.");
        }

        var resolved = ResolveExecutable(profile.Command);
        if (string.IsNullOrWhiteSpace(resolved))
        {
            profile.IsAvailable = false;
            throw new FileNotFoundException($"Command not found for profile \"{profile.Name}\".", profile.Command);
        }

        profile.IsAvailable = true;
        return new ShellCommand(resolved, profile.Arguments);
    }

    public bool TryResolveProfileCommand(TerminalProfile profile, out ShellCommand command)
    {
        try
        {
            command = ResolveProfileCommand(profile);
            return true;
        }
        catch
        {
            command = default;
            return false;
        }
    }

    private static string? ResolveExecutable(string command)
    {
        if (Path.IsPathRooted(command) || command.Contains(Path.DirectorySeparatorChar))
        {
            return File.Exists(command) ? command : null;
        }

        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        var paths = pathVar.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var path in paths)
        {
            var candidate = Path.Combine(path, command);
            if (File.Exists(candidate))
            {
                return candidate;
            }

            if (!command.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            {
                candidate = Path.Combine(path, $"{command}.exe");
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        return null;
    }

    public readonly record struct ShellCommand(string Application, string? Arguments);
}

public sealed class SessionStartOptions
{
    public int? Cols { get; init; }
    public int? Rows { get; init; }
    public string? WorkingDirectory { get; init; }
    public Dictionary<string, string>? Environment { get; init; }
    public string? Arguments { get; init; }
}
