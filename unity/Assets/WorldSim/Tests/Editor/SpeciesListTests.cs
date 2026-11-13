// EditMode tests of the species drawer's content (G3 P8): which species are listed and in what order, a row's text,
// the header of a tracked and an untracked world, the ancestry line, and tints that tell neighbouring ids apart.
using System.Collections.Generic;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class SpeciesListTests
    {
        private static SpeciesRecord Species(ulong id, ulong count, ulong parent = 0, ulong born = 0,
                                             SpeciesOrigin origin = SpeciesOrigin.Speciation,
                                             ulong extinct = SpeciesRecord.StepNone,
                                             ulong established = SpeciesRecord.StepNone) =>
            new SpeciesRecord
            {
                Id = id, Parent = parent, Born = born, Origin = origin, Extinct = extinct, Count = count,
                Established = established,
            };

        [Test]
        public void RowsPutTheMostNumerousFirstAndCapTheList()
        {
            var living = new List<SpeciesRecord> { Species(5, 3), Species(2, 9), Species(7, 9), Species(1, 1) };
            for (ulong id = 10; id < 50; id++)
            {
                living.Add(Species(id, 1));
            }
            SpeciesRecord[] rows = SpeciesList.Rows(living.ToArray());
            Assert.AreEqual(SpeciesList.MaxRows, rows.Length);
            CollectionAssert.AreEqual(new ulong[] { 2, 7, 5, 1, 10 }, rows.Take(5).Select(s => s.Id),
                                      "by members, then the older id");
        }

        [Test]
        public void ARowShowsIdMembersAgeOriginAndEstablishment()
        {
            Assert.AreEqual("#4  12 cells  age 70  speciation *",
                            SpeciesList.Row(Species(4, 12, parent: 1, born: 30, established: 60), 100));
            Assert.AreEqual("#1  3 cells  age 0  seed", SpeciesList.Row(Species(1, 3, origin: SpeciesOrigin.Seed), 0));
            Assert.AreEqual("immigrant", SpeciesList.Origin(SpeciesOrigin.Immigrant));
        }

        [Test]
        public void TheHeaderSaysWhyAnUntrackedWorldHasNoSpecies()
        {
            Assert.AreEqual("no species: this world was saved without a species tracker",
                            SpeciesList.Header(new SpeciesInfo { Tracked = 0 }, 0));
            var info = new SpeciesInfo { Tracked = 1, Extant = 40, Speciations = 12, Novelty = 3 };
            Assert.AreEqual("40 living species (top 30 shown)\n12 speciations, 3 established",
                            SpeciesList.Header(info, 30));
            info.Extant = 4;
            Assert.AreEqual("4 living species\n12 speciations, 3 established", SpeciesList.Header(info, 4));
        }

        [Test]
        public void AncestryEndsAtTheRootOrAtTheForgottenAncestors()
        {
            SpeciesRecord root = Species(1, 0, origin: SpeciesOrigin.Seed, extinct: 50);
            SpeciesRecord mid = Species(3, 2, parent: 1, born: 40);
            SpeciesRecord leaf = Species(8, 5, parent: 3, born: 90);
            Assert.AreEqual("#8 < #3 < #1  (root: seed at step 0)", SpeciesList.Ancestry(leaf, new[] { mid, root }));
            Assert.AreEqual("#8 < #3 < ... (older ancestors forgotten)",
                            SpeciesList.Ancestry(leaf, new[] { Species(3, 2, parent: 2) }));
            Assert.AreEqual("#1  (root: seed at step 0)\nextinct at step 50",
                            SpeciesList.Ancestry(root, new SpeciesRecord[0]));
        }

        [Test]
        public void NeighbouringIdsGetDistinctTints()
        {
            for (ulong id = 1; id < 40; id++)
            {
                Color.RGBToHSV(SpeciesList.Tint(id), out float a, out _, out _);
                Color.RGBToHSV(SpeciesList.Tint(id + 1), out float b, out _, out _);
                float gap = Mathf.Abs(a - b);
                Assert.Greater(Mathf.Min(gap, 1 - gap), 0.1f, $"ids {id} and {id + 1}");
            }
            Assert.AreEqual(SpeciesList.Tint(7), SpeciesList.Tint(7), "a species keeps its tint");
        }
    }
}
