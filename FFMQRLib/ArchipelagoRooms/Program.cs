using System.Security.Cryptography;
using System.Text;
using FFMQLib;
using RomUtilities;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.EventEmitters;
using YamlDotNet.Serialization.NamingConventions;

namespace FFMQRRoomsGenerator;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length < 6)
            {
                Console.Error.WriteLine("Usage: <seed> <map_shuffle> <crest_shuffle> <battlefield_shuffle> <companion_shuffle> <kaeli_mom>");
                return 2;
            }

            string seed = args[0];
            string mapShuffle = args[1];
            bool crestShuffle = ParseBool(args[2]);

            // Accepted for API compatibility; currently not used by the rooms shuffle logic.
            _ = ParseBool(args[3]); // battlefield_shuffle
            _ = ParseBool(args[4]); // companion_shuffle
            _ = ParseBool(args[5]); // kaeli_mom

            var flags = new Flags
            {
                MapShuffling = ParseMapShufflingMode(mapShuffle),
                CrestShuffle = crestShuffle,
            };

            MT19337 rng;
            using (SHA256 hasher = SHA256.Create())
            {
                Blob hash = hasher.ComputeHash(Encoding.UTF8.GetBytes(seed) + flags.EncodedFlagString());
                rng = new MT19337((uint)hash.ToUInts().Sum(x => x));
            }

            var gameLogic = new GameLogic();
            gameLogic.CrestShuffle(flags.CrestShuffle, rng);
            gameLogic.FloorShuffle(flags.MapShuffling, rng);

            var serializer = new SerializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .WithEventEmitter(next => new FlowStyleIntegerSequences(next))
                .Build();

            Console.Write(serializer.Serialize(gameLogic.Rooms));
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            Console.Error.WriteLine(ex.StackTrace);
            return 1;
        }
    }

    private static bool ParseBool(string value)
    {
        if (string.Equals(value, "1", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "true", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "yes", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "on", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (string.Equals(value, "0", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "false", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "no", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "off", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        throw new ArgumentException($"Invalid boolean value: {value}");
    }

    private static MapShufflingMode ParseMapShufflingMode(string value)
    {
        if (ParseBoolish(value, out var enabled))
        {
            return enabled ? MapShufflingMode.Dungeons : MapShufflingMode.None;
        }

        var normalized = value.Replace("_", "", StringComparison.Ordinal)
            .Replace("-", "", StringComparison.Ordinal)
            .Trim()
            .ToLowerInvariant();

        return normalized switch
        {
            "none" => MapShufflingMode.None,
            "overworld" => MapShufflingMode.Overworld,
            "dungeons" => MapShufflingMode.Dungeons,
            "overworlddungeons" => MapShufflingMode.OverworldDungeons,
            "everything" => MapShufflingMode.Everything,
            _ => throw new ArgumentException($"Invalid map_shuffle value: {value}"),
        };
    }

    private static bool ParseBoolish(string value, out bool result)
    {
        try
        {
            result = ParseBool(value);
            return true;
        }
        catch
        {
            result = false;
            return false;
        }
    }
}

internal sealed class FlowStyleIntegerSequences : ChainedEventEmitter
{
    public FlowStyleIntegerSequences(IEventEmitter nextEmitter)
        : base(nextEmitter)
    {
    }

    public override void Emit(SequenceStartEventInfo eventInfo, IEmitter emitter)
    {
        if (typeof(IEnumerable<int>).IsAssignableFrom(eventInfo.Source.Type))
        {
            eventInfo = new SequenceStartEventInfo(eventInfo.Source)
            {
                Style = SequenceStyle.Flow,
            };
        }

        nextEmitter.Emit(eventInfo, emitter);
    }
}
