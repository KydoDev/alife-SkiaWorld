"""scripts/unity_sync.py exports the G1 tool parameters the Unity sandbox applies (ADR-0013 piece 5)."""
import importlib.util
import json
from pathlib import Path

from worldsim.play import TOOLS, GameRules

ROOT = Path(__file__).resolve().parent.parent


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_exported_tools_are_the_records_the_golden_game_case_uses():
    """Each tool's (kind, radius, amount) is what g2_intervention_vectors.game_actions makes of a G1 log, the
    expansion the kernel is proven against, so Unity applies what Game.act would."""
    sync, iv = _script("unity_sync"), _script("g2_intervention_vectors")
    tools = sync.tool_parameters()
    assert [t["name"] for t in tools] == list(TOOLS)
    assert sync.TOOL_KIND == iv.TOOL_KIND
    log = [(0, t, 3, 4) for t in TOOLS]
    assert [(t["kind"], t["radius"], t["amount"]) for t in tools] == [a[1:2] + a[4:] for a in iv.game_actions(log)]
    rules = GameRules(radius={**GameRules().radius, "dig": 5}, nutrients_amount=2.5, max_chem=9.0)
    by_name = {t["name"]: t for t in sync.tool_parameters(rules)}
    assert by_name["dig"]["radius"] == 5 and by_name["nutrients"]["amount"] == 2.5
    assert (by_name["volcano"]["radius"], by_name["volcano"]["amount"]) == (0, 9.0)


def test_write_tools_writes_the_json_the_viewer_reads(tmp_path, monkeypatch):
    sync = _script("unity_sync")
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    dst = tmp_path / "StreamingAssets" / "game_tools.json"
    sync.write_tools(dst)
    doc = json.loads(dst.read_text(encoding="utf-8"))
    assert doc == {"tools": sync.tool_parameters()}
    assert all(isinstance(t["amount"], float) for t in doc["tools"])
