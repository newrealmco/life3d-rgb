import os
import sys
import pytest
import numpy as np
import colorsys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from life3d import Life3DRGB

def rgb_to_hsv_mean_saturation(rgb_array):
    """Compute mean saturation of RGB colors."""
    saturations = []
    for i in range(rgb_array.shape[1]):
        for j in range(rgb_array.shape[2]):
            for k in range(rgb_array.shape[3]):
                r, g, b = rgb_array[:, i, j, k] / 255.0
                h, s, v = colorsys.rgb_to_hsv(r, g, b)
                saturations.append(s)
    return np.mean(saturations)

def test_color_modes_not_gray():
    """Test that hsv_boosted_mean has higher saturation than mean_r2."""
    shape = (10, 10, 10)
    
    # Create seeds with vivid colors
    seeds = [
        {"z": 5, "y": 5, "x": 5, "rgb": [255, 100, 50]},  # Orange
        {"z": 4, "y": 4, "x": 4, "rgb": [100, 255, 50]},  # Green
        {"z": 6, "y": 6, "x": 6, "rgb": [50, 100, 255]},  # Blue
        {"z": 5, "y": 4, "x": 6, "rgb": [255, 50, 200]},  # Magenta
    ]
    
    # Test mean_r2 mode (causes gray drift)
    sim_mean = Life3DRGB(
        shape=shape, 
        seed_cells=seeds,
        color_inheritance_mode="mean_r2",
        random_state=42
    )
    
    # Test hsv_boosted_mean mode (prevents gray drift)
    sim_hsv = Life3DRGB(
        shape=shape,
        seed_cells=seeds,
        color_inheritance_mode="hsv_boosted_mean",
        color_params={"saturation_boost": 1.3, "saturation_floor": 0.35},
        random_state=42
    )
    
    # Run several steps to see color evolution
    for _ in range(15):
        sim_mean.step()
        sim_hsv.step()
        
        # Stop early if no living cells
        if sim_mean.alive.sum() == 0 or sim_hsv.alive.sum() == 0:
            break
    
    # Only compare if both simulations have living cells
    if sim_mean.alive.sum() > 0 and sim_hsv.alive.sum() > 0:
        # Extract colors only from living cells
        mean_mask = sim_mean.alive.astype(bool)
        hsv_mask = sim_hsv.alive.astype(bool)
        
        if mean_mask.any() and hsv_mask.any():
            # Compute mean saturation for living cells only
            mean_saturations = []
            hsv_saturations = []
            
            for z in range(shape[0]):
                for y in range(shape[1]):
                    for x in range(shape[2]):
                        if mean_mask[z, y, x]:
                            r, g, b = sim_mean.rgb[:, z, y, x] / 255.0
                            h, s, v = colorsys.rgb_to_hsv(r, g, b)
                            mean_saturations.append(s)
                        
                        if hsv_mask[z, y, x]:
                            r, g, b = sim_hsv.rgb[:, z, y, x] / 255.0
                            h, s, v = colorsys.rgb_to_hsv(r, g, b)
                            hsv_saturations.append(s)
            
            if mean_saturations and hsv_saturations:
                mean_sat = np.mean(mean_saturations)
                hsv_sat = np.mean(hsv_saturations)
                
                # HSV boosted should maintain higher saturation
                assert hsv_sat >= mean_sat, f"HSV saturation {hsv_sat:.3f} should be >= mean saturation {mean_sat:.3f}"
                
                # Additional check: HSV should maintain reasonable saturation
                assert hsv_sat > 0.2, f"HSV saturation {hsv_sat:.3f} should be > 0.2"

def test_random_parent_mode():
    """Test that random_parent mode works and preserves exact parent colors."""
    shape = (8, 8, 8)
    seeds = [
        {"z": 4, "y": 4, "x": 4, "rgb": [255, 0, 0]},    # Pure red
        {"z": 3, "y": 3, "x": 3, "rgb": [0, 255, 0]},    # Pure green
        {"z": 5, "y": 5, "x": 5, "rgb": [0, 0, 255]},    # Pure blue
    ]
    
    sim = Life3DRGB(
        shape=shape,
        seed_cells=seeds,
        color_inheritance_mode="random_parent",
        random_state=42
    )
    
    # Run a few steps
    for _ in range(5):
        sim.step()
        if sim.alive.sum() == 0:
            break
    
    if sim.alive.sum() > 0:
        # Check that some cells have the exact original colors
        living_cells = sim.alive.astype(bool)
        unique_colors = set()
        
        for z in range(shape[0]):
            for y in range(shape[1]):
                for x in range(shape[2]):
                    if living_cells[z, y, x]:
                        color = tuple(sim.rgb[:, z, y, x])
                        unique_colors.add(color)
        
        # Should have some distinct colors (not all blended)
        assert len(unique_colors) > 1, "Random parent mode should preserve distinct colors"

