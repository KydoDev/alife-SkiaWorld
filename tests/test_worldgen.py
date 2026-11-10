"""World seed from a planet form or an image (untrusted input)."""
import json

import numpy as np
import pytest
from PIL import Image

from worldsim import Config, World
from worldsim import worldgen
from worldsim.worldgen import PlanetError, config_from_form, load_planet, seed_from_bytes, terrain_from_rgb


def small():
    return Config(width=40, height=20, initial_cells=60)


def write_form(tmp_path, form, name="planet.json"):
    path = tmp_path / name
    path.write_text(json.dumps(form), encoding="utf-8")
    return path


def write_image(tmp_path, rgb, name="planet.png"):
    path = tmp_path / name
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def test_seed_from_bytes_is_stable():
    assert seed_from_bytes(b"planet") == seed_from_bytes(b"planet") == 1264063998  # SHA-256: same everywhere
    assert seed_from_bytes(b"planet") != seed_from_bytes(b"planet!")


def test_form_maps_fields_onto_config(tmp_path):
    path = write_form(tmp_path, {"star": "red_dwarf", "day_night": 1, "seasonality": 0.4,
                                 "seabed_relief": 0.2, "volcanism": 3, "mineral_richness": 2.5,
                                 "ocean_depth": 20, "seed": 77, "config": {"width": 40, "height": 20,
                                                                           "reseed_on_extinction": False}})
    cfg, terrain, seed = load_planet(path)
    assert seed == 77
    assert (cfg.light_max, cfg.day_length) == worldgen.STARS["red_dwarf"]
    assert (cfg.day_amplitude, cfg.season_amplitude, cfg.light_depth) == (1.0, 0.4, 20.0)
    assert (cfg.rock_fraction, cfg.vent_count, cfg.vent_strength) == (0.2, 3, 2.5)
    assert cfg.reseed_on_extinction is False
    assert terrain.rock.any() and terrain.chem.max() > 0
    world = World(cfg, seed=seed, terrain=terrain)
    for _ in range(20):
        world.step()


def test_form_without_seed_derives_one_from_content(tmp_path):
    a = load_planet(write_form(tmp_path, {"volcanism": 2, "config": {"width": 30}}, "a.json"))[2]
    b = load_planet(write_form(tmp_path, {"config": {"width": 30}, "volcanism": 2}, "b.json"))[2]
    assert a == b                                           # key order does not matter
    assert load_planet(write_form(tmp_path, {"volcanism": 2}, "c.json"), seed=5)[2] == 5


@pytest.mark.parametrize("form, message", [
    ([], "JSON object"),
    ({"gravity": 2}, "unknown form fields"),
    ({"star": "neutron"}, "unknown star"),
    ({"volcanism": 1000}, "outside"),
    ({"volcanism": 2.5}, "must be int"),
    ({"seasonality": True}, "must be float"),
    ({"name": 3}, "must be str"),
    ({"config": {"photo_gain": "lots"}}, "must be float"),
    ({"config": {"__class__": 1}}, "unknown Config field"),
    ({"config": {"width": 100000, "height": 100000}}, "world size"),
    ({"config": {"photo_gain": float("nan")}}, "finite"),
])
def test_form_rejects_invalid_input(form, message):
    with pytest.raises(PlanetError, match=message):
        config_from_form(form)


def test_form_rejects_bad_files(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"{not json")
    with pytest.raises(PlanetError, match="not valid JSON"):
        load_planet(bad)
    with pytest.raises(PlanetError, match="cannot read"):
        load_planet(tmp_path / "missing.json")
    monkeypatch.setattr(worldgen, "MAX_FORM_BYTES", 10)
    with pytest.raises(PlanetError, match="limit"):
        load_planet(write_form(tmp_path, {"volcanism": 2}))


def test_image_maps_channels_onto_terrain(tmp_path):
    H, W = 20, 40
    rgb = np.zeros((H, W, 3))
    rgb[:, :20, 1] = 0.9                                    # bright left half -> more sun
    rgb[15:, 30:34, 0] = 1.0                                # red patch -> chemical energy
    rgb[5:10, :, 2] = 1.0                                   # blue band -> organic matter
    path = write_image(tmp_path, rgb)
    cfg, terrain, seed = load_planet(path, small())
    assert seed == seed_from_bytes(path.read_bytes())
    assert terrain.sun[:20].mean() > terrain.sun[20:].mean()
    assert np.isclose(terrain.sun.mean(), 1.0)
    assert terrain.chem[17, 31:33].min() > 1.0 and terrain.chem[:, :25].max() == 0.0
    assert terrain.organic[7, 5] > 5.0
    assert terrain.rock.any() and not terrain.rock[0].any()  # the half-split edge is rock
    world = World(cfg, seed=seed, terrain=terrain)
    assert world.organic[7, 5] == terrain.organic[7, 5]
    for _ in range(20):
        world.step()
    assert not any(terrain.rock[c.y, c.x] for c in world.cells)


def test_uniform_image_gives_flat_sun_and_no_rock():
    terrain = terrain_from_rgb(np.full((10, 20, 3), 0.5), small())
    assert not terrain.rock.any() and np.allclose(terrain.sun, 1.0)


def test_image_rejects_non_images_and_oversized(tmp_path, monkeypatch):
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"definitely not a png")
    with pytest.raises(PlanetError, match="not a readable image"):
        load_planet(junk, small())
    path = write_image(tmp_path, np.zeros((30, 30, 3)))
    monkeypatch.setattr(worldgen, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(PlanetError, match="limit"):
        load_planet(path, small())
    monkeypatch.setattr(worldgen, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(PlanetError, match="limit"):
        load_planet(path, small())


def test_example_planets_load():
    for name in ("volcanic.json", "red_dwarf.json"):
        cfg, terrain, _ = load_planet(f"examples/{name}")
        assert terrain.chem.max() > 0
    cfg, terrain, _ = load_planet("examples/planet.png")
    assert terrain.rock.any() and terrain.chem.max() > 0


# ------------------------------------------------- hardening (security review, 2026-11-10)
@pytest.mark.parametrize("override, message", [
    ({"vent_count": 2_000_000_000}, "vent_count"),
    ({"vent_radius": 0.0}, "vent_radius"),
    ({"day_length": 0, "day_amplitude": 0.5}, "day_length"),
    ({"shade": -1.0}, "shade"),
    ({"initial_cells": 10**7}, "initial_cells"),
    ({"photo_gain": 10**400}, "too large"),
])
def test_form_config_overrides_are_range_checked(override, message):
    with pytest.raises(PlanetError, match=message):
        config_from_form({"config": override})


def test_form_rejects_huge_json_integers(tmp_path):
    path = tmp_path / "big.json"
    path.write_text('{"volcanism": ' + "9" * 5000 + "}", encoding="utf-8")
    with pytest.raises(PlanetError):
        load_planet(path)


def test_image_rejects_formats_outside_the_whitelist(tmp_path):
    path = tmp_path / "planet.tif"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(path, format="TIFF")
    with pytest.raises(PlanetError, match="not a readable image"):
        load_planet(path, small())
