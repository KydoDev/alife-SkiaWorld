// G2 M4 front-end: shows a kernel world as a texture, with play / pause / step / speed, (ADR-0012)
// "New world": a world the kernel creates from an exported config and a seed typed in the bar, and (ADR-0013)
// sandbox tools: the five G1 edits applied with a click, with the parameters Python's GameRules() exports.
// No budget or milestones (they stay in Python until G3).
// IMGUI only (no prefabs, no input package): the controls are buttons and keys handled in OnGUI.
using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace WorldSim
{
    public sealed class WorldSimView : MonoBehaviour
    {
        private static readonly int[] Speeds = { 1, 2, 5, 10, 20, 30, 60, 120, 240, 480 };

        // The kernel's caps (WS_MAX_SAVE_LEN, WS_MAX_CONFIG_LEN): larger files are refused before being read.
        private const long MaxSaveBytes = 256L * 1024 * 1024;
        private const long MaxConfigBytes = 64 * 1024;
        private const long MaxToolsBytes = 16 * 1024;
        private const float RowHeight = 30f;

        [Tooltip("Save in StreamingAssets, copied by scripts/unity_sync.py")]
        public string saveFile = "world.json.gz";

        [Tooltip("Config object in StreamingAssets for New world, exported by scripts/unity_sync.py")]
        public string configFile = "world_config.json";

        [Tooltip("G1 tool parameters in StreamingAssets, exported from GameRules() by scripts/unity_sync.py")]
        public string toolsFile = "game_tools.json";

        [Tooltip("Seed of the next New world (an unsigned 64-bit integer)")]
        public string seedText = "1";

        [Tooltip("Index into the speed table (steps per second)")]
        public int speedIndex = 5;

        [Tooltip("Upper bound of steps per frame, so a slow frame never blocks for long")]
        public int maxStepsPerFrame = 20;

        public bool running = true;

        private NativeWorld _world;
        private WorldInfo _info;
        private Texture2D _texture;
        private byte[] _rgb;
        private byte[] _flipped;
        private double _pending;
        private string _error;
        private ToolSpec[] _tools = Array.Empty<ToolSpec>();
        private int _tool = -1;              // index into _tools; -1: no tool (clicks do nothing)
        private string _toolStatus = "";

        // game_tools.json: one entry per G1 tool, the arguments of ws_world_intervene
        [Serializable]
        private class ToolSpec
        {
            public string name;
            public uint kind;
            public uint radius;
            public double amount;
        }

        [Serializable]
        private class ToolFile
        {
            public ToolSpec[] tools;
        }

        public int StepsPerSecond => Speeds[Mathf.Clamp(speedIndex, 0, Speeds.Length - 1)];

        private void Start()
        {
            string path = Path.Combine(Application.streamingAssetsPath, saveFile);
            Open(() => NativeWorld.Load(ReadCapped(path, MaxSaveBytes)), $"save: {path}");
            LoadTools();
        }

        /// <summary>Read the tool parameters; without them the viewer works, with no tools.</summary>
        private void LoadTools()
        {
            string path = Path.Combine(Application.streamingAssetsPath, toolsFile);
            try
            {
                string text = System.Text.Encoding.UTF8.GetString(ReadCapped(path, MaxToolsBytes));
                ToolFile file = JsonUtility.FromJson<ToolFile>(text);
                _tools = file?.tools ?? Array.Empty<ToolSpec>();
                _toolStatus = _tools.Length == 0 ? $"no tools in {path}" : "";
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is ArgumentException)
            {
                _tools = Array.Empty<ToolSpec>();
                _toolStatus = $"no tools ({e.GetType().Name}): run scripts/unity_sync.py";
            }
        }

        /// <summary>Apply the selected tool at tile (x, y), between steps; a refusal changes nothing.</summary>
        private void ApplyTool(uint x, uint y)
        {
            ToolSpec t = _tools[_tool];
            try
            {
                ulong changed = _world.Intervene((Edit)t.kind, x, y, t.radius, t.amount);
                _info = _world.Info;
                Redraw();
                _toolStatus = $"{t.name} at ({x}, {y}): {changed}";
            }
            catch (WorldSimException e)
            {
                _toolStatus = e.Message;
                if (e.Status != WorldSimException.StatusInvalid)
                {
                    running = false;    // the world is unusable after a panic
                    _error = e.Message;
                    Debug.LogError(_error);
                }
            }
        }

        /// <summary>Where ScaleToFit draws the texture inside <paramref name="area"/>.</summary>
        private Rect FittedRect(Rect area)
        {
            float aspect = (float)_texture.width / _texture.height;
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

        /// <summary>A left click on the world applies the selected tool to the tile under the mouse.</summary>
        private void HandleClick(Event e, Rect drawn)
        {
            if (e.type != EventType.MouseDown || e.button != 0 || _tool < 0 || _world == null
                || !drawn.Contains(e.mousePosition))
            {
                return;
            }
            // row 0 (the surface) is drawn at the top: texture rows were flipped in Redraw
            int x = Mathf.FloorToInt((e.mousePosition.x - drawn.x) / drawn.width * _info.Width);
            int y = Mathf.FloorToInt((e.mousePosition.y - drawn.y) / drawn.height * _info.Height);
            if (x >= 0 && y >= 0 && x < _info.Width && y < _info.Height)   // the kernel refuses the rest anyway
            {
                ApplyTool((uint)x, (uint)y);
            }
            e.Use();
        }

        /// <summary>Replace the shown world by one the kernel creates from the exported config and the seed.</summary>
        private void NewWorld()
        {
            string path = Path.Combine(Application.streamingAssetsPath, configFile);
            if (!ulong.TryParse(seedText.Trim(), NumberStyles.None, CultureInfo.InvariantCulture, out ulong seed))
            {
                _error = $"seed must be an integer from 0 to {ulong.MaxValue}";
                return;
            }
            Open(() => NativeWorld.Create(ReadCapped(path, MaxConfigBytes), seed), $"config: {path}, seed {seed}");
        }

        private static byte[] ReadCapped(string path, long limit)
        {
            long length = new FileInfo(path).Length;
            if (length > limit)
            {
                throw new IOException($"{path} is {length} bytes, more than the {limit} the kernel accepts");
            }
            return File.ReadAllBytes(path);
        }

        /// <summary>Show the world <paramref name="make"/> returns; on failure keep the current one.</summary>
        private void Open(Func<NativeWorld> make, string source)
        {
            try
            {
                NativeWorld world = make();
                WorldInfo info;
                int rgbLength;
                try
                {
                    info = world.Info;
                    rgbLength = world.RgbLength;
                }
                catch
                {
                    world.Dispose();
                    throw;
                }
                _world?.Dispose();   // only now: on failure the current world stays
                _world = world;
                _info = info;
                _rgb = new byte[rgbLength];
                _flipped = new byte[rgbLength];
                if (_texture == null || _texture.width != (int)_info.Width || _texture.height != (int)_info.Height)
                {
                    if (_texture != null)
                    {
                        Destroy(_texture);
                    }
                    _texture = new Texture2D((int)_info.Width, (int)_info.Height, TextureFormat.RGB24, false)
                    {
                        filterMode = FilterMode.Point,
                        wrapMode = TextureWrapMode.Clamp,
                        name = "WorldSim",
                    };
                }
                _pending = 0;
                _error = null;
                Redraw();
            }
            catch (Exception e) when (e is IOException || e is WorldSimException || e is DllNotFoundException
                                      || e is EntryPointNotFoundException || e is UnauthorizedAccessException
                                      || e is ArgumentException)
            {
                _error = $"{e.GetType().Name}: {e.Message}\n({source}; run scripts/unity_sync.py)";
                Debug.LogError(_error);
            }
        }

        private void Update()
        {
            if (_world == null || !running)
            {
                return;
            }
            _pending += Time.deltaTime * StepsPerSecond;
            int steps = (int)Math.Min(_pending, maxStepsPerFrame);
            _pending = Math.Min(_pending - steps, 1.0);   // drop what a slow frame could not run
            if (steps > 0)
            {
                Advance((uint)steps);
            }
        }

        private void Advance(uint steps)
        {
            try
            {
                _world.Step(steps);
                _info = _world.Info;
                Redraw();
            }
            catch (WorldSimException e)
            {
                running = false;
                _error = e.Message;
                Debug.LogError(_error);
            }
        }

        /// <summary>Render, flip rows (row 0 is the surface; texture row 0 is the bottom), upload.</summary>
        private void Redraw()
        {
            _world.RenderRgb(_rgb);
            int stride = (int)_info.Width * 3;
            int rows = (int)_info.Height;
            for (int y = 0; y < rows; y++)
            {
                Buffer.BlockCopy(_rgb, y * stride, _flipped, (rows - 1 - y) * stride, stride);
            }
            _texture.SetPixelData(_flipped, 0);
            _texture.Apply(false);
        }

        private void OnGUI()
        {
            HandleKeys(Event.current);
            float bar = _tools.Length > 0 || _toolStatus.Length > 0 ? 2 * RowHeight + 2 : RowHeight + 2;
            if (_texture != null)
            {
                Rect drawn = FittedRect(new Rect(0, bar, Screen.width, Screen.height - bar));
                HandleClick(Event.current, drawn);
                GUI.DrawTexture(drawn, _texture, ScaleMode.StretchToFill);
            }
            GUILayout.BeginArea(new Rect(4, 4, Screen.width - 8, RowHeight - 2));
            GUILayout.BeginHorizontal();
            if (GUILayout.Button(running ? "Pause" : "Play", GUILayout.Width(70)))
            {
                running = !running;
            }
            GUI.enabled = !running && _world != null;
            if (GUILayout.Button("Step", GUILayout.Width(50)))
            {
                Advance(1);
            }
            GUI.enabled = true;
            if (GUILayout.Button("-", GUILayout.Width(28)))
            {
                speedIndex = Math.Max(0, speedIndex - 1);
            }
            if (GUILayout.Button("+", GUILayout.Width(28)))
            {
                speedIndex = Math.Min(Speeds.Length - 1, speedIndex + 1);
            }
            GUILayout.Label("seed", GUILayout.Width(32));
            seedText = GUILayout.TextField(seedText, 20, GUILayout.Width(150));
            if (GUILayout.Button("New world", GUILayout.Width(90)))
            {
                GUIUtility.keyboardControl = 0;   // give the keys back to the controls
                NewWorld();
            }
            GUILayout.Label(_world == null
                ? "no world"
                : $"step {_info.StepCount}   cells {_info.Population}   {StepsPerSecond} steps/s   "
                  + "(Space play/pause, N step, +/- speed)");
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
            if (bar > RowHeight + 2)
            {
                ToolBar(new Rect(4, RowHeight + 4, Screen.width - 8, RowHeight - 2));
            }
            if (_error != null)
            {
                GUI.Label(new Rect(8, bar + 8, Screen.width - 16, 120), _error);
            }
        }

        /// <summary>Second row: pick a tool (click it again to put it down), then click the world.</summary>
        private void ToolBar(Rect row)
        {
            GUILayout.BeginArea(row);
            GUILayout.BeginHorizontal();
            GUILayout.Label("tool", GUILayout.Width(32));
            for (int i = 0; i < _tools.Length; i++)
            {
                bool on = GUILayout.Toggle(_tool == i, _tools[i].name, "Button", GUILayout.Width(90));
                if (on != (_tool == i))
                {
                    _tool = on ? i : -1;
                }
            }
            GUILayout.Label(_tool < 0 && _toolStatus.Length == 0 ? "(pick a tool, then click the world)" : _toolStatus);
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        private void HandleKeys(Event e)
        {
            if (e.type != EventType.KeyDown)
            {
                return;
            }
            if (GUIUtility.keyboardControl != 0)
            {
                // the seed field has the focus: keys type into it; Return creates the world
                if (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter)
                {
                    GUIUtility.keyboardControl = 0;
                    NewWorld();
                    e.Use();
                }
                return;
            }
            switch (e.keyCode)
            {
                case KeyCode.Space:
                    running = !running;
                    break;
                case KeyCode.N when !running && _world != null:
                    Advance(1);
                    break;
                case KeyCode.Plus:
                case KeyCode.Equals:
                case KeyCode.KeypadPlus:
                    speedIndex = Math.Min(Speeds.Length - 1, speedIndex + 1);
                    break;
                case KeyCode.Minus:
                case KeyCode.KeypadMinus:
                    speedIndex = Math.Max(0, speedIndex - 1);
                    break;
                default:
                    return;
            }
            e.Use();
        }

        private void OnDestroy()
        {
            _world?.Dispose();
            if (_texture != null)
            {
                Destroy(_texture);
            }
        }
    }
}
