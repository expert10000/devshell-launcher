using BatchLauncher;

var root = Path.Combine(Path.GetTempPath(), "devshell-search-checks-" + Guid.NewGuid().ToString("N"));
var first = Path.Combine(root, "first"); var second = Path.Combine(root, "second");
void Write(string relative, string content = "fixture") { var path = Path.Combine(root, relative); Directory.CreateDirectory(Path.GetDirectoryName(path)!); File.WriteAllText(path, content); }
void Check(string name, bool condition) { if (!condition) throw new Exception(name); Console.WriteLine("PASS: " + name); }
void Rejected(string name, Action action) { try { action(); } catch (ArgumentException) { Check(name, true); return; } throw new Exception(name); }
Write("first/py/api.py"); Write("second/nested/API.py"); Write("first/notebooks/demo.ipynb", "{\"nbformat\":4,\"cells\":[]}");
Write("first/node_modules/hidden.py"); Write("first/.git/hidden.py"); Write("first/.venv/hidden.py"); Write("first/secret.sqlite3");
var repos = new List<WorkspaceSearchRepository> { new("first", "First", first), new("second", "Second", second) };
var found = WorkspaceFileSearch.Search(repos, "api.py");
Check("case-insensitive filenames across repositories", found.Entries.Count == 2 && found.Entries.Select(hit => hit.RepositoryId).Distinct().Count() == 2);
Check("relative path search", WorkspaceFileSearch.Search(repos, "nested/API").Entries.Single().Entry.Path == "nested/API.py");
Check("Windows separators normalize in queries", WorkspaceFileSearch.Search(repos, "nested\\API").Entries.Count == 1);
Check("Git and dependency folders excluded", WorkspaceFileSearch.Search(repos, ".py").Entries.Count == 2);
Check("notebook search preserves safe type and artifact classification", WorkspaceFileSearch.Search(repos, ".ipynb").Entries.Single().Entry is { Kind: "text", Artifact: true });
var located = WorkspaceFiles.Locate(first, "notebooks/demo.ipynb");
Check("search result resolves containing folder and selected entry", located.Listing.Path == "notebooks" && located.Entry.Path == "notebooks/demo.ipynb" && located.Listing.Entries.Any(entry => entry.Path == located.Entry.Path));
Check("unsupported binary can be located without reading or executing it", WorkspaceFiles.Locate(first, "secret.sqlite3").Entry.Kind == "file");
Rejected("search result path escape rejected", () => WorkspaceFiles.Locate(first, "../second/nested/API.py"));
Rejected("short query rejected", () => WorkspaceFileSearch.Search(repos, "a"));
Rejected("oversized query rejected", () => WorkspaceFileSearch.Search(repos, new string('a', 161)));
var missing = WorkspaceFileSearch.Search(new() { new("missing", "Missing", Path.Combine(root, "missing")) }, "api");
Check("missing repositories produce a warning and partial result", missing.Truncated && missing.Warnings.Count == 1 && missing.Entries.Count == 0);
for (var index = 0; index < 510; index++) Write($"first/many/match-{index:D4}.txt");
var capped = WorkspaceFileSearch.Search(repos, "match-");
Check("search result count is capped and marked partial", capped.Entries.Count == 500 && capped.Truncated);
Console.WriteLine("Fixtures retained at " + root);
