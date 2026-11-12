// Screen geometry of the world view, kept apart from the UI so EditMode tests can check it: where a
// scale-to-fit texture lands inside its element, and which tile a point on it falls in.
using UnityEngine;

namespace WorldSim
{
    public static class ViewMath
    {
        /// <summary>Where a <paramref name="width"/> x <paramref name="height"/> image drawn scale-to-fit
        /// (aspect kept, centred) lands inside <paramref name="area"/>.</summary>
        public static Rect FittedRect(Rect area, float width, float height)
        {
            float aspect = width / height;
            float w = area.width, h = area.height;
            if (w / h > aspect)
            {
                w = h * aspect;
            }
            else
            {
                h = w / aspect;
            }
            return new Rect(area.x + (area.width - w) / 2, area.y + (area.height - h) / 2, w, h);
        }

        /// <summary>The tile under <paramref name="point"/> (same space as <paramref name="drawn"/>, y down,
        /// row 0 = the surface at the top); false outside the drawn world.</summary>
        public static bool TileAt(Vector2 point, Rect drawn, int width, int height, out int x, out int y)
        {
            x = Mathf.FloorToInt((point.x - drawn.x) / drawn.width * width);
            y = Mathf.FloorToInt((point.y - drawn.y) / drawn.height * height);
            return x >= 0 && y >= 0 && x < width && y < height;
        }
    }
}
