// ViewMath: where the scale-to-fit world lands in its element and which tile a click falls in (G3 P1).
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class ViewMathTests
    {
        [Test]
        public void FittedRectLetterboxesAWideArea()
        {
            // a 2:1 world in a 400x100 area: height-bound, 200 wide, centred horizontally
            Rect r = ViewMath.FittedRect(new Rect(10, 20, 400, 100), 200, 100);
            Assert.AreEqual(new Rect(110, 20, 200, 100), r);
        }

        [Test]
        public void FittedRectPillarboxesATallArea()
        {
            // a 2:1 world in a 100x300 area: width-bound, 50 high, centred vertically
            Rect r = ViewMath.FittedRect(new Rect(0, 0, 100, 300), 200, 100);
            Assert.AreEqual(new Rect(0, 125, 100, 50), r);
        }

        [Test]
        public void TileAtMapsCornersAndRowZeroOnTop()
        {
            var drawn = new Rect(100, 50, 200, 100);   // 4x2 tiles of 50x50
            Assert.IsTrue(ViewMath.TileAt(new Vector2(100, 50), drawn, 4, 2, out int x, out int y));
            Assert.AreEqual((0, 0), (x, y));
            Assert.IsTrue(ViewMath.TileAt(new Vector2(299.9f, 149.9f), drawn, 4, 2, out x, out y));
            Assert.AreEqual((3, 1), (x, y));
            Assert.IsTrue(ViewMath.TileAt(new Vector2(175, 60), drawn, 4, 2, out x, out y));
            Assert.AreEqual((1, 0), (x, y));
        }

        [Test]
        public void TileAtRefusesPointsOutsideTheWorld()
        {
            var drawn = new Rect(100, 50, 200, 100);
            Assert.IsFalse(ViewMath.TileAt(new Vector2(99.9f, 60), drawn, 4, 2, out _, out _));   // letterbox
            Assert.IsFalse(ViewMath.TileAt(new Vector2(300, 60), drawn, 4, 2, out _, out _));     // right edge
            Assert.IsFalse(ViewMath.TileAt(new Vector2(150, 150), drawn, 4, 2, out _, out _));    // bottom edge
            Assert.IsFalse(ViewMath.TileAt(new Vector2(150, 49), drawn, 4, 2, out _, out _));     // above
        }
    }
}
