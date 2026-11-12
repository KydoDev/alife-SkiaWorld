// WorldCamera (G3 P2, P2b): integer zoom, the whole world in the first view, both axes clamped (no x wrap in the
// view), and screen point -> tile, without a UI.
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class WorldCameraTests
    {
        // the default world (160 x 64) in a 1000 x 650 px view: the width limits the fit to 6 px per tile, so the
        // world is 960 x 384 px, centred with 20 px at the sides and 133 px above and below
        private static WorldCamera Fitted(int width = 160, int height = 64)
        {
            var camera = new WorldCamera(width, height, 48);
            camera.SetView(new Vector2(1000, 650));
            camera.FitWorld();
            return camera;
        }

        private static (int, int) Tile(WorldCamera camera, float px, float py)
        {
            Assert.IsTrue(camera.TileAt(new Vector2(px, py), out int x, out int y), $"no tile at ({px}, {py})");
            return (x, y);
        }

        private static bool Inside(WorldCamera camera, float px, float py) =>
            camera.TileAt(new Vector2(px, py), out _, out _);

        [Test]
        public void FitWorldShowsTheWholeWideWorldCentred()
        {
            WorldCamera camera = Fitted();
            Assert.AreEqual(6, camera.Scale);
            Assert.AreEqual(6, camera.MinScale);
            Assert.AreEqual(20, camera.Left());
            Assert.AreEqual(133, camera.Top());
            Assert.AreEqual((0, 0), Tile(camera, 20, 133));
            Assert.AreEqual((159, 63), Tile(camera, 979, 516));
            Assert.IsFalse(Inside(camera, 19, 200), "the left margin is no tile");
            Assert.IsFalse(Inside(camera, 980, 200), "the right margin is no tile");
            Assert.IsFalse(Inside(camera, 500, 132), "the margin above");
            Assert.IsFalse(Inside(camera, 500, 517), "the margin below");
        }

        [Test]
        public void FitWorldShowsTheWholeDeepWorldCentred()
        {
            WorldCamera camera = Fitted(64, 160);    // the portrait shape: the depth limits the fit to 4 px
            Assert.AreEqual(4, camera.Scale);
            Assert.AreEqual(372, camera.Left());     // (1000 - 256) / 2
            Assert.AreEqual(5, camera.Top());        // (650 - 640) / 2
            Assert.AreEqual((0, 0), Tile(camera, 372, 5));
            Assert.AreEqual((63, 159), Tile(camera, 627, 644));
            Assert.IsFalse(Inside(camera, 371, 100));
            Assert.IsFalse(Inside(camera, 628, 100));
        }

        [Test]
        public void ZoomKeepsTheTileUnderThePoint()
        {
            WorldCamera camera = Fitted();
            var point = new Vector2(503, 328);    // the middle of tile (80, 32)
            Assert.AreEqual((80, 32), Tile(camera, point.x, point.y));
            foreach (int scale in new[] { 20, 37, 48, 13 })
            {
                camera.ZoomAt(scale, point);
                Assert.AreEqual(scale, camera.Scale);
                Assert.AreEqual((80, 32), Tile(camera, point.x, point.y), $"scale {scale}");
            }
        }

        [Test]
        public void ZoomIsClampedToTheScaleRange()
        {
            WorldCamera camera = Fitted();
            camera.ZoomAt(1000, Vector2.zero);
            Assert.AreEqual(48, camera.Scale);
            camera.ZoomAt(1, Vector2.zero);
            Assert.AreEqual(6, camera.Scale);
            Assert.AreEqual(20, camera.Left(), "back at the fit: centred again");
            Assert.AreEqual(6, camera.NextScale(-1));
            Assert.AreEqual(7, camera.NextScale(1));
        }

        [Test]
        public void PanIsClampedInXAndNeverWraps()
        {
            WorldCamera camera = Fitted();
            camera.Pan(new Vector2(300, 0));       // the whole world is in view: nothing to pan to
            Assert.AreEqual(20, camera.Left());
            camera.ZoomAt(20, Vector2.zero);       // 3200 px of world in a 1000 px view
            camera.Pan(new Vector2(10000, 0));     // drag right: the west edge, no further
            Assert.AreEqual(0.0, camera.OffsetX, 1e-9);
            Assert.AreEqual((0, 16), Tile(camera, 0, 325));    // y: the surface at the top, 325 / 20
            camera.Pan(new Vector2(-10000, 0));    // drag left: the east edge at the right of the view, no seam
            Assert.AreEqual(160 - 1000 / 20.0, camera.OffsetX, 1e-9);
            Assert.AreEqual((159, 16), Tile(camera, 999, 325));
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
        public void AFittedWorldFollowsANewViewSize()
        {
            WorldCamera camera = Fitted();
            camera.SetView(new Vector2(650, 1000));   // the screen turned (or the layout settled): the fit is now 4 px
            Assert.IsTrue(camera.FollowFit);
            Assert.AreEqual(4, camera.Scale, "still the whole world, no refit call needed");
            Assert.AreEqual(5, camera.Left());         // (650 - 640) / 2
            Assert.AreEqual((159, 0), Tile(camera, 644, 500 - 128));
        }

        [Test]
        public void AZoomedWorldKeepsItsZoomOnANewViewSize()
        {
            WorldCamera camera = Fitted();
            camera.Pan(new Vector2(30, 0));           // the whole world is in view: the clamp undoes it, still fitted
            Assert.IsTrue(camera.FollowFit);
            camera.ZoomAt(20, Vector2.zero);
            Assert.IsFalse(camera.FollowFit);
            camera.SetView(new Vector2(650, 1000));
            Assert.AreEqual(20, camera.Scale, "the player's zoom is kept");
            camera.FitWorld();
            Assert.AreEqual(4, camera.Scale);
        }

        [Test]
        public void TileAtRefusesPointsOutsideTheView()
        {
            WorldCamera camera = Fitted();
            camera.ZoomAt(20, Vector2.zero);
            Assert.IsFalse(Inside(camera, -1, 100));
            Assert.IsFalse(Inside(camera, 1000, 100));
            Assert.IsFalse(Inside(camera, 100, 650));
        }
    }
}
