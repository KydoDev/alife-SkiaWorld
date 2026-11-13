// EditMode tests of ABI 6 (ADR-0018): the kernel's species tracker, called through P/Invoke, gives what
// engine-rs/tests/golden/species.json (scripts/g3_species_vectors.py, made by Python's SpeciesTracker) records, and a
// world without a tracker has no species.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class SpeciesTests
    {
        private static string Golden(string name) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "engine-rs", "tests", "golden", name));

        private static readonly Lazy<string> Vectors =
            new Lazy<string>(() => File.ReadAllText(Golden("species.json")));

        /// <summary>The tracker dump of one case: from its "tracker" key to the next case.</summary>
        private static string TrackerOf(string caseName)
        {
            string text = Vectors.Value;
            int start = text.IndexOf($"\"name\":\"{caseName}\"", StringComparison.Ordinal);
            Assert.GreaterOrEqual(start, 0, caseName);
            int end = text.IndexOf("\"name\":\"", start + 8, StringComparison.Ordinal);
            string body = end < 0 ? text.Substring(start) : text.Substring(start, end - start);
            return body.Substring(body.IndexOf("\"tracker\":{", StringComparison.Ordinal));
        }

        private static ulong Counter(string tracker, string key) =>
            ulong.Parse(Regex.Match(tracker, $"\"{key}\":(\\d+)").Groups[1].Value);

        private static ulong Step(string v) => v == "null" ? SpeciesRecord.StepNone : ulong.Parse(v);

        /// <summary>Every species row of a dump, as the ABI lays it out.</summary>
        private static Dictionary<ulong, SpeciesRecord> Rows(string tracker)
        {
            var rows = new Dictionary<ulong, SpeciesRecord>();
            const string row = "\\[(\\d+),(null|\\d+),\"(\\w+)\",\\[[^\\]]*\\],(\\d+),(null|\\d+),(\\d+),(\\d+),(\\d+)," +
                               "(null|\\d+),(\\d+)\\]";
            foreach (Match m in Regex.Matches(tracker, row))
            {
                var s = new SpeciesRecord
                {
                    Id = ulong.Parse(m.Groups[1].Value),
                    Parent = m.Groups[2].Value == "null" ? 0 : ulong.Parse(m.Groups[2].Value),
                    Origin = (SpeciesOrigin)Enum.Parse(typeof(SpeciesOrigin), m.Groups[3].Value, true),
                    Born = ulong.Parse(m.Groups[4].Value),
                    Extinct = Step(m.Groups[5].Value),
                    Count = ulong.Parse(m.Groups[6].Value),
                    Peak = ulong.Parse(m.Groups[7].Value),
                    Activity = ulong.Parse(m.Groups[8].Value),
                    Established = Step(m.Groups[9].Value),
                    Children = ulong.Parse(m.Groups[10].Value),
                };
                rows.Add(s.Id, s);
            }
            return rows;
        }

        private static void StepBy(NativeWorld world, uint steps)
        {
            for (uint done = 0; done < steps; done += 50)
            {
                world.Step(Math.Min(50, steps - done));
            }
        }

        private static void AssertEqualsDump(NativeWorld world, string caseName)
        {
            string tracker = TrackerOf(caseName);
            Dictionary<ulong, SpeciesRecord> rows = Rows(tracker);
            SpeciesInfo info = world.Species;
            Assert.IsTrue(info.IsTracked, caseName);
            Assert.AreEqual(Counter(tracker, "next_id"), info.NextId, $"{caseName}: next_id");
            Assert.AreEqual(Counter(tracker, "speciations"), info.Speciations, $"{caseName}: speciations");
            Assert.AreEqual(Counter(tracker, "novelty"), info.Novelty, $"{caseName}: novelty");
            Assert.AreEqual(Counter(tracker, "pruned"), info.Pruned, $"{caseName}: pruned");
            Assert.AreEqual((ulong)rows.Count, info.Retained, $"{caseName}: retained");
            SpeciesRecord[] living = world.LivingSpecies();
            CollectionAssert.AreEqual(rows.Values.Where(s => s.IsExtant).OrderBy(s => s.Id).ToArray(), living,
                                      $"{caseName}: living species");
            foreach (SpeciesRecord row in rows.Values)
            {
                Assert.IsTrue(world.TryGetSpecies(row.Id, out SpeciesRecord got), $"{caseName}: species {row.Id}");
                Assert.AreEqual(row, got, $"{caseName}: species {row.Id}");
            }
            Assert.AreEqual(world.Info.Population, living.Aggregate(0UL, (n, s) => n + s.Count), "members = cells");
        }

        [Test]
        public void ACreatedWorldTracksAsPython()
        {
            // created_default: Config() and seed 1, as the create_default golden set
            byte[] config = File.ReadAllBytes(Path.Combine(Golden("create_default"), "config.json"));
            using NativeWorld world = NativeWorld.Create(config, 1);
            StepBy(world, 1000);
            AssertEqualsDump(world, "created_default");
        }

        [Test]
        public void ATrackedSaveLoadsItsTracker()
        {
            using NativeWorld world = NativeWorld.Load(File.ReadAllBytes(Golden("species_start.json.gz")));
            Assert.AreEqual(300UL, world.Info.StepCount);
            StepBy(world, 700);
            AssertEqualsDump(world, "tracked_save");
        }

        [Test]
        public void CellsTilesAndAncestryAgreeWithTheList()
        {
            byte[] config = File.ReadAllBytes(Path.Combine(Golden("create_default"), "config.json"));
            using NativeWorld world = NativeWorld.Create(config, 1);
            StepBy(world, 300);
            WorldInfo info = world.Info;
            var tiles = new byte[world.TilesLength];
            world.Tiles(tiles);
            var members = new Dictionary<ulong, ulong>();
            for (uint y = 0; y < info.Height; y++)
            {
                for (uint x = 0; x < info.Width; x++)
                {
                    CellRecord c = world.Cell(x, y);
                    if (c.Present == 0)
                    {
                        continue;
                    }
                    Assert.AreEqual((int)(c.Species % 65536), Tile.At(tiles, (int)(y * info.Width + x)).Key,
                                    "a tracked world keys tiles by species");
                    members[c.Species] = members.TryGetValue(c.Species, out ulong n) ? n + 1 : 1;
                }
            }
            SpeciesRecord[] living = world.LivingSpecies();
            CollectionAssert.AreEquivalent(members.Keys, living.Select(s => s.Id));
            foreach (SpeciesRecord s in living)
            {
                Assert.AreEqual(members[s.Id], s.Count, $"species {s.Id}");
                ulong child = s.Id;
                foreach (SpeciesRecord a in world.Ancestors(s.Id))
                {
                    Assert.Less(a.Id, child, "ancestors are older");
                    child = a.Id;
                }
            }
            Assert.IsTrue(living.Any(s => world.Ancestors(s.Id).Count > 0), "some species descend from another");
        }

        [Test]
        public void AnUntrackedSaveHasNoSpeciesAndStaysUsable()
        {
            using NativeWorld world = NativeWorld.Load(File.ReadAllBytes(Path.Combine(Golden("default"),
                                                                                      "start.json.gz")));
            Assert.IsFalse(world.Species.IsTracked);
            CollectionAssert.IsEmpty(world.LivingSpecies());
            Assert.IsFalse(world.TryGetSpecies(1, out _));
            CollectionAssert.IsEmpty(world.Ancestors(1));
            world.Step(2);
            Assert.AreEqual(0UL, world.Cell(0, 0).Species);
        }

        [Test]
        public void UnknownSpeciesAreRefusedWithoutBreakingTheWorld()
        {
            byte[] config = File.ReadAllBytes(Path.Combine(Golden("create_default"), "config.json"));
            using NativeWorld world = NativeWorld.Create(config, 1);
            world.Step(10);
            SpeciesInfo info = world.Species;
            Assert.IsFalse(world.TryGetSpecies(0, out _));
            Assert.IsFalse(world.TryGetSpecies(info.NextId + 1, out _));
            Assert.IsFalse(world.TryGetSpecies(ulong.MaxValue, out _));
            world.Step(1);
        }
    }
}
