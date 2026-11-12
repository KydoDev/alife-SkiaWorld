// G3 P3 device check (docs/G3_PLAN.md): the golden sets that scripts/android_check.py bundles into
// StreamingAssets/golden/<set>/ (start.save, the gzip start save renamed, and hashes.csv) are stepped through the kernel on the device, as the EditMode test
// GoldenHashesThroughPInvoke does on the desktop, and the outcome goes to the log (logcat tag Unity) as one
// "WSCHECK" line per set. A divergence is reported, never tolerated: ARM's maths library may round differently
// from the platform the Python reference ran on (G2_PLAN "Golden sets per platform"), so a mismatch means
// "not comparable" until a reference from a matching platform exists. The time spent in Step (hashing excluded)
// gives the kernel's steps per second on the device.
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace WorldSim
{
    public sealed class DeviceCheck : MonoBehaviour
    {
        public const string Tag = "WSCHECK";
        private const long MaxSaveBytes = 256L * 1024 * 1024;
        private const long MaxHashesBytes = 4L * 1024 * 1024;

        [Tooltip("Golden sets under StreamingAssets/golden")]
        public string[] sets = { "default", "volcanic" };

        private readonly List<string> _lines = new List<string>();
        private GUIStyle _style;

        private IEnumerator Start()
        {
            Report($"device {SystemInfo.deviceModel}, {SystemInfo.processorType}, {SystemInfo.operatingSystem}");
            try
            {
                Report($"abi {NativeWorld.CheckAbi()}");
            }
            catch (System.Exception e)
            {
                Report($"error {e.GetType().Name}: {e.Message}");
                Report("done");
                yield break;
            }
            foreach (string set in sets)
            {
                yield return null;    // show the lines so far
                var start = new StreamingRead($"golden/{set}/start.save", MaxSaveBytes);
                var hashes = new StreamingRead($"golden/{set}/hashes.csv", MaxHashesBytes);
                yield return start.Wait();
                yield return hashes.Wait();
                if (start.Data == null || hashes.Data == null)
                {
                    Report($"set={set} error {start.Error ?? hashes.Error}");
                    continue;
                }
                try
                {
                    Report(Check(set, start.Data, Encoding.ASCII.GetString(hashes.Data)));
                }
                catch (System.Exception e)
                {
                    // Any failure ends this set with a line, so the script never waits for a "done" that a dead
                    // coroutine would not log.
                    Report($"set={set} error {e.GetType().Name}: {e.Message}");
                }
            }
            Report("done");
        }

        /// <summary>Step the set's start save through every row of hashes.csv, in the test's uneven chunks.</summary>
        private static string Check(string set, byte[] save, string csv)
        {
            string[] lines = csv.Split(new[] { '\n' }, System.StringSplitOptions.RemoveEmptyEntries);
            var rows = new List<string[]>();
            for (int i = 1; i < lines.Length; i++)    // line 0 is the header
            {
                string[] row = lines[i].Trim().Split(',');
                if (row.Length < 3)
                {
                    throw new System.FormatException($"hashes.csv line {i + 1} has {row.Length} fields, not 3");
                }
                rows.Add(row);
            }
            if (rows.Count == 0)
            {
                throw new System.FormatException("hashes.csv has no rows");
            }
            using NativeWorld world = NativeWorld.Load(save);
            string firstDivergence = world.StateHash() == rows[0][2] ? null : rows[0][0];
            var watch = new Stopwatch();
            int done = 0;
            uint chunk = 1;
            while (done + 1 < rows.Count)
            {
                uint n = (uint)System.Math.Min(chunk, rows.Count - 1 - done);
                watch.Start();
                world.Step(n);
                watch.Stop();
                done += (int)n;
                if (firstDivergence == null && world.StateHash() != rows[done][2])
                {
                    firstDivergence = rows[done][0];
                }
                chunk = chunk % 37 + 7;
            }
            WorldInfo info = world.Info;
            double seconds = watch.Elapsed.TotalSeconds;
            string verdict = firstDivergence == null ? "equal" : $"not-comparable first-divergence={firstDivergence}";
            return string.Format(CultureInfo.InvariantCulture,
                "set={0} world={1}x{2} steps={3} {4} population={5} step-seconds={6:F3} steps-per-second={7:F0}",
                set, info.Width, info.Height, done, verdict, info.Population, seconds, done / seconds);
        }

        private void Report(string line)
        {
            _lines.Add(line);
            UnityEngine.Debug.Log($"{Tag} {line}");
        }

        private void OnGUI()
        {
            _style ??= new GUIStyle(GUI.skin.label) { fontSize = Mathf.Max(14, Screen.height / 40), wordWrap = true };
            GUILayout.BeginArea(new Rect(16, 16, Screen.width - 32, Screen.height - 32));
            foreach (string line in _lines)
            {
                GUILayout.Label(line, _style);
            }
            GUILayout.EndArea();
        }
    }
}
