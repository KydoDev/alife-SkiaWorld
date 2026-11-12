// WorldCamera (G3 P2): integer zoom, x wrap, y clamp, and screen point -> tile, without a UI.
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class WorldCameraTests
    {
        // the default world (160 x 64) in a 1000 x 650 px view: fitting the height gives 10 px per tile
        private static WorldCamera Fitted()
        {
            var camera = new WorldCamera(160, 64, 48);
            camera.SetView(new Vector2(1000, 650));
            camera.FitHeight();
            return camera;
        }

        private static (int, int) Tile(WorldCamera camera, float px, float py)
        {
            Assert.IsTrue(camera.TileAt(new Vector2(px, py), out int x, out int y), $"no tile at ({px}, {py})");
            return (x, y);
        }

        [Test]
        public void FitHeightUsesTheLargestWholeScaleThatShowsTheDepth()
        {
            WorldCamera camera = Fitted();
            Assert.AreEqual(10, camera.Scale);
            Assert.AreEqual(10, camera.MinScale);
            // 640 px of world in a 650 px view: centred, 5 px above and below
            Assert.AreEqual(5, camera.Top());
            Assert.AreEqual((0, 0), Tile(camera, 0, 5));
            Assert.IsFalse(camera.TileAt(new Vector2(0, 4), out _, out _));
            Assert.AreEqual((99, 63), Tile(camera, 999, 644));
            Assert.IsFalse(camera.TileAt(new Vector2(0, 645), out _, out _));
        }

        [Test]
        public void ZoomKeepsTheTileUnderThePoint()
        {
            WorldCamera camera = Fitted();
            var point = new Vector2(305, 207);    // tile (30, 20), away from a tile edge
            Assert.AreEqual((30, 20), Tile(camera, point.x, point.y));
            foreach (int scale in new[] { 20, 37, 48, 13 })
            {
                camera.ZoomAt(scale, point);
                Assert.AreEqual(scale, camera.Scale);
                Assert.AreEqual((30, 20), Tile(camera, point.x, point.y), $"scale {scale}");
            }
        }

        [Test]
        public void ZoomIsClampedToTheScaleRange()
        {
            WorldCamera camera = Fitted();
            camera.ZoomAt(1000, Vector2.zero);
            Assert.AreEqual(48, camera.Scale);
            camera.ZoomAt(1, Vector2.zero);
            Assert.AreEqual(10, camera.Scale);
            Assert.AreEqual(10, camera.NextScale(-1));
            Assert.AreEqual(12, camera.NextScale(1));
        }

        [Test]
        public void PanWrapsAcrossTheSeamInX()
        {
            WorldCamera camera = Fitted();
            camera.Pan(new Vector2(30, 0));       // drag right by 3 tiles: tile 157 is now at the left edge
            Assert.AreEqual(157.0, camera.OffsetX, 1e-9);
            Assert.AreEqual((157, 0), Tile(camera, 0, 5));
            Assert.AreEqual((159, 0), Tile(camera, 29, 5));
            Assert.AreEqual((0, 0), Tile(camera, 30, 5));    // across the seam
            Assert.AreEqual(-1570, camera.FirstCopyLeft());
            Assert.AreEqual(2, camera.CopiesNeeded());
            camera.Pan(new Vector2(-60, 0));      // drag left by 6 tiles: back across the seam
            Assert.AreEqual(3.0, camera.OffsetX, 1e-9);
            Assert.AreEqual((3, 0), Tile(camera, 0, 5));
        }

        [Test]
        public void PanIsClampedInY()
        {
            WorldCamera camera = Fitted();
            camera.ZoomAt(20, Vector2.zero);      // 1280 px of world in a 650 px view
            camera.Pan(new Vector2(0, 10000));    // drag down: the surface, no further
            Assert.AreEqual(0.0, camera.OffsetY, 1e-9);
            camera.Pan(new Vector2(0, -10000));   // drag up: the sea floor at the bottom edge
            Assert.AreEqual(64 - 650 / 20.0, camera.OffsetY, 1e-9);
            Assert.AreEqual((0, 63), Tile(camera, 0, 649));
        }

        [Test]
        public void CopiesCoverAViewWiderThanTheWorld()
        {
            var camera = new WorldCamera(16, 8, 48);
            camera.SetView(new Vector2(500, 80));  // 10 px per tile: the world is 160 px wide
            camera.FitHeight();
            Assert.AreEqual(4, camera.CopiesNeeded());
            camera.Pan(new Vector2(-5, 0));
            Assert.AreEqual(-5, camera.FirstCopyLeft());
            Assert.AreEqual(4, camera.CopiesNeeded());   // -5 + 4 * 160 = 635 >= 500
            Assert.AreEqual((2, 0), Tile(camera, 498, 0));   // (498 + 5) / 10 = 50.3 -> 50 mod 16
        }

        [Test]
        public void TileAtRefusesPointsOutsideTheView()
        {
            WorldCamera camera = Fitted();
            Assert.IsFalse(camera.TileAt(new Vector2(-1, 100), out _, out _));
            Assert.IsFalse(camera.TileAt(new Vector2(1000, 100), out _, out _));
        }
    }
}
