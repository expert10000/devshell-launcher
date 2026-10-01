using BatchLauncher;
using System.Diagnostics;
using System.Text;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
static async Task<string> Git(string path, params string[] args)
{
    var info = new ProcessStartInfo("git") { WorkingDirectory = path, UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8 };
    foreach (var arg in new[] { "-C", path, "-c", "user.name=DevShell Test", "-c", "user.email=test@example.invalid" }.Concat(args)) info.ArgumentList.Add(arg);
    using var process = Process.Start(info)!; var output = process.StandardOutput.ReadToEndAsync(); var error = process.StandardError.ReadToEndAsync();
    await process.WaitForExitAsync(); if (process.ExitCode != 0) throw new Exception(await error); return await output;
}
static async Task Reject(Func<Task> action, string message) { try { await action(); } catch (InvalidOperationException) { return; } catch (ArgumentException) { return; } throw new Exception(message); }
var root = Path.Combine(Path.GetTempPath(), "devshell-changes-test-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
try
{
    await Git(root, "init", "-b", "main");
    var unicode = "za\u017c\u00f3\u0142\u0107 name.txt";
    File.WriteAllText(Path.Combine(root, unicode), "first\n"); File.WriteAllText(Path.Combine(root, "other.txt"), "leave me\n");
    var s = await RepositoryChanges.Read(root); Check(s.Head == "(unborn)" && s.Files.Count == 2, "Unborn status");
    var d = await RepositoryChanges.Diff(root, s, unicode, "working"); Check(d.Text.Contains("first"), "Untracked Unicode preview");
    s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { unicode }); Check(s.Files.Single(file => file.Path == unicode).Staged && !s.Files.Single(file => file.Path == "other.txt").Staged, "Selective stage only");
    s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "unstage", new[] { unicode }); Check(s.Files.All(file => !file.Staged) && File.ReadAllText(Path.Combine(root, unicode)) == "first\n", "Unborn unstage preserves files");
    await Git(root, "add", "--", unicode, "other.txt"); await Git(root, "commit", "-m", "test baseline");
    File.WriteAllText(Path.Combine(root, unicode), "staged version\n"); await Git(root, "add", "--", unicode); File.WriteAllText(Path.Combine(root, unicode), "working version\n");
    s = await RepositoryChanges.Read(root); var partial = s.Files.Single(); Check(partial.Staged && partial.Unstaged, "Partially staged file on both sides");
    Check((await RepositoryChanges.Diff(root, s, unicode, "staged")).Text.Contains("staged version"), "Staged diff");
    Check((await RepositoryChanges.Diff(root, s, unicode, "working")).Text.Contains("working version"), "Working diff");
    var before = File.ReadAllText(Path.Combine(root, unicode)); s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "unstage", new[] { unicode }); Check(File.ReadAllText(Path.Combine(root, unicode)) == before, "Unstage keeps working content");
    var stale = s; await Git(root, "add", "--", unicode); await Reject(() => RepositoryChanges.ChangeIndex(root, stale, stale.Token, "stage", new[] { unicode }), "Reject stale index");
    await Git(root, "commit", "-m", "test modification"); await Git(root, "mv", "other.txt", "renamed name.txt");
    s = await RepositoryChanges.Read(root); Check(s.Files.Single().OriginalPath == "other.txt", "Rename source");
    s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "unstage", new[] { "renamed name.txt" }); Check(s.Files.All(file => !file.Staged) && File.Exists(Path.Combine(root, "renamed name.txt")), "Unstage both rename sides without moving files");
    s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { "other.txt" }); Check(s.Files.Any(file => file.Path == "other.txt" && file.Index == "D"), "Stage selected deletion");
    var special = ":(glob)*.txt"; var parsed = RepositoryChanges.ParseStatus("?? " + special + "\0 M line\nname.txt\0R  new.txt\0old.txt\0"); Check(parsed.Count == 3 && parsed[1].Path.Contains('\n') && parsed[2].OriginalPath == "old.txt", "NUL parser retains literal names and rename pairs");
    await Reject(() => RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { "../outside.txt" }), "Reject path escape");
    await Reject(() => RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { "." }), "Reject stage-all path");
    File.WriteAllText(Path.Combine(root, "[literal].txt"), "literal\n"); File.WriteAllText(Path.Combine(root, "l.txt"), "not selected\n");
    s = await RepositoryChanges.Read(root); s = await RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { "[literal].txt" }); Check(s.Files.Single(file => file.Path == "[literal].txt").Staged && !s.Files.Single(file => file.Path == "l.txt").Staged, "Literal pathspec does not stage glob matches");
    File.WriteAllText(Path.Combine(root, "binary.dat"), "binary\0content"); s = await RepositoryChanges.Read(root); Check((await RepositoryChanges.Diff(root, s, "binary.dat", "working")).Text.Contains("Binary file"), "Binary preview");
    File.WriteAllText(Path.Combine(root, ".git", "MERGE_HEAD"), s.Head); s = await RepositoryChanges.Read(root); Check(s.BlockedReason != null, "Active operation blocks writes"); await Reject(() => RepositoryChanges.ChangeIndex(root, s, s.Token, "stage", new[] { "l.txt" }), "Block writes during merge");
    Console.WriteLine("PASS: selective stage, unstage preserves edits, unborn HEAD, partial staging, Unicode, rename, deletion, stale index, literal pathspecs, path escape, binary preview, active-operation guard");
}
finally
{
    var full = Path.GetFullPath(root);
    if (!full.StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase) || !Path.GetFileName(full).StartsWith("devshell-changes-test-")) throw new Exception("Unsafe cleanup path");
    foreach (var file in Directory.EnumerateFiles(full, "*", SearchOption.AllDirectories)) File.SetAttributes(file, FileAttributes.Normal);
    Directory.Delete(full, true);
}
