import argparse
import json
import os
import glob
from typing import Any, Dict, List
from pathlib import Path

from life3d import Life3DRGB
from visualize import render_voxels, render_slice_grid

try:
    import imageio.v2 as imageio
except ImportError:
    imageio = None

def get_step_frames(outdir: str) -> List[Path]:
    """Get step frame files in numerical order, excluding slice files."""
    step_files = []
    for path in Path(outdir).glob("step_*.png"):
        # Exclude slice files and final step files
        if "_slices" not in path.name and not path.name.startswith("final_"):
            step_files.append(path)
    
    # Sort by step number
    def extract_step_num(path):
        try:
            # Extract number from "step_XXX.png"
            stem = path.stem  # "step_XXX"
            return int(stem.split("_")[1])
        except (IndexError, ValueError):
            return 0
    
    step_files.sort(key=extract_step_num)
    return step_files

def create_gif(step_frames: List[Path], output_path: str, fps: int = 8) -> bool:
    """Create animated GIF from step frames."""
    if not imageio:
        print("Warning: imageio not available, skipping GIF creation")
        return False
    
    if len(step_frames) < 2:
        print(f"Warning: Need at least 2 frames for GIF, found {len(step_frames)}")
        return False
    
    try:
        print(f"Creating GIF from {len(step_frames)} frames...")
        duration = 1.0 / max(1, fps)
        
        images = []
        for frame_path in step_frames:
            img = imageio.imread(str(frame_path))
            images.append(img)
        
        imageio.mimsave(output_path, images, duration=duration, loop=0)
        
        # Verify GIF was created
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"✅ Created animated GIF: {output_path} ({len(step_frames)} frames, {fps} FPS)")
            return True
        else:
            print("❌ GIF creation failed: file not created or empty")
            return False
            
    except Exception as e:
        print(f"❌ GIF creation failed: {e}")
        return False

def delete_frames(frames: List[Path], also_delete_slices: bool = False) -> int:
    """Delete frame files after successful GIF creation."""
    deleted_count = 0
    failed_files = []
    
    for frame_path in frames:
        try:
            if frame_path.exists():
                frame_path.unlink()
                deleted_count += 1
        except Exception as e:
            failed_files.append(f"{frame_path.name}: {str(e)}")
    
    # Also delete slice files if requested
    if also_delete_slices:
        slice_files = list(frame_path.parent.glob("*_slices.png"))
        for slice_file in slice_files:
            try:
                if slice_file.exists():
                    slice_file.unlink()
                    deleted_count += 1
            except Exception as e:
                failed_files.append(f"{slice_file.name}: {str(e)}")
    
    if failed_files:
        print(f"⚠️  Some files could not be deleted: {failed_files[:3]}")
        if len(failed_files) > 3:
            print(f"   ... and {len(failed_files) - 3} more")
    
    return deleted_count

def run_sim(config: Dict[str, Any]) -> None:
    """Run simulation with JSON configuration."""
    shape = tuple(config["shape"])  # [Z,Y,X]
    steps = int(config.get("steps", 50))
    rule = config.get("rule", {"birth":[6], "survive":[5,6,7]})
    mutation = config.get("mutation", {
        "enable": True,
        "per_step_mutation_prob": 0.2,
        "per_birth_mutation_prob": 0.15,
        "max_mutants_per_step": 1,
        "mutation_std": 30.0,
        "p_interval": 0.2
    })
    seed_cells = config.get("seeds", [])
    outdir = config.get("outdir","./out")
    os.makedirs(outdir, exist_ok=True)

    # New configuration options
    render_slices = config.get("render_slices", False)  # Default false
    create_gif_flag = config.get("create_gif", False)
    gif_fps = config.get("gif_fps", 8)
    delete_frames_after = config.get("delete_frames_after", False)
    
    print(f"🚀 Starting 3D Life simulation")
    print(f"Grid: {shape[0]}×{shape[1]}×{shape[2]}, Steps: {steps}")
    print(f"Seeds: {len(seed_cells)}, Render slices: {render_slices}")
    print(f"Create GIF: {create_gif_flag} (FPS: {gif_fps})")
    
    sim = Life3DRGB(
        shape=shape, 
        rule=rule, 
        seed_cells=seed_cells,
        mutation=mutation, 
        color_inheritance_mode=config.get("color_inheritance_mode", "mean_r2"),
        color_params=config.get("color_params", {}),
        random_state=config.get("random_state")
    )

    # Initial diagnostics and render
    alive_count = sim.alive.sum()
    print(f"Step 0: {alive_count} alive cells")
    
    render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_000.png"), title="step 0")

    for t in range(1, steps+1):
        sim.step()
        
        # Diagnostics every 20 steps
        if t % 20 == 0:
            alive_count = sim.alive.sum()
            print(f"Step {t}: {alive_count} alive cells")
            
            # Early extinction detection
            if alive_count == 0:
                print(f"⚠️  Simulation extinct at step {t}. Stopping early.")
                break
        
        # Render step frame
        if t % max(1, int(config.get("render_every", 1))) == 0:
            render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_{t:03d}.png"), title=f"step {t}")
        
        # Render slice grid only if explicitly enabled and slice_every > 0
        slice_every = int(config.get("slice_every", 0))
        if render_slices and slice_every > 0 and t % slice_every == 0:
            render_slice_grid(sim.alive, sim.rgb, os.path.join(outdir, f"step_{t:03d}_slices.png"), axis=0)
            
        if config.get("verbose", False) and t % 10 == 0:
            print(f"  step {t}")

    # Final diagnostics
    final_alive = sim.alive.sum()
    print(f"🏁 Simulation complete. Final: {final_alive} alive cells")

    # GIF creation and frame management
    if create_gif_flag and imageio:
        step_frames = get_step_frames(outdir)
        if len(step_frames) >= 2:
            gif_path = os.path.join(outdir, "evolution.gif")
            gif_success = create_gif(step_frames, gif_path, gif_fps)
            
            if gif_success and delete_frames_after:
                deleted_count = delete_frames(step_frames, also_delete_slices=render_slices)
                print(f"🗑️  Deleted {deleted_count} frame files after GIF creation")
        else:
            print(f"⚠️  Cannot create GIF: only {len(step_frames)} frame(s) found")
    elif create_gif_flag and not imageio:
        print("⚠️  GIF creation requested but imageio not available")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="3D Life with RGB birth colors + mutations")
    ap.add_argument("--config", type=str, default="example_config.json", help="Path to JSON config")
    args = ap.parse_args()
    
    with open(args.config, "r") as f:
        cfg = json.load(f)
    
    run_sim(cfg)