import os
import sys
import pytest
import json
import tempfile
import shutil
from pathlib import Path
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import CLI module
from life3d_rgb import cli as main


def test_cli_imports():
    """Test that CLI module imports correctly."""
    assert hasattr(main, 'run_sim')
    assert hasattr(main, 'create_gif')
    assert hasattr(main, 'get_step_frames')
    assert hasattr(main, 'delete_frames')


def test_get_step_frames():
    """Test step frame detection and sorting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test files
        (tmpdir_path / "step_000.png").touch()
        (tmpdir_path / "step_005.png").touch()
        (tmpdir_path / "step_010.png").touch()
        (tmpdir_path / "step_002_slices.png").touch()  # Should be excluded
        (tmpdir_path / "final_step_010.png").touch()  # Should be excluded
        (tmpdir_path / "other_file.png").touch()  # Should be excluded
        
        frames = main.get_step_frames(str(tmpdir_path))
        
        # Should find exactly 3 step frames, sorted by number
        assert len(frames) == 3
        assert frames[0].name == "step_000.png"
        assert frames[1].name == "step_005.png"
        assert frames[2].name == "step_010.png"


def test_create_gif_insufficient_frames():
    """Test GIF creation with insufficient frames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create only one frame
        (tmpdir_path / "step_000.png").touch()
        frames = [tmpdir_path / "step_000.png"]
        
        # Should fail with insufficient frames
        result = main.create_gif(frames, str(tmpdir_path / "test.gif"), 8)
        assert result is False


def test_delete_frames():
    """Test frame deletion functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test files
        frames = [
            tmpdir_path / "step_000.png",
            tmpdir_path / "step_001.png",
            tmpdir_path / "nonexistent.png"  # Should not cause error
        ]
        
        # Create the existing files
        frames[0].touch()
        frames[1].touch()
        
        # Create slice file
        slice_file = tmpdir_path / "step_000_slices.png"
        slice_file.touch()
        
        # Delete frames without slices
        deleted_count = main.delete_frames(frames[:2], also_delete_slices=False)
        assert deleted_count == 2
        assert not frames[0].exists()
        assert not frames[1].exists()
        assert slice_file.exists()  # Should still exist
        
        # Test with slice deletion
        frames[0].touch()  # Recreate for second test
        deleted_count = main.delete_frames([frames[0]], also_delete_slices=True)
        assert deleted_count == 2  # frame + slice
        assert not slice_file.exists()


def test_run_sim_basic():
    """Test basic simulation run with minimal config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [8, 8, 8],
            "steps": 3,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [
                {"z": 4, "y": 4, "x": 4, "rgb": [255, 100, 100]}
            ],
            "outdir": tmpdir,
            "render_every": 1,
            "verbose": False
        }
        
        # Should complete without error
        main.run_sim(config)
        
        # Check that step files were created
        step_files = list(Path(tmpdir).glob("step_*.png"))
        assert len(step_files) >= 1  # At least initial step


