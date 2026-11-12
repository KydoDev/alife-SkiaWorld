// G3 P1 front-end shell (docs/G3_PLAN.md): a kernel world shown as a point-filtered texture, with play / pause /
// step / speed, (ADR-0012) "New world" from an exported config and a typed seed, and (ADR-0013) the five G1
// sandbox tools applied with a click, with the parameters Python's GameRules() exports. No budget or milestones
// yet (G3 P7). The UI is UI Toolkit (WorldSimView.uxml / .uss, Neon Abyss palette); keys come from the legacy
// Input Manager (no input package until P2).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

namespace WorldSim
{
    [RequireComponent(typeof(UIDocument))]
    public sealed class WorldSimView : MonoBehaviour
    {
        private static readonly int[] Speeds = { 1, 2, 5, 10, 20, 30, 60, 120, 240, 480 };

        // The kernel's caps (WS_MAX_SAVE_LEN, WS_MAX_CONFIG_LEN): larger files are refused before being read.
        private const long MaxSaveBytes = 256L * 1024 * 1024;
        private const long MaxConfigBytes = 64 * 1024;
        private const long MaxToolsBytes = 16 * 1024;

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
        private ToolSpec[] _tools = Array.Empty<ToolSpec>();
        private int _tool = -1;              // index into _tools; -1: no tool (clicks do nothing)

        // UI Toolkit elements (WorldSimView.uxml)
        private VisualElement _root;
        private Image _image;
        private Label _stats, _speed, _error, _toolStatus;
        private Button _play, _step;
        private TextField _seed;
        private readonly List<Button> _toolButtons = new List<Button>();

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
            BindUi();
            LoadTools();
            string path = Path.Combine(Application.streamingAssetsPath, saveFile);
            Open(() => NativeWorld.Load(ReadCapped(path, MaxSaveBytes)), $"save: {path}");
            RefreshHud();
        }

        // ------------------------------------------------------------------ UI

        private void BindUi()
        {
            VisualElement doc = GetComponent<UIDocument>().rootVisualElement;
            _root = doc.Q("root");
            _stats = doc.Q<Label>("stats");
            _speed = doc.Q<Label>("speed");
            _error = doc.Q<Label>("error");
            _toolStatus = doc.Q<Label>("tool-status");
            _play = Bind(doc, "play", () => running = !running);
            _step = Bind(doc, "step", () =>
            {
                if (!running && _world != null)
                {
                    Advance(1);
                }
            });
            Bind(doc, "slower", () => speedIndex = Math.Max(0, speedIndex - 1));
            Bind(doc, "faster", () => speedIndex = Math.Min(Speeds.Length - 1, speedIndex + 1));
            Bind(doc, "new-world", NewWorld);
            _seed = doc.Q<TextField>("seed");
            _seed.value = seedText;
            _seed.RegisterValueChangedCallback(e => seedText = e.newValue);
            // Return in the seed field creates the world (TrickleDown: before the field handles the key)
            _seed.RegisterCallback<KeyDownEvent>(e =>
            {
                if (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter)
                {
                    NewWorld();
                    _seed.Blur();
                    e.StopPropagation();
                }
            }, TrickleDown.TrickleDown);
            _image = new Image { scaleMode = ScaleMode.ScaleToFit, pickingMode = PickingMode.Position };
            _image.AddToClassList("ws-world-image");
            doc.Q("world").Insert(0, _image);
            _image.RegisterCallback<PointerDownEvent>(OnWorldPointerDown);
            _root.RegisterCallback<GeometryChangedEvent>(_ => ApplyLayout());
        }

        /// <summary>A button that runs <paramref name="action"/> and then refreshes the HUD. Buttons never take
        /// the focus, so Space (play / pause) is never also a "submit" of the last button clicked.</summary>
        private Button Bind(VisualElement doc, string name, Action action)
        {
            var button = doc.Q<Button>(name);
            button.focusable = false;
            button.clicked += () =>
            {
                action();
                RefreshHud();
            };
            return button;
        }

        /// <summary>Portrait or landscape classes, and padding for the screen's safe area (notches, bars).</summary>
        private void ApplyLayout()
        {
            if (_root?.panel == null || Screen.width <= 0 || Screen.height <= 0)
            {
                return;
            }
            bool portrait = Screen.height > Screen.width;
            _root.EnableInClassList("ws-portrait", portrait);
            _root.EnableInClassList("ws-landscape", !portrait);
            float k = _root.panel.visualTree.layout.width / Screen.width;   // screen pixels -> panel units
            Rect safe = Screen.safeArea;
            SetIfChanged(_root.style.paddingLeft, safe.xMin * k, v => _root.style.paddingLeft = v);
            SetIfChanged(_root.style.paddingRight, (Screen.width - safe.xMax) * k, v => _root.style.paddingRight = v);
            SetIfChanged(_root.style.paddingTop, (Screen.height - safe.yMax) * k, v => _root.style.paddingTop = v);
            SetIfChanged(_root.style.paddingBottom, safe.yMin * k, v => _root.style.paddingBottom = v);
        }

        private static void SetIfChanged(StyleLength current, float value, Action<StyleLength> set)
        {
            if (current.keyword != StyleKeyword.Undefined || Mathf.Abs(current.value.value - value) > 0.5f)
            {
                set(new StyleLength(value));
            }
        }

        private void RefreshHud()
        {
            if (_stats == null)
            {
                return;
            }
            _stats.text = _world == null ? "no world" : $"step {_info.StepCount}   cells {_info.Population}";
            _speed.text = $"{StepsPerSecond}/s";
            _play.text = running ? "Pause" : "Play";
            _step.SetEnabled(!running && _world != null);
        }

