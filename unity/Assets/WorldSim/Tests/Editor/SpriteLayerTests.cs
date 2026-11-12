// EditMode tests of the P5b sprite layer: the GPU sprites of a golden world equal a CPU reference of the rules in
// docs/G3_PLAN.md (P5) pixel for pixel, the top of the image is the lit surface, and empty tiles are transparent.
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class SpriteLayerTests
    {
        private const int S = SpriteArt.Size;

        private static NativeWorld Golden(string set) =>
            NativeWorld.Load(File.ReadAllBytes(Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..",
                "engine-rs", "tests", "golden", set, "start.json.gz"))));

        private static Color32[] Read(RenderTexture rt)
        {
            RenderTexture previous = RenderTexture.active;
            var t = new Texture2D(rt.width, rt.height, TextureFormat.RGBA32, false);
            try
            {
                RenderTexture.active = rt;
                t.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
                t.Apply();
                return t.GetPixels32();
            }
            finally
            {
                RenderTexture.active = previous;
                Object.DestroyImmediate(t);
            }
        }

        private static bool Bonded(byte[] tiles, int w, int h, int x, int row)
        {
            if (row < 0 || row >= h)
            {
                return false;
            }
            Tile t = Tile.At(tiles, row * w + (x + w) % w);
            return t.Kind != TileKind.Empty && t.Bonded;
        }

        /// <summary>The shader's rule on the CPU: the colour of sprite pixel (col, prow) of tile (x, row), or clear.
        /// </summary>
        private static Color32 Expected(byte[] tiles, int w, int h, int x, int row, int col, int prow, int frame,
                                        int time)
        {
            Tile t = Tile.At(tiles, row * w + x);
            if (t.Kind == TileKind.Empty)
            {
                return new Color32(0, 0, 0, 0);
            }
            SpriteRole role = SpriteArt.RoleAt(t.Kind, (frame + t.Key) & 1, col, prow);
            if (role == SpriteRole.Clear)
            {
                return new Color32(0, 0, 0, 0);
            }
            if (t.Bonded && ((col == 0 && Bonded(tiles, w, h, x - 1, row))
                             || (col == S - 1 && Bonded(tiles, w, h, x + 1, row))
                             || (prow == 0 && Bonded(tiles, w, h, x, row - 1))
                             || (prow == S - 1 && Bonded(tiles, w, h, x, row + 1))))
            {
                role = SpriteRole.Light;
            }
            Color32 c = SpriteArt.RoleColour(t.Kind, time, role);
            if (t.Energy == 0)
            {
                if ((prow * 3 + col) % 4 == 0)
                {
                    return new Color32(0, 0, 0, 0);
                }
                float grey = 0.299f * c.r + 0.587f * c.g + 0.114f * c.b;
                c = new Color32((byte)Mathf.Round(grey + 0.35f * (c.r - grey)),
                                (byte)Mathf.Round(grey + 0.35f * (c.g - grey)),
                                (byte)Mathf.Round(grey + 0.35f * (c.b - grey)), 255);
            }
            return c;
        }

        private static void CheckAll(string set, int frame, int time)
        {
            using NativeWorld world = Golden(set);
            WorldInfo info = world.Info;
            int w = (int)info.Width, h = (int)info.Height;
            var tiles = new byte[world.TilesLength];
            world.Tiles(tiles);
            using var layer = new SpriteLayer(w, h);
            layer.Upload(world);
            layer.Render(frame, time);
            Color32[] px = Read(layer.Texture);
            Assert.AreEqual(w * S * h * S, px.Length);
            int checkedCells = 0, starving = 0, bondedEdges = 0;
            for (int row = 0; row < h; row++)
            {
                for (int x = 0; x < w; x++)
                {
                    Tile t = Tile.At(tiles, row * w + x);
                    checkedCells += t.Kind != TileKind.Empty ? 1 : 0;
                    starving += t.Kind != TileKind.Empty && t.Energy == 0 ? 1 : 0;
                    bondedEdges += t.Kind != TileKind.Empty && t.Bonded ? 1 : 0;
                    for (int prow = 0; prow < S; prow++)
                    {
                        for (int col = 0; col < S; col++)
                        {
                            // texture rows grow upwards: world row 0 (the surface) is the top band
                            int py = (h - 1 - row) * S + (S - 1 - prow);
                            Color32 got = px[py * w * S + x * S + col];
                            Color32 want = Expected(tiles, w, h, x, row, col, prow, frame, time);
                            string where = $"{set}: tile ({x}, {row}) pixel ({col}, {prow})";
                            Assert.AreEqual(want.a, got.a, $"{where}: alpha");
                            if (want.a != 0)
                            {
                                // exact, except one step of rounding in the starving desaturation
                                Assert.LessOrEqual(Mathf.Abs(want.r - got.r), 1, $"{where}: {want} vs {got}");
                                Assert.LessOrEqual(Mathf.Abs(want.g - got.g), 1, $"{where}: {want} vs {got}");
                                Assert.LessOrEqual(Mathf.Abs(want.b - got.b), 1, $"{where}: {want} vs {got}");
                            }
                        }
                    }
                }
            }
            Assert.Greater(checkedCells, 50, $"{set}: the golden world has cells");
            TestContext.WriteLine($"{set}: {checkedCells} cells, {starving} starving, {bondedEdges} bonded");
        }

        [Test]
        public void SpritesEqualTheCpuRuleOnTheDefaultWorld() => CheckAll("default", 0, SpriteArt.Night);

        [Test]
        public void SpritesEqualTheCpuRuleOnTheOtherFrameAndByDay() => CheckAll("plasticity", 1, SpriteArt.Day);

        [Test]
        public void SpritesEqualTheCpuRuleOnTheVolcanicWorld() => CheckAll("volcanic", 0, SpriteArt.Night);
    }
}
