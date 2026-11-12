// G3 camera over the world, kept apart from the UI so EditMode tests can check it. Units: device pixels in the
// view (origin top-left, y down) and tiles (row 0 = the surface). The scale is a whole number of device pixels per
// tile, so every tile has the same size on screen. The world is drawn once (P2b, owner's rule): the simulation is
// toroidal in x, but the view never repeats it; both axes are clamped, and an axis shorter than the view is centred.
using UnityEngine;

namespace WorldSim
{
    public sealed class WorldCamera
    {
        public int Width { get; }
        public int Height { get; }
        public int MaxScale { get; }

        /// <summary>Device pixels per tile, from <see cref="MinScale"/> to <see cref="MaxScale"/>.</summary>
        public int Scale { get; private set; }

        /// <summary>The smallest scale: the whole world, width and depth, fits the view (rounded down, at least 1).
        /// </summary>
        public int MinScale { get; private set; } = 1;

        /// <summary>Tile coordinate at the view's left edge; negative when the world is narrower than the view (it
        /// is then centred).</summary>
        public double OffsetX { get; private set; }

        /// <summary>Tile coordinate at the view's top edge; negative when the world is shorter than the view.</summary>
        public double OffsetY { get; private set; }

        public Vector2 ViewSize { get; private set; }

        /// <summary>Set by <see cref="FitWorld"/>, cleared when the player zooms or pans: while set, every new view
        /// size refits, so a fit taken on a stale or still-changing layout (a screen turn, the safe-area padding)
        /// corrects itself on the next size.</summary>
        public bool FollowFit { get; private set; }

        public WorldCamera(int width, int height, int maxScale)
        {
            Width = width;
            Height = height;
            MaxScale = Mathf.Max(1, maxScale);
            Scale = 1;
        }

        /// <summary>Set the view's size; the scale and offsets are kept as far as the new size allows.</summary>
        public void SetView(Vector2 viewSize)
        {
            ViewSize = viewSize;
            int fit = Mathf.FloorToInt(Mathf.Min(viewSize.x / Width, viewSize.y / Height));
            MinScale = Mathf.Clamp(fit, 1, MaxScale);
            Scale = FollowFit ? MinScale : Mathf.Clamp(Scale, MinScale, MaxScale);
            Clamp();
        }

        /// <summary>The first view: the smallest scale, so the whole world is on screen, centred.</summary>
        public void FitWorld()
        {
            Scale = MinScale;
            OffsetX = 0;
            OffsetY = 0;
            FollowFit = true;
            Clamp();
        }

        /// <summary>Change the scale so the tile under <paramref name="point"/> stays under it (as far as the
        /// clamp allows).</summary>
        public void ZoomAt(int scale, Vector2 point)
        {
            scale = Mathf.Clamp(scale, MinScale, MaxScale);
            if (scale == Scale)
            {
                return;
            }
            double tileX = OffsetX + point.x / Scale;
            double tileY = OffsetY + point.y / Scale;
            Scale = scale;
            FollowFit = false;
            OffsetX = tileX - point.x / scale;
            OffsetY = tileY - point.y / scale;
            Clamp();
        }

        /// <summary>The next scale up or down (about a quarter at a time, at least one step).</summary>
        public int NextScale(int direction)
        {
            int step = Mathf.Max(1, Scale / 4);
            return Mathf.Clamp(Scale + (direction > 0 ? step : -step), MinScale, MaxScale);
        }

        /// <summary>Move the world by <paramref name="delta"/> device pixels (a drag to the right shows what is
        /// on the left).</summary>
        public void Pan(Vector2 delta)
        {
            double x = OffsetX, y = OffsetY;
            OffsetX -= delta.x / Scale;
            OffsetY -= delta.y / Scale;
            Clamp();
            if (OffsetX != x || OffsetY != y)
            {
                FollowFit = false;    // a pan that moved the world; one that the clamp undid keeps the fit
            }
        }

        /// <summary>The world's left edge, in whole device pixels.</summary>
        public int Left() => -(int)System.Math.Round(OffsetX * Scale);

        /// <summary>The world's top edge, in whole device pixels.</summary>
        public int Top() => -(int)System.Math.Round(OffsetY * Scale);

        /// <summary>The tile under <paramref name="point"/>, measured from the drawn edges, so the tile a tap
        /// names is the tile drawn there; false in the margins around the world and outside the view.</summary>
        public bool TileAt(Vector2 point, out int x, out int y)
        {
            x = (int)System.Math.Floor((point.x - Left()) / Scale);
            y = (int)System.Math.Floor((point.y - Top()) / Scale);
            return x >= 0 && x < Width && y >= 0 && y < Height
                   && point.x >= 0 && point.x < ViewSize.x && point.y >= 0 && point.y < ViewSize.y;
        }

        private void Clamp()
        {
            OffsetX = ClampAxis(OffsetX, ViewSize.x / Scale, Width);
            OffsetY = ClampAxis(OffsetY, ViewSize.y / Scale, Height);
        }

        private static double ClampAxis(double offset, double visible, int size)
        {
            return visible >= size
                ? -(visible - size) / 2                          // shorter than the view: centred
                : System.Math.Clamp(offset, 0, size - visible);
        }
    }
}
