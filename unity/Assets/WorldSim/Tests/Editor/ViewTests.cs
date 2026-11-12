// EditMode tests of the ABI 4 views (ADR-0016, G3 P4): through P/Invoke the tile snapshot, the cell records and the
// light factor equal engine-rs/tests/golden/views.json (scripts/g3_view_vectors.py, Python's worldsim/views.py), and
// the views leave the state hash unchanged.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class ViewTests
    {
        private static string Golden(string name) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "engine-rs", "tests", "golden", name));

        // views.json, the fields this test reads
        [Serializable]
        private class VCell
        {
            public uint x, y, bonds, colony, rules;
            public ulong id, lineage, age;
            public string energy;
            public string[] genes, shares, traits;
        }

        [Serializable]
        private class VSnapshot
        {
            public ulong step;
            public string tiles_sha256, light_factor, state_hash;
            public VCell[] cells;
        }

        [Serializable]
        private class VCase
        {
            public string set;
            public VSnapshot[] snapshots;
        }

        [Serializable]
        private class VFile
        {
            public uint steps;
            public VCase[] cases;
        }

        private static VFile Vectors() => JsonUtility.FromJson<VFile>(File.ReadAllText(Golden("views.json")));

        /// <summary>A float written by Python as its IEEE-754 bytes (little-endian hex).</summary>
        private static long Bits(string hex)
        {
            var bytes = new byte[8];
            for (int i = 0; i < 8; i++)
            {
                bytes[i] = Convert.ToByte(hex.Substring(2 * i, 2), 16);
            }
            return BitConverter.ToInt64(bytes, 0);
        }

        private static void AssertBits(string[] expected, double[] actual, string what)
        {
            Assert.AreEqual(expected.Length, actual.Length, what);
            for (int i = 0; i < expected.Length; i++)
            {
                Assert.AreEqual(Bits(expected[i]), BitConverter.DoubleToInt64Bits(actual[i]), $"{what}[{i}]");
            }
        }

        private static void Check(NativeWorld world, string set, VSnapshot snap)
        {
            string at = $"{set} at step {snap.step}";
            WorldInfo info = world.Info;
            Assert.AreEqual(snap.step, info.StepCount, at);
            string before = world.StateHash();
            Assert.AreEqual(snap.state_hash, before, $"{at}: state hash");
            Assert.AreEqual(Bits(snap.light_factor), BitConverter.DoubleToInt64Bits(info.LightFactor), $"{at}: light");
            var tiles = new byte[world.TilesLength];
            world.Tiles(tiles);
            using (var sha = SHA256.Create())
            {
                string digest = BitConverter.ToString(sha.ComputeHash(tiles)).Replace("-", "").ToLowerInvariant();
                Assert.AreEqual(snap.tiles_sha256, digest, $"{at}: tiles");
            }
            foreach (VCell c in snap.cells)
            {
                string what = $"{at}: cell at ({c.x}, {c.y})";
                CellRecord r = world.Cell(c.x, c.y);
                Assert.AreEqual(1u, r.Present, what);
                Assert.AreEqual((c.id, c.lineage, c.age), (r.Id, r.Lineage, r.Age), what);
                Assert.AreEqual((c.bonds, c.colony, c.rules), (r.Bonds, r.Colony, r.Rules), what);
                Assert.AreEqual(Bits(c.energy), BitConverter.DoubleToInt64Bits(r.Energy), $"{what}: energy");
                AssertBits(c.genes, r.Genes, $"{what}: genes");
                AssertBits(c.shares, r.Shares, $"{what}: shares");
                AssertBits(c.traits, r.Traits, $"{what}: traits");
                // the tile word agrees with the record
                Tile t = Tile.At(tiles, (int)(c.y * info.Width + c.x));
                Assert.AreEqual(c.bonds > 0, t.Bonded, $"{what}: bonded bit");
                Assert.AreEqual((int)(c.lineage % 65536), t.Key, $"{what}: key");
                Assert.AreNotEqual(TileKind.Empty, t.Kind, what);
            }
            Assert.AreEqual(before, world.StateHash(), $"{at}: the views changed the state");
        }

        [Test]
        public void TheStructsHaveTheKernelsLayout()
        {
            Assert.AreEqual(56, Marshal.SizeOf<WorldInfo>());
            Assert.AreEqual(248, Marshal.SizeOf<CellRecord>());
        }

        [Test]
        public void ATileUnpacksEveryFieldWithoutSignExtension()
        {
            // byte 0: chemo (4) | bonded | rock | chem 3; byte 1: energy 15; key 0xFF01 (top bit set)
            var bytes = new byte[] { 0, 0, 0, 0, 4 | 0x8 | 0x10 | 0x60, 0x0F, 0x01, 0xFF };
            Tile t = Tile.At(bytes, 1);
            Assert.AreEqual(TileKind.Chemo, t.Kind);
            Assert.IsTrue(t.Bonded);
            Assert.IsTrue(t.Rock);
            Assert.AreEqual(3, t.Chem);
            Assert.AreEqual(15, t.Energy);
            Assert.AreEqual(0xFF01, t.Key);
            Tile empty = Tile.At(bytes, 0);
            Assert.AreEqual((TileKind.Empty, false, false, 0, 0, 0),
                            (empty.Kind, empty.Bonded, empty.Rock, empty.Chem, empty.Energy, empty.Key));
        }

        [Test]
        public void ViewsEqualPythonAndChangeNothing()
        {
            VFile file = Vectors();
            Assert.AreEqual(4, file.cases.Length);
            foreach (VCase c in file.cases)
            {
                using NativeWorld world = NativeWorld.Load(File.ReadAllBytes(Path.Combine(Golden(c.set),
                                                                                          "start.json.gz")));
                Check(world, c.set, c.snapshots[0]);
                world.Step(file.steps);
                Check(world, c.set, c.snapshots[1]);
            }
        }

        [Test]
        public void AnEmptyTileIsAbsentAndOutsideIsRefused()
        {
            using NativeWorld world = NativeWorld.Load(File.ReadAllBytes(Path.Combine(Golden("default"),
                                                                                      "start.json.gz")));
            WorldInfo info = world.Info;
            var tiles = new byte[world.TilesLength];
            world.Tiles(tiles);
            int empty = 0;
            while (Tile.At(tiles, empty).Kind != TileKind.Empty)
            {
                empty++;
            }
            CellRecord r = world.Cell((uint)(empty % info.Width), (uint)(empty / info.Width));
            Assert.AreEqual(0u, r.Present);
            Assert.AreEqual(0ul, r.Id);
            var e = Assert.Throws<WorldSimException>(() => world.Cell(info.Width, 0));
            Assert.AreEqual(WorldSimException.StatusInvalid, e.Status);
            world.Step(1);    // still usable
            Assert.Throws<WorldSimException>(() => world.Tiles(new byte[3]));
        }
    }
}
