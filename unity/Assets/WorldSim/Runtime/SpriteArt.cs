// G3 P5 sprite art: the 5x5 cell sprites and the neon palette of the design reference (docs/G3_PLAN.md, "Design
// reference"), as two small textures the sprite shader reads. The atlas stores a colour *role* per pixel, not a
// colour, so night and day (P5c) only swap palette rows. EditMode tests check this data against the table in the doc.
using System;
using UnityEngine;

namespace WorldSim
{
    /// <summary>Colour role of one sprite pixel: transparent, base, light, shade, eye.</summary>
    public enum SpriteRole : byte
    {
        Clear = 0,
        Base = 1,
        Light = 2,
        Shade = 3,
        Eye = 4,
    }

    public static class SpriteArt
    {
        public const int Size = 5;     // pixels per sprite side
        public const int Frames = 2;   // idle frames
        public const int Roles = 4;    // Base, Light, Shade, Eye
        public const int Night = 0, Day = 1;

        /// <summary>The kinds with a sprite, in <see cref="TileKind"/> order (Photo = 1 ... Chemo = 4).</summary>
        public static readonly TileKind[] Kinds = { TileKind.Photo, TileKind.Sapro, TileKind.Pred, TileKind.Chemo };

        // Frames as in the design table: five rows top to bottom, B base, H light, D shade, E eye, '.' clear.
        private static readonly string[][] FrameRows =
        {
            new[] { ".BHB. BHBBB BBEBD BBBDD .DDD.", ".BHB. BBHBB BBEBB DBBBD .DDD." },   // photo
            new[] { ".BB.. BHBBB BBEB. .BBBD B.DD.", "..BB. BBHBB .BEBB DBBB. .DD.B" },   // sapro
            new[] { "B.B.B .DBD. BBEBB .DBD. B.B.B", ".B.B. BDBDB .BEB. BDBDB .B.B." },   // pred
            new[] { "..H.. .HBB. HBEBD .BBD. ..D..", "..H.. .BHB. HBEBD .DBB. ..D.." },   // chemo
        };

        // base, light, shade per kind; [Night] then [Day]. The eye is the light colour, white for predators.
        private static readonly string[][,] PaletteHex =
        {
            new[,] { { "#59ffa0", "#d8ffe8", "#1f8a52" }, { "#a6ff4a", "#e4ffb8", "#4f9a1e" } },   // photo
            new[,] { { "#ffcc33", "#fff4c4", "#9a6a08" }, { "#ffc23a", "#fff0b0", "#a8680e" } },   // sapro
            new[,] { { "#ff3fd1", "#ffd6f4", "#6a0456" }, { "#ff3fd1", "#ffd6f4", "#7a0a62" } },   // pred
            new[,] { { "#39f5e0", "#e0fffb", "#127a72" }, { "#39f5e0", "#c8fff8", "#178a80" } },   // chemo
        };

        /// <summary>The design-table string of a kind's frame (five rows, top to bottom, space separated).</summary>
        public static string FrameString(TileKind kind, int frame) => FrameRows[KindIndex(kind)][frame];

        /// <summary>Hex colour of a kind's base (0), light (1) or shade (2) at night or by day.</summary>
        public static string PaletteString(TileKind kind, int time, int shade) => PaletteHex[KindIndex(kind)][time, shade];

        public static int KindIndex(TileKind kind)
        {
            int i = (int)kind - 1;
            if (i < 0 || i >= Kinds.Length)
            {
                throw new ArgumentOutOfRangeException(nameof(kind), kind, "no sprite for this kind");
            }
            return i;
        }

        /// <summary>Role of pixel (<paramref name="col"/>, <paramref name="row"/>), row 0 at the top.</summary>
        public static SpriteRole RoleAt(TileKind kind, int frame, int col, int row)
        {
            char c = FrameString(kind, frame)[row * (Size + 1) + col];
            return c switch
            {
                '.' => SpriteRole.Clear,
                'B' => SpriteRole.Base,
                'H' => SpriteRole.Light,
                'D' => SpriteRole.Shade,
                'E' => SpriteRole.Eye,
                _ => throw new FormatException($"bad sprite pixel '{c}' in {kind} frame {frame}"),
            };
        }

        public static Color32 RoleColour(TileKind kind, int time, SpriteRole role)
        {
            switch (role)
            {
                case SpriteRole.Base: return Hex(PaletteString(kind, time, 0));
                case SpriteRole.Light: return Hex(PaletteString(kind, time, 1));
                case SpriteRole.Shade: return Hex(PaletteString(kind, time, 2));
                case SpriteRole.Eye:
                    return kind == TileKind.Pred ? new Color32(255, 255, 255, 255) : Hex(PaletteString(kind, time, 1));
                default: return new Color32(0, 0, 0, 0);
            }
        }

        /// <summary>The role atlas: <see cref="Frames"/> sprites across, one kind per band, kind 0 at the bottom
        /// (texture rows grow upwards); a pixel's R channel is its role. Linear, point-filtered, no mips.</summary>
        public static Texture2D BuildAtlas()
        {
            int w = Frames * Size, h = Kinds.Length * Size;
            var pixels = new Color32[w * h];
            for (int k = 0; k < Kinds.Length; k++)
            {
                for (int f = 0; f < Frames; f++)
                {
                    for (int row = 0; row < Size; row++)
                    {
                        for (int col = 0; col < Size; col++)
                        {
                            int x = f * Size + col, y = k * Size + (Size - 1 - row);
                            pixels[y * w + x] = new Color32((byte)RoleAt(Kinds[k], f, col, row), 0, 0, 255);
                        }
                    }
                }
            }
            return Texture(w, h, pixels, linear: true);
        }

        /// <summary>The palette: column <c>kind * Roles + role - 1</c>, row <see cref="Night"/> or
        /// <see cref="Day"/>. Gamma colours: the project is in gamma space, so the hex values come out as written.
        /// </summary>
        public static Texture2D BuildPalette()
        {
            int w = Kinds.Length * Roles;
            var pixels = new Color32[w * 2];
            for (int time = Night; time <= Day; time++)
            {
                for (int k = 0; k < Kinds.Length; k++)
                {
                    for (int r = 1; r <= Roles; r++)
                    {
                        pixels[time * w + k * Roles + r - 1] = RoleColour(Kinds[k], time, (SpriteRole)r);
                    }
                }
            }
            return Texture(w, 2, pixels, linear: false);
        }

        private static Texture2D Texture(int w, int h, Color32[] pixels, bool linear)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, false, linear)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp,
            };
            t.SetPixels32(pixels);
            t.Apply(false, false);
            return t;
        }

        public static Color32 Hex(string hex)
        {
            if (!ColorUtility.TryParseHtmlString(hex, out Color c))
            {
                throw new FormatException($"bad colour '{hex}'");
            }
            return c;
        }
    }
}
