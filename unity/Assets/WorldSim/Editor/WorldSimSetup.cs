// Builds the front-end scene from code, so the scene file can be regenerated instead of hand-edited.
//   Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.CreateScene
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace WorldSim.EditorTools
{
    public static class WorldSimSetup
    {
        public const string ScenePath = "Assets/Scenes/WorldSim.unity";

        [MenuItem("WorldSim/Create front-end scene")]
        public static void CreateScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.orthographic = true;
            new GameObject("WorldSim").AddComponent<WorldSimView>();
            System.IO.Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            Debug.Log($"WorldSim: scene written to {ScenePath}");
        }
    }
}
