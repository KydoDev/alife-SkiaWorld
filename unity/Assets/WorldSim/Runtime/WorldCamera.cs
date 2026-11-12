// G3 P2 camera over the world, kept apart from the UI so EditMode tests can check it. Units: device pixels in the
// view (origin top-left, y down) and tiles (row 0 = the surface). The scale is a whole number of device pixels per
// tile, so every tile has the same size on screen. x wraps (the world is toroidal), y is clamped.
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

        /// <summary>The smallest scale: the whole depth fits the view (rounded down, at least 1).</summary>
        public int MinScale { get; private set; } = 1;

        /// <summary>Tile coordinate at the view's left edge, in [0, Width).</summary>
        public double OffsetX { get; private set; }

        /// <summary>Tile coordinate at the view's top edge; negative when the world is shorter than the view
        /// (it is then centred).</summary>
        public double OffsetY { get; private set; }

        public Vector2 ViewSize { get; private set; }

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
            MinScale = Mathf.Clamp(Mathf.FloorToInt(viewSize.y / Height), 1, MaxScale);
            Scale = Mathf.Clamp(Scale, MinScale, MaxScale);
            ClampY();
        }

        /// <summary>The first-run view: the smallest scale (the whole depth), x at tile 0.</summary>
        public void FitHeight()
        {
            Scale = MinScale;
            OffsetX = 0;
            OffsetY = 0;
            ClampY();
        }

        /// <summary>Change the scale so the tile under <paramref name="point"/> stays under it.</summary>
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
            OffsetX = Wrap(tileX - point.x / scale);
            OffsetY = tileY - point.y / scale;
            ClampY();
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
            OffsetX = Wrap(OffsetX - delta.x / Scale);
            OffsetY -= delta.y / Scale;
            ClampY();
        }

        /// <summary>The tile under <paramref name="point"/>; false above or below the world.</summary>
        public bool TileAt(Vector2 point, out int x, out int y)
        {
            x = (int)Wrap(System.Math.Floor(OffsetX + point.x / Scale));
            y = (int)System.Math.Floor(OffsetY + point.y / Scale);
            return y >= 0 && y < Height && point.x >= 0 && point.x < ViewSize.x;
        }

        /// <summary>Where copy 0 of the world starts, in whole device pixels (in (-Width * Scale, 0]); further
        /// copies follow every Width * Scale pixels until the view is covered.</summary>
        public int FirstCopyLeft()
        {
            int left = -(int)System.Math.Round(OffsetX * Scale);
            int period = Width * Scale;
            return left <= -period ? left + period : left;
        }

        /// <summary>The world's top edge, in whole device pixels.</summary>
        public int Top() => -(int)System.Math.Round(OffsetY * Scale);

        /// <summary>How many side-by-side copies cover the view.</summary>
        public int CopiesNeeded()
        {
            int period = Width * Scale;
            return Mathf.Max(1, Mathf.CeilToInt((ViewSize.x - FirstCopyLeft()) / period));
        }

        private double Wrap(double x)
        {
            double r = x % Width;
            if (r < 0)
            {
                r += Width;
            }
            return r >= Width ? 0 : r;   // -1e-17 + Width rounds to Width
        }

        private void ClampY()
        {
            double visible = ViewSize.y / Scale;
            if (visible >= Height)
            {
                OffsetY = -(visible - Height) / 2;     // shorter than the view: centred
            }
            else
            {
                OffsetY = System.Math.Clamp(OffsetY, 0, Height - visible);
            }
        }
    }
}
