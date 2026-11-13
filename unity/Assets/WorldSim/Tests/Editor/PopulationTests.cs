// EditMode tests of the P6b population data: on every golden world the counts per kind add up to the kernel's
// population and agree with each cell's record, and the history stays bounded while spanning the whole run.
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class PopulationTests
    {
        [TestCase("default")]
        [TestCase("volcanic")]
        [TestCase("plasticity")]
        [TestCase("combined")]
        public void CountsAddUpAndAgreeWithTheRecords(string set)
        {
            using NativeWorld world = NativeWorld.Load(File.ReadAllBytes(Path.GetFullPath(Path.Combine(
                Application.dataPath, "..", "..", "engine-rs", "tests", "golden", set, "start.json.gz"))));
            world.Step(10);
            WorldInfo info = world.Info;
            var tiles = new byte[world.TilesLength];
            world.Tiles(tiles);
            int[] counts = Population.Count(tiles);
            Assert.AreEqual(0, counts[0]);
            Assert.AreEqual((int)info.Population, counts[1] + counts[2] + counts[3] + counts[4], set);
            var byRecord = new int[5];
            for (uint y = 0; y < info.Height; y++)
            {
                for (uint x = 0; x < info.Width; x++)
                {
                    CellRecord r = world.Cell(x, y);
                    if (r.Present == 1)
                    {
                        byRecord[(int)CellSheet.KindOf(r)]++;
                    }
                }
            }
            CollectionAssert.AreEqual(byRecord, counts, $"{set}: tile kinds vs record shares");
        }

        [Test]
        public void HistoryIsBoundedAndSpansTheRun()
        {
            var h = new PopulationHistory(capacity: 8);
            for (ulong step = 0; step <= 1000; step++)
            {
                h.Add(step, new[] { 0, (int)step, 1, 2, 3 });
            }
            Assert.LessOrEqual(h.Samples.Count, 8);
            Assert.GreaterOrEqual(h.Samples.Count, 4, "thinning keeps about half");
            Assert.AreEqual(0ul, h.Samples[0].Step, "the chart starts at the run's first step");
            Assert.Greater(h.Samples[h.Samples.Count - 1].Step, 1000ul - h.Interval - 1, "and ends near now");
            for (int i = 1; i < h.Samples.Count; i++)
            {
                Assert.Greater(h.Samples[i].Step, h.Samples[i - 1].Step);
            }
            Assert.AreEqual(h.Samples[h.Samples.Count - 1].Photo, h.Peak());

            h.Add(5, new[] { 0, 1, 1, 1, 1 });    // an earlier step: a new world
            Assert.AreEqual(1, h.Samples.Count);
            Assert.AreEqual(1ul, h.Interval);
        }
    }
}
