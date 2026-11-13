// PlayMode tests of the G3 P2/P2b camera in the real view (UI Toolkit panel, Input System): the first view shows the
// whole world; the tile drawn at a screen point is the tile a tap there selects, at three zoom levels and at both x
// edges (the view never wraps); and a virtual mouse reaches the panel (the Input System is the only input backend).
//   Unity -projectPath unity -runTests -testPlatform PlayMode -testResults <file>
// Without -batchmode: the Editor opens a window, and only then do runtime panels receive input (the mouse test
// is skipped in batchmode).
using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.TestTools;
using UnityEngine.UIElements;

namespace WorldSim.PlayTests
{
    public class WorldViewPlayTests
    {
        private const string PanelPath = "Assets/WorldSim/UI/WorldSimPanel.asset";
        private const string LayoutPath = "Assets/WorldSim/UI/WorldSimView.uxml";

        private GameObject _host;
        private WorldSimView _view;
        private Mouse _mouse;
        private Keyboard _keyboard;
        private InputSettings.EditorInputBehaviorInPlayMode _inputBehaviour;
        private InputSettings.BackgroundBehavior _backgroundBehaviour;

        // the default golden start save (160 x 64), from the repository, so the test needs no unity_sync.py
        private static string GoldenSave() => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..",
                                                                              "engine-rs", "tests", "golden",
                                                                              "default", "start.json.gz"));

        private IEnumerator OpenView()
        {
#if UNITY_EDITOR
            _host = new GameObject("WorldSim (test)");
            _host.SetActive(false);
            var document = _host.AddComponent<UIDocument>();
            document.panelSettings = UnityEditor.AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelPath);
            document.visualTreeAsset = UnityEditor.AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(LayoutPath);
            _view = _host.AddComponent<WorldSimView>();
            _view.saveFile = GoldenSave();        // Path.Combine keeps an absolute second path
            _view.toolsFile = "no_tools.json";    // no tools: a tap names the tile
            _view.running = false;
            _host.SetActive(true);
#else
            Assert.Ignore("needs the Editor's AssetDatabase");
