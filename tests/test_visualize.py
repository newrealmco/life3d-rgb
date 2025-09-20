import numpy as np
import os
import tempfile
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from life3d_rgb.visualize import render_voxels, render_slice_grid

def test_render_voxels_smoke_test():
    """Smoke test: render a tiny grid to PNG using Agg backend."""
    # Create a simple 3x3x3 grid with a few alive cells
    alive = np.zeros((3, 3, 3), dtype=np.uint8)
    alive[1, 1, 1] = 1  # center cell
    alive[0, 1, 1] = 1  # one neighbor
    alive[2, 1, 1] = 1  # another neighbor
    
    # Create corresponding RGB values
    rgb = np.zeros((3, 3, 3, 3), dtype=np.uint8)
    rgb[0, 1, 1, 1] = 255  # center cell: red
    rgb[1, 0, 1, 1] = 255  # neighbor: green
    rgb[2, 2, 1, 1] = 255  # neighbor: blue
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Render should not crash
        render_voxels(
            alive=alive,
            rgb=rgb,
            out_path=tmp_path,
            title="Test render",
            figsize=(4, 4),
            dpi=50  # Low DPI for speed
        )
        
        # File should exist and have content
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_render_voxels_empty_grid():
    """Test rendering an empty grid doesn't crash."""
    alive = np.zeros((2, 2, 2), dtype=np.uint8)
    rgb = np.zeros((3, 2, 2, 2), dtype=np.uint8)
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        render_voxels(
            alive=alive,
            rgb=rgb,
            out_path=tmp_path,
            figsize=(3, 3),
            dpi=50
        )
        
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_render_voxels_custom_parameters():
    """Test rendering with custom elevation, azimuth, and alpha."""
    alive = np.ones((2, 2, 2), dtype=np.uint8)  # All cells alive
    rgb = np.ones((3, 2, 2, 2), dtype=np.uint8) * 128  # Gray color
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        render_voxels(
            alive=alive,
            rgb=rgb,
            out_path=tmp_path,
            elev=30,
            azim=60,
            alpha=0.7,
            figsize=(5, 5),
            dpi=50
        )
        
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_render_slice_grid_smoke_test():
    """Smoke test for slice grid rendering."""
    # Create a 3x3x3 grid with some pattern
    alive = np.zeros((3, 3, 3), dtype=np.uint8)
    alive[1, :, :] = 1  # Middle slice all alive
    
    rgb = np.zeros((3, 3, 3, 3), dtype=np.uint8)
    rgb[0, 1, :, :] = 255  # Red in middle slice
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        render_slice_grid(
            alive=alive,
            rgb=rgb,
            out_path=tmp_path,
            axis=0  # Z-axis slices
        )
        
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_render_slice_grid_different_axes():
    """Test slice grid rendering along different axes."""
    alive = np.zeros((4, 4, 4), dtype=np.uint8)
    alive[2, 2, :] = 1  # Line along X axis
    
    rgb = np.zeros((3, 4, 4, 4), dtype=np.uint8)
    rgb[0, 2, 2, :] = 255  # Red channel
    rgb[1, 2, 2, :] = 128  # Green channel
    rgb[2, 2, 2, :] = 64   # Blue channel
    
    for axis in [0, 1, 2]:  # Test all three axes
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            render_slice_grid(
                alive=alive,
                rgb=rgb,
                out_path=tmp_path,
                axis=axis
            )
            
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

def test_high_dpi_rendering():
    """Test that high DPI rendering works without crashing."""
    alive = np.zeros((2, 2, 2), dtype=np.uint8)
    alive[0, 0, 0] = 1
    alive[1, 1, 1] = 1
    
    rgb = np.zeros((3, 2, 2, 2), dtype=np.uint8)
    rgb[:, 0, 0, 0] = [255, 0, 0]    # Red
    rgb[:, 1, 1, 1] = [0, 255, 0]    # Green
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        render_voxels(
            alive=alive,
            rgb=rgb,
            out_path=tmp_path,
            figsize=(6, 6),
            dpi=150  # Higher DPI
        )
        
        assert os.path.exists(tmp_path)
        file_size = os.path.getsize(tmp_path)
        assert file_size > 0
        # Higher DPI should generally result in larger files
        assert file_size > 1000  # At least 1KB
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)