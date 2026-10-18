using BatchLauncher;
using System.Drawing.Imaging;
using System.Text.Json;
using System.Text.Json.Nodes;

var root = Path.Combine(Path.GetTempPath(), "devshell-presentation-checks-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var checks = 0;
void Check(bool condition, string name) { if (!condition) throw new Exception(name); checks++; Console.WriteLine("PASS: " + name); }
void Reject(Action action, string name)
{
    try { action(); } catch (Exception exception) when (exception is InvalidOperationException or ArgumentException or IOException) { Check(true, name); return; }
    throw new Exception(name);
}
var screen = new Rectangle(0, 0, 1920, 1040);
var minimum = new Size(640, 420);
var normal = new WindowPlacement(100, 150, 1100, 800, false);
Check(WindowPlacementStore.Fit(normal, new[] { screen }, minimum) == normal, "normal size and position preserved");
var maximized = normal with { Maximized = true };
Check(WindowPlacementStore.Fit(maximized, new[] { screen }, minimum) == maximized, "maximized state retains normal restore bounds");
var leftMonitor = new Rectangle(-1920, 0, 1920, 1080);
var onLeft = normal with { X = -1800 };
Check(WindowPlacementStore.Fit(onLeft, new[] { screen, leftMonitor }, minimum) == onLeft, "negative coordinates on connected secondary monitor preserved");
var disconnected = WindowPlacementStore.Fit(onLeft, new[] { screen }, minimum)!;
Check(disconnected.X == 0 && disconnected.Width == normal.Width, "disconnected monitor position moved into visible work area");
var large = WindowPlacementStore.Fit(normal with { Width = 8000, Height = 4000 }, new[] { screen }, minimum)!;
Check(large.Width == screen.Width && large.Height == screen.Height && large.X == 0 && large.Y == 0, "oversized bounds clamped to monitor");
var small = WindowPlacementStore.Fit(normal with { Width = 20, Height = 20 }, new[] { screen }, minimum)!;
Check(small.Width == minimum.Width && small.Height == minimum.Height, "minimum normal size restored");
Check(WindowPlacementStore.Fit(normal with { Width = 0 }, new[] { screen }, minimum) == null, "invalid stored dimensions ignored");
var taskbar = new Rectangle(0, 40, 1200, 760);
var clamped = WindowPlacementStore.Fit(normal with { X = 9999, Y = -9999 }, new[] { taskbar }, minimum)!;
Check(new Rectangle(clamped.X, clamped.Y, clamped.Width, clamped.Height).Top >= taskbar.Top, "title bar remains inside work area");
var store = Path.Combine(root, "settings", "window.json");
WindowPlacementStore.Save(store, maximized);
Check(WindowPlacementStore.Load(store) == maximized, "placement JSON survives save and reload");
File.WriteAllText(store, "broken JSON");
Check(WindowPlacementStore.Load(store) == null, "corrupt placement falls back to default");
var path = Path.Combine(root, "render with spaces.png");
using (var bitmap = new Bitmap(640, 480))
{
    using var graphics = Graphics.FromImage(bitmap);
    graphics.Clear(Color.Teal);
    bitmap.Save(path, ImageFormat.Png);
}
JsonElement Result() => JsonSerializer.SerializeToElement(new JsonObject { ["state"] = "succeeded", ["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(root, "render with spaces.png")) });
var result = Result();
var dataUrl = ScientificArtifactThumbnails.Create(root, result, "render with spaces.png");
using (var stream = new MemoryStream(Convert.FromBase64String(dataUrl.Split(',')[1])))
using (var image = Image.FromStream(stream)) Check(image.Width == 160 && image.Height == 120, "PNG thumbnail bounded to 160 by 120 with correct aspect ratio");
Check(new FileInfo(path).Length == result.GetProperty("artifacts")[0].GetProperty("bytes").GetInt64(), "thumbnail leaves source artifact unchanged");
Reject(() => ScientificArtifactThumbnails.Create(root, result, "not-registered.png"), "unregistered thumbnail rejected");
File.AppendAllText(path, "changed");
Reject(() => ScientificArtifactThumbnails.Create(root, result, "render with spaces.png"), "modified thumbnail source rejected");
File.WriteAllText(path, "not a PNG");
Reject(() => ScientificArtifactThumbnails.Create(root, Result(), "render with spaces.png"), "invalid PNG rejected");
using (var file = File.Create(path)) file.SetLength(WorkspaceFiles.MaxImageBytes + 1L);
Reject(() => ScientificArtifactThumbnails.Create(root, Result(), "render with spaces.png"), "oversized thumbnail source rejected");
var header = new byte[24];
new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }.CopyTo(header, 0);
"IHDR"u8.CopyTo(header.AsSpan(12));
System.Buffers.Binary.BinaryPrimitives.WriteUInt32BigEndian(header.AsSpan(16, 4), 100000);
System.Buffers.Binary.BinaryPrimitives.WriteUInt32BigEndian(header.AsSpan(20, 4), 100000);
File.WriteAllBytes(path, header);
Reject(() => ScientificArtifactThumbnails.Create(root, Result(), "render with spaces.png"), "excessive PNG dimensions rejected before decode");
Console.WriteLine($"{checks} checks passed. Fixtures retained at {root}");
