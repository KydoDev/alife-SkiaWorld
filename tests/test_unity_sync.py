"""scripts/unity_sync.py exports the planet configs New world uses (G3 P2b)."""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_config_writes_a_wide_and_a_deep_world_of_the_same_planet(tmp_path, monkeypatch):
    """G3 P2b: New world is wide in landscape and deep in portrait; both shapes are validated configs."""
    from worldsim.config import Config
    sync = _script("unity_sync")
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    wide, deep = tmp_path / "world_config.json", tmp_path / "world_config_portrait.json"
    sync.write_config(ROOT / "examples" / "volcanic.json", wide, deep)
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (wide, deep))
    assert (a["width"], a["height"]) == (160, 64)
    assert (b["width"], b["height"]) == (64, 160)
    assert {k: v for k, v in a.items() if k not in ("width", "height")} == \
        {k: v for k, v in b.items() if k not in ("width", "height")}
    Config(**b).validate()
    deep_form = Config(width=50, height=90)    # a form that is already deep gives the same two shapes
    assert (sync.shaped(deep_form, False).width, sync.shaped(deep_form, True).width) == (90, 50)
