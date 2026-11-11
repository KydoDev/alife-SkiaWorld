// P/Invoke wrapper of the Rust kernel's C ABI (engine-rs/src/ffi.rs, ABI version 3).
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

    /// <summary>The five G1 edits of `ws_world_intervene` (`WS_EDIT_*`; ADR-0013).</summary>
    public enum Edit : uint
    {
        Nutrients = 1,
        Meteorite = 2,
        RaiseRock = 3,
        Dig = 4,
        Vent = 5,
    }

    /// <summary>A call into the kernel failed; the message comes from `ws_last_error`.</summary>
    public sealed class WorldSimException : Exception
    {
        /// <summary>`WS_ERR_INVALID`: an edit the kernel refused; the world is unchanged and still usable.</summary>
        public const int StatusInvalid = -5;

        /// <summary>`WS_ERR_PANIC`: the kernel caught a panic; the world may be half-updated and is now unusable.</summary>
        public const int StatusPanic = -3;

        /// <summary>`WS_ERR_POISONED`: the world was made unusable by an earlier panic.</summary>
        public const int StatusPoisoned = -4;

        public WorldSimException(string message, int status = 0) : base(message)
        {
            Status = status;
        }

        /// <summary>The kernel's status code, or 0 when the failure has none (a null handle from load or create).</summary>
        public int Status { get; }
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
        internal static extern WorldHandle ws_world_create(byte[] configJson, UIntPtr len, ulong seed);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern void ws_world_free(IntPtr handle);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_step(WorldHandle handle, uint steps);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int ws_world_intervene(WorldHandle handle, uint kind, uint x, uint y, uint radius,
                                                      double amount, out ulong changed);

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
        public const uint AbiVersion = 3;

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

        /// <summary>
        /// Create a world from a config object (UTF-8 JSON, `Config.to_dict()`, exported by scripts/unity_sync.py)
        /// and a seed, as the Python engine's `World(cfg, seed)`: procedural terrain, then the founders.
        /// </summary>
        public static NativeWorld Create(byte[] configJson, ulong seed)
        {
            if (configJson == null || configJson.Length == 0)
            {
                throw new ArgumentException("empty config", nameof(configJson));
            }
            CheckAbi();
            WorldHandle handle = Native.ws_world_create(configJson, (UIntPtr)configJson.Length, seed);
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

        /// <summary>
        /// Apply one G1 edit between steps, as Python's `play.py` does, and return its value: tiles changed
        /// (nutrients, rock, dig), cells killed (meteorite), or 1/0 for a vent (0 on rock). <paramref name="radius"/>
        /// must be 0 for a vent; <paramref name="amount"/> (organic per tile, or `max_chem` for a vent) must be 0 for
        /// the other edits. A refusal throws <see cref="WorldSimException"/> with
        /// <see cref="WorldSimException.StatusInvalid"/> and leaves the world unchanged.
        /// </summary>
        public ulong Intervene(Edit kind, uint x, uint y, uint radius, double amount)
        {
            Check(Native.ws_world_intervene(_handle, (uint)kind, x, y, radius, amount, out ulong changed));
            return changed;
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
                throw new WorldSimException($"kernel error {status}: {LastError()}", status);
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