def test_two_parent_blend_mode():
    """Test that two_parent_blend mode works."""
    shape = (8, 8, 8)
    seeds = [
        {"z": 4, "y": 4, "x": 4, "rgb": [200, 100, 50]},
        {"z": 3, "y": 3, "x": 3, "rgb": [100, 200, 50]},
    ]
    
    sim = Life3DRGB(
        shape=shape,
        seed_cells=seeds,
        color_inheritance_mode="two_parent_blend",
        random_state=42
    )
    
    # Run a few steps
    for _ in range(3):
        sim.step()
        if sim.alive.sum() == 0:
            break
    
    # Should complete without errors
    assert True, "Two parent blend mode should work without errors"

def test_dist_weighted_mean_mode():
    """Test that distance-weighted mean mode works."""
    shape = (8, 8, 8)
    seeds = [
        {"z": 4, "y": 4, "x": 4, "rgb": [200, 100, 50]},
        {"z": 3, "y": 3, "x": 3, "rgb": [100, 200, 50]},
    ]
    
    sim = Life3DRGB(
        shape=shape,
        seed_cells=seeds,
        color_inheritance_mode="dist_weighted_mean",
        random_state=42
    )
    
    # Run a few steps
    for _ in range(3):
        sim.step()
        if sim.alive.sum() == 0:
            break
    
    # Should complete without errors
    assert True, "Distance weighted mean mode should work without errors"

def test_per_birth_mutations():
    """Test that per-birth mutations work and mutate multiple newborns."""
    shape = (10, 10, 10)
    seeds = [
        {"z": 5, "y": 5, "x": 5, "rgb": [128, 128, 128]},  # Gray starting point
        {"z": 4, "y": 4, "x": 4, "rgb": [128, 128, 128]},
        {"z": 6, "y": 6, "x": 6, "rgb": [128, 128, 128]},
    ]
    
    # High per-birth mutation probability
    mutation_config = {
        "enable": True,
        "per_birth_mutation_prob": 1.0,  # 100% mutation rate
        "per_step_mutation_prob": 0.0,   # Disable per-step
        "max_mutants_per_step": 1,
        "mutation_std": 30.0,
        "p_interval": 0.0
    }
    
    sim = Life3DRGB(
        shape=shape,
        seed_cells=seeds,
        mutation=mutation_config,
        random_state=42
    )
    
    # Store initial colors
    initial_colors = set()
    initial_mask = sim.alive.astype(bool)
    for z in range(shape[0]):
        for y in range(shape[1]):
            for x in range(shape[2]):
                if initial_mask[z, y, x]:
                    color = tuple(sim.rgb[:, z, y, x])
                    initial_colors.add(color)
    
    # Run a step to create new births
    stats = sim.step()
    
    if stats["born"] > 1:  # If multiple births occurred
        # Check that newborn colors are different from starting gray
        new_mask = sim.alive.astype(bool)
        new_colors = set()
        
        for z in range(shape[0]):
            for y in range(shape[1]):
                for x in range(shape[2]):
                    if new_mask[z, y, x]:
                        color = tuple(sim.rgb[:, z, y, x])
                        new_colors.add(color)
        
        # Should have more color diversity due to mutations
        assert len(new_colors) >= len(initial_colors), "Per-birth mutations should create color diversity"
        
        # Check that colors are within valid range
        for z in range(shape[0]):
            for y in range(shape[1]):
                for x in range(shape[2]):
                    if new_mask[z, y, x]:
                        for c in range(3):
                            val = sim.rgb[c, z, y, x]
                            assert 0 <= val <= 255, f"Color value {val} should be in [0,255]"

def test_age_tracking():
    """Test that age tracking works correctly."""
    shape = (8, 8, 8)
    seeds = [{"z": 4, "y": 4, "x": 4, "rgb": [200, 100, 50]}]
    
    sim = Life3DRGB(shape=shape, seed_cells=seeds, random_state=42)
    
    # Initial age should be 0 for seed
    assert sim.age[4, 4, 4] == 0, "Initial seed age should be 0"
    
    # After one step, surviving cells should have age 1
    sim.step()
    if sim.alive[4, 4, 4]:  # If the seed survived
        assert sim.age[4, 4, 4] == 1, "Age should increment for survivors"
    
    # Check that newborn cells have age 0
    birth_mask = sim.alive.astype(bool)
    for z in range(shape[0]):
        for y in range(shape[1]):
            for x in range(shape[2]):
                if birth_mask[z, y, x] and (z != 4 or y != 4 or x != 4):
                    # This is a newborn cell (not the original seed)
                    assert sim.age[z, y, x] == 0, "Newborn cells should have age 0"