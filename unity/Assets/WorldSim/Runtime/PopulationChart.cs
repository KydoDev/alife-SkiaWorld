// G3 P6b: the population chart, one line per kind over the run, in the kinds' neon base colours (the sprite
// palette's night row). Drawn with UI Toolkit's vector API; the data is a PopulationHistory.
using UnityEngine;
using UnityEngine.UIElements;

namespace WorldSim
{
    public sealed class PopulationChart : VisualElement
    {
        private PopulationHistory _history;

        public PopulationChart()
        {
            AddToClassList("ws-pop__chart");
            pickingMode = PickingMode.Ignore;
            generateVisualContent += Draw;
        }

        public void Show(PopulationHistory history)
        {
            _history = history;
            MarkDirtyRepaint();
        }

        /// <summary>The line colour of a kind (1 photo ... 4 chemo).</summary>
        public static Color KindColour(TileKind kind) => SpriteArt.RoleColour(kind, SpriteArt.Night, SpriteRole.Base);

        private void Draw(MeshGenerationContext context)
        {
            Rect r = contentRect;
            if (_history == null || _history.Samples.Count < 2 || r.width < 2 || r.height < 2)
            {
                return;
            }
            var samples = _history.Samples;
            double first = samples[0].Step, span = System.Math.Max(1.0, samples[samples.Count - 1].Step - first);
            float peak = _history.Peak();
            Painter2D p = context.painter2D;
            p.lineWidth = 2f;
            p.lineJoin = LineJoin.Round;
            foreach (TileKind kind in SpriteArt.Kinds)
            {
                p.strokeColor = KindColour(kind);
                p.BeginPath();
                for (int i = 0; i < samples.Count; i++)
                {
                    float x = r.xMin + (float)((samples[i].Step - first) / span) * r.width;
                    float y = r.yMax - samples[i][(int)kind] / peak * r.height;
                    if (i == 0)
                    {
                        p.MoveTo(new Vector2(x, y));
                    }
                    else
                    {
                        p.LineTo(new Vector2(x, y));
                    }
                }
                p.Stroke();
            }
        }
    }
}
