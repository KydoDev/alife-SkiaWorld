// EditMode tests of the game texts (G3 P7 piece 4): the milestone texts and tool names equal worldsim/play.py's, and
// only milestones not yet announced are announced.
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class GameTextTests
    {
        private static string PlayPy() => File.ReadAllText(Path.GetFullPath(Path.Combine(
            Application.dataPath, "..", "..", "worldsim", "play.py")));

        [Test]
        public void MilestoneTextsEqualPlayPy()
        {
            string text = PlayPy();
            Match block = Regex.Match(text, @"MILESTONES = \{(.*?)\n\}", RegexOptions.Singleline);
            Assert.IsTrue(block.Success, "MILESTONES not found in play.py");
            var entries = Regex.Matches(block.Groups[1].Value, "\"(\\w+)\": \"([^\"]*)\"").Cast<Match>()
                .Select(m => (m.Groups[1].Value, m.Groups[2].Value)).ToArray();
            var milestones = (Milestone[])System.Enum.GetValues(typeof(Milestone));
            Assert.AreEqual(milestones.Length, entries.Length);
            for (int i = 0; i < entries.Length; i++)
            {
                Assert.AreEqual(entries[i].Item1, milestones[i].ToString().ToLowerInvariant());
                Assert.AreEqual(entries[i].Item2, GameText.Of(milestones[i]), entries[i].Item1);
            }
        }

        [Test]
        public void ToolNamesEqualPlayPy()
        {
            Match tools = Regex.Match(PlayPy(), @"TOOLS = \(([^)]*)\)");
            string[] names = Regex.Matches(tools.Groups[1].Value, "\"(\\w+)\"").Cast<Match>()
                .Select(m => m.Groups[1].Value).ToArray();
            CollectionAssert.AreEqual(names,
                ((Tool[])System.Enum.GetValues(typeof(Tool))).Select(GameText.Name).ToArray());
        }

        [Test]
        public void OnlyNewMilestonesAreAnnounced()
        {
            CollectionAssert.IsEmpty(GameText.Fresh(0, 0));
            CollectionAssert.AreEqual(new[] { Milestone.Giant }, GameText.Fresh(1u << 2, 0));
            CollectionAssert.AreEqual(new[] { Milestone.Abyss, Milestone.Divided },
                                      GameText.Fresh(0b10101, 0b00100));
            CollectionAssert.IsEmpty(GameText.Fresh(0b111, 0b111));
        }
    }
}