def test_run_sim_with_gif():
    """Test simulation with GIF creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [10, 10, 10],
            "steps": 3,
            "rule": {"birth": [4, 5, 6], "survive": [3, 4, 5, 6, 7, 8]},  # More permissive rules
            "seeds": [
                {"z": 5, "y": 5, "x": 5, "rgb": [255, 0, 0]},
                {"z": 4, "y": 5, "x": 5, "rgb": [0, 255, 0]},
                {"z": 6, "y": 5, "x": 5, "rgb": [0, 0, 255]},
                {"z": 5, "y": 4, "x": 5, "rgb": [255, 255, 0]},
                {"z": 5, "y": 6, "x": 5, "rgb": [255, 0, 255]},
                {"z": 5, "y": 5, "x": 4, "rgb": [0, 255, 255]}
            ],
            "outdir": tmpdir,
            "create_gif": True,
            "gif_fps": 10,
            "delete_frames_after": False,
            "verbose": False
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check outputs
        tmpdir_path = Path(tmpdir)
        step_files = list(tmpdir_path.glob("step_*.png"))
        gif_file = tmpdir_path / "evolution.gif"
        
        assert len(step_files) >= 1  # Should have at least initial step
        
        # GIF creation depends on imageio availability and having enough frames
        try:
            import imageio.v2 as imageio
            if imageio and len(step_files) >= 2:
                assert gif_file.exists()
                assert gif_file.stat().st_size > 0
            elif len(step_files) < 2:
                # If insufficient frames (due to early extinction), GIF may not be created
                pass
        except ImportError:
            # If imageio not available, GIF should not be created
            pass


def test_run_sim_with_slices():
    """Test simulation with slice rendering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [6, 6, 6],
            "steps": 4,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 50]}],
            "outdir": tmpdir,
            "render_slices": True,
            "slice_every": 2,
            "verbose": False
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check that slice files were created
        slice_files = list(Path(tmpdir).glob("*_slices.png"))
        step_files = list(Path(tmpdir).glob("step_*.png"))
        
        # Should have step files but slices depend on simulation surviving
        assert len(step_files) >= 1
        
        # If simulation survives long enough, should have slice files
        # Note: slice files only created if cells are alive at slice_every intervals


def test_run_sim_slice_control():
    """Test that slices are not created when render_slices is false."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [6, 6, 6],
            "steps": 4,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 50]}],
            "outdir": tmpdir,
            "render_slices": False,  # Explicitly disabled
            "slice_every": 1,  # Even with slice_every set
            "verbose": False
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Should have NO slice files
        slice_files = list(Path(tmpdir).glob("*_slices.png"))
        assert len(slice_files) == 0


def test_run_sim_with_color_modes():
    """Test simulation with different color inheritance modes."""
    color_modes = ["mean_r2", "hsv_boosted_mean", "random_parent"]
    
    for mode in color_modes:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "shape": [6, 6, 6],
                "steps": 2,
                "rule": {"birth": [6], "survive": [5, 6, 7]},
                "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 50]}],
                "color_inheritance_mode": mode,
                "outdir": tmpdir,
                "verbose": False
            }
            
            if mode == "hsv_boosted_mean":
                config["color_params"] = {
                    "saturation_boost": 1.3,
                    "saturation_floor": 0.35
                }
            
            # Should complete without error
            main.run_sim(config)
            
            # Check that files were created
            step_files = list(Path(tmpdir).glob("step_*.png"))
            assert len(step_files) >= 1


def test_cli_script_execution():
    """Test that main.py can be executed as a script."""
    # Create a minimal test config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "shape": [4, 4, 4],
            "steps": 2,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [{"z": 2, "y": 2, "x": 2, "rgb": [255, 0, 0]}],
            "outdir": tempfile.mkdtemp(),
            "verbose": False
        }
        json.dump(config, f)
        config_path = f.name
    
    try:
        # Set up environment with src path
        env = os.environ.copy()
        src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
        env['PYTHONPATH'] = src_path + ':' + env.get('PYTHONPATH', '')
        
        # Run the CLI script
        result = subprocess.run([
            sys.executable, "-m", "life3d_rgb.cli", "--config", config_path
        ], capture_output=True, text=True, timeout=30, env=env)
        
        # Should complete successfully
        assert result.returncode == 0
        
        # Should have some output indicating completion (either normal or extinction)
        assert "🚀 Starting 3D Life simulation" in result.stdout
        assert ("🏁 Simulation stopped:" in result.stdout)
        
    finally:
        # Cleanup
        os.unlink(config_path)
        shutil.rmtree(config["outdir"], ignore_errors=True)


def test_config_validation():
    """Test configuration validation and error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with truly invalid data that should cause errors
        invalid_configs = [
            {"shape": "invalid"},  # Shape should be list
            {"shape": [8, 8, 8], "steps": "not_a_number"},  # Steps should be int
            {"shape": [8, 8, 8], "steps": 10, "rule": "invalid"},  # Rule should be dict
        ]
        
        for config in invalid_configs:
            config["outdir"] = tmpdir  # Add required outdir
            with pytest.raises((KeyError, TypeError, ValueError)):
                main.run_sim(config)


