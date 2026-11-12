// EditMode tests of the P5d margins (Backdrop.Compute): beside the world a row continues as its water, or as rock
// where the edge tile is rock; above the surface the top water, below the floor the deepest rock; cells never tint
// the water; everything dimmed; texture rows bottom-up.
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class BackdropTests
    {
        // a 4 x 3 world: row 0 water (one cell), row 1 water with rock at the west edge, row 2 all rock
        private const int W = 4, H = 3;

        private static (byte[] rgb, byte[] tiles) World()
        {
            var rgb = new byte[W * H * 3];
            var tiles = new byte[W * H * 4];
            void Set(int x, int y, byte r, byte g, byte b, byte word0)
            {
                int i = y * W + x;
                rgb[i * 3] = r;
                rgb[i * 3 + 1] = g;
                rgb[i * 3 + 2] = b;
                tiles[i * 4] = word0;
            }
            for (int x = 0; x < W; x++)
            {
                Set(x, 0, 0, 100, 200, 0);
                Set(x, 1, 0, 60, 120, 0);
                Set(x, 2, 30, 30, 40, 0x10);
            }
            Set(2, 0, 250, 0, 250, 1);          // a photo cell: not water
            Set(0, 1, 20, 20, 20, 0x10);        // rock on the west edge of row 1
            return (rgb, tiles);
        }

        private static Color32 Dimmed(int r, int g, int b) =>
            new Color32((byte)Mathf.RoundToInt(r * Backdrop.Dim), (byte)Mathf.RoundToInt(g * Backdrop.Dim),
                        (byte)Mathf.RoundToInt(b * Backdrop.Dim), 255);

        /// <summary>The texel of tile (x, row) in a backdrop computed from x0 = -2, y0 = -1, 8 x 5 tiles.</summary>
        private static Color32 At(Color32[] px, int x, int row) => px[(5 - 1 - (row + 1)) * 8 + (x + 2)];

        [Test]
        public void MarginsContinueTheRowsOfTheWorld()
        {
            (byte[] rgb, byte[] tiles) = World();
            Color32[] px = Backdrop.Compute(rgb, tiles, W, H, -2, -1, 8, 5);
            Assert.AreEqual(40, px.Length);
            Assert.AreEqual(Dimmed(0, 100, 200), At(px, -2, 0), "row 0 water, the cell left out of the mean");
            Assert.AreEqual(Dimmed(0, 100, 200), At(px, 5, 0), "east margin, same row");
            Assert.AreEqual(Dimmed(20, 20, 20), At(px, -1, 1), "west edge of row 1 is rock: rock continues");
            Assert.AreEqual(Dimmed(0, 60, 120), At(px, 4, 1), "east edge of row 1 is water: water continues");
            Assert.AreEqual(Dimmed(30, 30, 40), At(px, -2, 2), "the seabed row");
            Assert.AreEqual(Dimmed(0, 100, 200), At(px, 1, -1), "above the surface: the top water");
            Assert.AreEqual(Dimmed(30, 30, 40), At(px, 1, 3), "below the floor: the deepest rock");
        }

        [Test]
        public void TheWorldsOwnBuffersMustMatchItsSize()
        {
            (byte[] rgb, byte[] tiles) = World();
            Assert.Throws<System.ArgumentException>(() => Backdrop.Compute(rgb, new byte[4], W, H, 0, 0, 1, 1));
            Assert.Throws<System.ArgumentException>(() => Backdrop.Compute(new byte[3], tiles, W, H, 0, 0, 1, 1));
        }
    }
}
