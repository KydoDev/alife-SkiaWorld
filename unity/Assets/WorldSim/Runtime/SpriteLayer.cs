// G3 P5b: the sprite layer over the RGB world. It uploads the ABI 4 tile words (ADR-0016) as a data texture and
// blits the sprite shader (Resources/WorldSimSprites.shader) into a render texture of 5 x 5 pixels per tile; the
// view shows it on top of the RGB image when a tile is at least SpriteArt.Size device pixels wide (LOD).
// Kept apart from WorldSimView so EditMode tests can render a golden world and read the pixels back.
using System;
using UnityEngine;

namespace WorldSim
{
    public sealed class SpriteLayer : IDisposable
    {
        private static readonly int TilesId = Shader.PropertyToID("_Tiles");
        private static readonly int AtlasId = Shader.PropertyToID("_Atlas");
        private static readonly int PaletteId = Shader.PropertyToID("_Palette");
        private static readonly int WidthId = Shader.PropertyToID("_Width");
        private static readonly int HeightId = Shader.PropertyToID("_Height");
        private static readonly int FrameId = Shader.PropertyToID("_Frame");
        private static readonly int DaylightId = Shader.PropertyToID("_Daylight");

        private readonly Texture2D _tiles;
        private readonly Texture2D _atlas;
        private readonly Texture2D _palette;
        private readonly Material _material;
        private readonly byte[] _words;

        public int Width { get; }
        public int Height { get; }

        /// <summary>The sprites: (Width * 5) x (Height * 5), transparent where the RGB world shows through.
        /// </summary>
        public RenderTexture Texture { get; }

        public SpriteLayer(int width, int height)
        {
            Shader shader = Resources.Load<Shader>("WorldSimSprites");
            if (shader == null || !shader.isSupported)
            {
                throw new InvalidOperationException("the WorldSimSprites shader is missing or not supported here");
            }
            Width = width;
            Height = height;
            _words = new byte[width * height * 4];
            // linear: the bytes are bit fields, not colours; point and clamp: read by texel only
            _tiles = new Texture2D(width, height, TextureFormat.RGBA32, false, true)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp,
                name = "WorldSimTiles",
            };
            _atlas = SpriteArt.BuildAtlas();
            _palette = SpriteArt.BuildPalette();
            _material = new Material(shader) { name = "WorldSimSprites" };
            _material.SetTexture(TilesId, _tiles);
            _material.SetTexture(AtlasId, _atlas);
            _material.SetTexture(PaletteId, _palette);
            _material.SetInt(WidthId, width);
            _material.SetInt(HeightId, height);
            Texture = new RenderTexture(width * SpriteArt.Size, height * SpriteArt.Size, 0, RenderTextureFormat.ARGB32)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp,
                useMipMap = false,
                name = "WorldSimSprites",
            };
            Texture.Create();
        }

        /// <summary>Copy the world's tile words into the data texture (call after each step).</summary>
        public void Upload(NativeWorld world)
        {
            world.Tiles(_words);
            _tiles.SetPixelData(_words, 0);
            _tiles.Apply(false);
        }

        /// <summary>Draw the sprites with idle <paramref name="frame"/> (0 or 1) and <paramref name="daylight"/>
        /// (0 night palette ... 1 day palette).</summary>
        public void Render(int frame, float daylight)
        {
            _material.SetInt(FrameId, frame & 1);
            _material.SetFloat(DaylightId, daylight);
            Graphics.Blit(_tiles, Texture, _material);    // _tiles is only the (unused) _MainTex
        }

        public void Dispose()
        {
            Texture.Release();
            Destroy(Texture);
            Destroy(_tiles);
            Destroy(_atlas);
            Destroy(_palette);
            Destroy(_material);
        }

        private static void Destroy(UnityEngine.Object o)
        {
            if (Application.isPlaying)
            {
                UnityEngine.Object.Destroy(o);
            }
            else
            {
                UnityEngine.Object.DestroyImmediate(o);
            }
        }
    }
}
