// EditMode tests of the P6a cell sheet data (CellSheet.cs): the gene and trait names are Python's, the kind follows
// the tile word's rule, the text shows the record, and a selected cell is found again across the x seam.
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class CellSheetTests
    {
        private static string WorldPy() => File.ReadAllText(Path.GetFullPath(Path.Combine(Application.dataPath, "..",
                                                                                           "..", "worldsim",
                                                                                           "world.py")));

        private static CellRecord Record(ulong id, double photo = 0.7, double sapro = 0.1, double pred = 0.1,
                                         double chemo = 0.1)
        {
            return new CellRecord
            {
                Present = 1, Id = id, Lineage = 42, Age = 300, Energy = 12.34, Colony = 1,
                Genes = new double[16], Shares = new[] { photo, sapro, pred, chemo }, Traits = new double[5],
            };
        }

        [Test]
        public void GeneAndTraitNamesArePythons()
        {
            string py = WorldPy();
            Match genes = Regex.Match(py, @"GENE_NAMES = \[(.*?)\]", RegexOptions.Singleline);
            Assert.IsTrue(genes.Success, "GENE_NAMES in worldsim/world.py");
            string[] names = Regex.Matches(genes.Groups[1].Value, "\"([a-z_]+)\"").Select(m => m.Groups[1].Value)
                                  .ToArray();
            CollectionAssert.AreEqual(names, CellSheet.GeneNames);
            Match traits = Regex.Match(py, @"TRAITS = \((.*?)\n\)", RegexOptions.Singleline);
            Assert.IsTrue(traits.Success, "TRAITS in worldsim/world.py");
            string[] traitNames = Regex.Matches(traits.Groups[1].Value, "Trait\\(\"([a-z_]+)\"")
                                       .Select(m => m.Groups[1].Value).ToArray();
            CollectionAssert.AreEqual(traitNames, CellSheet.TraitNames);
        }

        [Test]
        public void KindIsTheLargestShareAndTheFirstOnATie()
        {
            Assert.AreEqual(TileKind.Photo, CellSheet.KindOf(Record(1)));
            Assert.AreEqual(TileKind.Chemo, CellSheet.KindOf(Record(1, 0.1, 0.1, 0.1, 0.7)));
            Assert.AreEqual(TileKind.Sapro, CellSheet.KindOf(Record(1, 0.1, 0.4, 0.1, 0.4)));
            Assert.AreEqual("PHOTO  #9", CellSheet.Title(Record(9)));
        }

        [Test]
        public void SummaryShowsTheRecordAndOnlyTheTraitsInUse()
        {
            CellRecord r = Record(5);
            string text = CellSheet.Summary(r);
            StringAssert.Contains("energy 12.3", text);
            StringAssert.Contains("age 300", text);
            StringAssert.Contains("lineage 42", text);
            StringAssert.Contains("alone", text);
            StringAssert.DoesNotContain("armor_p", text);
            r.Colony = 4;
            r.Bonds = 2;
            r.Traits[3] = 0.25;
            r.Rules = 3;
            text = CellSheet.Summary(r);
            StringAssert.Contains("colony of 4 cells, 2 bonds", text);
            StringAssert.Contains("armor_p 0.25", text);
            StringAssert.Contains("3 rule genes", text);
        }

        [Test]
        public void FollowFindsTheCellNearbyAndAcrossTheSeam()
        {
            const int w = 10, h = 6;
            int cx = 0, cy = 3;    // where cell #7 is now
            CellRecord At(int x, int y) => x == cx && y == cy ? Record(7) : default;

            Assert.IsTrue(CellSheet.Follow(At, w, h, w - 1, 3, 7, 1, out int x, out int y, out CellRecord r));
            Assert.AreEqual((0, 3, 7ul), (x, y, r.Id), "one step east of the last column is column 0");
            Assert.IsFalse(CellSheet.Follow(At, w, h, w - 1, 3, 7, 0, out x, out y, out _), "radius 0: same tile only");
            Assert.AreEqual((w - 1, 3), (x, y), "not found: the last tile is kept");
            Assert.IsFalse(CellSheet.Follow(At, w, h, 3, 3, 8, 2, out _, out _, out _), "another id is not followed");
            cy = 0;
            Assert.IsFalse(CellSheet.Follow(At, w, h, 0, h - 1, 7, 1, out _, out _, out _), "y does not wrap");
            Assert.IsTrue(CellSheet.Follow(At, w, h, 2, 2, 7, 5, out x, out y, out _), "radius is capped at 2 ...");
            Assert.AreEqual((0, 0), (x, y), "... which still reaches (0, 0) from (2, 2)");
        }
    }
}
