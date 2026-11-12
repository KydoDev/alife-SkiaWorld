// G3 P5b: draws every occupied tile as a 5x5 sprite (docs/G3_PLAN.md, P5) into a render texture of
// (width * 5) x (height * 5) pixels, by Graphics.Blit. Inputs, all read by texel (Load), never filtered:
//   _Tiles   the ABI 4 tile words (ADR-0016) as RGBA32 linear, one texel per tile; texel row 0 = world row 0 (the
//            lit surface), so the world's top is at the texture's bottom and is flipped here;
//   _Atlas   SpriteArt.BuildAtlas: R = colour role, one 5-row band per kind, two frames across;
//   _Palette SpriteArt.BuildPalette: column kind * 4 + role - 1, row 0 night, row 1 day.
// Empty tiles and clear sprite pixels are transparent, so the RGB world under this layer shows through.
Shader "Hidden/WorldSim/Sprites"
{
    Properties
    {
        _MainTex ("Unused (Blit source)", 2D) = "black" {}
    }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always Blend Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"

            Texture2D<float4> _Tiles;
            Texture2D<float4> _Atlas;
            Texture2D<float4> _Palette;
            int _Width;
            int _Height;
            int _Frame;       // 0 or 1, the idle frame of the whole world (each species is offset by its key)
            float _Daylight;  // 0 night palette, 1 day palette (P5c)

            static const int SIZE = 5;

            uint Byte(float v) { return (uint)round(v * 255.0); }

            // the tile word's first two bytes at (x, row), x wrapped (the world is toroidal), row from the surface
            uint2 TileBytes(int x, int row, out uint key)
            {
                x = (x + _Width) % _Width;
                float4 t = _Tiles.Load(int3(x, row, 0));
                key = Byte(t.b) | (Byte(t.a) << 8);
                return uint2(Byte(t.r), Byte(t.g));
            }

            bool Bonded(int x, int row)
            {
                if (row < 0 || row >= _Height) return false;
                uint key;
                uint2 b = TileBytes(x, row, key);
                return (b.x & 7u) != 0u && (b.x & 8u) != 0u;
            }

            float4 frag(v2f_img i) : SV_Target
            {
                int2 px = int2(floor(i.uv * float2(_Width * SIZE, _Height * SIZE)));
                int cx = px.x / SIZE;
                int cyUp = px.y / SIZE;                 // from the bottom of the render texture
                int row = _Height - 1 - cyUp;           // world row, 0 = the surface (top of the image)
                int col = px.x - cx * SIZE;             // sprite column, left to right
                int prow = SIZE - 1 - (px.y - cyUp * SIZE);   // sprite row, 0 at the top

                uint key;
                uint2 b = TileBytes(cx, row, key);
                uint kind = b.x & 7u;
                if (kind == 0u || kind > 4u) return float4(0, 0, 0, 0);
                uint energy = b.y & 15u;
                uint k = kind - 1u;
                uint frame = ((uint)_Frame + key) & 1u;

                float4 a = _Atlas.Load(int3(frame * SIZE + col, k * SIZE + (SIZE - 1 - prow), 0));
                uint role = Byte(a.r);
                if (role == 0u) return float4(0, 0, 0, 0);

                // bonded: the edge shared with a bonded neighbour is drawn in the light colour (approximate: two
                // touching colonies look joined; the word has no bond direction, see docs/G3_PLAN.md)
                if ((b.x & 8u) != 0u)
                {
                    bool edge = (col == 0 && Bonded(cx - 1, row)) || (col == SIZE - 1 && Bonded(cx + 1, row))
                             || (prow == 0 && Bonded(cx, row - 1)) || (prow == SIZE - 1 && Bonded(cx, row + 1));
                    if (edge) role = 2u;
                }

                int column = (int)(k * 4u + role - 1u);
                float3 night = _Palette.Load(int3(column, 0, 0)).rgb;
                float3 day = _Palette.Load(int3(column, 1, 0)).rgb;
                float3 c = lerp(night, day, saturate(_Daylight));

                // starving (energy level 0): desaturated to 35 % and dithered, the design's "dying" look
                if (energy == 0u)
                {
                    if ((prow * 3 + col) % 4 == 0) return float4(0, 0, 0, 0);
                    float grey = dot(c, float3(0.299, 0.587, 0.114));
                    c = lerp(float3(grey, grey, grey), c, 0.35);
                }
                return float4(c, 1);
            }
            ENDCG
        }
    }
}
