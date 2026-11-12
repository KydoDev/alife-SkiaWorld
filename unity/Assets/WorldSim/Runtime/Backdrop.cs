// G3 P5d: the margins around the fitted world show the abyss continuing (owner's choice, 2026-11-12): beside the
// world each row carries on as that row's water, or as rock where the world's edge tile is rock; above the surface
// the top row's water; below the floor the deepest rock. Colours are the means of the world's own RGB render, so
// the bands follow day and night with it, dimmed so the playable world stands out. One texel per tile, aligned
// with the world's grid; the world image is drawn over it. Pure, so EditMode tests check it without a panel.
using System;
using UnityEngine;

namespace WorldSim
{
    public static class Backdrop
    {
        /// <summary>Brightness of the margins relative to the world.</summary>
        public const float Dim = 0.55f;

        /// <summary>Colours of the backdrop texels for tiles <c>x0 .. x0 + width - 1</c> and rows
        /// <c>y0 .. y0 + height - 1</c> (world coordinates, row 0 the surface; outside the world is the margin).
        /// The result is a texture's pixels: its first row is the bottom (the deepest row, <c>y0 + height - 1</c>).
        /// </summary>
        /// <param name="rgb">The world's render (ABI 1): row-major from the surface, 3 bytes per tile.</param>
        /// <param name="tiles">The world's tile words (ABI 4), for the rock bit.</param>
        public static Color32[] Compute(byte[] rgb, byte[] tiles, int worldWidth, int worldHeight, int x0, int y0,
                                        int width, int height)
        {
            if (rgb.Length != worldWidth * worldHeight * 3 || tiles.Length != worldWidth * worldHeight * 4)
            {
                throw new ArgumentException("render or tile buffer does not match the world size");
            }
            var water = new Color32[worldHeight];
            var rock = new Color32[worldHeight];
            var hasRock = new bool[worldHeight];
            Color32 deepRock = default;
            bool anyRock = false;
            for (int row = 0; row < worldHeight; row++)
            {
                water[row] = RowMean(rgb, tiles, worldWidth, row, wantRock: false, out _);
                rock[row] = RowMean(rgb, tiles, worldWidth, row, wantRock: true, out hasRock[row]);
                if (hasRock[row])
                {
                    deepRock = rock[row];
                    anyRock = true;
                }
            }
            Color32 floor = anyRock ? deepRock : Scale(water[worldHeight - 1], 0.5f);

            var pixels = new Color32[width * height];
            for (int j = 0; j < height; j++)
            {
                int row = y0 + j;
                for (int i = 0; i < width; i++)
                {
                    int x = x0 + i;
                    Color32 c;
                    if (row < 0)
                    {
                        c = water[0];
                    }
                    else if (row >= worldHeight)
                    {
                        c = floor;
                    }
                    else
                    {
                        int edge = x < 0 ? 0 : x >= worldWidth ? worldWidth - 1 : x;
                        c = IsRock(tiles, row * worldWidth + edge) && hasRock[row] ? rock[row] : water[row];
                    }
                    pixels[(height - 1 - j) * width + i] = Scale(c, Dim);
                }
            }
            return pixels;
        }

        private static bool IsRock(byte[] tiles, int i) => (tiles[i * 4] & 0x10) != 0;

        /// <summary>Mean colour of the row's rock tiles, or of its water tiles (no rock, no cell: the cells would
        /// tint the water).</summary>
        private static Color32 RowMean(byte[] rgb, byte[] tiles, int w, int row, bool wantRock, out bool found)
        {
            long r = 0, g = 0, b = 0, n = 0;
            for (int x = 0; x < w; x++)
            {
                int i = row * w + x;
                bool rockTile = IsRock(tiles, i);
                bool empty = (tiles[i * 4] & 0x7) == 0;
                if (wantRock ? rockTile : !rockTile && empty)
                {
                    r += rgb[i * 3];
                    g += rgb[i * 3 + 1];
                    b += rgb[i * 3 + 2];
                    n++;
                }
            }
            if (n == 0 && !wantRock)
            {
                // a row full of cells or rock: fall back to every non-rock tile, then to the whole row
                for (int x = 0; x < w; x++)
                {
                    int i = row * w + x;
                    r += rgb[i * 3];
                    g += rgb[i * 3 + 1];
                    b += rgb[i * 3 + 2];
                    n++;
                }
            }
            found = n > 0;
            if (n == 0)
            {
                return new Color32(0, 0, 0, 255);
            }
            return new Color32((byte)((r + n / 2) / n), (byte)((g + n / 2) / n), (byte)((b + n / 2) / n), 255);
        }

        private static Color32 Scale(Color32 c, float k) =>
            new Color32((byte)Mathf.RoundToInt(c.r * k), (byte)Mathf.RoundToInt(c.g * k), (byte)Mathf.RoundToInt(c.b * k),
                        255);
    }
}