        private void ShowError(string message)
        {
            _error.text = message ?? "";
            _error.style.display = message == null ? DisplayStyle.None : DisplayStyle.Flex;
        }

        /// <summary>One dock button per tool: pick a tool (tap it again to put it down), then tap the world.</summary>
        private void BuildToolDock()
        {
            VisualElement dock = _root.Q("tools");
            dock.Clear();
            _toolButtons.Clear();
            for (int i = 0; i < _tools.Length; i++)
            {
                int index = i;
                var button = new Button(() => SelectTool(index)) { text = _tools[i].name, focusable = false };
                button.AddToClassList("ws-btn");
                button.AddToClassList("ws-tool");
                dock.Add(button);
                _toolButtons.Add(button);
            }
        }

        private void SelectTool(int index)
        {
            _tool = _tool == index ? -1 : index;
            for (int i = 0; i < _toolButtons.Count; i++)
            {
                _toolButtons[i].EnableInClassList("ws-tool--on", i == _tool);
            }
            if (_tool < 0)
            {
                _toolStatus.text = "pick a tool, then tap the world";
            }
        }

        /// <summary>A left click (or a touch) on the world applies the selected tool to the tile under it.</summary>
        private void OnWorldPointerDown(PointerDownEvent e)
        {
            if (e.button != 0 || _tool < 0 || _world == null || _texture == null)
            {
                return;
            }
            Rect drawn = ViewMath.FittedRect(_image.contentRect, _texture.width, _texture.height);
            if (ViewMath.TileAt(e.localPosition, drawn, (int)_info.Width, (int)_info.Height, out int x, out int y))
            {
                ApplyTool((uint)x, (uint)y);
            }
            e.StopPropagation();
        }

        // ------------------------------------------------------------------ world

        /// <summary>Read the tool parameters; without them the viewer works, with no tools.</summary>
        private void LoadTools()
        {
            string path = Path.Combine(Application.streamingAssetsPath, toolsFile);
            try
            {
                string text = System.Text.Encoding.UTF8.GetString(ReadCapped(path, MaxToolsBytes));
                ToolFile file = JsonUtility.FromJson<ToolFile>(text);
                _tools = file?.tools ?? Array.Empty<ToolSpec>();
                _toolStatus.text = _tools.Length == 0 ? $"no tools in {path}" : "pick a tool, then tap the world";
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is ArgumentException)
            {
                _tools = Array.Empty<ToolSpec>();
                _toolStatus.text = $"no tools ({e.GetType().Name}): run scripts/unity_sync.py";
            }
            BuildToolDock();
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
                _toolStatus.text = $"{t.name} at ({x}, {y}): {changed}";
            }
            catch (WorldSimException e)
            {
                _toolStatus.text = e.Message;
                if (e.Status != WorldSimException.StatusInvalid)
                {
                    running = false;    // the world is unusable after a panic
                    ShowError(e.Message);
                    Debug.LogError(e.Message);
                }
            }
            RefreshHud();
        }

        /// <summary>Replace the shown world by one the kernel creates from the exported config and the seed.</summary>
        private void NewWorld()
        {
            string path = Path.Combine(Application.streamingAssetsPath, configFile);
            if (!ulong.TryParse(seedText.Trim(), NumberStyles.None, CultureInfo.InvariantCulture, out ulong seed))
            {
                ShowError($"seed must be an integer from 0 to {ulong.MaxValue}");
                return;
            }
            Open(() => NativeWorld.Create(ReadCapped(path, MaxConfigBytes), seed), $"config: {path}, seed {seed}");
            RefreshHud();
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
                    _image.image = _texture;
                }
                _pending = 0;
                ShowError(null);
                Redraw();
            }
            catch (Exception e) when (e is IOException || e is WorldSimException || e is DllNotFoundException
                                      || e is EntryPointNotFoundException || e is UnauthorizedAccessException
                                      || e is ArgumentException)
            {
                string message = $"{e.GetType().Name}: {e.Message}\n({source}; run scripts/unity_sync.py)";
                ShowError(message);
                Debug.LogError(message);
            }
        }

        private void Update()
        {
            HandleKeys();
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

        /// <summary>Space play / pause, N step, +/- speed; ignored while the seed field has the focus.</summary>
        private void HandleKeys()
        {
            var focused = _root?.panel?.focusController?.focusedElement as VisualElement;
            if (focused != null && (focused == _seed || _seed.Contains(focused)))
            {
                return;
            }
            bool changed = true;
            if (Input.GetKeyDown(KeyCode.Space))
            {
                running = !running;
            }
            else if (Input.GetKeyDown(KeyCode.N) && !running && _world != null)
            {
                Advance(1);
            }
            else if (Input.GetKeyDown(KeyCode.Plus) || Input.GetKeyDown(KeyCode.Equals)
                     || Input.GetKeyDown(KeyCode.KeypadPlus))
            {
                speedIndex = Math.Min(Speeds.Length - 1, speedIndex + 1);
            }
            else if (Input.GetKeyDown(KeyCode.Minus) || Input.GetKeyDown(KeyCode.KeypadMinus))
            {
                speedIndex = Math.Max(0, speedIndex - 1);
            }
            else
            {
                changed = false;
            }
            if (changed)
            {
                RefreshHud();
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
                ShowError(e.Message);
                Debug.LogError(e.Message);
            }
            RefreshHud();
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
            _image.MarkDirtyRepaint();   // the panel repaints only when something in it is dirty
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
