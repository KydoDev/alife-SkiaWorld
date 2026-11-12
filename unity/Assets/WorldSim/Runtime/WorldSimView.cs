// G3 P1 front-end shell (docs/G3_PLAN.md): a kernel world shown as a point-filtered texture, with play / pause /
// step / speed, (ADR-0012) "New world" from an exported config and a typed seed, and (ADR-0013) the five G1
// sandbox tools applied with a click, with the parameters Python's GameRules() exports. No budget or milestones
// yet (G3 P7). The UI is UI Toolkit (WorldSimView.uxml / .uss, Neon Abyss palette). G3 P2: the world is seen through
// a WorldCamera (pinch or wheel zoom in whole device pixels per tile, drag to pan); a tap applies the selected tool
// or, with none, names the tile. Input comes from the Input System package. G3 P2b: the whole world is on screen at
// the first view and drawn once (no x wrap in the view); the player picks portrait or landscape, which locks a phone's
// screen and shapes New world (wide or deep).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;
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

        // A gzip save under a name without ".gz": an Android build unpacks *.gz files of StreamingAssets and drops
        // the extension, and the kernel reads gzip only.
        [Tooltip("Save (gzip JSON) in StreamingAssets, copied by scripts/unity_sync.py")]
        public string saveFile = "world.save";

        [Tooltip("Config object in StreamingAssets for New world, exported by scripts/unity_sync.py")]
        public string configFile = "world_config.json";

        [Tooltip("The same planet, deep instead of wide: New world in portrait (G3 P2b), exported by unity_sync.py")]
        public string portraitConfigFile = "world_config_portrait.json";

        [Tooltip("G1 tool parameters in StreamingAssets, exported from GameRules() by scripts/unity_sync.py")]
        public string toolsFile = "game_tools.json";

        [Tooltip("Seed of the next New world (an unsigned 64-bit integer)")]
        public string seedText = "1";

        [Tooltip("Index into the speed table (steps per second)")]
        public int speedIndex = 5;

        [Tooltip("Upper bound of steps per frame, so a slow frame never blocks for long")]
        public int maxStepsPerFrame = 20;

        [Tooltip("Largest zoom, in device pixels per tile")]
        public int maxScale = 48;

        [Tooltip("A press that moves less than this (panel units) and is never joined by a second finger is a tap")]
        public float tapSlop = 8f;

        public bool running = true;

        private NativeWorld _world;
        private WorldCamera _camera;
        private bool _fitPending;            // every world opened starts whole on screen, once the view has a size
        private Vector2Int _fittedScreen;    // the screen size FitView last used (device pixels per point follow it)
        private WorldInfo _info;
        private Texture2D _texture;
        private byte[] _rgb;
        private byte[] _flipped;
        private double _pending;
        private StreamingRead _config;       // read once at Start, used by every New world in landscape
        private StreamingRead _portraitConfig;    // ... and in portrait
        private bool _ready;                 // Start has opened the bundled world: New world may replace it
        private Button _newWorld;
        private Button _orientation;
        private bool _portrait;              // the player's choice (PlayerPrefs); landscape until one is made
        private const string OrientationKey = "worldsim.orientation";
        private ToolSpec[] _tools = Array.Empty<ToolSpec>();
        private int _tool = -1;              // index into _tools; -1: no tool (clicks do nothing)

        // UI Toolkit elements (WorldSimView.uxml)
        private VisualElement _root;
        private VisualElement _worldView;
        private Image _image;                // the world, drawn once (no copies: P2b)
        private Label _stats, _speed, _error, _toolStatus;

        // gestures on the world: the pointers down (panel units, world-local), a tap candidate, a pinch
        private readonly Dictionary<int, Vector2> _pointers = new Dictionary<int, Vector2>();
        private int _tapId = -1;
        private Vector2 _tapStart;
        private bool _dragging;
        private float _pinchStartDistance;
        private int _pinchStartScale;
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

        // On the desktop every read finishes in its constructor, so Start runs to the end in its first frame; on
        // Android the files come out of the APK and Start waits for them (StreamingRead).
        private IEnumerator Start()
        {
            BindUi();
            _portrait = PlayerPrefs.GetInt(OrientationKey, 0) == 1;
            ApplyOrientation();
            var tools = new StreamingRead(toolsFile, MaxToolsBytes);
            _config = new StreamingRead(configFile, MaxConfigBytes);
            _portraitConfig = new StreamingRead(portraitConfigFile, MaxConfigBytes);
            var save = new StreamingRead(saveFile, MaxSaveBytes);
            foreach (StreamingRead read in new[] { tools, _config, _portraitConfig, save })
            {
                if (!read.Done)
                {
                    yield return read.Wait();
                }
            }
            LoadTools(tools);
            if (save.Data == null)
            {
                ShowError($"{save.Error}\n(run scripts/unity_sync.py)");
                Debug.LogError(save.Error);
            }
            else
            {
                Open(() => NativeWorld.Load(save.Data), $"save: {save.Location}");
            }
            // Only now: a New world made while the save was still being read would be replaced by it.
            _ready = true;
            _newWorld?.SetEnabled(true);
            RefreshHud();
        }

        // ------------------------------------------------------------------ UI

        private void BindUi()
        {
            VisualElement doc = GetComponent<UIDocument>().rootVisualElement;
            _root = doc.Q("root");
            _stats = doc.Q<Label>("stats");
            Label title = doc.Q<Label>("title");
            if (title != null)
            {
                title.text += $" v{Application.version}";    // which build is installed, at a glance
            }
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
            _newWorld = Bind(doc, "new-world", NewWorld);
            _newWorld?.SetEnabled(false);    // until Start has read the files (see _ready)
            _orientation = Bind(doc, "orientation", () =>
            {
                _portrait = !_portrait;
                PlayerPrefs.SetInt(OrientationKey, _portrait ? 1 : 0);
                PlayerPrefs.Save();
                ApplyOrientation();
            });
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
            _worldView = doc.Q("world");
            _worldView.RegisterCallback<PointerDownEvent>(OnWorldPointerDown);
            _worldView.RegisterCallback<PointerMoveEvent>(OnWorldPointerMove);
            _worldView.RegisterCallback<PointerUpEvent>(e => EndPointer(e.pointerId, e.localPosition, e.button));
            _worldView.RegisterCallback<PointerCancelEvent>(e => EndPointer(e.pointerId, e.localPosition, -1));
            _worldView.RegisterCallback<PointerCaptureOutEvent>(e => DropPointer(e.pointerId));
            _worldView.RegisterCallback<WheelEvent>(OnWorldWheel);
            _worldView.RegisterCallback<GeometryChangedEvent>(_ => FitView());
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

        /// <summary>The player's orientation: on a phone the screen is locked to it (no autorotation); everywhere it
        /// picks the shape of the next New world. The button names the other orientation, the one it switches to.
        /// </summary>
        private void ApplyOrientation()
        {
            if (Application.isMobilePlatform)
            {
                // both sides of the chosen orientation, so the phone may be held either way up
                Screen.autorotateToPortrait = _portrait;
                Screen.autorotateToPortraitUpsideDown = _portrait;
                Screen.autorotateToLandscapeLeft = !_portrait;
                Screen.autorotateToLandscapeRight = !_portrait;
                Screen.orientation = ScreenOrientation.AutoRotation;
            }
            if (_orientation != null)
            {
                _orientation.text = _portrait ? "Landscape" : "Portrait";
            }
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

        // ------------------------------------------------------------------ camera and gestures

        /// <summary>The camera over the shown world (null without a world); tests read it.</summary>
        public WorldCamera Camera => _camera;

        /// <summary>The world element (the camera's view); tests read its layout.</summary>
        public VisualElement WorldElement => _worldView;

        /// <summary>Device pixels per panel unit (the panel scales with the screen).</summary>
        public float PixelsPerPoint()
        {
            float width = _root?.panel?.visualTree.layout.width ?? 0f;
            return width > 0 && Screen.width > 0 ? Screen.width / width : 1f;
        }

        /// <summary>The tile under a point of the world element (panel units, element-local).</summary>
        public bool TileAtLocal(Vector2 local, out int x, out int y)
        {
            x = y = 0;
            return _camera != null && _camera.TileAt(local * PixelsPerPoint(), out x, out y);
        }

        /// <summary>Give the camera the view's size; a pending fit then shows the whole world.</summary>
        private void FitView()
        {
            if (_camera == null)
            {
                return;
            }
            Vector2 size = _worldView.contentRect.size * PixelsPerPoint();
            if (size.x <= 0 || size.y <= 0)
            {
                return;
            }
            var screen = new Vector2Int(Screen.width, Screen.height);
            if (_fittedScreen != Vector2Int.zero && (screen.x > screen.y) != (_fittedScreen.x > _fittedScreen.y))
            {
                _fitPending = true;    // the screen turned: show the whole world again, whatever the zoom was
            }
            _camera.SetView(size);
            _fittedScreen = screen;
            if (_fitPending)
            {
                _camera.FitWorld();
                _fitPending = false;
            }
            LayoutWorld();
        }

        /// <summary>The world's image element (null before the first world); tests read its layout.</summary>
        public Image WorldImage => _image;

        /// <summary>Place the world's image (whole device pixels, so every tile is the same size).</summary>
        public void LayoutWorld()
        {
            if (_camera == null || _texture == null)
            {
                return;
            }
            float k = PixelsPerPoint();
            if (_image == null)
            {
                _image = new Image { scaleMode = ScaleMode.StretchToFill, pickingMode = PickingMode.Ignore };
                _image.AddToClassList("ws-world-image");
                _worldView.Insert(0, _image);    // under the error label
            }
            _image.image = _texture;
            _image.style.left = _camera.Left() / k;
            _image.style.top = _camera.Top() / k;
            _image.style.width = _camera.Width * _camera.Scale / k;
            _image.style.height = _camera.Height * _camera.Scale / k;
        }

        private void OnWorldPointerDown(PointerDownEvent e)
        {
            _pointers[e.pointerId] = e.localPosition;
            _worldView.CapturePointer(e.pointerId);
            if (_pointers.Count == 1)
            {
                _tapId = e.pointerId;
                _tapStart = e.localPosition;
                _dragging = false;
            }
            else
            {
                _tapId = -1;          // a second finger: this gesture is a pinch, never a tap
                StartPinch();
            }
            e.StopPropagation();
        }

        private void OnWorldPointerMove(PointerMoveEvent e)
        {
            if (!_pointers.TryGetValue(e.pointerId, out Vector2 last) || _camera == null)
            {
                return;
            }
            Vector2 now = e.localPosition;
            float k = PixelsPerPoint();
            if (_pointers.Count == 1)
            {
                if (!_dragging && (now - _tapStart).magnitude > tapSlop)
                {
                    _dragging = true;     // past the slop: a drag, and the pan catches up from the press
                    _tapId = -1;
                    last = _tapStart;
                }
                if (_dragging)
                {
                    _camera.Pan((now - last) * k);
                }
            }
            else
            {
                Vector2 midBefore = Midpoint();
                _pointers[e.pointerId] = now;
                Vector2 mid = Midpoint();
                _camera.Pan((mid - midBefore) * k);
                float distance = PinchDistance();
                if (_pinchStartDistance > 0 && distance > 0)
                {
                    int target = Mathf.RoundToInt(_pinchStartScale * distance / _pinchStartDistance);
                    _camera.ZoomAt(target, mid * k);
                }
            }
            _pointers[e.pointerId] = now;
            LayoutWorld();
            e.StopPropagation();
        }

        private void EndPointer(int pointerId, Vector2 local, int button)
        {
            if (pointerId == _tapId && !_dragging && button == 0 && _pointers.Count == 1)
            {
                Tap(local);
            }
            DropPointer(pointerId);
            if (_worldView.HasPointerCapture(pointerId))
            {
                _worldView.ReleasePointer(pointerId);
            }
        }

        private void DropPointer(int pointerId)
        {
            if (!_pointers.Remove(pointerId))
            {
                return;
            }
            if (pointerId == _tapId)
            {
                _tapId = -1;
            }
            if (_pointers.Count >= 2)
            {
                StartPinch();         // three fingers down to two: restart from the two left
            }
            else
            {
                _dragging = _pointers.Count == 1;   // one finger left after a pinch pans, it never taps
            }
        }

        private void StartPinch()
        {
            _pinchStartDistance = PinchDistance();
            _pinchStartScale = _camera?.Scale ?? 1;
        }

        private void OnWorldWheel(WheelEvent e)
        {
            if (_camera == null || e.delta.y == 0)
            {
                return;
            }
            _camera.ZoomAt(_camera.NextScale(e.delta.y < 0 ? 1 : -1), e.localMousePosition * PixelsPerPoint());
            LayoutWorld();
            e.StopPropagation();
        }

        /// <summary>A tap applies the selected tool to the tile under it, or names the tile.</summary>
        private void Tap(Vector2 local)
        {
            if (_world == null || !TileAtLocal(local, out int x, out int y))
            {
                return;
            }
            if (_tool >= 0)
            {
                ApplyTool((uint)x, (uint)y);
            }
            else
            {
                _toolStatus.text = $"tile ({x}, {y})";
            }
        }

        // the first two pointers down (a pinch uses two fingers; a third is ignored)
        private (Vector2, Vector2) FirstTwo()
        {
            using var it = _pointers.Values.GetEnumerator();
            it.MoveNext();
            Vector2 a = it.Current;
            it.MoveNext();
            return (a, it.Current);
        }

        private Vector2 Midpoint()
        {
            (Vector2 a, Vector2 b) = FirstTwo();
            return (a + b) / 2;
        }

        private float PinchDistance()
        {
            if (_pointers.Count < 2)
            {
                return 0f;
            }
            (Vector2 a, Vector2 b) = FirstTwo();
            return (a - b).magnitude;
        }

        // ------------------------------------------------------------------ world

        /// <summary>Read the tool parameters; without them the viewer works, with no tools.</summary>
        private void LoadTools(StreamingRead read)
        {
            _tools = Array.Empty<ToolSpec>();
            if (read.Data == null)
            {
                _toolStatus.text = "no tools: run scripts/unity_sync.py";
                Debug.LogWarning(read.Error);
            }
            else
            {
                try
                {
                    ToolFile file = JsonUtility.FromJson<ToolFile>(System.Text.Encoding.UTF8.GetString(read.Data));
                    _tools = file?.tools ?? Array.Empty<ToolSpec>();
                    _toolStatus.text = _tools.Length == 0 ? $"no tools in {read.Location}"
                                                          : "pick a tool, then tap the world";
                }
                catch (ArgumentException e)
                {
                    _toolStatus.text = $"no tools ({e.GetType().Name}): run scripts/unity_sync.py";
                }
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
            if (!ulong.TryParse(seedText.Trim(), NumberStyles.None, CultureInfo.InvariantCulture, out ulong seed))
            {
                ShowError($"seed must be an integer from 0 to {ulong.MaxValue}");
                return;
            }
            if (!_ready)
            {
                ShowError("still loading the bundled files");
                return;
            }
            StreamingRead config = _portrait ? _portraitConfig : _config;    // wide in landscape, deep in portrait
            if (config.Data == null)
            {
                ShowError($"{config.Error}\n(run scripts/unity_sync.py)");
                return;
            }
            Open(() => NativeWorld.Create(config.Data, seed), $"config: {config.Location}, seed {seed}");
            RefreshHud();
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
                    _camera = new WorldCamera((int)_info.Width, (int)_info.Height, maxScale);
                }
                _fitPending = true;    // every world opened starts whole on screen, once the view has a size
                FitView();
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
            // a resize that keeps the aspect ratio changes no layout in panel units, so no geometry event comes,
            // yet the device pixels per point change: refit the camera here
            if (_camera != null && (Screen.width != _fittedScreen.x || Screen.height != _fittedScreen.y))
            {
                FitView();
            }
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
            Keyboard keys = Keyboard.current;
            if (keys == null)
            {
                return;               // phones and tablets: no keyboard
            }
            bool changed = true;
            if (keys.spaceKey.wasPressedThisFrame)
            {
                running = !running;
            }
            else if (keys.nKey.wasPressedThisFrame && !running && _world != null)
            {
                Advance(1);
            }
            else if (keys.equalsKey.wasPressedThisFrame || keys.numpadPlusKey.wasPressedThisFrame)
            {
                speedIndex = Math.Min(Speeds.Length - 1, speedIndex + 1);
            }
            else if (keys.minusKey.wasPressedThisFrame || keys.numpadMinusKey.wasPressedThisFrame)
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
            _image?.MarkDirtyRepaint();    // the panel repaints only when something in it is dirty
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
