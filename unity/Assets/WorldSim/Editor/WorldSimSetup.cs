// Builds the front-end scene and the render pipeline settings from code, so they can be regenerated
// instead of hand-edited.
//   Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.CreateScene
//   Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.ConfigureRenderPipeline
//   Unity -batchmode -quit -projectPath unity -buildTarget Android -executeMethod WorldSim.EditorTools.WorldSimSetup.BuildAndroid [-appVersion X.Y.Z]
//   (the APK is Builds/Android/worldsim-<version>.apk; -appVersion first sets the version, see SetVersion)
//   (BuildAndroidCheck: the G3 P3 device check, normally run by scripts/android_check.py)
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UIElements;

namespace WorldSim.EditorTools
{
    public static class WorldSimSetup
    {
        public const string ScenePath = "Assets/Scenes/WorldSim.unity";
        public const string PipelineAssetPath = "Assets/Settings/WorldSim_URP.asset";
        public const string RendererAssetPath = "Assets/Settings/WorldSim_URP_Renderer.asset";
        public const string LayoutPath = "Assets/WorldSim/UI/WorldSimView.uxml";
        public const string ThemePath = "Assets/WorldSim/UI/WorldSimTheme.tss";
        public const string PanelSettingsPath = "Assets/WorldSim/UI/WorldSimPanel.asset";
        public const string CheckScenePath = "Assets/Scenes/DeviceCheck.unity";
        public const string AndroidLibPath = "Assets/Plugins/Android/arm64-v8a/libworldsim_core.so";
        public const string WindowsLibPath = "Assets/Plugins/x86_64/worldsim_core.dll";
        // Provisional: the store name and its trademark check are still open (G3_PLAN "Design reference").
        public const string AndroidId = "com.kydodev.worldsim";
        public const string AndroidCheckId = "com.kydodev.worldsim.check";
        public const string AndroidApkFolder = "Builds/Android";
        public const string AndroidCheckApk = "Builds/Android/worldsim-check.apk";

        [MenuItem("WorldSim/Create front-end scene")]
        public static void CreateScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.orthographic = true;
            // The whole view is a UI Toolkit panel drawn over the camera's clear, so URP needs no
            // post-processing, anti-aliasing or depth texture here.
            var cameraData = camera.gameObject.AddComponent<UniversalAdditionalCameraData>();
            cameraData.renderPostProcessing = false;
            cameraData.antialiasing = AntialiasingMode.None;
            var view = new GameObject("WorldSim");
            var document = view.AddComponent<UIDocument>();
            document.panelSettings = PanelSettingsAsset();
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(LayoutPath)
                                       ?? throw new System.IO.FileNotFoundException(LayoutPath);
            view.AddComponent<WorldSimView>();
            System.IO.Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            Debug.Log($"WorldSim: scene written to {ScenePath}");
        }

        // The panel the view draws into: the Neon Abyss theme, scaled from a 1280x720 reference so the
        // same layout reads on a desktop window and on a phone (G3 P1). Created once, then reused.
        private static PanelSettings PanelSettingsAsset()
        {
            var panel = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            if (panel != null)
            {
                return panel;
            }
            panel = ScriptableObject.CreateInstance<PanelSettings>();
            panel.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(ThemePath)
                                    ?? throw new System.IO.FileNotFoundException(ThemePath);
            panel.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            panel.referenceResolution = new Vector2Int(1280, 720);
            panel.screenMatchMode = PanelScreenMatchMode.MatchWidthOrHeight;
            panel.match = 0.5f;
            AssetDatabase.CreateAsset(panel, PanelSettingsPath);
            AssetDatabase.SaveAssets();
            return panel;
        }

        // Creates (or reuses) the URP asset and its renderer, then assigns it in Graphics settings and in
        // every Quality level. Idempotent: running it again changes nothing.
        [MenuItem("WorldSim/Configure render pipeline (URP)")]
        public static void ConfigureRenderPipeline()
        {
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelineAssetPath);
            if (pipeline == null)
            {
                System.IO.Directory.CreateDirectory("Assets/Settings");
                // No PostProcessData: the viewer is a UI Toolkit panel and uses no post-processing.
                var renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(renderer, RendererAssetPath);
                pipeline = UniversalRenderPipelineAsset.Create(renderer);
                pipeline.msaaSampleCount = 1;
                AssetDatabase.CreateAsset(pipeline, PipelineAssetPath);
            }

