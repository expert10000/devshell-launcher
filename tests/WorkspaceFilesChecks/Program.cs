using BatchLauncher;

var root = Path.Combine(Path.GetTempPath(), "devshell-files-checks-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(Path.Combine(root, "build", "pdf"));
Directory.CreateDirectory(Path.Combine(root, ".git"));
File.WriteAllText(Path.Combine(root, "README.md"), "Read-only preview / Unicode: \u017c\u00f3\u0142\u0107");
File.WriteAllText(Path.Combine(root, "build", "pdf", "volume.pdf"), "%PDF-1.7\nfixture");
File.WriteAllText(Path.Combine(root, "build", "pdf", "invalid.pdf"), "not a PDF");
File.WriteAllText(Path.Combine(root, "large.log"), new string('x', WorkspaceFiles.MaxPreviewChars + 100));
void Check(bool condition, string label) { if (!condition) throw new Exception(label); Console.WriteLine("PASS: " + label); }
void Reject(Action action, string label) { try { action(); } catch (ArgumentException) { Check(true, label); return; } throw new Exception(label); }
var listing = WorkspaceFiles.List(root, "");
Check(listing.Entries.Any(entry => entry.Name == "build" && entry.Kind == "folder"), "root folder browsing");
Check(listing.Entries.All(entry => entry.Name != ".git"), "Git internals excluded");
Check(WorkspaceFiles.List(root, "build/pdf").Entries.Count(entry => entry.Kind == "pdf" && entry.Artifact) == 2, "PDF collection classified");
Check(WorkspaceFiles.Preview(root, "README.md").Text.Contains("\u017c\u00f3\u0142\u0107"), "UTF-8 text preview");
Check(WorkspaceFiles.Preview(root, "large.log").Truncated, "bounded preview");
Reject(() => WorkspaceFiles.List(root, "../escape"), "folder escape rejected");
Reject(() => WorkspaceFiles.List(root, ".git"), "Git directory request rejected");
Reject(() => WorkspaceFiles.Preview(root, "../README.md"), "preview escape rejected");
Reject(() => WorkspaceFiles.Preview(root, "build/pdf/volume.pdf"), "PDF cannot use text preview");
Check(PdfFile.Resolve(root, "build/pdf/volume.pdf").EndsWith("volume.pdf"), "selected PDF resolution");
try { PdfFile.Resolve(root, "build/pdf/invalid.pdf"); throw new Exception("Invalid PDF accepted"); } catch (InvalidDataException) { Check(true, "invalid PDF rejected"); }
var workspace = new WorkspaceConfig { Projects = new() { new() { Id = "project", Repositories = new() { new() { Id = "repo", Path = root, PdfDirectory = "build/pdf" } } } } };
var state = new WorkspaceTabsState { Tabs = new() {
    new() { Kind = "pdf", ProjectId = "project", RepositoryId = "repo", FilePath = null },
    new() { Kind = "pdf", ProjectId = "project", RepositoryId = "repo", FilePath = null },
    new() { Kind = "files", ProjectId = "project", RepositoryId = "repo", FilePath = "build/pdf" },
    new() { Kind = "files", ProjectId = "project", RepositoryId = "repo", FilePath = "../escape" }
} };
var normalized = WorkspaceTabsStore.Normalize(state, workspace);
Check(normalized.Tabs.Count(tab => tab.Kind == "pdf") == 1, "restored PDF selectors deduplicated");
Check(normalized.Tabs.Single(tab => tab.Kind == "files").FilePath == "build/pdf", "files descriptor stores scoped location only");
Console.WriteLine("Fixtures retained at " + root);
