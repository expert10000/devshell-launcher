using System.Buffers.Binary;
using System.Drawing.Imaging;
using System.Text.Json;

namespace BatchLauncher;

internal static class ScientificArtifactThumbnails
{
    internal static string Create(string directory, JsonElement result, string relative)
    {
        var path = ScientificArtifactFiles.ResolveRegistered(directory, result, relative);
        if (!Path.GetExtension(path).Equals(".png", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Thumbnails require a registered PNG artifact.");
        using var stream = File.OpenRead(path);
        if (stream.Length > WorkspaceFiles.MaxImageBytes) throw new InvalidOperationException("Image exceeds the 8 MiB preview limit.");
        Span<byte> header = stackalloc byte[24];
        stream.ReadExactly(header);
        if (!header[..8].SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }) || !header.Slice(12, 4).SequenceEqual("IHDR"u8))
            throw new InvalidOperationException("Invalid PNG image header.");
        var width = BinaryPrimitives.ReadUInt32BigEndian(header[16..20]);
        var height = BinaryPrimitives.ReadUInt32BigEndian(header[20..24]);
        if (width == 0 || height == 0 || (ulong)width * height > 16777216)
            throw new InvalidOperationException("PNG dimensions exceed the thumbnail limit.");
        stream.Position = 0;
        using var image = Image.FromStream(stream, useEmbeddedColorManagement: false, validateImageData: true);
        var ratio = Math.Min(1d, Math.Min(160d / image.Width, 120d / image.Height));
        using var thumbnail = new Bitmap(Math.Max(1, (int)(image.Width * ratio)), Math.Max(1, (int)(image.Height * ratio)));
        using (var graphics = Graphics.FromImage(thumbnail))
        {
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            graphics.DrawImage(image, 0, 0, thumbnail.Width, thumbnail.Height);
        }
        using var output = new MemoryStream();
        thumbnail.Save(output, ImageFormat.Png);
        return "data:image/png;base64," + Convert.ToBase64String(output.ToArray());
    }
}