#endif
            for (int frame = 0; frame < 60; frame++)
            {
                if (_view.Camera != null && _view.WorldElement.contentRect.height > 0 && _view.Camera.ViewSize.y > 0)
                {
                    yield break;
                }
                yield return null;
            }
            Assert.Fail("the view never got a world and a size");
        }

        [TearDown]
        public void TearDown()
        {
            if (_host != null)
            {
                Object.Destroy(_host);
            }
            if (_mouse != null)
            {
                InputSystem.RemoveDevice(_mouse);
                InputSystem.RemoveDevice(_keyboard);
                InputSystem.settings.editorInputBehaviorInPlayMode = _inputBehaviour;
                InputSystem.settings.backgroundBehavior = _backgroundBehaviour;
                _mouse = null;
            }
        }

        /// <summary>The centre of tile (x, y) as drawn by the world image, in world-local panel units.</summary>
        private static Vector2 DrawnCentre(WorldSimView view, int x, int y)
        {
            Rect r = view.WorldImage.layout;
            WorldCamera camera = view.Camera;
            return new Vector2(r.x + (x + 0.5f) * r.width / camera.Width,
                               r.y + (y + 0.5f) * r.height / camera.Height);
        }

        private static string State(WorldSimView view)
        {
            WorldCamera c = view.Camera;
            return $"screen {Screen.width}x{Screen.height}, k {view.PixelsPerPoint()}, world {view.WorldElement.contentRect}, "
                   + $"view {c.ViewSize}, offset ({c.OffsetX}, {c.OffsetY}), image {view.WorldImage.layout}";
        }

        [UnityTest]
        public IEnumerator FirstViewShowsTheWholeWorld()
        {
            yield return OpenView();
            yield return null;                    // the panel lays the image out
            WorldCamera camera = _view.Camera;
            Assert.AreEqual(camera.MinScale, camera.Scale, "the first view is the fit");
            Rect image = _view.WorldImage.layout;
            Rect view = _view.WorldElement.contentRect;
            const float slack = 0.5f;             // a device pixel rounded to panel units
            Assert.IsTrue(image.xMin >= -slack && image.xMax <= view.width + slack
                          && image.yMin >= -slack && image.yMax <= view.height + slack,
                          $"the world is not wholly inside the view; {State(_view)}");
            var images = _view.WorldElement.Query<Image>().ToList();
            Assert.AreEqual(1, images.FindAll(i => i.image == _view.WorldImage.image).Count, "the world is drawn once");
            Assert.LessOrEqual(images.Count, 3, "the backdrop, the world and at most one sprite layer");
            // P5d: the backdrop fills the view (no black bands) and lies under the world
            Image backdrop = images[0];
            Assert.AreNotSame(_view.WorldImage, backdrop, "the backdrop is drawn first");
            float tile = _view.Camera.Scale / _view.PixelsPerPoint();
            Assert.IsTrue(backdrop.layout.xMin <= slack && backdrop.layout.yMin <= slack
                          && backdrop.layout.xMax >= view.width - slack && backdrop.layout.yMax >= view.height - slack
                          && backdrop.layout.width <= view.width + 2 * tile + slack,
                          $"backdrop {backdrop.layout} does not cover the view {view}; {State(_view)}");
        }

        [UnityTest]
        public IEnumerator SpritesAppearFromFivePixelsPerTileOverTheWorld()
        {
            yield return OpenView();
            WorldCamera camera = _view.Camera;
            Assume.That(_view.SpriteImage, Is.Not.Null, "the sprite shader is supported on this GPU");
            camera.ZoomAt(SpriteArt.Size - 1, Vector2.zero);
            _view.LayoutWorld();
            yield return null;
            Assert.AreEqual(camera.Scale >= SpriteArt.Size, _view.SpritesShown, State(_view));
            if (camera.MinScale < SpriteArt.Size)
            {
                Assert.AreEqual(DisplayStyle.None, _view.SpriteImage.resolvedStyle.display, "flat LOD below 5 px");
            }
            camera.ZoomAt(SpriteArt.Size, Vector2.zero);
            _view.LayoutWorld();
            yield return null;
            Assert.IsTrue(_view.SpritesShown);
            Assert.AreEqual(DisplayStyle.Flex, _view.SpriteImage.resolvedStyle.display);
            Assert.AreEqual(_view.WorldImage.layout, _view.SpriteImage.layout, "the sprites sit on their tiles");
            Assert.AreSame(_view.WorldImage.parent, _view.SpriteImage.parent);
            Assert.Greater(_view.SpriteImage.parent.IndexOf(_view.SpriteImage),
                           _view.WorldImage.parent.IndexOf(_view.WorldImage), "the sprites are drawn over the world");
        }

        [UnityTest]
        public IEnumerator DrawnTileIsTheTappedTileAtThreeZoomsAndBothEdges()
        {
            yield return OpenView();
            WorldCamera camera = _view.Camera;
            Assert.AreEqual(160, camera.Width);
            int[] scales = { camera.MinScale, camera.MinScale + 3, camera.MaxScale };
            foreach (int scale in scales)
            {
                camera.ZoomAt(scale, Vector2.zero);
                foreach ((float drag, int[] xs) in new[] { (1e5f, new[] { 0, 1 }), (-1e5f, new[] { 158, 159 }) })
                {
                    camera.Pan(new Vector2(drag, 0));    // to the west edge, then to the east edge: no seam
                    _view.LayoutWorld();
                    yield return null;                  // the panel lays the image out
                    int row = Mathf.Clamp((int)System.Math.Max(camera.OffsetY, 0) + 1, 0, camera.Height - 1);
                    foreach (int x in xs)
                    {
                        Vector2 centre = DrawnCentre(_view, x, row);
                        Assert.IsTrue(_view.TileAtLocal(centre, out int tx, out int ty),
                                      $"scale {scale}, tile {x}, centre {centre}; {State(_view)}");
                        Assert.AreEqual((x, row), (tx, ty), $"scale {scale}, centre {centre}");
                    }
                }
            }
        }

        [UnityTest]
        public IEnumerator VirtualInputReachesTheView()
        {
            if (Application.isBatchMode)
            {
                // without a window, UI Toolkit gives runtime panels no input (checked: the mouse device gets the
                // events, the panel none); run it in a windowed Editor, see the header
                Assert.Ignore("needs a windowed Editor: Unity -projectPath unity -runTests -testPlatform PlayMode");
            }
            // a virtual mouse and keyboard in the real input system (the UI provider's actions live there); the
            // two settings let their events reach play mode without the Game view's focus
            _inputBehaviour = InputSystem.settings.editorInputBehaviorInPlayMode;
            _backgroundBehaviour = InputSystem.settings.backgroundBehavior;
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            InputSystem.settings.editorInputBehaviorInPlayMode =
                InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;
            _mouse = InputSystem.AddDevice<Mouse>("WorldSim test mouse");
            _keyboard = InputSystem.AddDevice<Keyboard>("WorldSim test keyboard");
            Mouse mouse = _mouse;
            yield return OpenView();
            VisualElement root = _host.GetComponent<UIDocument>().rootVisualElement;
            float k = _view.PixelsPerPoint();
            var seen = new System.Text.StringBuilder();
            root.RegisterCallback<PointerMoveEvent>(e => seen.Append($" move{e.position}"), TrickleDown.TrickleDown);
            root.RegisterCallback<PointerDownEvent>(e => seen.Append($" down{e.position}"), TrickleDown.TrickleDown);
            root.RegisterCallback<PointerUpEvent>(e => seen.Append($" up{e.position}"), TrickleDown.TrickleDown);

            // a click on Play starts the world
            Vector2 play = root.Q<Button>("play").worldBound.center;
            yield return Click(mouse, new Vector2(play.x * k, Screen.height - play.y * k));
            Assert.IsTrue(_view.running, $"the Play button did not receive the click at {play}; mouse {mouse.position.ReadValue()} "
                          + $"pressed {mouse.leftButton.isPressed}; events:{seen}; {State(_view)}");
            _view.running = false;

            // a click on the world names the tile under it
            WorldCamera camera = _view.Camera;
            Vector2 local = DrawnCentre(_view, 3, Mathf.Clamp((int)System.Math.Max(camera.OffsetY, 0) + 2, 0, camera.Height - 1));
            Assert.IsTrue(_view.TileAtLocal(local, out int x, out int y));
            Vector2 panel = _view.WorldElement.LocalToWorld(local);
            yield return Click(mouse, new Vector2(panel.x * k, Screen.height - panel.y * k));
            Assert.AreEqual($"tile ({x}, {y})", root.Q<Label>("tool-status").text);

            // Space toggles play / pause (Keyboard.current, read in Update)
            InputSystem.QueueStateEvent(_keyboard, new KeyboardState(Key.Space));
            yield return null;
            InputSystem.QueueStateEvent(_keyboard, new KeyboardState());
            yield return null;
            Assert.IsTrue(_view.running, "Space did not start the world");
        }

        [UnityTest]
        public IEnumerator TappingACellOpensItsSheetAndTheSheetFollowsIt()
        {
            yield return OpenView();
            yield return null;
            using NativeWorld twin = NativeWorld.Load(File.ReadAllBytes(GoldenSave()));    // the same world, apart
            WorldCamera camera = _view.Camera;
            int w = camera.Width, h = camera.Height;
            int cx = -1, cy = -1, ex = -1, ey = -1;
            for (int i = 0; i < w * h && (cx < 0 || ex < 0); i++)
            {
                bool present = twin.Cell((uint)(i % w), (uint)(i / w)).Present == 1;
                if (present && cx < 0)
                {
                    (cx, cy) = (i % w, i / w);
                }
                else if (!present && ex < 0)
                {
                    (ex, ey) = (i % w, i / w);
                }
            }
            CellRecord want = twin.Cell((uint)cx, (uint)cy);

            _view.TapAt(DrawnCentre(_view, cx, cy));
            Assert.IsTrue(_view.SheetOpen, "a tap on a cell with no tool opens the sheet");
            Assert.AreEqual(want.Id, _view.SelectedId);
            StringAssert.Contains($"#{want.Id}", _view.SheetText);
            StringAssert.Contains($"energy {want.Energy:0.0}", _view.SheetText);

            // one step later the sheet shows the same cell where the kernel put it (or says it was lost)
            _view.StepNow(1);
            twin.Step(1);
            int fx = -1, fy = -1;
            for (int i = 0; i < w * h; i++)
            {
                CellRecord r = twin.Cell((uint)(i % w), (uint)(i / w));
                if (r.Present == 1 && r.Id == want.Id)
                {
                    (fx, fy) = (i % w, i / w);
                }
            }
            if (fx < 0)
            {
                Assert.IsTrue(_view.SelectionLost, "the cell died: the sheet says so");
            }
            else
            {
                Assert.IsFalse(_view.SelectionLost, "a cell moves at most one tile a step");
                Assert.AreEqual(new Vector2Int(fx, fy), _view.SelectedTile);
                Assert.AreEqual(twin.Cell((uint)fx, (uint)fy).Age, _view.SelectedAge());
            }

            _view.TapAt(DrawnCentre(_view, ex, ey));
            Assert.IsFalse(_view.SheetOpen, "a tap on an empty tile closes the sheet");
        }

        [UnityTest]
        public IEnumerator PopulationPanelShowsTheCountsAndTheirHistory()
        {
            yield return OpenView();
            using NativeWorld twin = NativeWorld.Load(File.ReadAllBytes(GoldenSave()));
            Assert.IsFalse(_view.PopulationOpen, "closed at first");
            _view.TogglePopulation();
            yield return null;
            Assert.IsTrue(_view.PopulationOpen);
            int[] c = _view.KindCounts;
            Assert.AreEqual((int)twin.Info.Population, c[1] + c[2] + c[3] + c[4]);
            Assert.AreEqual($"photo {c[1]}  sapro {c[2]}  pred {c[3]}  chemo {c[4]}", _view.PopulationText);
            int before = _view.History.Samples.Count;
            _view.StepNow(5);
            Assert.AreEqual(before + 1, _view.History.Samples.Count, "one sample per redraw");
            _view.TogglePopulation();
            Assert.IsFalse(_view.PopulationOpen);
        }

        // Input System screen coordinates: pixels, origin bottom-left
        private static IEnumerator Click(Mouse mouse, Vector2 screen)
        {
            InputSystem.QueueStateEvent(mouse, new MouseState { position = screen });
            yield return null;
            InputSystem.QueueStateEvent(mouse, new MouseState { position = screen }.WithButton(UnityEngine.InputSystem.LowLevel.MouseButton.Left));
            yield return null;
            InputSystem.QueueStateEvent(mouse, new MouseState { position = screen });
            yield return null;
            yield return null;
        }
    }
}
