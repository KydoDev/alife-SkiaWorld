// The species drawer's content (G3 P8, ADR-0018): which living species to list and in what order, the text of a row,
// a tint per species, and the ancestry line. Plain functions of the kernel's records, so EditMode tests check them.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

namespace WorldSim
{
    public static class SpeciesList
    {
        /// <summary>Most rows the drawer shows; the rest are summed up in one line.</summary>
        public const int MaxRows = 30;

        /// <summary>Python's origin names (`species.ORIGIN_*`).</summary>
        public static string Origin(SpeciesOrigin o) => o switch
        {
            SpeciesOrigin.Seed => "seed",
            SpeciesOrigin.Immigrant => "immigrant",
            SpeciesOrigin.Speciation => "speciation",
            _ => "unknown",
        };

        /// <summary>A colour per species id: hues spread by the golden ratio, so neighbouring ids differ.</summary>
        public static Color Tint(ulong id)
        {
            double hue = (id * 0.6180339887498949) % 1.0;
            return Color.HSVToRGB((float)hue, 0.65f, 0.95f);
        }

        /// <summary>The species to list: the most numerous first (ties: the older id first), at most
        /// <see cref="MaxRows"/>.</summary>
        public static SpeciesRecord[] Rows(SpeciesRecord[] living) =>
            living.OrderByDescending(s => s.Count).ThenBy(s => s.Id).Take(MaxRows).ToArray();

        /// <summary>One row: id, members, age at <paramref name="step"/>, origin, and a star once established.</summary>
        public static string Row(SpeciesRecord s, ulong step)
        {
            ulong age = step >= s.Born ? step - s.Born : 0;
            string star = s.IsEstablished ? " *" : "";
            return $"#{s.Id}  {s.Count} cells  age {age}  {Origin(s.Origin)}{star}";
        }

        /// <summary>The drawer's header: living species and the tracker's counters, or why there are none.</summary>
        public static string Header(SpeciesInfo info, int shown)
        {
            if (!info.IsTracked)
            {
                return "no species: this world was saved without a species tracker";
            }
            string more = info.Extant > (ulong)shown ? $" (top {shown} shown)" : "";
            return $"{info.Extant} living species{more}\n{info.Speciations} speciations, {info.Novelty} established";
        }

        /// <summary>The ancestry line of <paramref name="s"/>: itself, then each ancestor (parent first), ending with
        /// its root's origin or with a note that older ancestors were forgotten (pruned).</summary>
        public static string Ancestry(SpeciesRecord s, IReadOnlyList<SpeciesRecord> ancestors)
        {
            var text = new StringBuilder($"#{s.Id}");
            foreach (SpeciesRecord a in ancestors)
            {
                text.Append($" < #{a.Id}");
            }
            SpeciesRecord last = ancestors.Count > 0 ? ancestors[ancestors.Count - 1] : s;
            text.Append(last.Parent == 0
                ? $"  (root: {Origin(last.Origin)} at step {last.Born})"
                : $" < ... (older ancestors forgotten)");
            if (!s.IsExtant)
            {
                text.Append($"\nextinct at step {s.Extinct}");
            }
            return text.ToString();
        }
    }
}
