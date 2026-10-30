using BatchLauncher;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Diagnostics;

static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
if (args.Length == 2 && args[0] == "--serve")
{
    var listener = new TcpListener(IPAddress.Loopback, int.Parse(args[1]));
    listener.Start();
    Console.WriteLine("WORKER_HTTP_READY");
    while (true)
    {
        using var client = await listener.AcceptTcpClientAsync();
        using var stream = client.GetStream();
        var request = new byte[2048];
        await stream.ReadAsync(request);
        var response = Encoding.ASCII.GetBytes("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}");
        await stream.WriteAsync(response);
    }
}
if (args.Length == 2 && args[0] == "--relay")
{
    using var child = Process.Start(new ProcessStartInfo(Environment.ProcessPath!) { UseShellExecute = false,
        ArgumentList = { "--serve", args[1] } }) ?? throw new Exception("Could not start relay child.");
    await child.WaitForExitAsync();
    return;
}
var shell = Path.GetFullPath(args[0]);
var root = Path.Combine(Path.GetTempPath(), "devshell-worker-check-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var service = new WorkspaceService
{
    Kind = "process", Name = "Disposable worker", Command = shell, Cwd = root,
    Arguments = new() { "-NoProfile", "-Command", "Write-Output ('WORKER ' + $env:DEVSHELL_WORKER_TEST); Start-Sleep -Seconds 60" },
    Environment = new() { ["DEVSHELL_WORKER_TEST"] = "ready ' ż" }
};
var command = ProcessServiceCommand.Create(service, shell, root, value => value);
Check(command.Cwd == root && command.Script.Contains("DEVSHELL_WORKER_TEST"), "Worker command was not built from its declaration");
using var runner = new RepositoryRunner();
async Task Running()
{
    for (var i = 0; i < 150; i++)
    {
        var status = runner.Snapshot().Single();
        if (status.State == "failed") throw new Exception(status.Log);
        if (status.State == "running" && status.Log.Contains("WORKER ready ' ż")) return;
        await Task.Delay(100);
    }
    throw new Exception("Disposable worker did not report running status and output.");
}
Check(runner.Start("profile:worker:service", null, command, root, "service"), "Worker did not start");
await Running();
Check(ProcessServiceCommand.State(runner.Snapshot().Single()) == "running", "Worker status was not running");
Check(!runner.Start("profile:worker:service", null, command, root, "service"), "Duplicate worker start was accepted");
runner.Stop("profile:worker:service");
var stopped = await runner.Completion("profile:worker:service").WaitAsync(TimeSpan.FromSeconds(20));
Check(stopped.State == "stopped" && ProcessServiceCommand.State(stopped) == "stopped", "Worker did not stop its owned process tree");
Check(runner.Start("profile:worker:service", null, command, root, "service"), "Worker did not restart after Stop");
await Running();
runner.Stop("profile:worker:service");
Check((await runner.Completion("profile:worker:service").WaitAsync(TimeSpan.FromSeconds(20))).State == "stopped", "Restarted worker did not stop");
using var reserved = new TcpListener(IPAddress.Loopback, 0);
reserved.Start();
var port = ((IPEndPoint)reserved.LocalEndpoint).Port;
reserved.Stop();
var http = new WorkspaceService { Kind = "process", Name = "HTTP worker", Command = Environment.ProcessPath!, Cwd = root,
    Arguments = new() { "--relay", port.ToString() }, ReadyUrl = $"http://127.0.0.1:{port}/", ReadyTimeoutSeconds = 15 };
var httpCommand = ProcessServiceCommand.Create(http, shell, root, value => value);
var opened = false;
runner.BrowserReady += (_, _) => opened = true;
Check(runner.Start("profile:http:service", null, httpCommand, root, "service",
    new RepositoryBrowserLaunch(http.ReadyUrl!, new[] { http.ReadyUrl! }, 15, AutoOpen: false)), "HTTP worker did not start");
for (var i = 0; i < 150 && runner.Snapshot().Single(item => item.Key == "profile:http:service").BrowserState != "ready"; i++) await Task.Delay(100);
var ready = runner.Snapshot().Single(item => item.Key == "profile:http:service");
Check(ready.State == "running" && ready.BrowserState == "ready" && !opened, "HTTP worker readiness failed or opened a browser unexpectedly: " + ready.Log);
runner.Stop("profile:http:service");
Check((await runner.Completion("profile:http:service").WaitAsync(TimeSpan.FromSeconds(20))).State == "stopped", "HTTP worker did not stop");
using (var probe = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp) { ExclusiveAddressUse = true })
    probe.Bind(new IPEndPoint(IPAddress.Loopback, port));
Console.WriteLine("PASS: declared worker command, environment, status, logs, duplicate-start guard, Stop, Restart, HTTP readiness without auto-open");
