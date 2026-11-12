// Builds the front-end scene and the render pipeline settings from code, so they can be regenerated
// instead of hand-edited.
//   Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.CreateScene
//   Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.ConfigureRenderPipeline
using UnityEditor;
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
    }
}
