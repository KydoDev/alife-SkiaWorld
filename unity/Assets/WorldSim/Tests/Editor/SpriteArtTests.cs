// EditMode tests of the P5 sprite art: the sprites and the palette in SpriteArt.cs are the ones in the design table
// of docs/G3_PLAN.md (so the code and the doc cannot drift apart), and the two textures hold them where the shader
// looks for them.
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class SpriteArtTests
    {
        private static readonly string[] Names = { "photo", "sapro", "pred", "chemo" };

        /// <summary>Backticked cells of the design-table row of <paramref name="name"/>, sprites or palette.
        /// </summary>
        private static List<string> TableRow(string name, bool palette)
        {
            string doc = File.ReadAllText(Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "docs",
                                                                        "G3_PLAN.md")));
            foreach (string line in doc.Split('\n'))
            {
                if (!line.StartsWith($"| {name} |"))
                {
                    continue;
                }
                List<string> cells = Regex.Matches(line, "`([^`]*)`").Select(m => m.Groups[1].Value).ToList();
                if (cells.Count > 0 && cells[0].StartsWith("#") == palette)
                {
                    return cells;
                }
            }
            Assert.Fail($"no {(palette ? "palette" : "sprite")} row for {name} in docs/G3_PLAN.md");
            return null;
        }

        [Test]
        public void SpritesAreTheDesignTables()
        {
            for (int k = 0; k < Names.Length; k++)
            {
                List<string> row = TableRow(Names[k], palette: false);
                Assert.AreEqual(SpriteArt.Frames, row.Count, Names[k]);
                for (int f = 0; f < SpriteArt.Frames; f++)
                {
                    Assert.AreEqual(row[f], SpriteArt.FrameString(SpriteArt.Kinds[k], f), $"{Names[k]} frame {f}");
                }
            }
        }

        [Test]
        public void PaletteIsTheDesignTables()
        {
            for (int k = 0; k < Names.Length; k++)
            {
                List<string> row = TableRow(Names[k], palette: true);
                Assert.AreEqual(6, row.Count, Names[k]);
                for (int time = SpriteArt.Night; time <= SpriteArt.Day; time++)
                {
                    for (int shade = 0; shade < 3; shade++)
                    {
                        Assert.AreEqual(row[time * 3 + shade], SpriteArt.PaletteString(SpriteArt.Kinds[k], time, shade),
                                        $"{Names[k]} time {time} shade {shade}");
                    }
                }
            }
        }

        [Test]
        public void AtlasHoldsEachRoleWhereTheShaderReadsIt()
        {
            Texture2D atlas = SpriteArt.BuildAtlas();
            try
            {
                Assert.AreEqual((SpriteArt.Frames * 5, 4 * 5), (atlas.width, atlas.height));
                Assert.AreEqual(FilterMode.Point, atlas.filterMode);
                Color32[] px = atlas.GetPixels32();
                // photo frame 0, top row ".BHB.": texture row 4 of band 0 (rows grow upwards)
                Assert.AreEqual(new byte[] { 0, 1, 2, 1, 0 }, Enumerable.Range(0, 5).Select(c => px[4 * 10 + c].r).ToArray());
                // pred frame 1 centre is the eye: band 2, row 2, column 5 + 2
                Assert.AreEqual((byte)SpriteRole.Eye, px[(2 * 5 + 2) * 10 + 7].r);
                foreach (TileKind kind in SpriteArt.Kinds)
                {
                    for (int f = 0; f < SpriteArt.Frames; f++)
                    {
                        Assert.AreEqual(1, Enumerable.Range(0, 25)
                                            .Count(i => SpriteArt.RoleAt(kind, f, i % 5, i / 5) == SpriteRole.Eye),
                                        $"{kind} frame {f}: one eye");
                    }
                }
            }
            finally
            {
                Object.DestroyImmediate(atlas);
            }
        }

        [Test]
        public void PaletteTextureMapsKindAndRoleToTheTableColour()
        {
            Texture2D palette = SpriteArt.BuildPalette();
            try
            {
                Assert.AreEqual((16, 2), (palette.width, palette.height));
                Color32[] px = palette.GetPixels32();
                Assert.AreEqual(SpriteArt.Hex("#59ffa0"), px[0]);                // photo base, night
                Assert.AreEqual(SpriteArt.Hex("#178a80"), px[16 + 3 * 4 + 2]);   // chemo shade, day
                Assert.AreEqual(new Color32(255, 255, 255, 255), px[2 * 4 + 3]); // pred eye is white
                Assert.AreEqual(SpriteArt.Hex("#fff4c4"), px[1 * 4 + 3]);        // sapro eye = its light colour
            }
            finally
            {
                Object.DestroyImmediate(palette);
            }
        }
    }
}
