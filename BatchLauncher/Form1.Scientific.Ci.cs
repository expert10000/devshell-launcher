using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private static JsonElement[] ScientificCiMatrix()
    {
        var root = Path.Combine(ScientificDataRoot, "ci-imports");
        if (!Directory.Exists(root)) return [];
        var rows = new List<JsonElement>();
        foreach (var path in Directory.EnumerateFiles(root, "*.json").OrderByDescending(File.GetLastWriteTimeUtc).Take(100))
        {
            var id = Path.GetFileNameWithoutExtension(path);
            if (!Regex.IsMatch(id, "^[0-9a-f]{64}$")) continue;
            try
            {
                var bytes = File.ReadAllBytes(path);
                if (bytes.Length > 65536) continue;
                var digest = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
                if (!string.Equals(digest, File.ReadAllText(path + ".sha256").Trim(), StringComparison.Ordinal)) continue;
                using var document = JsonDocument.Parse(bytes);
                var item = document.RootElement;
                if (item.GetProperty("schemaVersion").GetInt32() != 1
                    || item.GetProperty("kind").GetString() != "scientific.ci-import"
                    || item.GetProperty("bundleId").GetString() != id
                    || item.GetProperty("bundleSha256").GetString() != id
                    || item.GetProperty("bundleName").GetString() != id + ".zip"
                    || item.GetProperty("executionLocation").GetString() != "ci"
                    || item.GetProperty("reasons").ValueKind != JsonValueKind.Array
                    || item.GetProperty("agentId").ValueKind != JsonValueKind.String
                    || item.GetProperty("hostFingerprintSha256").ValueKind != JsonValueKind.String
                    || item.GetProperty("runtimeId").ValueKind != JsonValueKind.String
                    || item.GetProperty("capabilityId").ValueKind != JsonValueKind.String
                    || item.GetProperty("jobState").ValueKind != JsonValueKind.String
                    || item.GetProperty("sourceJobId").ValueKind != JsonValueKind.String) continue;
                var bundle = Path.Combine(root, id + ".zip");
                if (!File.Exists(bundle) || new FileInfo(bundle).Length > 34 * 1024 * 1024) continue;
                using var stream = File.OpenRead(bundle);
                if (Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant() != id) continue;
                rows.Add(item.Clone());
            }
            catch (Exception error) when (error is IOException or JsonException or InvalidOperationException
                or UnauthorizedAccessException or KeyNotFoundException) { }
        }
        return rows.ToArray();
    }
}
