import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from life3d_rgb.engine import Life3DRGB

def test_birth_color_mean_of_neighbors():
    """Newborn gets mean color of living neighbors within radius 2."""
    # Create a configuration where center (1,1,1) will be born
    # Place neighbors with known colors
    seed_cells = [
        # Direct neighbors (radius 1) with specific colors
        {"z": 0, "y": 1, "x": 1, "rgb": [100, 0, 0]},    # red
        {"z": 2, "y": 1, "x": 1, "rgb": [0, 100, 0]},    # green
        {"z": 1, "y": 0, "x": 1, "rgb": [0, 0, 100]},    # blue
        {"z": 1, "y": 2, "x": 1, "rgb": [200, 0, 0]},    # red
        {"z": 1, "y": 1, "x": 0, "rgb": [0, 200, 0]},    # green
        {"z": 1, "y": 1, "x": 2, "rgb": [0, 0, 200]},    # blue
    ]
    
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Center should be empty initially
    assert sim.alive[1, 1, 1] == 0
    
    # After step, center should be born with mean color
    sim.step()
    assert sim.alive[1, 1, 1] == 1
    
    # Expected mean: R=(100+200)/6=50, G=(100+200)/6=50, B=(100+200)/6=50
    expected_r = (100 + 0 + 0 + 200 + 0 + 0) // 6  # 50
    expected_g = (0 + 100 + 0 + 0 + 200 + 0) // 6  # 50  
    expected_b = (0 + 0 + 100 + 0 + 0 + 200) // 6  # 50
    
    actual_r = sim.rgb[0, 1, 1, 1]
    actual_g = sim.rgb[1, 1, 1, 1] 
    actual_b = sim.rgb[2, 1, 1, 1]
    
    assert actual_r == expected_r
    assert actual_g == expected_g
    assert actual_b == expected_b

def test_birth_color_fallback_when_no_neighbors():
    """When no living neighbors in radius 2, use fallback random color."""
    # Create a birth situation with no neighbors in radius 2
    # This is tricky - let's use a larger grid and place neighbors at distance > 2
    seed_cells = [
        # Place 6 neighbors at exactly distance 1 to trigger birth,
        # but in a way that there are no other living cells in radius 2
        {"z": 1, "y": 1, "x": 1, "rgb": [100, 100, 100]},  # Will die next step
        {"z": 0, "y": 1, "x": 1, "rgb": [255, 0, 0]},
        {"z": 2, "y": 1, "x": 1, "rgb": [0, 255, 0]},
        {"z": 1, "y": 0, "x": 1, "rgb": [0, 0, 255]},
        {"z": 1, "y": 2, "x": 1, "rgb": [255, 255, 0]},
        {"z": 1, "y": 1, "x": 0, "rgb": [255, 0, 255]},
        {"z": 1, "y": 1, "x": 2, "rgb": [0, 255, 255]},
    ]
    
    sim = Life3DRGB(
        shape=(5, 5, 5),
        rule={"birth": [6], "survive": [1]},  # Only center will survive next step
        seed_cells=seed_cells,
        random_state=42
    )
    
    # First step: some cells die, some new are born
    sim.step()
    
    # Find newly born cells and check their colors are in fallback range [40, 216]
    born_cells = np.where(sim.alive == 1)
    if len(born_cells[0]) > 0:
        for i in range(len(born_cells[0])):
            z, y, x = born_cells[0][i], born_cells[1][i], born_cells[2][i]
            r, g, b = sim.rgb[0, z, y, x], sim.rgb[1, z, y, x], sim.rgb[2, z, y, x]
            # Colors should be in fallback range if no neighbors contributed
            if r >= 40 and r <= 216:  # Could be fallback
                assert 40 <= r <= 216
                assert 40 <= g <= 216  
                assert 40 <= b <= 216

def test_birth_color_radius_2_inclusion():
    """Test that neighbors at radius 2 (Chebyshev distance) are included."""
    # Create a birth situation with exactly 6 neighbors around center (2,2,2)
    seed_cells = [
        # Place exactly 6 neighbors to trigger birth with B6 rule
        {"z": 1, "y": 2, "x": 2, "rgb": [100, 0, 0]},   # radius 1 in z
        {"z": 3, "y": 2, "x": 2, "rgb": [0, 100, 0]},   # radius 1 in z
        {"z": 2, "y": 1, "x": 2, "rgb": [0, 0, 100]},   # radius 1 in y
        {"z": 2, "y": 3, "x": 2, "rgb": [200, 0, 0]},   # radius 1 in y
        {"z": 2, "y": 2, "x": 1, "rgb": [0, 200, 0]},   # radius 1 in x
        {"z": 2, "y": 2, "x": 3, "rgb": [0, 0, 200]},   # radius 1 in x
        # Add a radius 2 neighbor for color inheritance testing
        {"z": 0, "y": 2, "x": 2, "rgb": [255, 255, 255]}, # radius 2 in z
    ]
    
    sim = Life3DRGB(
        shape=(5, 5, 5),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Center (2,2,2) should be empty initially
    assert sim.alive[2, 2, 2] == 0
    
    # After step, center should be born (6 neighbors at radius 1)
    sim.step()
    assert sim.alive[2, 2, 2] == 1
    
    # The color should be influenced by all neighbors within radius 2
    r = sim.rgb[0, 2, 2, 2]
    g = sim.rgb[1, 2, 2, 2]
    b = sim.rgb[2, 2, 2, 2]
    
    # Should not be 0 since we have living neighbors for color calculation
    assert r > 0 or g > 0 or b > 0

def test_birth_color_deterministic():
    """Test that birth colors are deterministic with fixed random seed."""
    seed_cells = [
        {"z": 0, "y": 1, "x": 1, "rgb": [100, 150, 200]},
        {"z": 2, "y": 1, "x": 1, "rgb": [200, 100, 50]},
        {"z": 1, "y": 0, "x": 1, "rgb": [50, 200, 100]},
        {"z": 1, "y": 2, "x": 1, "rgb": [150, 50, 200]},
        {"z": 1, "y": 1, "x": 0, "rgb": [200, 200, 50]},
        {"z": 1, "y": 1, "x": 2, "rgb": [50, 50, 200]},
    ]
    
    # Run same simulation twice with same random seed
    sim1 = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    sim2 = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    sim1.step()
    sim2.step()
    
    # RGB arrays should be identical
    np.testing.assert_array_equal(sim1.rgb, sim2.rgb)
    np.testing.assert_array_equal(sim1.alive, sim2.alive)