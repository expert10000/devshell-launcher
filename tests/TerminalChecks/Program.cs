using BatchLauncher;
using System.Text;

var pwsh = args.Length > 0 ? args[0] : @"C:\Program Files\PowerShell\7\pwsh.exe";
await Check(pwsh, "-NoLogo -NoProfile", "Write-Output ('TERMINAL_' + 'OUTPUT_OK')\r");
await Check(Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe", "/d /q", "set \"marker=TERMINAL_\"\r\necho %marker%OUTPUT_OK\r\n");
Console.WriteLine("PASS: PowerShell and CMD input, ConPTY output, resize, and exit notification.");

static async Task Check(string executable, string arguments, string command)
{
    var profile = new TerminalProfile { Id = "check", Name = "Check", Command = executable, Arguments = arguments };
    using var manager = new TerminalManager(new[] { profile });
    var output = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
    var exited = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
    var captured = new StringBuilder();
    manager.Output += (_, data) =>
    {
        lock (captured)
        {
            captured.Append(data);
            if (captured.ToString().Contains("TERMINAL_OUTPUT_OK")) output.TrySetResult();
        }
    };
    manager.Error += (_, message) => output.TrySetException(new Exception(message));
    manager.Exited += (_, code) => exited.TrySetResult(code);
    var session = manager.StartSession("check", "check", new SessionStartOptions { WorkingDirectory = Path.GetTempPath(), Cols = 100, Rows = 30 });
    await Task.Delay(500);
    session.Resize(120, 40);
    await session.WriteAsync(command);
    await output.Task.WaitAsync(TimeSpan.FromSeconds(20));
    await session.WriteAsync("exit 0\r\n");
    var code = await exited.Task.WaitAsync(TimeSpan.FromSeconds(20));
    if (code != 0) throw new Exception($"{executable} exited with {code}.");
    session.Dispose();
}
