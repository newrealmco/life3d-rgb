import argparse
import json
import os
import glob
import hashlib
import numpy as np
from typing import Any, Dict, List
from pathlib import Path
try:
    from importlib.resources import files
except ImportError:
    # Fallback for Python < 3.9
    from importlib_resources import files

from .engine import Life3DRGB
from .visualize import render_voxels, render_slice_grid
from .death_switch import (
    list_step_frames, build_gif, delete_files,
    handle_extinction_cleanup, create_gif_after_extinction
)

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

def hash_alive(alive: np.ndarray) -> str:
    """Create hash of alive state for steady-state detection."""
    return hashlib.md5(alive.view(np.uint8)).hexdigest()

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

    # Configuration options
    render_slices = config.get("render_slices", False)
    create_gif_flag = config.get("create_gif", False)
    gif_fps = config.get("gif_fps", 8)
    delete_frames_after = config.get("delete_frames_after", False)
    render_every = max(1, int(config.get("render_every", 1)))
    slice_every = int(config.get("slice_every", 0))
    final_only = config.get("render_final_only", False)
    
    # Auto-stop settings
    auto_stop_extinction = config.get("auto_stop_extinction", True)
    auto_stop_steady = config.get("auto_stop_steady", True) 
    steady_patience = int(config.get("steady_patience", 50))
    
    print(f"🚀 Starting 3D Life simulation")
    print(f"Grid: {shape[0]}×{shape[1]}×{shape[2]}, Steps: {steps}")
    print(f"Seeds: {len(seed_cells)}, Render slices: {render_slices}")
    print(f"Create GIF: {create_gif_flag} (FPS: {gif_fps})")
    print(f"Auto-stop: extinction={auto_stop_extinction}, steady={auto_stop_steady} (patience={steady_patience})")
    
    sim = Life3DRGB(
        shape=shape, 
        rule=rule, 
        seed_cells=seed_cells,
        mutation=mutation, 
        color_inheritance_mode=config.get("color_inheritance_mode", "mean_r2"),
        color_params=config.get("color_params", {}),
        random_state=config.get("random_state")
    )

    # Initial render (step 0)
    alive_count = int(sim.alive.sum())
    print(f"Step 0: {alive_count} alive cells")
    
    if not final_only:
        render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_000.png"), title="step 0")
        if render_slices and slice_every > 0:  # Render initial slices if enabled
            render_slice_grid(sim.alive, sim.rgb, os.path.join(outdir, f"step_000_slices.png"), axis=0)

    # Main simulation loop with robust stepping and steady-state detection
    extinct = False
    steady_stopped = False
    last_alive_step = 0 if alive_count > 0 else -1
    
    # Steady-state detection
    steady_cnt = 0
    prev_hash = hash_alive(sim.alive)
    
    actual_steps = 0
    
    for step in range(1, steps + 1):
        # ALWAYS advance simulation
        sim.step()
        actual_steps = step
        
        # Get current state
        cur_alive = sim.alive
        cur_hash = hash_alive(cur_alive)
        alive_count = int(cur_alive.sum())
        
        # Track last step with living cells
        if alive_count > 0:
            last_alive_step = step
        
        # Extinction check - stop immediately if no cells alive
        if alive_count == 0 and auto_stop_extinction:
            extinct = True
            print(f"⚠️  Population extinct at step {step}. Stopping early.")
            break
        
        # Steady-state detection
        if auto_stop_steady and alive_count > 0:
            if cur_hash == prev_hash:
                steady_cnt += 1
                if steady_cnt >= steady_patience:
                    steady_stopped = True
                    print(f"⚠️  Steady state detected at step {step} (unchanged for {steady_cnt} steps). Stopping early.")
                    break
            else:
                steady_cnt = 0
                prev_hash = cur_hash
        
        # Render frames based on cadence (not tied to stepping)
        if not final_only and (step % render_every == 0):
            render_voxels(sim.alive, sim.rgb, os.path.join(outdir, f"step_{step:03d}.png"), title=f"step {step}")
            
            # Render slice grid if enabled
            if render_slices and slice_every > 0 and (step % slice_every == 0):
                render_slice_grid(sim.alive, sim.rgb, os.path.join(outdir, f"step_{step:03d}_slices.png"), axis=0)
        
        # Periodic logging for debugging
        if step % 10 == 0:
            print(f"[dbg] step={step} alive={alive_count} steady={steady_cnt}")
        
        if config.get("verbose", False) and step % 10 == 0:
            print(f"  step {step}")

    # Final diagnostics
    final_alive = sim.alive.sum()
    stop_reason = "normal completion"
    if extinct:
        stop_reason = f"extinction at step {actual_steps}"
    elif steady_stopped:
        stop_reason = f"steady state at step {actual_steps}"
    
    print(f"🏁 Simulation stopped: {stop_reason}. Final: {final_alive} alive cells")

    # GIF creation with death switch support
    gif_status = "No GIF created"
    
    if create_gif_flag and imageio:
        # Get all step frames
        step_frames = get_step_frames(outdir)
        
        # Apply death switch: only use frames up to last_alive_step
        if last_alive_step >= 0:
            valid_frames = []
            for frame in step_frames:
                try:
                    # Extract step number from filename
                    stem = frame.stem  # "step_XXX"
                    step_num = int(stem.split("_")[1])
                    if step_num <= last_alive_step:
                        valid_frames.append(frame)
                except (IndexError, ValueError):
                    continue
            step_frames = valid_frames
        
        if len(step_frames) >= 2:
            gif_path = os.path.join(outdir, "evolution.gif")
            gif_success = create_gif(step_frames, gif_path, gif_fps)
            
            if gif_success:
                gif_status = f"GIF created ({len(step_frames)} frames)"
                if delete_frames_after:
                    deleted_count = delete_frames(step_frames, also_delete_slices=render_slices)
                    print(f"🗑️  Deleted {deleted_count} frame files after GIF creation")
                    gif_status += f", {deleted_count} frames deleted"
            else:
                gif_status = "GIF creation failed"
        else:
            print(f"⚠️  Cannot create GIF: only {len(step_frames)} frame(s) found")
            gif_status = f"Insufficient frames ({len(step_frames)})"
    elif create_gif_flag and not imageio:
        print("⚠️  GIF creation requested but imageio not available")
        gif_status = "imageio not available"
    
    # Final report
    if extinct or steady_stopped:
        print(f"\n💀 [AUTO-STOP ACTIVATED]")
        print(f"   Reason: {stop_reason}")
        print(f"   Valid frames: {len(get_step_frames(outdir))}")
        print(f"   {gif_status}")

