"""Run the G3 P3 device check on a connected Android phone (docs/G3_PLAN.md).

1. `unity_sync.py --android`: the kernel for the desktop and for arm64 Android, the save, the config, the tools;
2. the golden sets' `start.json.gz` (as `start.save`) and `hashes.csv` into
   `unity/Assets/StreamingAssets/golden/<set>/`;
3. a batchmode Unity build of `WorldSimSetup.BuildAndroidCheck` (the Editor must not have the project open);
4. `adb install` of the check APK, a launch, and the "WSCHECK" lines of logcat until the check says "done".

The golden copies are removed again after the build, so the viewer APK does not carry them. Equal hashes, or a
"not-comparable" verdict with the first diverging step, are both results, not failures (G2_PLAN "Golden sets per
platform"); the script fails only when a step of the pipeline does. Windows hosts (the Unity Hub folder):

    python scripts/android_check.py
    python scripts/android_check.py --no-build        # install and run the APK already built
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import unity_sync  # noqa: E402

UNITY = unity_sync.UNITY
GOLDEN = ROOT / "engine-rs/tests/golden"
BUNDLED = UNITY / "Assets/StreamingAssets/golden"
SETS = ("default", "volcanic")
APK = UNITY / "Builds/Android/worldsim-check.apk"
PACKAGE = "com.kydodev.worldsim.check"
TAG = "WSCHECK"


def editor_dir() -> Path:
    return unity_sync.unity_ndk().parents[3]   # .../Editor/Data/PlaybackEngines/AndroidPlayer/NDK -> .../Editor


def build(log: Path) -> None:
    unity_sync.main(["--android"])
    try:   # the copies too: a copy that fails halfway must not leave golden data for the viewer build
        for s in SETS:
            unity_sync.copy(GOLDEN / s / "start.json.gz", BUNDLED / s / "start.save")   # no .gz: see unity_sync
            unity_sync.copy(GOLDEN / s / "hashes.csv", BUNDLED / s / "hashes.csv")
        cmd = [str(editor_dir() / "Unity.exe"), "-batchmode", "-quit", "-projectPath", str(UNITY),
               "-buildTarget", "Android", "-executeMethod", "WorldSim.EditorTools.WorldSimSetup.BuildAndroidCheck",
               "-logFile", str(log)]
        print("building the check APK (log:", log, ")")
        if subprocess.run(cmd).returncode != 0:
            raise SystemExit(f"the Unity build failed: see {log}")
    finally:
        shutil.rmtree(BUNDLED, ignore_errors=True)
        BUNDLED.with_suffix(".meta").unlink(missing_ok=True)


def run_on_device(adb: Path, timeout: float) -> None:
    subprocess.run([str(adb), "install", "-r", str(APK)], check=True)
    subprocess.run([str(adb), "logcat", "-c"], check=True)
    subprocess.run([str(adb), "shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"],
                   check=True, stdout=subprocess.DEVNULL)
    seen = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = subprocess.run([str(adb), "logcat", "-d", "-s", "Unity"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=True).stdout
        lines = [line[line.index(TAG):] for line in out.splitlines() if TAG in line]
        for line in lines[seen:]:
            print(line)
        seen = len(lines)
        if any(line == f"{TAG} done" for line in lines):
            return
        time.sleep(2)
    raise SystemExit(f"no '{TAG} done' within {timeout:.0f} s")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-build", action="store_true", help="install and run the APK already built")
    ap.add_argument("--timeout", type=float, default=600, help="seconds to wait for the check")
    ap.add_argument("--log", type=Path, default=UNITY / "Builds/android-check-build.log")
    args = ap.parse_args(argv)
    if not args.no_build:
        build(args.log)
    adb = editor_dir() / "Data/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb.exe"
    run_on_device(adb, args.timeout)


if __name__ == "__main__":
    main()
