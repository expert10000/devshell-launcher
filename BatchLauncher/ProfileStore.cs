using System.Text.Json;
using System.Linq;

namespace BatchLauncher;

internal static class ProfileStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public static List<TerminalProfile> LoadProfiles()
    {
        AppPaths.EnsureProfilesDirectory();
        TryMigrateProfiles();
        if (File.Exists(AppPaths.ProfilesPath))
        {
            try
            {
                var json = File.ReadAllText(AppPaths.ProfilesPath);
                var profiles = JsonSerializer.Deserialize<List<TerminalProfile>>(json, Options)
                               ?? new List<TerminalProfile>();
                return EnsureDefaultProfiles(profiles);
            }
            catch
            {
                // If corrupted, fall back to defaults.
            }
        }

        var defaults = BuildDefaultProfiles();
        SaveProfiles(defaults);
        return defaults;
    }

    public static void SaveProfiles(List<TerminalProfile> profiles)
    {
        AppPaths.EnsureProfilesDirectory();
        var json = JsonSerializer.Serialize(profiles, Options);
        File.WriteAllText(AppPaths.ProfilesPath, json);
    }

    private static List<TerminalProfile> EnsureDefaultProfiles(List<TerminalProfile> profiles)
    {
        var existingIds = new HashSet<string>(profiles.Select(p => p.Id), StringComparer.OrdinalIgnoreCase);
        var defaults = BuildDefaultProfiles();
        foreach (var profile in defaults)
        {
            if (!existingIds.Contains(profile.Id))
            {
                profiles.Add(profile);
            }
        }

        return profiles;
    }

    private static List<TerminalProfile> BuildDefaultProfiles()
    {
        var gitBashCommand = ResolveGitBashCommand();
        var profiles = new List<TerminalProfile>
        {
            new()
            {
                Id = "powershell",
                Name = "Windows PowerShell",
                Command = "powershell.exe",
                Arguments = "-NoLogo",
                DefaultCols = 100,
                DefaultRows = 30,
                Icon = "ps",
                IsBuiltin = true
            },
            new()
            {
                Id = "pwsh",
                Name = "PowerShell 7",
                Command = "pwsh.exe",
                Arguments = "-NoLogo",
                DefaultCols = 100,
                DefaultRows = 30,
                Icon = "pwsh",
                IsBuiltin = true
            },
            new()
            {
                Id = "cmd",
                Name = "CMD",
                Command = "cmd.exe",
                DefaultCols = 100,
                DefaultRows = 30,
                Icon = "cmd",
                IsBuiltin = true
            },
            new()
            {
                Id = "wsl-ubuntu",
                Name = "WSL (Ubuntu)",
                Command = "wsl.exe",
                Arguments = "-d Ubuntu",
                DefaultCols = 110,
                DefaultRows = 32,
                Icon = "wsl",
                IsBuiltin = true
            },
            new()
            {
                Id = "git-bash",
                Name = "Git Bash / MSYS2",
                Command = gitBashCommand ?? "bash.exe",
                Arguments = "--login -i",
                DefaultCols = 110,
                DefaultRows = 32,
                Icon = "bash",
                IsBuiltin = true
            },
            new()
            {
                Id = "custom",
                Name = "Custom Profile...",
                Command = string.Empty,
                DefaultCols = 100,
                DefaultRows = 30,
                Icon = "custom",
                IsBuiltin = true,
                IsTemplate = true
            }
        };

        return profiles;
    }

    private static string? ResolveGitBashCommand()
    {
        var candidates = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Git", "bin", "bash.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Git", "usr", "bin", "bash.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Git", "bin", "bash.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Git", "usr", "bin", "bash.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "MSYS2", "usr", "bin", "bash.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "MSYS2", "usr", "bin", "bash.exe"),
            Path.Combine(GetSystemDrive(), "msys64", "usr", "bin", "bash.exe")
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private static string GetSystemDrive()
    {
        var systemDrive = Environment.GetEnvironmentVariable("SystemDrive");
        if (!string.IsNullOrWhiteSpace(systemDrive))
        {
            return systemDrive;
        }

        return Path.GetPathRoot(Environment.SystemDirectory) ?? "C:";
    }

    private static void TryMigrateProfiles()
    {
        if (File.Exists(AppPaths.ProfilesPath))
        {
            return;
        }

        var legacyPaths = new[]
        {
            AppPaths.LegacyProfilesPath,
            AppPaths.LegacyProfilesPathAlt,
            AppPaths.LegacyProfilesPathAlt2
        };
        foreach (var legacyPath in legacyPaths)
        {
            if (!File.Exists(legacyPath))
            {
                continue;
            }

            try
            {
                File.Move(legacyPath, AppPaths.ProfilesPath);
                return;
            }
            catch
            {
                try
                {
                    File.Copy(legacyPath, AppPaths.ProfilesPath, overwrite: true);
                    return;
                }
                catch
                {
                    // Ignore migration errors.
                }
            }
        }
    }
}
