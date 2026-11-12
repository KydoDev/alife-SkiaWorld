// G3 P3 review: the viewer needs no network, but Unity's "Internet Access: Auto" adds INTERNET to the manifest as
// soon as UnityWebRequest is referenced, and StreamingRead uses it only for the jar: files inside the APK, which
// need no permission. The permission is removed from the generated Gradle project, so an install asks for nothing.
using System.Collections.Generic;
using System.IO;
using System.Xml;
using UnityEditor.Android;

namespace WorldSim.EditorTools
{
    public sealed class DropInternetPermission : IPostGenerateGradleAndroidProject
    {
        private const string AndroidNs = "http://schemas.android.com/apk/res/android";
        private const string Internet = "android.permission.INTERNET";

        public int callbackOrder => 0;

        /// <param name="path">The unityLibrary module of the generated project.</param>
        public void OnPostGenerateGradleAndroidProject(string path)
        {
            string manifest = Path.Combine(path, "src", "main", "AndroidManifest.xml");
            var doc = new XmlDocument();
            doc.Load(manifest);
            var drop = new List<XmlElement>();
            foreach (XmlNode node in doc.SelectNodes("/manifest/uses-permission"))
            {
                if (node is XmlElement e && e.GetAttribute("name", AndroidNs) == Internet)
                {
                    drop.Add(e);
                }
            }
            foreach (XmlElement e in drop)
            {
                e.ParentNode.RemoveChild(e);
            }
            doc.Save(manifest);
        }
    }
}
