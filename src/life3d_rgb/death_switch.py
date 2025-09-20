"""
Death Switch utilities for 3D Life RGB simulation.

Provides shared functionality for handling extinction in both UI and CLI modes:
- Frame management (listing, deletion)
- GIF creation with proper frame selection
- Extinction cleanup logic
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import imageio.v2 as imageio
except ImportError:
    imageio = None


def list_step_frames(run_dir: Path) -> List[Path]:
    """
    List step frame files in numerical order, excluding slice files.
    
    Args:
        run_dir: Directory containing step frames
        
    Returns:
        List of Path objects for step_###.png files, sorted numerically
    """
    step_files = []
    for path in run_dir.glob("step_*.png"):
        # Exclude slice files and final step files
        if "_slices" not in path.name and not path.name.startswith("final_"):
            step_files.append(path)
    
    # Sort by step number
    def extract_step_num(path):
        try:
            stem = path.stem  # "step_XXX"
            return int(stem.split("_")[1])
        except (IndexError, ValueError):
            return 0
    
    step_files.sort(key=extract_step_num)
    return step_files


def build_gif(frames: List[Path], out_gif: Path, fps: int = 8) -> bool:
    """
    Build animated GIF from frame list.
    
    Args:
        frames: List of frame file paths
        out_gif: Output GIF path
        fps: Frames per second
        
    Returns:
        True if GIF was created successfully, False otherwise
    """
    if not imageio:
        print("Warning: imageio not available, skipping GIF creation")
        return False
    
    if len(frames) < 2:
        print(f"Warning: Need at least 2 frames for GIF, found {len(frames)}")
        return False
    
    try:
        duration = 1.0 / max(1, fps)
        
        images = []
        for frame_path in frames:
            img = imageio.imread(str(frame_path))
            images.append(img)
        
        imageio.mimsave(str(out_gif), images, duration=duration, loop=0)
        
        # Verify GIF was created
        if out_gif.exists() and out_gif.stat().st_size > 0:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ GIF creation failed: {e}")
        return False


def delete_files(files: List[Path]) -> int:
    """
    Safe deletion of files with error handling.
    
    Args:
        files: List of file paths to delete
        
    Returns:
        Number of files successfully deleted
    """
    deleted_count = 0
    failed_files = []
    
    for file_path in files:
        try:
            if file_path.exists():
                file_path.unlink()
                deleted_count += 1
        except Exception as e:
            failed_files.append(f"{file_path.name}: {str(e)}")
    
    if failed_files:
        print(f"⚠️  Some files could not be deleted: {failed_files[:3]}")
        if len(failed_files) > 3:
            print(f"   ... and {len(failed_files) - 3} more")
    
    return deleted_count


def handle_extinction_cleanup(
    outdir: Path, 
    current_step: int, 
    last_alive_step: int,
    render_slices: bool = False,
    slice_every: int = 0
) -> Tuple[List[Path], int]:
    """
    Handle cleanup when extinction is detected.
    
    Args:
        outdir: Output directory containing frames
        current_step: Current simulation step where extinction was detected
        last_alive_step: Last step that had living cells
        render_slices: Whether slice rendering is enabled
        slice_every: Slice rendering interval
        
    Returns:
        Tuple of (remaining_valid_frames, deleted_frames_count)
    """
    deleted_count = 0
    
    # Delete the current extinct frame(s) if they exist
    current_frame = outdir / f"step_{current_step:03d}.png"
    if current_frame.exists():
        try:
            current_frame.unlink()
            deleted_count += 1
            print(f"[extinction] Deleted empty frame: {current_frame.name}")
        except Exception as e:
            print(f"⚠️  Could not delete {current_frame.name}: {e}")
    
    # Delete corresponding slice file if it exists
    if render_slices and slice_every > 0 and current_step % slice_every == 0:
        slice_file = outdir / f"step_{current_step:03d}_slices.png"
        if slice_file.exists():
            try:
                slice_file.unlink()
                deleted_count += 1
                print(f"[extinction] Deleted empty slice: {slice_file.name}")
            except Exception as e:
                print(f"⚠️  Could not delete {slice_file.name}: {e}")
    
    # Get remaining valid frames (up to last_alive_step)
    all_frames = list_step_frames(outdir)
    valid_frames = []
    
    for frame in all_frames:
        try:
            # Extract step number from filename
            stem = frame.stem  # "step_XXX"
            step_num = int(stem.split("_")[1])
            if step_num <= last_alive_step:
                valid_frames.append(frame)
        except (IndexError, ValueError):
            # Skip files with unexpected naming
            continue
    
    print(f"[extinction] step={current_step}, removed_empty_frames={deleted_count}")
    print(f"[extinction] valid_frames_remaining={len(valid_frames)} (up to step {last_alive_step})")
    
    return valid_frames, deleted_count


def create_gif_after_extinction(
    valid_frames: List[Path],
    out_gif: Path,
    fps: int = 8
) -> bool:
    """
    Create GIF from valid frames after extinction cleanup.
    
    Args:
        valid_frames: List of valid frame paths (non-empty frames only)
        out_gif: Output GIF path
        fps: Frames per second
        
    Returns:
        True if GIF was created successfully, False otherwise
    """
    if len(valid_frames) < 2:
        print(f"[extinction] Cannot create GIF: only {len(valid_frames)} non-empty frame(s)")
        return False
    
    print(f"[extinction] Creating GIF from {len(valid_frames)} non-empty frames...")
    success = build_gif(valid_frames, out_gif, fps)
    
    if success:
        print(f"✅ [extinction] Created GIF: {out_gif} ({len(valid_frames)} frames, {fps} FPS)")
    else:
        print(f"❌ [extinction] Failed to create GIF")
    
    return success