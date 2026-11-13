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
        private SpriteLayer _sprites;        // P5b: null where the sprite shader is unsupported (RGB only)
        private bool _spritesStale;          // the world changed since the sprite layer was last drawn
        private int _spriteFrame;            // idle frame, swapped every IdleFrameSeconds
        private float _frameClock;
        private float _frameMs;              // smoothed frame time, shown in the HUD (P5 pass: <= 16 ms on the phone)
        private const float IdleFrameSeconds = 0.5f;
        private byte[] _tileWords;           // ABI 4 tile words of the shown step (rock bits for the backdrop)
        private Texture2D _backdropTexture;  // P5d: the abyss continuing in the margins, one texel per tile
        private static readonly Color EdgeLine = new Color(1f, 1f, 1f, 0.18f);
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
        private Image _spriteImage;          // the sprites over it, shown at >= SpriteArt.Size device px per tile
        private Image _backdrop;             // under the world: the margins (P5d)

        // P6a cell sheet: the selected cell, followed by id after each redraw (CellSheet.Follow)
        private VisualElement _sheet, _marker;
        private Label _sheetTitle, _sheetSummary;
        private readonly List<VisualElement> _shareFills = new List<VisualElement>();
        private readonly List<VisualElement> _geneFills = new List<VisualElement>();
        private bool _selected;
        private bool _selectionLost;
        private int _selX, _selY;
        private CellRecord _selRecord;

        // P6b population panel
        private readonly PopulationHistory _history = new PopulationHistory();
        private VisualElement _populationPanel;
        private PopulationChart _chart;
        private readonly Label[] _countLabels = new Label[5];
        private int[] _counts = new int[5];
        private VisualElement _edge;         // a faint line just outside the world's edge
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
            _sheet = doc.Q("sheet");
            _sheetTitle = doc.Q<Label>("sheet-title");
            _sheetSummary = doc.Q<Label>("sheet-summary");
            Bind(doc, "sheet-close", Deselect);
            BuildBars(doc.Q("sheet-shares"), CellSheet.ShareNames, _shareFills);
            BuildBars(doc.Q("sheet-genes"), CellSheet.GeneNames, _geneFills);
            _populationPanel = doc.Q("population-panel");
            VisualElement countRow = doc.Q("population-counts");
            foreach (TileKind kind in SpriteArt.Kinds)
            {
                var label = new Label();
                label.AddToClassList("ws-pop__count");
                label.style.color = PopulationChart.KindColour(kind);
                countRow.Add(label);
                _countLabels[(int)kind] = label;
            }
            _chart = new PopulationChart();
            _populationPanel.Add(_chart);
            Bind(doc, "population", () =>
            {
                _populationPanel.ToggleInClassList("ws-pop--open");
                ShowPopulation();
            });
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

        private static void BuildBars(VisualElement parent, string[] names, List<VisualElement> fills)
        {
            foreach (string name in names)
            {
                var row = new VisualElement();
                row.AddToClassList("ws-bar-row");
                var label = new Label(name);
                label.AddToClassList("ws-bar-row__name");
                var track = new VisualElement();
                track.AddToClassList("ws-bar-row__track");
                var fill = new VisualElement();
                fill.AddToClassList("ws-bar-row__fill");
                track.Add(fill);
                row.Add(label);
                row.Add(track);
                parent.Add(row);
                fills.Add(fill);
            }
        }

        // ------------------------------------------------------------------ population (P6b)

        /// <summary>True while the population panel is open.</summary>
        public bool PopulationOpen => _populationPanel != null && _populationPanel.ClassListContains("ws-pop--open");

        /// <summary>The shown step's cells per kind (index = TileKind) and the run's history (tests).</summary>
        public int[] KindCounts => _counts;
        public PopulationHistory History => _history;

        /// <summary>The counts' labels in kind order (tests).</summary>
        public string PopulationText =>
            string.Join("  ", System.Linq.Enumerable.Select(SpriteArt.Kinds, k => _countLabels[(int)k]?.text));

        /// <summary>Open or close the population panel, as its button does (tests).</summary>
        public void TogglePopulation()
        {
            _populationPanel?.ToggleInClassList("ws-pop--open");
            ShowPopulation();
        }

        private void ShowPopulation()
        {
            if (!PopulationOpen)
            {
                return;
            }
            foreach (TileKind kind in SpriteArt.Kinds)
            {
                _countLabels[(int)kind].text = $"{kind.ToString().ToLowerInvariant()} {_counts[(int)kind]}";
            }
            _chart.Show(_history);
        }

        // ------------------------------------------------------------------ cell sheet (P6a)

        /// <summary>True while the cell sheet is open.</summary>
        public bool SheetOpen => _selected;

        /// <summary>The selected cell's id and tile, and whether it was lost (moved too far or died).</summary>
        public ulong SelectedId => _selRecord.Id;
        public Vector2Int SelectedTile => new Vector2Int(_selX, _selY);
        public bool SelectionLost => _selectionLost;
        public ulong SelectedAge() => _selRecord.Age;

        /// <summary>The sheet's title and text, for tests.</summary>
        public string SheetText => $"{_sheetTitle?.text}\n{_sheetSummary?.text}";

        /// <summary>A tap at a world-local point, as a finger or the mouse would make it (tests).</summary>
        public void TapAt(Vector2 local) => Tap(local);

        /// <summary>Run <paramref name="steps"/> steps now, as the Step button does (tests).</summary>
        public void StepNow(uint steps) => Advance(steps);

        private void Select(int x, int y, CellRecord record)
        {
            _selected = true;
            _selectionLost = false;
            _selX = x;
            _selY = y;
            _selRecord = record;
            ShowSheet();
        }

        private void Deselect()
        {
            _selected = false;
            _sheet?.RemoveFromClassList("ws-sheet--open");
            if (_marker != null)
            {
                _marker.style.display = DisplayStyle.None;
            }
        }

        private void ShowSheet()
        {
            if (_sheet == null)
            {
                return;
            }
            _sheet.AddToClassList("ws-sheet--open");
            CellRecord r = _selRecord;
            _sheetTitle.text = CellSheet.Title(r) + (_selectionLost ? "  (lost: moved away or died)" : "");
            _sheetSummary.text = CellSheet.Summary(r);
            for (int i = 0; i < _shareFills.Count; i++)
            {
                _shareFills[i].style.width = Length.Percent(Mathf.Clamp01((float)r.Shares[i]) * 100f);
            }
            for (int i = 0; i < _geneFills.Count; i++)
            {
                _geneFills[i].style.width = Length.Percent(Mathf.Clamp01((float)r.Genes[i]) * 100f);
            }
            PlaceMarker(PixelsPerPoint());
        }

        /// <summary>After <paramref name="steps"/> steps, find the selected cell again near its last tile.</summary>
        private void RefreshSelection(uint steps)
        {
            if (!_selected || _selectionLost || _world == null)
            {
                return;
            }
            int radius = (int)Math.Min(steps, (uint)CellSheet.MaxFollowRadius);
            if (CellSheet.Follow((x, y) => _world.Cell((uint)x, (uint)y), (int)_info.Width, (int)_info.Height,
                                 _selX, _selY, _selRecord.Id, radius, out int nx, out int ny, out CellRecord r))
            {
                _selX = nx;
                _selY = ny;
                _selRecord = r;
            }
            else
            {
                _selectionLost = true;    // the last values stay on the sheet
            }
            ShowSheet();
        }

        /// <summary>An outline over the selected tile, in whole device pixels like the world.</summary>
        private void PlaceMarker(float k)
        {
            if (_camera == null || _worldView == null)
            {
                return;
            }
            if (_marker == null)
            {
                _marker = new VisualElement { pickingMode = PickingMode.Ignore };
                _marker.AddToClassList("ws-marker");
                _worldView.Add(_marker);
            }
            bool show = _selected && !_selectionLost;
            _marker.style.display = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (!show)
            {
                return;
            }
            int s = _camera.Scale;
            _marker.style.left = (_camera.Left() + _selX * s) / k;
            _marker.style.top = (_camera.Top() + _selY * s) / k;
            _marker.style.width = s / k;
            _marker.style.height = s / k;
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
            _speed.text = $"{StepsPerSecond}/s  {_frameMs:0.0} ms";
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

        /// <summary>The sprite image (null before the first world or without sprite support); tests read it.
        /// </summary>
        public Image SpriteImage => _spriteImage;

        /// <summary>Sprites are drawn when a tile is at least <see cref="SpriteArt.Size"/> device pixels wide;
        /// below that the flat RGB world is the level of detail.</summary>
        public bool SpritesShown => _sprites != null && _camera != null && _camera.Scale >= SpriteArt.Size;

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
            Place(_image, k);
            PlaceBackdrop(k);
            if (_sprites == null)
            {
                return;
            }
            if (_spriteImage == null)
            {
                _spriteImage = new Image { scaleMode = ScaleMode.StretchToFill, pickingMode = PickingMode.Ignore };
                _spriteImage.AddToClassList("ws-world-image");
                _worldView.Insert(_worldView.IndexOf(_image) + 1, _spriteImage);    // over the world, under the error label
            }
            _spriteImage.image = _sprites.Texture;
            Place(_spriteImage, k);
            _spriteImage.style.display = SpritesShown ? DisplayStyle.Flex : DisplayStyle.None;
            RefreshSprites();
            if (_selected)
            {
                PlaceMarker(k);
            }
        }

        /// <summary>The backdrop covers the view in whole tiles aligned with the world's grid; the edge line sits
        /// one device pixel outside the world, so it never covers a tile.</summary>
        private void PlaceBackdrop(float k)
        {
            if (_tileWords == null)
            {
                return;
            }
            if (_backdrop == null)
            {
                _backdrop = new Image { scaleMode = ScaleMode.StretchToFill, pickingMode = PickingMode.Ignore };
                _backdrop.AddToClassList("ws-world-image");
                _edge = new VisualElement { pickingMode = PickingMode.Ignore };
                _edge.AddToClassList("ws-world-image");
                _worldView.Insert(0, _edge);        // under the world image
                _worldView.Insert(0, _backdrop);    // under everything
            }
            int s = _camera.Scale;
            int x0 = (int)Math.Floor(_camera.OffsetX), y0 = (int)Math.Floor(_camera.OffsetY);
            int w = (int)Math.Ceiling(_camera.OffsetX + _camera.ViewSize.x / s) - x0;
            int h = (int)Math.Ceiling(_camera.OffsetY + _camera.ViewSize.y / s) - y0;
            w = Math.Max(1, w);
            h = Math.Max(1, h);
            if (_backdropTexture == null || _backdropTexture.width != w || _backdropTexture.height != h)
            {
                if (_backdropTexture != null)
                {
                    Destroy(_backdropTexture);
                }
                _backdropTexture = new Texture2D(w, h, TextureFormat.RGBA32, false)
                {
                    filterMode = FilterMode.Point,
                    wrapMode = TextureWrapMode.Clamp,
                    name = "WorldSimBackdrop",
                };
            }
            _backdropTexture.SetPixels32(Backdrop.Compute(_rgb, _tileWords, (int)_info.Width, (int)_info.Height, x0, y0,
                                                          w, h));
            _backdropTexture.Apply(false);
            _backdrop.image = _backdropTexture;
            _backdrop.style.left = (_camera.Left() + x0 * s) / k;
            _backdrop.style.top = (_camera.Top() + y0 * s) / k;
            _backdrop.style.width = w * s / k;
            _backdrop.style.height = h * s / k;
            _backdrop.MarkDirtyRepaint();

            float line = 1f / k;
            _edge.style.left = _camera.Left() / k - line;
            _edge.style.top = _camera.Top() / k - line;
            _edge.style.width = _camera.Width * s / k + 2 * line;
            _edge.style.height = _camera.Height * s / k + 2 * line;
            _edge.style.borderLeftWidth = _edge.style.borderRightWidth = line;
            _edge.style.borderTopWidth = _edge.style.borderBottomWidth = line;
            _edge.style.borderLeftColor = _edge.style.borderRightColor = EdgeLine;
            _edge.style.borderTopColor = _edge.style.borderBottomColor = EdgeLine;
        }

        private void Place(Image image, float k)
        {
            image.style.left = _camera.Left() / k;
            image.style.top = _camera.Top() / k;
            image.style.width = _camera.Width * _camera.Scale / k;
            image.style.height = _camera.Height * _camera.Scale / k;
        }

        /// <summary>Draw the sprite layer if it is shown and out of date; hidden, it waits (no GPU work at the
        /// flat LOD).</summary>
        private void RefreshSprites()
        {
            if (!SpritesShown || !_spritesStale)
            {
                return;
            }
            _sprites.Upload(_world);
            _sprites.Render(_spriteFrame, SpriteArt.Daylight(_info.LightFactor));
            _spritesStale = false;
            _spriteImage?.MarkDirtyRepaint();
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
                return;
            }
            _toolStatus.text = $"tile ({x}, {y})";
            CellRecord record = _world.Cell((uint)x, (uint)y);
            if (record.Present == 1)
            {
                Select(x, y, record);
            }
            else
            {
                Deselect();
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
                RefreshSelection(0);    // an edit kills cells but moves none
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
                Deselect();    // a new world has none of the old cells
                _history.Clear();
                _info = info;
                _rgb = new byte[rgbLength];
                _tileWords = new byte[world.TilesLength];
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
                    _sprites?.Dispose();
                    _sprites = MakeSprites((int)_info.Width, (int)_info.Height);
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

        private static SpriteLayer MakeSprites(int width, int height)
        {
            try
            {
                return new SpriteLayer(width, height);
            }
            catch (InvalidOperationException e)
            {
                Debug.LogWarning($"{e.Message}: the world is drawn without sprites");
                return null;
            }
        }

        /// <summary>Idle frames and the frame-time readout: the sprites swap frame every
        /// <see cref="IdleFrameSeconds"/>, also while paused, and the HUD's frame time is refreshed with them.
        /// </summary>
        private void Tick()
        {
            _frameMs += (Time.unscaledDeltaTime * 1000f - _frameMs) * 0.1f;
            _frameClock += Time.unscaledDeltaTime;
            if (_frameClock < IdleFrameSeconds)
            {
                return;
            }
            _frameClock = 0f;
            _spriteFrame ^= 1;
            _spritesStale = true;
            RefreshSprites();
            RefreshHud();
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
            if (_world != null)
            {
                Tick();
            }
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
                RefreshSelection(steps);
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
            _world.Tiles(_tileWords);
            _counts = Population.Count(_tileWords);
            _history.Add(_info.StepCount, _counts);    // one sample per redraw, thinned as the run grows
            ShowPopulation();
            if (_image != null)
            {
                PlaceBackdrop(PixelsPerPoint());    // the margins follow the world's light and its terrain edits
            }
            _spritesStale = true;
            RefreshSprites();
        }

        private void OnDestroy()
        {
            _sprites?.Dispose();
            _world?.Dispose();
            if (_texture != null)
            {
                Destroy(_texture);
            }
            if (_backdropTexture != null)
            {
                Destroy(_backdropTexture);
            }
        }
    }
}
