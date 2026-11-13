// G3 P7 piece 4: the game's player-facing texts. The kernel reports which milestones are reached (ADR-0017
// Decision 4); their texts live here, and GameTextTests keeps them equal to worldsim/play.py's MILESTONES.
using System;

namespace WorldSim
{
    public static class GameText
    {
        /// <summary>`play.MILESTONES` values, in <see cref="Milestone"/> order.</summary>
        public static readonly string[] Milestones =
        {
            "Life in the abyss: a vent you made is colonised by chemosynthesizers",
            "Full ecosystem: plants, decomposers, predators and chemosynthesizers at your vents thrive together",
            "Giant organism: one colony of 80 cells",
            "Survivors: life recovers from a cataclysm you caused",
            "Divided ocean: two isolated seas, both alive",
        };

        public static string Of(Milestone m) => Milestones[(int)m];

        /// <summary>The tool's name as `play.TOOLS` spells it.</summary>
        public static string Name(Tool t) => t.ToString().ToLowerInvariant();

        /// <summary>The milestones reached in <paramref name="reached"/> but not in <paramref name="announced"/>, in
        /// <see cref="Milestone"/> order.</summary>
        public static Milestone[] Fresh(uint reached, uint announced)
        {
            uint fresh = reached & ~announced;
            return Array.FindAll((Milestone[])Enum.GetValues(typeof(Milestone)), m => (fresh & (1u << (int)m)) != 0);
        }
    }
}
