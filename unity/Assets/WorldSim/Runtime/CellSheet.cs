// G3 P6a: what the cell sheet shows, from the ABI 4 record (ADR-0016), and how a selected cell is followed from step
// to step. Pure, so EditMode tests check it without a panel; WorldSimView draws it.
using System;
using UnityEngine;

namespace WorldSim
{
    public static class CellSheet
    {
        /// <summary>Python's `GENE_NAMES` (worldsim/world.py), the order of <see cref="CellRecord.Genes"/>.</summary>
        public static readonly string[] GeneNames =
        {
            "photo", "sapro", "pred", "move", "div", "child", "attach", "share", "mut", "chemo",
            "w_light", "w_organic", "w_chem", "w_kin", "w_stranger", "w_danger",
        };

        /// <summary>Python's `TRAITS` names (ADR-0014), the order of <see cref="CellRecord.Traits"/>.</summary>
        public static readonly string[] TraitNames = { "sex_p", "plast_p", "hgt_p", "armor_p", "sense_r" };

        /// <summary>Feeding shares in <see cref="CellRecord.Shares"/> order.</summary>
        public static readonly string[] ShareNames = { "photo", "sapro", "pred", "chemo" };

        /// <summary>How far (tiles, each axis) a selected cell is searched for after a redraw.</summary>
        public const int MaxFollowRadius = 2;

        /// <summary>The tile word's kind of a record: the largest share, the first on a tie (Python's `kind`).
        /// </summary>
        public static TileKind KindOf(CellRecord r)
        {
            int best = 0;
            for (int i = 1; i < 4; i++)
            {
                if (r.Shares[i] > r.Shares[best])
                {
                    best = i;
                }
            }
            return (TileKind)(best + 1);
        }

        public static string Title(CellRecord r) => $"{KindOf(r).ToString().ToUpperInvariant()}  #{r.Id}";

        /// <summary>The sheet's text lines above the bars; traits only when some is non-zero (their flag is on).
        /// </summary>
        public static string Summary(CellRecord r)
        {
            string colony = r.Colony > 1 ? $"colony of {r.Colony} cells, {r.Bonds} bonds" : "alone (no bonds)";
            string text = $"energy {r.Energy:0.0}   age {r.Age}   lineage {r.Lineage}\n{colony}";
            string traits = "";
            for (int i = 0; i < TraitNames.Length; i++)
            {
                if (r.Traits[i] != 0.0)
                {
                    traits += $"{TraitNames[i]} {r.Traits[i]:0.00}   ";
                }
            }
            if (traits.Length > 0)
            {
                text += "\n" + traits.TrimEnd();
            }
            if (r.Rules > 0)
            {
                text += $"\n{r.Rules} rule genes";
            }
            return text;
        }

        /// <summary>Find cell <paramref name="id"/> again after it may have moved: the last tile first, then rings
        /// of growing distance up to <paramref name="radius"/> (x wraps, the world is toroidal; y does not).
        /// <paramref name="cellAt"/> reads the record of a tile.</summary>
        public static bool Follow(Func<int, int, CellRecord> cellAt, int width, int height, int lastX, int lastY,
                                  ulong id, int radius, out int x, out int y, out CellRecord record)
        {
            radius = Mathf.Clamp(radius, 0, Mathf.Min(MaxFollowRadius, (width - 1) / 2));
            for (int ring = 0; ring <= radius; ring++)
            {
                for (int dy = -ring; dy <= ring; dy++)
                {
                    for (int dx = -ring; dx <= ring; dx++)
                    {
                        if (Math.Max(Math.Abs(dx), Math.Abs(dy)) != ring)
                        {
                            continue;    // inner tiles were searched in an earlier ring
                        }
                        int ty = lastY + dy;
                        if (ty < 0 || ty >= height)
                        {
                            continue;
                        }
                        int tx = ((lastX + dx) % width + width) % width;
                        CellRecord r = cellAt(tx, ty);
                        if (r.Present == 1 && r.Id == id)
                        {
                            x = tx;
                            y = ty;
                            record = r;
                            return true;
                        }
                    }
                }
            }
            x = lastX;
            y = lastY;
            record = default;
            return false;
        }
    }
}
