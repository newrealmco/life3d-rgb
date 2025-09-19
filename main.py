import argparse
import json
import os
from typing import Any, Dict

from life3d import Life3DRGB
from visualize import render_voxels, render_slice_grid

def run_sim(config: Dict[str, Any]) -> None:
    shape = tuple(config["shape"])  # [Z,Y,X]
    steps = int(config.get("steps", 50))
    rule = config.get("rule", {"birth":[6], "survive":[5,6,7]})
    mutation = config.get("mutation", {
        "enable": True,
        "per_step_birth_mutation_prob": 0.2,
        "std": 30.0,
        "p_interval": 0.2
    })
    seed_cells = config.get("seeds", [])
    outdir = config.get("outdir","./out")
    os.makedirs(outdir, exist_ok=True)

    sim = Life3DRGB(shape=shape, rule=rule, seed_cells=seed_cells,
                    mutation=mutation, random_state=config.get("random_state"))

    render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_000.png"), title="step 0")

    for t in range(1, steps+1):
        sim.step()
        if t % max(1,int(config.get("render_every",1))) == 0:
            render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_{t:03d}.png"), title=f"step {t}")
        if t % max(1,int(config.get("slice_every",0))) == 0:
            render_slice_grid(sim.alive, sim.rgb, os.path.join(outdir, f"step_{t:03d}_slices.png"), axis=0)
        if config.get("verbose", False):
            print(f"step {t}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="3D Life with RGB birth colors + mutations")
    ap.add_argument("--config", type=str, default="example_config.json", help="Path to JSON config")
    args = ap.parse_args()
    with open(args.config, "r") as f:
        cfg = json.load(f)
    run_sim(cfg)
