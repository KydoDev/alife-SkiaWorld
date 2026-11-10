"""Charts for headless runs (matplotlib). Kept outside `worldsim/`, which stays headless.

- `plot_stats`: population by strategy, mean genes, colonies/lineages.
- `plot_novelty`: extant species, speciation and novelty rates, mean activity.
- `plot_species_tree`: phylogeny of the species that mattered, over time.
"""
import csv

from worldsim.species import ORIGIN_SPECIATION
from worldsim.world import G_PHOTO, G_PRED, G_SAPRO

STRATEGY_RGB = {"photo": (0.24, 0.71, 0.27), "sapro": (0.60, 0.35, 0.90), "pred": (0.88, 0.20, 0.18)}


def _pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("matplotlib not installed: plot skipped")
        return None


def _read_rows(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_stats(csv_path, png_path):
    plt = _pyplot()
    rows = _read_rows(csv_path)
    if plt is None or not rows:
        return
    step = [int(r["step"]) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    ax = axes[0]
    ax.plot(step, [int(r["photo"]) for r in rows], color="#3cb446", label="photosynthesis")
    ax.plot(step, [int(r["sapro"]) for r in rows], color="#9a5ae6", label="decomposers")
    ax.plot(step, [int(r["pred"]) for r in rows], color="#e0322d", label="predators")
    ax.set_ylabel("cells")
    ax.legend(loc="upper left")
    ax.set_title("Population by dominant strategy")
    ax = axes[1]
    for g in ["move", "attach", "share", "mut", "div"]:
        ax.plot(step, [float(r["mean_" + g]) for r in rows], label=g)
    ax.set_ylabel("mean gene value")
    ax.legend(loc="upper left", ncol=5)
    ax = axes[2]
    pop = [max(int(r["population"]), 1) for r in rows]
    ax.plot(step, [int(r["in_colony"]) / p for r, p in zip(rows, pop)], label="% in colony")
    ax.plot(step, [int(r["lineages"]) / 400 for r in rows], label="lineages / 400")
    ax.set_ylabel("fraction")
    ax.set_xlabel("step")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def _rate_per(rows, key, per):
    """Increase of a cumulative column between samples, scaled to `per` steps."""
    out = []
    for prev, cur in zip(rows, rows[1:]):
        dt = int(cur["step"]) - int(prev["step"])
        out.append((int(cur[key]) - int(prev[key])) * per / dt if dt else 0.0)
    return out


def _smooth(values, window):
    out, acc = [], 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        out.append(acc / min(i + 1, window))
    return out


def plot_novelty(csv_path, png_path, per=100, smooth=10):
    plt = _pyplot()
    rows = _read_rows(csv_path)
    if plt is None or len(rows) < 2 or "novelty" not in rows[0]:
        return
    step = [int(r["step"]) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    ax = axes[0]
    ax.plot(step, [int(r["species"]) for r in rows], color="#2b6cb0")
    ax.set_ylabel("extant species")
    ax.set_title("Novelty over time (simplified evolutionary activity)")
    ax = axes[1]
    ax.plot(step[1:], _smooth(_rate_per(rows, "speciations", per), smooth), color="#a0aec0",
            label=f"speciations / {per} steps")
    ax.plot(step[1:], _smooth(_rate_per(rows, "novelty", per), smooth), color="#c05621", lw=2,
            label=f"newly established species / {per} steps")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylabel("rate (smoothed)")
    ax.legend(loc="upper right")
    ax = axes[2]
    ax.plot(step, [float(r["mean_species_activity"]) for r in rows], color="#4a5568")
    ax.set_ylabel("mean activity of\nextant species")
    ax.set_xlabel("step")
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def _founder_color(genes):
    p, s, d = genes[G_PHOTO], genes[G_SAPRO], genes[G_PRED]
    tot = (p + s + d) or 1e-9
    return tuple(min(1.0, (p * a + s * b + d * c) / tot)
                 for a, b, c in zip(STRATEGY_RGB["photo"], STRATEGY_RGB["sapro"], STRATEGY_RGB["pred"]))


def plot_species_tree(tracker, final_step, png_path, min_peak=20):
    """Each line is a species from origin to extinction; links join a species to its parent.
    Shows species whose peak reached `min_peak` (or that became established), plus their ancestors.
    Color = founder strategy mix (green photosynthesis, purple decomposition, red predation)."""
    plt = _pyplot()
    if plt is None:
        return
    species = tracker.species
    keep = set()
    for s in species.values():
        if s.peak >= min_peak:
            while s is not None and s.id not in keep:
                keep.add(s.id)
                s = species.get(s.parent) if s.parent is not None else None
    if not keep:
        return

    children: dict[int | None, list[int]] = {}
    for sid in sorted(keep, key=lambda i: (species[i].born, i)):
        children.setdefault(species[sid].parent, []).append(sid)
    order = []

    def visit(sid):  # iterative DFS keeps deep phylogenies safe from recursion limits
        stack = [sid]
        while stack:
            cur = stack.pop()
            order.append(cur)
            stack.extend(reversed(children.get(cur, [])))

    for root in children.get(None, []):
        visit(root)
    y = {sid: i for i, sid in enumerate(order)}

    height = min(30, max(4, len(order) * 0.06))
    fig, ax = plt.subplots(figsize=(12, height))
    for sid in order:
        s = species[sid]
        end = s.extinct if s.extinct is not None else final_step
        lw = 0.6 + min(3.0, s.peak / 100)
        ax.plot([s.born, end], [y[sid], y[sid]], color=_founder_color(s.founder_genes), lw=lw,
                solid_capstyle="butt")
        if s.parent is not None and s.parent in y:
            ax.plot([s.born, s.born], [y[s.parent], y[sid]], color="#a0aec0", lw=0.4)
    roots = len(children.get(None, []))
    born_by_speciation = sum(1 for sid in order if species[sid].origin == ORIGIN_SPECIATION)
    ax.set_title(f"Species tree — {len(order)} species shown (peak ≥ {min_peak} + ancestors), "
                 f"{roots} root lineages, {born_by_speciation} by speciation")
    ax.set_xlabel("step")
    ax.set_yticks([])
    ax.set_xlim(0, final_step)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def write_species_csv(tracker, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "parent", "origin", "born", "extinct", "peak", "activity", "established",
                    "children", "founder_genes"])
        for s in tracker.species.values():
            w.writerow([s.id, s.parent, s.origin, s.born, s.extinct, s.peak, s.activity, s.established,
                        s.children, " ".join(f"{g:.3f}" for g in s.founder_genes)])
