// EditMode tests: the kernel, called through P/Invoke from inside Unity, reproduces the golden data
// of engine-rs/tests/golden (hashes and renders made by the Python reference engine).
//   Unity -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults <file>
using System.IO;
using System.IO.Compression;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WorldSim.Tests
{
    public class NativeWorldTests
    {
        private static readonly string[] Sets = { "default", "volcanic" };

        // The creation sets (hashed from step 0) and their seeds (rng.json "seed"; checked by pytest).
        private static readonly object[] CreateSets = { new object[] { "create_default", 1UL },
                                                         new object[] { "create_volcanic", 42UL } };

        private static string GoldenDir(string set) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "engine-rs", "tests", "golden", set));

        private static string[][] Hashes(string set) =>
            File.ReadAllLines(Path.Combine(GoldenDir(set), "hashes.csv")).Skip(1)
                .Select(line => line.Split(',')).ToArray();

        private static NativeWorld LoadStart(string set) =>
            NativeWorld.Load(File.ReadAllBytes(Path.Combine(GoldenDir(set), "start.json.gz")));

        private static byte[] Gunzip(string path)
        {
            using var file = File.OpenRead(path);
            using var gz = new GZipStream(file, CompressionMode.Decompress);
            using var output = new MemoryStream();
            gz.CopyTo(output);
            return output.ToArray();
        }

        [Test]
        public void AbiVersionMatchesTheWrapper()
        {
            Assert.AreEqual(NativeWorld.AbiVersion, NativeWorld.CheckAbi());
        }

        [Test]
        public void GoldenHashesThroughPInvoke([ValueSource(nameof(Sets))] string set)
        {
            string[][] rows = Hashes(set);
            using NativeWorld world = LoadStart(set);
            Assert.AreEqual(rows[0][2], world.StateHash(), $"{set}: start");
            int done = 0;
            uint chunk = 1;
            while (done + 1 < rows.Length)
            {
                uint n = (uint)System.Math.Min(chunk, rows.Length - 1 - done);
                world.Step(n);
                done += (int)n;
                Assert.AreEqual(rows[done][2], world.StateHash(), $"{set}: step {rows[done][0]}");
                chunk = chunk % 37 + 7;
            }
            WorldInfo info = world.Info;
            Assert.AreEqual(ulong.Parse(rows[done][0]), info.StepCount);
            Assert.AreEqual(ulong.Parse(rows[done][1]), info.Population);
        }

        [Test]
        public void RenderEqualsPythonAtTheStart([ValueSource(nameof(Sets))] string set)
        {
            using NativeWorld world = LoadStart(set);
            var rgb = new byte[world.RgbLength];
            world.RenderRgb(rgb);
            CollectionAssert.AreEqual(Gunzip(Path.Combine(GoldenDir(set), "render_start.rgb.gz")), rgb);
        }

        [Test, TestCaseSource(nameof(CreateSets))]
        public void CreatedWorldsFollowTheCreationSets(string set, ulong seed)
        {
            string[][] rows = Hashes(set);
            byte[] config = File.ReadAllBytes(Path.Combine(GoldenDir(set), "config.json"));
            using NativeWorld world = NativeWorld.Create(config, seed);
            Assert.AreEqual(rows[0][2], world.StateHash(), $"{set}: step 0");
            world.Step(100);
            Assert.AreEqual(rows[100][2], world.StateHash(), $"{set}: step 100");
        }

        [Test]
        public void ABadConfigThrowsWithTheKernelMessage()
        {
            var e = Assert.Throws<WorldSimException>(
                () => NativeWorld.Create(System.Text.Encoding.UTF8.GetBytes("{\"width\": 3}"), 1));
            StringAssert.Contains("missing", e.Message);
        }

        [Test]
        public void BadInputThrowsWithTheKernelMessage()
        {
            var e = Assert.Throws<WorldSimException>(() => NativeWorld.Load(new byte[] { 1, 2, 3 }));
            StringAssert.Contains("not a valid save", e.Message);
            using NativeWorld world = LoadStart("default");
            var shortBuffer = new byte[world.RgbLength - 1];
            e = Assert.Throws<WorldSimException>(() => world.RenderRgb(shortBuffer));
            StringAssert.Contains("render buffer", e.Message);
            world.Step(1);   // still usable after a refused call
        }

        [Test]
        public void ADisposedWorldCannotBeUsed()
        {
            NativeWorld world = LoadStart("default");
            world.Dispose();
            Assert.Throws<System.ObjectDisposedException>(() => world.Step(1));
        }
    }
}
