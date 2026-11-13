// EditMode tests of ABI 5 (ADR-0017): the kernel's game, called through P/Invoke, replays engine-rs/tests/golden/games.json
// (scripts/g3_game_vectors.py, made by Python's play.Game) and refuses what it must.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class GameTests
    {
        private static string GoldenDir(string set) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "engine-rs", "tests", "golden", set));

        private static NativeWorld LoadStart(string set) =>
            NativeWorld.Load(File.ReadAllBytes(Path.Combine(GoldenDir(set), "start.json.gz")));

        // games.json, the fields JsonUtility can read; "achieved" (an object) and "hashes" (nested arrays) are read
        // with regular expressions below.
        [Serializable]
        private class RulesJson
        {
            public double budget_max;
            public double budget_start;
            public double regen;
            public double[] cost;
            public uint[] radius;
            public double nutrients_amount;
            public double max_chem;
            public ulong check_every;
            public ulong abyss_cells;
            public double abyss_radius;
            public ulong balance_cells;
            public ulong giant_colony;
            public double kill_fraction;
            public ulong collapse_window;
            public double recover_fraction;
            public ulong divided_cells;

            public GameRules ToRules() => new GameRules
            {
                BudgetMax = budget_max,
                BudgetStart = budget_start,
                Regen = regen,
                Cost = cost,
                NutrientsAmount = nutrients_amount,
                MaxChem = max_chem,
                AbyssRadius = abyss_radius,
                KillFraction = kill_fraction,
                RecoverFraction = recover_fraction,
                CheckEvery = check_every,
                AbyssCells = abyss_cells,
                BalanceCells = balance_cells,
                GiantColony = giant_colony,
                CollapseWindow = collapse_window,
                DividedCells = divided_cells,
                Radius = radius,
            };
        }

        [Serializable]
        private class ActionJson
        {
            public ulong offset;
            public string tool;
            public uint x;
            public uint y;
            public bool accepted;
            public string budget;
        }

        [Serializable]
        private class CaseJson
        {
            public string name;
            public string set;
            public RulesJson rules;
            public ulong steps;
            public ulong start_step;
            public ActionJson[] actions;
            public string budget;
            public ulong player_vents;
        }

        [Serializable]
        private class GamesJson
        {
            public string[] tools;
            public string[] milestones;
            public RulesJson default_rules;
            public CaseJson[] cases;
        }

        private static string Text() => File.ReadAllText(Path.Combine(GoldenDir(""), "games.json"));

        private static string Hex(double v) =>
            string.Concat(BitConverter.GetBytes(v).Select(b => b.ToString("x2")));   // little-endian, as f64_hex

        /// <summary>Per case, in file order: milestone name to step.</summary>
        private static List<Dictionary<string, ulong>> Achieved(string text) =>
            Regex.Matches(text, "\"achieved\": \\{([^}]*)\\}").Cast<Match>()
                .Select(m => Regex.Matches(m.Groups[1].Value, "\"(\\w+)\": (\\d+)").Cast<Match>()
                    .ToDictionary(p => p.Groups[1].Value, p => ulong.Parse(p.Groups[2].Value)))
                .ToList();

        /// <summary>Per case, in file order: step to state hash.</summary>
        private static List<Dictionary<ulong, string>> Hashes(string text) =>
            Regex.Matches(text, "\"hashes\": \\[(.*?)\\]\\s*,\\s*\"trace\"", RegexOptions.Singleline).Cast<Match>()
                .Select(m => Regex.Matches(m.Groups[1].Value, "\\[\\s*(\\d+),\\s*\"([0-9a-f]{64})\"\\s*\\]").Cast<Match>()
                    .ToDictionary(p => ulong.Parse(p.Groups[1].Value), p => p.Groups[2].Value))
                .ToList();

        [Test]
        public void ToolsMilestonesAndDefaultsEqualPython()
        {
            GamesJson file = JsonUtility.FromJson<GamesJson>(Text());
            CollectionAssert.AreEqual(file.tools,
                Enum.GetValues(typeof(Tool)).Cast<Tool>().Select(t => t.ToString().ToLowerInvariant()));
            CollectionAssert.AreEqual(file.milestones,
                Enum.GetValues(typeof(Milestone)).Cast<Milestone>().Select(m => m.ToString().ToLowerInvariant()));
            GameRules kernel = NativeWorld.DefaultGameRules();
            GameRules python = file.default_rules.ToRules();
            Assert.AreEqual(JsonUtility.ToJson(new Boxed(python)), JsonUtility.ToJson(new Boxed(kernel)));
            CollectionAssert.AreEqual(python.Cost, kernel.Cost);
            CollectionAssert.AreEqual(python.Radius, kernel.Radius);
            Assert.AreEqual(0u, kernel.Reserved);
        }

        // JsonUtility serialises public fields of a [Serializable] class: a field-by-field comparison of two rule sets.
        [Serializable]
        private class Boxed
        {
            public double budget_max, budget_start, regen, nutrients_amount, max_chem, abyss_radius, kill_fraction,
                recover_fraction;
            public ulong check_every, abyss_cells, balance_cells, giant_colony, collapse_window, divided_cells;

            public Boxed(GameRules r)
            {
                budget_max = r.BudgetMax;
                budget_start = r.BudgetStart;
                regen = r.Regen;
                nutrients_amount = r.NutrientsAmount;
                max_chem = r.MaxChem;
                abyss_radius = r.AbyssRadius;
                kill_fraction = r.KillFraction;
                recover_fraction = r.RecoverFraction;
                check_every = r.CheckEvery;
                abyss_cells = r.AbyssCells;
                balance_cells = r.BalanceCells;
                giant_colony = r.GiantColony;
                collapse_window = r.CollapseWindow;
                divided_cells = r.DividedCells;
            }
        }

        [Test]
        public void GamesFollowTheGameVectors()
        {
            string text = Text();
            GamesJson file = JsonUtility.FromJson<GamesJson>(text);
            List<Dictionary<string, ulong>> achieved = Achieved(text);
            List<Dictionary<ulong, string>> hashes = Hashes(text);
            Assert.AreEqual(8, file.cases.Length);
            Assert.AreEqual(file.cases.Length, achieved.Count);
            Assert.AreEqual(file.cases.Length, hashes.Count);
            for (int i = 0; i < file.cases.Length; i++)
            {
                CaseJson c = file.cases[i];
                using NativeWorld world = LoadStart(c.set);
                Assert.AreEqual(c.start_step, world.Info.StepCount, c.name);
                world.AttachGame(c.rules.ToRules());
                int next = 0;
                for (ulong k = 0; k <= c.steps; k++)
                {
                    for (; next < c.actions.Length && c.actions[next].offset <= k; next++)
                    {
                        ActionJson a = c.actions[next];
                        var tool = (Tool)Enum.Parse(typeof(Tool), a.tool, ignoreCase: true);
                        bool accepted = world.Act(tool, a.x, a.y);
                        Assert.AreEqual(a.accepted, accepted, $"{c.name}: {a.tool} at ({a.x}, {a.y}), offset {k}");
                        Assert.AreEqual(a.budget, Hex(world.Game.Budget), $"{c.name}: budget after {a.tool}");
                    }
                    if (hashes[i].TryGetValue(c.start_step + k, out string hash))
                    {
                        Assert.AreEqual(hash, world.StateHash(), $"{c.name}: hash at offset {k}");
                    }
                    if (k < c.steps)
                    {
                        world.Step(1);
                    }
                }
                GameInfo info = world.Game;
                Assert.AreEqual(c.budget, Hex(info.Budget), $"{c.name}: final budget");
                Assert.AreEqual(c.player_vents, info.PlayerVents, $"{c.name}: player vents");
                foreach (Milestone m in Enum.GetValues(typeof(Milestone)))
                {
                    string key = m.ToString().ToLowerInvariant();
                    bool reached = achieved[i].TryGetValue(key, out ulong step);
                    Assert.AreEqual(reached, info.Has(m), $"{c.name}: {key}");
                    Assert.AreEqual(reached ? step : 0UL, info.StepOf(m), $"{c.name}: {key} step");
                }
            }
        }

        [Test]
        public void TheGameRefusesWhatItMust()
        {
            using NativeWorld world = LoadStart("default");
            string before = world.StateHash();
            var e = Assert.Throws<WorldSimException>(() => _ = world.Game);
            Assert.AreEqual(WorldSimException.StatusInvalid, e.Status);
            e = Assert.Throws<WorldSimException>(() => world.Act(Tool.Meteorite, 1, 1));
            StringAssert.Contains("no game", e.Message);

            GameRules bad = NativeWorld.DefaultGameRules();
            bad.CheckEvery = 0;
            e = Assert.Throws<WorldSimException>(() => world.AttachGame(bad));
            StringAssert.Contains("check_every", e.Message);
            bad = NativeWorld.DefaultGameRules();
            bad.Regen = double.NaN;
            e = Assert.Throws<WorldSimException>(() => world.AttachGame(bad));
            StringAssert.Contains("regen", e.Message);
            bad = NativeWorld.DefaultGameRules();
            bad.Reserved = 1;
            e = Assert.Throws<WorldSimException>(() => world.AttachGame(bad));
            StringAssert.Contains("reserved", e.Message);

            bad = NativeWorld.DefaultGameRules();
            bad.Cost = null;
            Assert.Throws<ArgumentException>(() => world.AttachGame(bad));
            bad.Cost = new double[4];
            Assert.Throws<ArgumentException>(() => world.AttachGame(bad));

            world.AttachGame(NativeWorld.DefaultGameRules());
            e = Assert.Throws<WorldSimException>(() => world.AttachGame(NativeWorld.DefaultGameRules()));
            StringAssert.Contains("already has a game", e.Message);
            e = Assert.Throws<WorldSimException>(() => world.Intervene(Edit.Nutrients, 5, 5, 1, 1.0));
            Assert.AreEqual(WorldSimException.StatusInvalid, e.Status);
            StringAssert.Contains("ws_game_act", e.Message);
            e = Assert.Throws<WorldSimException>(() => world.Act((Tool)6, 1, 1));
            StringAssert.Contains("unknown tool", e.Message);
            Assert.IsFalse(world.Act(Tool.Meteorite, world.Info.Width, 0), "off the world: refused, free");
            Assert.AreEqual(before, world.StateHash());
            Assert.AreEqual(100.0, world.Game.Budget);

            Assert.IsTrue(world.Act(Tool.Volcano, 40, 30));
            Assert.AreEqual(60.0, world.Game.Budget);
            world.Step(20);
            Assert.AreEqual(61.0, world.Game.Budget, 1e-9, "regenerates 0.05 per step");
        }
    }
}
