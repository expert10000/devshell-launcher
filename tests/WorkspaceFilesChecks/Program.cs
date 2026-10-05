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
File.WriteAllText(Path.Combine(root, "sample.py"), "print('read-only')\n");
File.WriteAllText(Path.Combine(root, "sample.html"), "<script>throw new Error('never execute')</script>");
File.WriteAllText(Path.Combine(root, "sample.json"), "{\"ready\":true,\"count\":2}");
File.WriteAllText(Path.Combine(root, "sample.csv"), "name,value\n\"quoted, name\",42\n");
File.WriteAllText(Path.Combine(root, "private.env"), "SECRET=never-preview");
File.WriteAllText(Path.Combine(root, "sample.sqlite3"), "binary database fixture");
File.WriteAllBytes(Path.Combine(root, "pixel.png"), Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="));
File.WriteAllText(Path.Combine(root, "bad.png"), "<svg onload='alert(1)'></svg>");
File.WriteAllText(Path.Combine(root, "safe.svg"), "<svg onload='alert(1)'></svg>");
Check(WorkspaceFiles.List(root, "").Entries.Any(entry => entry.Name == "sample.py" && entry.Kind == "code"), "Python classified as code");
Check(WorkspaceFiles.Preview(root, "sample.py").Text.Contains("read-only"), "source preview reads text only");
Check(WorkspaceFiles.Preview(root, "sample.html").Text.Contains("<script>"), "HTML preview remains source text");
Check(WorkspaceFiles.Preview(root, "sample.json").Text.Contains("ready"), "JSON text available to safe viewer");
Check(WorkspaceFiles.Preview(root, "sample.csv").Text.Contains("quoted, name"), "CSV text available to bounded table viewer");
Reject(() => WorkspaceFiles.Preview(root, "private.env"), "environment files are not previewable");
Reject(() => WorkspaceFiles.Preview(root, "sample.sqlite3"), "database files are not treated as text");
Check(WorkspaceFiles.ImagePreview(root, "pixel.png").DataUrl.StartsWith("data:image/png;base64,"), "validated local image preview");
Reject(() => WorkspaceFiles.ImagePreview(root, "bad.png"), "image signature validation");
Reject(() => WorkspaceFiles.ImagePreview(root, "safe.svg"), "SVG cannot become an executable image preview");
Reject(() => WorkspaceFiles.ImagePreview(root, "../pixel.png"), "image path escape rejected");
using (var oversized = new FileStream(Path.Combine(root, "oversized.png"), FileMode.Create)) oversized.SetLength(WorkspaceFiles.MaxImageBytes + 1L);
Reject(() => WorkspaceFiles.ImagePreview(root, "oversized.png"), "image preview size limit");
Check(WorkspaceFiles.FindOutputDirectory(root, workspace.Projects![0].Repositories![0]) == "build/pdf", "configured PDF output directory");
Check(WorkspaceFiles.FindOutputDirectory(root, new WorkspaceRepository()) == "build", "existing build output directory inference");
Reject(() => WorkspaceFiles.FindOutputDirectory(root, new WorkspaceRepository { OutputDirectory = "../escape" }), "output directory escape rejected");
Directory.CreateDirectory(Path.Combine(root, "node_modules"));
File.WriteAllText(Path.Combine(root, "node_modules", "dependency.json"), "{}");
var overview = WorkspaceArtifacts.Scan(root, workspace.Projects![0].Repositories![0]);
Check(overview.Entries.Any(entry => entry.Kind == "pdf") && overview.Entries.Any(entry => entry.Kind == "image") && overview.Entries.Any(entry => entry.Name == "sample.csv"), "artifact overview includes PDFs, images, and reports");
Check(overview.Entries.All(entry => !entry.Path.StartsWith("node_modules/")), "artifact overview excludes dependency folders");
Directory.CreateDirectory(Path.Combine(root, "reports"));
for (var index = 0; index < 510; index++) File.WriteAllText(Path.Combine(root, "reports", $"report-{index:D3}.json"), "{}");
var boundedOverview = WorkspaceArtifacts.Scan(root, new WorkspaceRepository { OutputDirectory = "reports" });
Check(boundedOverview.Truncated && boundedOverview.Entries.Count <= 500, "artifact overview entry limit");