            GraphicsSettings.defaultRenderPipeline = pipeline;
            int current = QualitySettings.GetQualityLevel();
            for (int level = 0; level < QualitySettings.names.Length; level++)
            {
                QualitySettings.SetQualityLevel(level, false);
                QualitySettings.renderPipeline = pipeline;
            }
            QualitySettings.SetQualityLevel(current, false);
            AssetDatabase.SaveAssets();
            Debug.Log($"WorldSim: URP asset {PipelineAssetPath} assigned to Graphics and "
                      + $"{QualitySettings.names.Length} Quality levels");
        }

        // G3 P3: the scene of the device check, a camera and a DeviceCheck (no UI Toolkit, no input).
        [MenuItem("WorldSim/Create device check scene")]
        public static void CreateCheckScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            var cameraData = camera.gameObject.AddComponent<UniversalAdditionalCameraData>();
            cameraData.renderPostProcessing = false;
            cameraData.antialiasing = AntialiasingMode.None;
            new GameObject("DeviceCheck").AddComponent<DeviceCheck>();
            System.IO.Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, CheckScenePath);
            Debug.Log($"WorldSim: scene written to {CheckScenePath}");
        }

        // Android player settings kept in the project (IL2CPP, ARM64 only, the provisional id), and the import
        // settings of the two kernel libraries, which live in the git-ignored Plugins folder and so cannot carry
        // their own .meta: the .so goes to Android ARM64 only, the .dll to the Editor and Windows only.
        public static void ConfigureAndroid()
        {
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, AndroidId);
            var so = AssetImporter.GetAtPath(AndroidLibPath) as PluginImporter
                     ?? throw new BuildFailedException($"{AndroidLibPath} missing: run scripts/unity_sync.py --android");
            so.SetCompatibleWithAnyPlatform(false);
            so.SetCompatibleWithEditor(false);
            so.SetCompatibleWithPlatform(BuildTarget.Android, true);
            so.SetPlatformData(BuildTarget.Android, "CPU", "ARM64");
            so.SaveAndReimport();
            if (AssetImporter.GetAtPath(WindowsLibPath) is PluginImporter dll)
            {
                dll.SetCompatibleWithAnyPlatform(false);
                dll.SetCompatibleWithEditor(true);
                dll.SetEditorData("CPU", "x86_64");
                dll.SetEditorData("OS", "Windows");
                dll.SetCompatibleWithPlatform(BuildTarget.StandaloneWindows64, true);
                dll.SetCompatibleWithPlatform(BuildTarget.Android, false);
                dll.SaveAndReimport();
            }
            AssetDatabase.SaveAssets();
        }

        [MenuItem("WorldSim/Build Android viewer")]
        public static void BuildAndroid()
        {
            // left behind by an interrupted scripts/android_check.py: the viewer must not ship the golden sets
            if (AssetDatabase.IsValidFolder("Assets/StreamingAssets/golden"))
            {
                throw new BuildFailedException("Assets/StreamingAssets/golden exists: delete it before a viewer build");
            }
            string[] args = System.Environment.GetCommandLineArgs();
            int at = System.Array.IndexOf(args, "-appVersion");
            if (at >= 0)
            {
                SetVersion(at + 1 < args.Length ? args[at + 1] : "");
            }
            ConfigureAndroid();
            string apk = $"{AndroidApkFolder}/worldsim-{PlayerSettings.bundleVersion}.apk";
            Build(new[] { ScenePath }, apk, AndroidId, PlayerSettings.productName);
        }

        // The app's version, one source for the Unity player (Application.version, shown in the HUD) and the APK:
        // MAJOR.MINOR.PATCH (owner's rule, 2026-11-12): PATCH goes up with every APK delivered to the phone, MINOR
        // only with the owner's approval for a substantial change, 1.0.0 at the first release. The Android version
        // code follows it (MAJOR * 10000 + MINOR * 100 + PATCH), so an install always sees a newer build; a version
        // older than the current one is refused.
        public static void SetVersion(string version)
        {
            int code = VersionCode(version);
            if (code < VersionCode(PlayerSettings.bundleVersion, lenient: true))
            {
                throw new BuildFailedException($"version {version} is older than {PlayerSettings.bundleVersion}");
            }
            PlayerSettings.bundleVersion = version;
            PlayerSettings.Android.bundleVersionCode = code;
            AssetDatabase.SaveAssets();
            Debug.Log($"WorldSim: version {version} (Android version code {code})");
        }

        private static int VersionCode(string version, bool lenient = false)
        {
            string[] parts = version.Split('.');
            if (parts.Length == 3
                && int.TryParse(parts[0], out int major) && int.TryParse(parts[1], out int minor)
                && int.TryParse(parts[2], out int patch)
                && major >= 0 && major < 2000 && minor >= 0 && minor < 100 && patch >= 0 && patch < 100)
            {
                return major * 10000 + minor * 100 + patch;
            }
            if (lenient)
            {
                return 0;    // a version from before this scheme (Unity's default "1.0")
            }
            throw new BuildFailedException($"-appVersion '{version}': expected MAJOR.MINOR.PATCH, MINOR and PATCH < 100");
        }

        public static void BuildAndroidCheck()
        {
            ConfigureAndroid();
            CreateCheckScene();
            Build(new[] { CheckScenePath }, AndroidCheckApk, AndroidCheckId, PlayerSettings.productName + " check");
        }

        // A release (non-development) APK, so the timings are those of a player; the id and the name are swapped
        // in for the build only, so the check installs beside the viewer.
        private static void Build(string[] scenes, string apk, string id, string name)
        {
            string keptId = PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android);
            string keptName = PlayerSettings.productName;
            bool keptBundle = EditorUserBuildSettings.buildAppBundle;
            try
            {
                PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, id);
                PlayerSettings.productName = name;
                EditorUserBuildSettings.buildAppBundle = false;
                BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = scenes,
                    locationPathName = apk,
                    target = BuildTarget.Android,
                    options = BuildOptions.None,
                });
                if (report.summary.result != BuildResult.Succeeded)
                {
                    throw new BuildFailedException($"Android build {report.summary.result}: {apk}");
                }
                Debug.Log($"WorldSim: {apk} ({report.summary.totalSize} bytes)");
            }
            finally
            {
                PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, keptId);
                PlayerSettings.productName = keptName;
                EditorUserBuildSettings.buildAppBundle = keptBundle;
                AssetDatabase.SaveAssets();
            }
        }
    }
}
