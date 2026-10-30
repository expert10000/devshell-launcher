using BatchLauncher;
using System.Text.Json;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
var folder = Path.Combine(Path.GetTempPath(), "devshell-manifest-check-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(folder);
try
{
    var path = Path.Combine(folder, "devshell.project.json");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"sample","name":"Sample","root":".","repositories":[{"id":"source","name":"Source","path":"."}],"tasks":{"Build":{"shell":"pwsh","cwd":".","steps":[{"run":"Write-Host ok"}]}},"quickTasks":["Build"]}}
        """);
    var valid = ProjectManifestImporter.Preview(path, Array.Empty<string>());
    Check(valid.Errors.Count == 0 && valid.Project?.Id == "sample", "valid manifest rejected");
    Check(valid.Project!.Root == folder && valid.Project.Repositories![0].Path == folder, "relative paths were not resolved to the chosen folder");
    Check(valid.Project.Tasks!["Build"].Cwd == folder, "task working directory was not resolved");
    Check(ProjectManifestImporter.Preview(path, new[] { "sample" }).Errors.Any(error => error.Contains("already exists")), "duplicate id accepted");
    var profile = Path.Combine(folder, "profile.json");
    File.WriteAllText(profile, """{"version":2,"customSetting":"preserved","projects":[]}""");
    ProjectManifestImporter.ImportIntoProfile(profile, path);
    using (var imported = JsonDocument.Parse(File.ReadAllText(profile)))
    {
        Check(imported.RootElement.GetProperty("customSetting").GetString() == "preserved", "unrelated profile settings changed");
        Check(imported.RootElement.GetProperty("projects")[0].GetProperty("id").GetString() == "sample", "project was not saved");
    }
    var savedProfile = File.ReadAllText(profile);
    try { ProjectManifestImporter.ImportIntoProfile(profile, path); throw new Exception("duplicate import accepted"); }
    catch (InvalidOperationException) { }
    Check(File.ReadAllText(profile) == savedProfile, "failed import changed profile");
    File.WriteAllText(path, """
        {"version":2,"project":{"id":"bad","name":"Bad","root":"..","quickTasks":["Missing"]}}
        """);
    var invalid = ProjectManifestImporter.Preview(path, Array.Empty<string>());
    Check(invalid.Errors.Any(error => error.Contains("version")), "unsupported version accepted");
    Check(invalid.Errors.Any(error => error.Contains("inside")), "escaping path accepted");
    Check(invalid.Errors.Any(error => error.Contains("Missing")), "missing task reference accepted");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"bad-url","name":"Bad URL","root":".","tasks":{"Open":{"type":"browser","url":"https://user:secret@example.com/"}}}}
        """);
    Check(ProjectManifestImporter.Preview(path, Array.Empty<string>()).Errors.Any(error => error.Contains("credentials")), "URL credentials accepted");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"cycle","name":"Cycle","tasks":{"A":{"dependsOn":["B"]},"B":{"dependsOn":["A"]}}}}
        """);
    Check(ProjectManifestImporter.Preview(path, Array.Empty<string>()).Errors.Any(error => error.Contains("cycle")), "task cycle accepted");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"unknown","name":"Unknown","autoExecute":true}}
        """);
    Check(ProjectManifestImporter.Preview(path, Array.Empty<string>()).Errors.Any(error => error.Contains("autoExecute")), "unknown project field accepted");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"bad-file","name":"Bad file","repositories":[{"id":"source","name":"Source","path":".","pdfPath":"../secret.pdf"}]}}
        """);
    Check(ProjectManifestImporter.Preview(path, Array.Empty<string>()).Errors.Any(error => error.Contains("pdfPath")), "escaping artifact path accepted");
    Check(ProjectManifestImporter.Preview(Path.Combine(folder, "missing", "devshell.project.json"), Array.Empty<string>()).Errors.Any(error => error.Contains("not found")), "missing folder manifest not reported");
    Console.WriteLine("Project manifest validation passed.");
}
finally { Directory.Delete(folder, true); }
