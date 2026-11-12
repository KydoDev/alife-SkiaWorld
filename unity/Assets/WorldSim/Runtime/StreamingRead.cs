// A file of StreamingAssets, read with a size cap (G3 P3). On the desktop StreamingAssets is a folder, so the file
// is read at once, in the constructor. On Android it stays inside the APK (a jar:file:// URL), which System.IO cannot
// open, so the file comes through a UnityWebRequest and the caller waits on Wait().
using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;

namespace WorldSim
{
    public sealed class StreamingRead
    {
        private readonly long _limit;

        /// <param name="name">Path under StreamingAssets; an absolute path is used as it is (tests).</param>
        /// <param name="limit">Largest accepted size in bytes; a larger file is refused, not truncated.</param>
        public StreamingRead(string name, long limit)
        {
            _limit = limit;
            Location = Path.Combine(Application.streamingAssetsPath, name);
            if (Location.StartsWith("jar:", StringComparison.Ordinal))
            {
                // Inside the APK: Wait() reads it. Only the app's own package takes this path, never another
                // scheme, so a name can never turn into a network fetch.
                return;
            }
            try
            {
                long length = new FileInfo(Location).Length;
                if (length > limit)
                {
                    throw new IOException($"{length} bytes, more than the {limit} the kernel accepts");
                }
                Data = File.ReadAllBytes(Location);
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is ArgumentException
                                      || e is NotSupportedException)
            {
                Error = $"{Location}: {e.Message} ({e.GetType().Name})";
            }
            Done = true;
        }

        public string Location { get; }
        public bool Done { get; private set; }
        /// <summary>The bytes read, or null when <see cref="Error"/> says why not.</summary>
        public byte[] Data { get; private set; }
        public string Error { get; private set; }

        /// <summary>Coroutine that reads a file inside a package; does nothing once <see cref="Done"/>.</summary>
        public IEnumerator Wait()
        {
            if (Done)
            {
                yield break;
            }
            using (UnityWebRequest request = UnityWebRequest.Get(Location))
            {
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    Error = $"{Location}: {request.error}";
                }
                else if ((long)request.downloadedBytes > _limit)
                {
                    // The file is part of the app's own package; the cap is checked after the read to keep the
                    // same contract as the desktop path (a file over the kernel's limit is refused).
                    Error = $"{Location}: {request.downloadedBytes} bytes, more than the {_limit} the kernel accepts";
                }
                else
                {
                    Data = request.downloadHandler.data;
                }
            }
            Done = true;
        }
    }
}