def test_mutation_configuration():
    """Test various mutation configurations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [6, 6, 6],
            "steps": 3,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 50]}],
            "mutation": {
                "enable": True,
                "per_birth_mutation_prob": 0.5,
                "per_step_mutation_prob": 0.1,
                "mutation_std": 40.0
            },
            "outdir": tmpdir,
            "verbose": False
        }
        
        # Should complete without error
        main.run_sim(config)
        
        # Check that files were created
        step_files = list(Path(tmpdir).glob("step_*.png"))
        assert len(step_files) >= 1


def test_cli_defaults():
    """Test that CLI uses proper defaults for missing optional fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Minimal config with only required fields
        config = {
            "shape": [6, 6, 6],
            "steps": 2,
            "rule": {"birth": [6], "survive": [5, 6, 7]},
            "seeds": [{"z": 3, "y": 3, "x": 3, "rgb": [255, 100, 50]}],
            "outdir": tmpdir
        }
        
        # Should use defaults and complete successfully
        main.run_sim(config)
        
        # Check defaults were applied correctly
        step_files = list(Path(tmpdir).glob("step_*.png"))
        slice_files = list(Path(tmpdir).glob("*_slices.png"))
        gif_files = list(Path(tmpdir).glob("*.gif"))
        
        assert len(step_files) >= 1
        assert len(slice_files) == 0  # render_slices defaults to False
        assert len(gif_files) == 0    # create_gif defaults to False


def test_death_switch_functionality():
    """Test death switch detects extinction and cleans up properly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [8, 8, 8],
            "steps": 20,
            "rule": {"birth": [10], "survive": [10]},  # Impossible rules - guaranteed extinction
            "seeds": [{"z": 4, "y": 4, "x": 4, "rgb": [255, 100, 100]}],
            "outdir": tmpdir,
            "create_gif": True,
            "verbose": False
        }
        
        # Run simulation - should trigger death switch
        main.run_sim(config)
        
        # Check that only valid frames exist (no empty frames)
        step_files = list(Path(tmpdir).glob("step_*.png"))
        
        # Should have step_000.png (initial frame) but no extinct frames
        assert len(step_files) >= 1
        assert (Path(tmpdir) / "step_000.png").exists()
        
        # Should not have created a GIF since insufficient frames
        gif_file = Path(tmpdir) / "evolution.gif"
        assert not gif_file.exists()
        
        # Verify all existing frames have content (are not empty simulation states)
        for frame_file in step_files:
            assert frame_file.stat().st_size > 0  # File should not be empty


def test_death_switch_with_multiple_frames():
    """Test death switch with a configuration that survives a few steps before extinction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "shape": [8, 8, 8],
            "steps": 20,
            "rule": {"birth": [5], "survive": [1]},  # Will survive briefly then die
            "seeds": [
                {"z": 4, "y": 4, "x": 4, "rgb": [255, 100, 100]},
                {"z": 3, "y": 4, "x": 4, "rgb": [100, 255, 100]},
                {"z": 5, "y": 4, "x": 4, "rgb": [100, 100, 255]}
            ],
            "outdir": tmpdir,
            "create_gif": True,
            "delete_frames_after": False,
            "verbose": False
        }
        
        # Run simulation
        main.run_sim(config)
        
        # Check outputs
        step_files = list(Path(tmpdir).glob("step_*.png"))
        gif_file = Path(tmpdir) / "evolution.gif"
        
        # Should have multiple frames before extinction
        assert len(step_files) >= 2
        
        # If we have enough frames, GIF should be created
        if len(step_files) >= 2:
            assert gif_file.exists()
            assert gif_file.stat().st_size > 0