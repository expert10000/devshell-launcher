using BatchLauncher;
using System.Text.Json;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
if (args.Length > 0 && args[0] == "--validate")
{
    foreach (var manifest in args.Skip(1))
    {
        var preview = ProjectManifestImporter.Preview(manifest, Array.Empty<string>());
        foreach (var warning in preview.Warnings) Console.WriteLine("WARN " + warning);
        foreach (var error in preview.Errors) Console.Error.WriteLine("ERROR " + error);
        Check(preview.Project != null && preview.Errors.Count == 0, "Manifest validation failed: " + manifest);
        var tempProfile = Path.Combine(Path.GetTempPath(), "devshell-real-manifest-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            File.WriteAllText(tempProfile, """{"version":2,"projects":[]}""");
            var imported = ProjectManifestImporter.ImportIntoProfile(tempProfile, preview.ManifestPath);
            Check(imported.Id == preview.Project!.Id && imported.ManifestSource == preview.ManifestPath, "Real manifest import failed");
            if (imported.Service?.Kind == "jupyter")
            {
                var environment = Path.Combine(imported.Root!, ".venv");
                Check(imported.PythonEnvironment == environment && imported.Service.Python == Path.Combine(environment, "Scripts", "python.exe"),
                    "Imported Jupyter environment and service paths disagree");
                var setupRepository = new WorkspaceRepository { Path = imported.Root!, PythonEnvironment = imported.PythonEnvironment,
                    PythonModules = imported.PythonModules, PythonPackages = imported.PythonPackages, RequiredTools = imported.RequiredTools };
                var plan = EnvironmentSetup.Plan(setupRepository, imported.Root!, new Dictionary<string, string>(), targets: new[] { "python" });
                Check(plan.Issues.Count == 0 && plan.Steps.Any(step => step.Kind == "python-create" && step.Environment == environment)
                    && plan.Steps.Any(step => step.Kind == "python-install" && step.Arguments?.Contains("-r") == true),
                    "Jupyter setup did not plan environment creation and requirements installation");
            }
        }
        finally { File.Delete(tempProfile); }
        Console.WriteLine("PASS " + preview.Project!.Name + " — " + preview.ManifestPath);
    }
    return;
}
var folder = Path.Combine(Path.GetTempPath(), "devshell-manifest-check-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(folder);
try
{
    var path = Path.Combine(folder, "devshell.project.json");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"sample","name":"Sample","root":".","repositories":[{"id":"source","name":"Source","path":"."}],"service":{"name":"Lab","kind":"jupyter","cwd":"."},"tasks":{"Build":{"shell":"pwsh","cwd":".","steps":[{"run":"Write-Host ok"}]}},"quickTasks":["Build"]}}
        """);
    var valid = ProjectManifestImporter.Preview(path, Array.Empty<string>());
    Check(valid.Errors.Count == 0 && valid.Project?.Id == "sample", "valid manifest rejected");
    Check(valid.Project!.Root == folder && valid.Project.Repositories![0].Path == folder, "relative paths were not resolved to the chosen folder");
    Check(valid.Project.Tasks!["Build"].Cwd == folder, "task working directory was not resolved");
    Check(ProjectManifestImporter.Preview(path, new[] { "sample" }).Errors.Any(error => error.Contains("already exists")), "duplicate id accepted");
    var profile = Path.Combine(folder, "profile.json");
    File.WriteAllText(profile, """{"version":2,"customSetting":"preserved","projects":[]}""");
    ProjectManifestImporter.ImportIntoProfile(profile, path);
    var importedProject = JsonDocument.Parse(File.ReadAllText(profile)).RootElement.GetProperty("projects")[0];
    var defaultPython = Path.Combine(folder, ".venv");
    Check(importedProject.GetProperty("pythonEnvironment").GetString() == defaultPython, "Jupyter import did not select a local environment");
    Check(importedProject.GetProperty("service").GetProperty("python").GetString() == Path.Combine(defaultPython, "Scripts", "python.exe"), "Jupyter service did not use the local environment");
    using (var imported = JsonDocument.Parse(File.ReadAllText(profile)))
    {
        Check(imported.RootElement.GetProperty("customSetting").GetString() == "preserved", "unrelated profile settings changed");
        Check(imported.RootElement.GetProperty("projects")[0].GetProperty("id").GetString() == "sample", "project was not saved");
        Check(imported.RootElement.GetProperty("projects")[0].GetProperty("manifestSource").GetString() == path, "manifest source was not saved locally");
    }
    var savedProfile = File.ReadAllText(profile);
    try { ProjectManifestImporter.ImportIntoProfile(profile, path); throw new Exception("duplicate import accepted"); }
    catch (InvalidOperationException) { }
    Check(File.ReadAllText(profile) == savedProfile, "failed import changed profile");
    var localRoot = Path.Combine(folder, "machine-root");
    var localPython = Path.Combine(folder, ".venv");
    var repoPython = Path.Combine(folder, ".venv-repo");
    var jupyterPython = Path.Combine(localPython, "Scripts", "python.exe");
    var overrides = new WorkspaceManifestOverrides { Root = localRoot, PythonEnvironment = localPython,
        ServicePython = jupyterPython, RepositoryPythonEnvironments = new() { ["source"] = repoPython } };
    var configured = ProjectManifestImporter.SaveOverrides(profile, "sample", overrides);
    Check(configured.Root == localRoot && configured.Repositories![0].Path == localRoot, "local root did not rebase repository");
    Check(configured.Tasks!["Build"].Cwd == localRoot && configured.Service!.Cwd == localRoot, "local root did not rebase task/service");
    Check(configured.PythonEnvironment == localPython && configured.Service!.Python == jupyterPython && configured.Repositories![0].PythonEnvironment == repoPython, "Python overrides were not applied");
    File.WriteAllText(path, """
        {"version":1,"project":{"id":"sample","name":"Sample updated","root":".","repositories":[{"id":"source","name":"Source","path":"."}],"service":{"name":"Lab","kind":"jupyter","cwd":"."},"tasks":{"Build":{"shell":"pwsh","cwd":".","steps":[{"run":"Write-Host ok"}]},"Test":{"shell":"pwsh","cwd":".","steps":[{"run":"Write-Host test"}]}},"quickTasks":["Build","Test"]}}
        """);
    var refresh = ProjectManifestImporter.PreviewRefresh(profile, "sample");
    Check(refresh.Errors.Count == 0 && refresh.Changes!.Contains("Task 'Test' added") && refresh.Changes.Any(change => change.StartsWith("Name:")), "refresh preview did not identify source changes");
    try { ProjectManifestImporter.SaveOverrides(profile, "sample", overrides); throw new Exception("source change was silently applied"); }
    catch (InvalidOperationException error) { Check(error.Message.Contains("Preview"), "source change was not explained"); }
    var updated = ProjectManifestImporter.RefreshInProfile(profile, "sample");
    Check(updated.Name == "Sample updated" && updated.Tasks!.ContainsKey("Test"), "shared changes were not refreshed");
    Check(updated.Root == localRoot && updated.PythonEnvironment == localPython && updated.Service!.Python == jupyterPython && updated.Repositories![0].PythonEnvironment == repoPython, "refresh lost local overrides");
    var beforeInvalidSettings = File.ReadAllText(profile);
    try { ProjectManifestImporter.SaveOverrides(profile, "sample", new WorkspaceManifestOverrides { Root = "relative-root" }); throw new Exception("relative local override accepted"); }
    catch (InvalidOperationException error) { Check(error.Message.Contains("absolute"), "invalid override was not explained"); }
    Check(File.ReadAllText(profile) == beforeInvalidSettings, "invalid local settings changed profile");
    var reset = ProjectManifestImporter.SaveOverrides(profile, "sample", new WorkspaceManifestOverrides());
    Check(reset.Root == folder && reset.Repositories![0].Path == folder && reset.PythonEnvironment == null && reset.Service!.Python == "", "clearing overrides did not restore source defaults");
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
