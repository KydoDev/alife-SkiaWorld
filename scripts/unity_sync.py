"""Copy the Rust kernel and a sample save into the Unity project (G2 M4).

Builds `engine-rs` in release mode and copies:
- the native library into `unity/Assets/Plugins/x86_64/`;
- a save (default: the default golden start save) to `unity/Assets/StreamingAssets/world.json.gz`;
- the config of a planet form (default: examples/volcanic.json), `Config.to_dict()` as a save stores it, to
  `unity/Assets/StreamingAssets/world_config.json`: the input of "New world", which the kernel creates with the
  seed typed in the front-end (ADR-0012; forms and images themselves stay in Python);
- the G1 tool parameters of `GameRules()` (kind, radius, amount per tool) to
  `unity/Assets/StreamingAssets/game_tools.json`: the viewer's sandbox tools (ADR-0013 piece 5), so the game
  rules keep one home, in Python.
The destinations are git-ignored. The Unity editor locks a loaded native library: close it before
re-running this script after a kernel change.

    python scripts/unity_sync.py
    python scripts/unity_sync.py --save runs/a/world_final.json.gz --planet examples/red_dwarf.json
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine-rs"
UNITY = ROOT / "unity"
sys.path.insert(0, str(ROOT))
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
    ap.add_argument("--planet", type=Path, default=ROOT / "examples/volcanic.json",
                    help="planet form (.json) whose config New world uses")
    ap.add_argument("--no-build", action="store_true", help="copy the library already built")
    args = ap.parse_args(argv)
    lib = LIB_NAMES.get(sys.platform)
    if lib is None:
        raise SystemExit(f"unsupported platform {sys.platform}")
    if not args.no_build:
        subprocess.run(["cargo", "build", "--release", "--locked"], cwd=ENGINE, check=True)
    copy(ENGINE / "target/release" / lib, UNITY / "Assets/Plugins/x86_64" / lib)
    copy(args.save, UNITY / "Assets/StreamingAssets/world.json.gz")
    write_config(args.planet, UNITY / "Assets/StreamingAssets/world_config.json")
    write_tools(UNITY / "Assets/StreamingAssets/game_tools.json")


# `ws_world_intervene` kind of each G1 tool (WS_EDIT_*, engine-rs/src/ffi.rs)
TOOL_KIND = {"nutrients": 1, "meteorite": 2, "mountain": 3, "dig": 4, "volcano": 5}


def tool_parameters(rules=None) -> list[dict]:
    """Each G1 tool as the arguments of `ws_world_intervene`: what `Game.act` passes to the `play.py` edit (the
    radius from `rules.radius`, `nutrients_amount` or `max_chem` as the amount; unused arguments 0)."""
    from worldsim.play import TOOLS, GameRules
    rules = rules or GameRules()
    out = []
    for tool in TOOLS:
        kind = TOOL_KIND[tool]
        radius = 0 if tool == "volcano" else int(rules.radius[tool])
        amount = {"nutrients": rules.nutrients_amount, "volcano": rules.max_chem}.get(tool, 0.0)
        out.append({"name": tool, "kind": kind, "radius": radius, "amount": float(amount)})
    return out


def write_tools(dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps({"tools": tool_parameters()}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"GameRules() tools -> {dst.relative_to(ROOT)}")


def write_config(planet: Path, dst: Path) -> None:
    """The planet form's config as a save stores it (forms only: an image's terrain is not procedural). The form
    is read by worldgen (size cap, validation), as `run.py --planet` reads it."""
    from worldsim.worldgen import PlanetError, planet_from_form
    if planet.suffix.lower() != ".json":
        raise SystemExit(f"{planet}: New world needs a planet form (.json), not an image")
    try:
        cfg, _, seed = planet_from_form(planet)
    except (OSError, PlanetError, RecursionError) as e:
        raise SystemExit(f"cannot export the config of {planet}: {e}") from e
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(cfg.to_dict(), separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{planet.name} config -> {dst.relative_to(ROOT)} (seed {seed} gives the planet of run.py --planet)")


if __name__ == "__main__":
    main()
