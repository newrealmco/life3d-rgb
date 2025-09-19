import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from life3d import Life3DRGB

def test_single_cell_dies_underpopulation():
    """A single alive cell should die due to underpopulation (has 0 neighbors)."""
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=[{"z": 1, "y": 1, "x": 1, "rgb": [255, 255, 255]}],
        random_state=42
    )
    
    # Initially one cell alive
    assert sim.alive.sum() == 1
    assert sim.alive[1, 1, 1] == 1
    
    # After one step, cell should die (0 neighbors, not in survive list)
    sim.step()
    assert sim.alive.sum() == 0

def test_dead_cell_with_birth_count_becomes_alive():
    """A dead cell with exactly B neighbors should become alive."""
    # Create a configuration where a center cell has exactly 6 neighbors
    seed_cells = []
    # Place 6 neighbors around center (1,1,1)
    neighbors = [
        (0, 1, 1), (2, 1, 1),  # z neighbors
        (1, 0, 1), (1, 2, 1),  # y neighbors  
        (1, 1, 0), (1, 1, 2)   # x neighbors
    ]
    for i, (z, y, x) in enumerate(neighbors):
        seed_cells.append({"z": z, "y": y, "x": x, "rgb": [100+i*20, 100, 100]})
    
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Initially 6 cells alive, center empty
    assert sim.alive.sum() == 6
    assert sim.alive[1, 1, 1] == 0
    
    # After one step, center should be born (6 neighbors)
    sim.step()
    assert sim.alive[1, 1, 1] == 1

def test_wrong_neighbor_count_no_birth():
    """A dead cell with wrong neighbor count should not become alive."""
    # Create a configuration where center has 5 neighbors (not 6)
    seed_cells = []
    neighbors = [
        (0, 1, 1), (2, 1, 1),  # z neighbors
        (1, 0, 1), (1, 2, 1),  # y neighbors  
        (1, 1, 0)              # only 5 neighbors
    ]
    for i, (z, y, x) in enumerate(neighbors):
        seed_cells.append({"z": z, "y": y, "x": x, "rgb": [100+i*20, 100, 100]})
    
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Initially 5 cells alive, center empty
    assert sim.alive.sum() == 5
    assert sim.alive[1, 1, 1] == 0
    
    # After one step, center should still be dead (5 neighbors, not 6)
    sim.step()
    assert sim.alive[1, 1, 1] == 0

def test_survival_rules():
    """Test that cells with survive neighbor counts survive."""
    # Create a cell with exactly 5 neighbors (in survive list)
    seed_cells = [{"z": 1, "y": 1, "x": 1, "rgb": [255, 255, 255]}]  # center
    neighbors = [
        (0, 1, 1), (2, 1, 1),  # z neighbors
        (1, 0, 1), (1, 2, 1),  # y neighbors  
        (1, 1, 0)              # 5 neighbors total
    ]
    for i, (z, y, x) in enumerate(neighbors):
        seed_cells.append({"z": z, "y": y, "x": x, "rgb": [100+i*20, 100, 100]})
    
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Initially 6 cells alive (center + 5 neighbors)
    assert sim.alive.sum() == 6
    assert sim.alive[1, 1, 1] == 1
    
    # After one step, center should survive (5 neighbors, in survive list)
    sim.step()
    assert sim.alive[1, 1, 1] == 1

def test_death_by_wrong_neighbor_count():
    """Test that cells with wrong neighbor counts die."""
    # Create a cell with 4 neighbors (not in survive list [5,6,7])
    seed_cells = [{"z": 1, "y": 1, "x": 1, "rgb": [255, 255, 255]}]  # center
    neighbors = [
        (0, 1, 1), (2, 1, 1),  # z neighbors
        (1, 0, 1), (1, 2, 1)   # 4 neighbors total
    ]
    for i, (z, y, x) in enumerate(neighbors):
        seed_cells.append({"z": z, "y": y, "x": x, "rgb": [100+i*20, 100, 100]})
    
    sim = Life3DRGB(
        shape=(3, 3, 3),
        rule={"birth": [6], "survive": [5, 6, 7]},
        seed_cells=seed_cells,
        random_state=42
    )
    
    # Initially 5 cells alive (center + 4 neighbors)
    assert sim.alive.sum() == 5
    assert sim.alive[1, 1, 1] == 1
    
    # After one step, center should die (4 neighbors, not in survive list)
    sim.step()
    assert sim.alive[1, 1, 1] == 0