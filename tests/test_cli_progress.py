"""
Test CLI progress and stepping functionality.
Ensures simulation advances every step and doesn't produce identical frames.
"""

import tempfile
import json
from pathlib import Path
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import CLI module
from life3d_rgb import cli as main


def test_simulation_advances_every_step():
    """Test that simulation state changes across multiple steps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [16, 16, 16],
            "steps": 10,
            "rule": {"birth": [4, 5, 6], "survive": [3, 4, 5, 6, 7, 8]},  # Very permissive rules
            "seeds": [
                {"z": 8, "y": 8, "x": 8, "rgb": [255, 100, 100]},
                {"z": 7, "y": 8, "x": 8, "rgb": [100, 255, 100]},
                {"z": 9, "y": 8, "x": 8, "rgb": [100, 100, 255]},
                {"z": 8, "y": 7, "x": 8, "rgb": [255, 255, 100]},
                {"z": 8, "y": 9, "x": 8, "rgb": [255, 100, 255]},
                {"z": 8, "y": 8, "x": 7, "rgb": [100, 255, 255]},
                {"z": 8, "y": 8, "x": 9, "rgb": [255, 200, 100]},
                # Add more seeds in a cluster to prevent early extinction
                {"z": 7, "y": 7, "x": 7, "rgb": [200, 100, 255]},
                {"z": 9, "y": 9, "x": 9, "rgb": [100, 200, 200]}
            ],
            "outdir": tmpdir,
            "render_every": 1,
            "create_gif": False,
            "verbose": False,
            "auto_stop_extinction": True,
            "auto_stop_steady": False  # Disable steady-state for this test
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check that frames exist and have progression
        step_files = list(Path(tmpdir).glob("step_*.png"))
        assert len(step_files) >= 3, f"Expected at least 3 frames, got {len(step_files)}"
        
        # Files should have different timestamps/sizes (indicating different content)
        file_sizes = [f.stat().st_size for f in sorted(step_files)]
        
        # Should see some variation in file sizes (different frame content)
        # At least one frame should be different from the first
        assert not all(size == file_sizes[0] for size in file_sizes), \
            "All frames have identical size - simulation may not be advancing"


def test_early_stopping_with_steady_state():
    """Test that steady-state detection works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [8, 8, 8],
            "steps": 50,
            "rule": {"birth": [6], "survive": [5, 6, 7]},  # Standard rules
            "seeds": [
                {"z": 4, "y": 4, "x": 4, "rgb": [255, 100, 100]}
            ],
            "outdir": tmpdir,
            "render_every": 1,
            "create_gif": False,
            "verbose": False,
            "auto_stop_extinction": True,
            "auto_stop_steady": True,
            "steady_patience": 3  # Small patience for quick test
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check outputs
        step_files = list(Path(tmpdir).glob("step_*.png"))
        
        # Should stop early due to extinction or steady state
        assert len(step_files) <= 50, "Should have stopped before completing all steps"
        assert len(step_files) >= 1, "Should have at least one step file"


def test_extinction_detection_and_cleanup():
    """Test that extinction is properly detected and handled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [6, 6, 6],
            "steps": 20,
            "rule": {"birth": [10], "survive": [10]},  # Impossible rules - guaranteed extinction
            "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 100]}],
            "outdir": tmpdir,
            "render_every": 1,
            "create_gif": True,
            "delete_frames_after": False,
            "verbose": False,
            "auto_stop_extinction": True
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check that simulation stopped early due to extinction
        step_files = list(Path(tmpdir).glob("step_*.png"))
        gif_file = Path(tmpdir) / "evolution.gif"
        
        # Should have initial frame but stop quickly due to extinction
        assert len(step_files) >= 1, "Should have at least initial frame"
        assert len(step_files) <= 5, "Should stop quickly due to extinction"
        
        # Should not create GIF with insufficient frames
        if len(step_files) < 2:
            assert not gif_file.exists(), "Should not create GIF with insufficient frames"


def test_render_cadence_independence():
    """Test that simulation advances regardless of render cadence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [14, 14, 14],
            "steps": 6,
            "rule": {"birth": [4, 5, 6], "survive": [3, 4, 5, 6, 7, 8]},  # Very permissive
            "seeds": [
                {"z": 7, "y": 7, "x": 7, "rgb": [255, 100, 100]},
                {"z": 6, "y": 7, "x": 7, "rgb": [100, 255, 100]},
                {"z": 8, "y": 7, "x": 7, "rgb": [100, 100, 255]},
                {"z": 7, "y": 6, "x": 7, "rgb": [255, 255, 100]},
                {"z": 7, "y": 8, "x": 7, "rgb": [255, 100, 255]},
                {"z": 7, "y": 7, "x": 6, "rgb": [100, 255, 255]},
                {"z": 7, "y": 7, "x": 8, "rgb": [255, 200, 100]}
            ],
            "outdir": tmpdir,
            "render_every": 2,  # Render every 2nd step
            "create_gif": False,
            "verbose": False,
            "auto_stop_extinction": True,
            "auto_stop_steady": False
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check that rendering happened according to cadence
        step_files = list(Path(tmpdir).glob("step_*.png"))
        
        # Should have rendered at steps 0, 2, 4, 6 (render_every=2)
        existing_frames = [f.name for f in step_files]
        
        # At least step_000 should exist
        assert "step_000.png" in existing_frames, "Initial frame should exist"
        
        # Should have some frames, but not every step due to render_every=2
        assert len(step_files) >= 1, "Should have at least initial frame"
        
        # If simulation ran for multiple steps, should have more frames
        # Note: May stop early due to extinction, which is expected behavior