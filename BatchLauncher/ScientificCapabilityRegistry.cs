using System.Reflection;
using System.Text.Json;

namespace BatchLauncher;

public sealed record ScientificCapabilityProvider(string RuntimeId, string Backend, string Limitations);

public sealed record ScientificCapability(
    string Id, int Version, string ParametersSchemaId, string ResultSchemaId,
    JsonElement ParametersSchema, JsonElement ResultSchema,
    IReadOnlyList<ScientificCapabilityProvider> Providers);

// Both the desktop and standalone broker embed the same versioned catalog that React imports.
// A declaration is discoverable; qualification and certification still require saved run evidence.
public static class ScientificCapabilityRegistry
{
    public const int SchemaVersion = 1;
    private static readonly Lazy<IReadOnlyList<ScientificCapability>> Catalog = new(Load);

    public static IReadOnlyList<ScientificCapability> Capabilities => Catalog.Value;

    public static ScientificCapability Get(string capabilityId) => Capabilities.SingleOrDefault(item => item.Id == capabilityId)
        ?? throw new InvalidOperationException($"Unknown scientific capability: {capabilityId}.");

    public static IReadOnlyList<object> Discover(string runtimeId)
    {
        var provider = ScientificProviderRegistry.Get(runtimeId);
        return Capabilities.SelectMany(capability => capability.Providers
            .Where(mapping => mapping.RuntimeId == runtimeId)
            .Select(mapping => (object)new
            {
                capabilityId = capability.Id, capabilityVersion = capability.Version,
                parametersSchemaId = capability.ParametersSchemaId, resultSchemaId = capability.ResultSchemaId,
                parametersSchema = capability.ParametersSchema, resultSchema = capability.ResultSchema,
                runtimeId, backend = provider.Backend, limitations = mapping.Limitations,
                qualification = "read saved run evidence"
            })).ToArray();
    }

    public static bool IsDeclared(string runtimeId, string capabilityId) =>
        Capabilities.Any(capability => capability.Id == capabilityId
            && capability.Providers.Any(provider => provider.RuntimeId == runtimeId));

    private static IReadOnlyList<ScientificCapability> Load()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("ScientificCapabilities")
            ?? throw new InvalidOperationException("The scientific capability catalog is missing.");
        using var document = JsonDocument.Parse(stream);
        var root = document.RootElement;
        if (root.GetProperty("schemaVersion").GetInt32() != SchemaVersion
            || root.GetProperty("schemaId").GetString() != "devshell.scientific-capabilities")
            throw new InvalidOperationException("Unsupported scientific capability catalog version.");
        var parameters = root.GetProperty("parameterSchemas");
        var results = root.GetProperty("resultSchemas");
        var list = new List<ScientificCapability>();
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in root.GetProperty("capabilities").EnumerateArray())
        {
            var id = entry.GetProperty("id").GetString() ?? "";
            var version = entry.GetProperty("version").GetInt32();
            var input = entry.GetProperty("parametersSchema").GetString() ?? "";
            var output = entry.GetProperty("resultSchema").GetString() ?? "";
            if (!ids.Add(id) || !System.Text.RegularExpressions.Regex.IsMatch(id, "^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
                || version != 1 || !parameters.TryGetProperty(input, out var parameterSchema)
                || !results.TryGetProperty(output, out var resultSchema)
                || parameterSchema.GetProperty("type").GetString() != "object"
                || resultSchema.GetProperty("type").GetString() != "object")
                throw new InvalidOperationException($"Invalid scientific capability declaration: {id}.");
            var mappings = new List<ScientificCapabilityProvider>();
            var providerIds = new HashSet<string>(StringComparer.Ordinal);
            foreach (var mapping in entry.GetProperty("providers").EnumerateArray())
            {
                var runtimeId = mapping.GetProperty("runtimeId").GetString() ?? "";
                var backend = mapping.GetProperty("backend").GetString() ?? "";
                var limitations = mapping.GetProperty("limitations").GetString() ?? "";
                if (!providerIds.Add(runtimeId) || ScientificProviderRegistry.Get(runtimeId).Backend != backend
                    || string.IsNullOrWhiteSpace(limitations))
                    throw new InvalidOperationException($"Invalid provider mapping for {id}: {runtimeId}.");
                mappings.Add(new ScientificCapabilityProvider(runtimeId, backend, limitations));
            }
            if (mappings.Count == 0) throw new InvalidOperationException($"No provider for {id}.");
            list.Add(new ScientificCapability(id, version, input, output,
                parameterSchema.Clone(), resultSchema.Clone(), mappings));
        }
        if (list.Count == 0) throw new InvalidOperationException("The scientific capability catalog is empty.");
        return list;
    }
}
