// P/Invoke wrapper of the Rust kernel's C ABI (engine-rs/src/ffi.rs, ABI version 1).
// No UnityEngine dependency: this file is plain C# and is exercised by the EditMode tests.
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace WorldSim
{
    /// <summary>Sizes and counters of a world (`WsInfo`, 48 bytes, sequential layout).</summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct WorldInfo
    {
        public uint Width;
        public uint Height;
        public ulong StepCount;
        public ulong Population;
        public ulong Births;
        public ulong Deaths;
        public ulong Kills;
    }

    /// <summary>A call into the kernel failed; the message comes from `ws_last_error`.</summary>
    public sealed class WorldSimException : Exception
    {
        public WorldSimException(string message) : base(message) { }
    }

    /// <summary>Owns one kernel world; released exactly once by the runtime.</summary>
    public sealed class WorldHandle : SafeHandle
    {
        private WorldHandle() : base(IntPtr.Zero, true) { }

        public override bool IsInvalid => handle == IntPtr.Zero;

        protected override bool ReleaseHandle()
        {
            Native.ws_world_free(handle);
            return true;
        }
    }

    internal static class Native
    {
        private const string Lib = "worldsim_core";

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern uint ws_abi_version();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern WorldHandle ws_world_load(byte[] data, UIntPtr len);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern void ws_world_free(IntPtr handle);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_step(WorldHandle handle, uint steps);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_info(WorldHandle handle, out WorldInfo info);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_state_hash(WorldHandle handle, [Out] byte[] buffer, UIntPtr len);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_render_rgb(WorldHandle handle, [Out] byte[] buffer, UIntPtr len);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UIntPtr ws_last_error([Out] byte[] buffer, UIntPtr len);
    }

    /// <summary>
    /// A world of the Rust kernel. Not thread-safe: call it from one thread (Unity's main thread).
    /// </summary>
    public sealed class NativeWorld : IDisposable
    {
        /// <summary>The ABI this wrapper was written for (`WS_ABI_VERSION`).</summary>
        public const uint AbiVersion = 1;

        private const int HashLength = 64;
        private readonly WorldHandle _handle;

        private NativeWorld(WorldHandle handle)
        {
            _handle = handle;
        }

        /// <summary>The library's ABI version; throws if it differs from <see cref="AbiVersion"/>.</summary>
        public static uint CheckAbi()
        {
            uint found = Native.ws_abi_version();
            if (found != AbiVersion)
            {
                throw new WorldSimException(
                    $"worldsim_core ABI {found}, expected {AbiVersion}: re-run scripts/unity_sync.py");
            }
            return found;
        }

        /// <summary>Load a save (gzip JSON, as written by the Python engine).</summary>
        public static NativeWorld Load(byte[] save)
        {
            if (save == null || save.Length == 0)
            {
                throw new ArgumentException("empty save", nameof(save));
            }
            CheckAbi();
            WorldHandle handle = Native.ws_world_load(save, (UIntPtr)save.Length);
            if (handle.IsInvalid)
            {
                handle.Dispose();
                throw new WorldSimException(LastError());
            }
            return new NativeWorld(handle);
        }

        public WorldInfo Info
        {
            get
            {
                Check(Native.ws_world_info(_handle, out WorldInfo info));
                return info;
            }
        }

        /// <summary>Bytes of an RGB image of this world (width x height x 3).</summary>
        public int RgbLength
        {
            get
            {
                WorldInfo info = Info;
                return checked((int)(info.Width * info.Height * 3));
            }
        }

        /// <summary>Advance by <paramref name="steps"/> steps (blocking; keep it small per frame).</summary>
        public void Step(uint steps)
        {
            Check(Native.ws_world_step(_handle, steps));
        }

        /// <summary>The state hash, comparable with the golden `hashes.csv`.</summary>
        public string StateHash()
        {
            var buffer = new byte[HashLength];
            Check(Native.ws_world_state_hash(_handle, buffer, (UIntPtr)buffer.Length));
            return Encoding.ASCII.GetString(buffer);
        }

        /// <summary>Render into <paramref name="rgb"/> (row 0 = the lit surface, top of the world).</summary>
        public void RenderRgb(byte[] rgb)
        {
            if (rgb == null)
            {
                throw new ArgumentNullException(nameof(rgb));
            }
            Check(Native.ws_world_render_rgb(_handle, rgb, (UIntPtr)rgb.Length));
        }

        public void Dispose()
        {
            _handle.Dispose();
        }

        private void Check(int status)
        {
            if (_handle.IsClosed)
            {
                throw new ObjectDisposedException(nameof(NativeWorld));
            }
            if (status != 0)
            {
                throw new WorldSimException($"kernel error {status}: {LastError()}");
            }
        }

        private static string LastError()
        {
            int length = checked((int)Native.ws_last_error(null, UIntPtr.Zero));
            var buffer = new byte[length];
            Native.ws_last_error(buffer, (UIntPtr)length);
            return Encoding.UTF8.GetString(buffer);
        }
    }
}
