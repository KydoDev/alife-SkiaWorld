"""Copy the Rust kernel and a sample save into the Unity project (G2 M4).

Builds `engine-rs` in release mode and copies:
- the native library into `unity/Assets/Plugins/x86_64/`;
- a save (default: the default golden start save) to `unity/Assets/StreamingAssets/world.json.gz`.
Both destinations are git-ignored. The Unity editor locks a loaded native library: close it before
re-running this script after a kernel change.

    python scripts/unity_sync.py
    python scripts/unity_sync.py --save runs/a/world_final.json.gz
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine-rs"
UNITY = ROOT / "unity"
LIB_NAMES = {"win32": "worldsim_core.dll", "linux": "libworldsim_core.so", "darwin": "libworldsim_core.dylib"}


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(src, dst)
    except PermissionError as e:
        raise SystemExit(f"cannot overwrite {dst} ({e}): close the Unity editor, which locks the library") from e
    print(f"{src.relative_to(ROOT) if src.is_relative_to(ROOT) else src} -> {dst.relative_to(ROOT)}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--save", type=Path, default=ENGINE / "tests/golden/default/start.json.gz",
                    help="save (v8, default flags) the Unity front-end loads")
    ap.add_argument("--no-build", action="store_true", help="copy the library already built")
    args = ap.parse_args(argv)
    lib = LIB_NAMES.get(sys.platform)
    if lib is None:
        raise SystemExit(f"unsupported platform {sys.platform}")
    if not args.no_build:
        subprocess.run(["cargo", "build", "--release", "--locked"], cwd=ENGINE, check=True)
    copy(ENGINE / "target/release" / lib, UNITY / "Assets/Plugins/x86_64" / lib)
    copy(args.save, UNITY / "Assets/StreamingAssets/world.json.gz")


if __name__ == "__main__":
    main()