def load_preset(preset_name: str) -> Dict[str, Any]:
    """Load a preset configuration from package resources."""
    try:
        preset_files = files("life3d_rgb.presets")
        preset_path = preset_files / f"{preset_name}.json"
        return json.loads(preset_path.read_text())
    except Exception as e:
        raise FileNotFoundError(f"Preset '{preset_name}' not found: {e}")

def main():
    """Main CLI entry point."""
    ap = argparse.ArgumentParser(description="3D Life with RGB birth colors + mutations")
    ap.add_argument("--config", type=str, help="Path to JSON config file")
    ap.add_argument("--preset", type=str, help="Use built-in preset (sample, starburst, example_config)")
    ap.add_argument("--list-presets", action="store_true", help="List available presets")
    args = ap.parse_args()
    
    if args.list_presets:
        try:
            preset_files = files("life3d_rgb.presets")
            presets = [f.stem for f in preset_files.iterdir() if f.suffix == ".json"]
            print("Available presets:")
            for preset in sorted(presets):
                print(f"  {preset}")
        except Exception as e:
            print(f"Error listing presets: {e}")
        return
    
    if args.preset:
        cfg = load_preset(args.preset)
    elif args.config:
        with open(args.config, "r") as f:
            cfg = json.load(f)
    else:
        ap.error("Either --config or --preset is required")
    
    run_sim(cfg)

if __name__ == "__main__":
    main()