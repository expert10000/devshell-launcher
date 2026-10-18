using System.Drawing;
using System.Text.Json;

namespace BatchLauncher;

internal sealed record WindowPlacement(int X, int Y, int Width, int Height, bool Maximized);

internal static class WindowPlacementStore
{
    internal static WindowPlacement? Load(string path)
    {
        try { return File.Exists(path) ? JsonSerializer.Deserialize<WindowPlacement>(File.ReadAllText(path)) : null; }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException) { return null; }
    }

    internal static void Save(string path, WindowPlacement placement)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            var temporary = path + ".tmp";
            File.WriteAllText(temporary, JsonSerializer.Serialize(placement));
            File.Move(temporary, path, true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        { System.Diagnostics.Debug.WriteLine($"Window placement could not be saved: {exception.Message}"); }
    }

    internal static WindowPlacement? Fit(WindowPlacement? saved, IReadOnlyList<Rectangle> workingAreas, Size minimum)
    {
        if (saved == null || saved.Width <= 0 || saved.Height <= 0 || workingAreas.Count == 0) return null;
        var bounds = new Rectangle(saved.X, saved.Y, saved.Width, saved.Height);
        var area = workingAreas.OrderByDescending(candidate =>
        {
            var intersection = Rectangle.Intersect(candidate, bounds);
            return (long)Math.Max(0, intersection.Width) * Math.Max(0, intersection.Height);
        }).First();
        var width = Math.Clamp(saved.Width, Math.Min(minimum.Width, area.Width), area.Width);
        var height = Math.Clamp(saved.Height, Math.Min(minimum.Height, area.Height), area.Height);
        return saved with { X = Math.Clamp(saved.X, area.Left, area.Right - width), Y = Math.Clamp(saved.Y, area.Top, area.Bottom - height), Width = width, Height = height };
    }
}
