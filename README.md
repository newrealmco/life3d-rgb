# 3D Life (RGB + Mutations) — with UI & High-Res Final

Conway-inspired cellular automaton in **3D** (26-neighbor / Moore). Each cell has:
- `alive` (1/0)
- `RGB` (0..255) assigned **only on birth** as the mean color of living cells within **Chebyshev radius 2** (neighbors + neighbors-of-neighbors).

- **Parallel** updates
- **Toroidal** wrap edges (via `np.roll`)
- Default rule: **B6/S5-7** (tweakable)
- **Mutations**: at each step, with some probability, **one** newborn cell’s RGB is perturbed (Gaussian), with “burstiness” intervals.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python ui.py
```

## Development & Testing

The project separates runtime and development dependencies:

- **`requirements.txt`**: Runtime dependencies (numpy, matplotlib, imageio)
- **`requirements-dev.txt`**: Testing and development tools (pytest, coverage, linting)

### Setup for Development

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Running Tests

The project includes a comprehensive test suite that validates the core 3D Life logic:

```bash
# Run all tests (quiet mode)
pytest -q

# Run with verbose output
pytest -v

# Run specific test files
pytest tests/test_neighbors.py
pytest tests/test_birth_color.py
pytest tests/test_mutation.py
pytest tests/test_visualize.py

# Run tests with coverage
pytest --cov=life3d --cov=visualize
```

### Test Coverage

- **Neighbor rules**: Birth/death based on 26-neighbor counts
- **Color inheritance**: Mean color calculation from radius-2 neighbors  
- **Mutation logic**: Single-newborn mutations with probability and bounds checking
- **Determinism**: Fixed random seeds produce identical results
- **Visualization**: Smoke tests for PNG rendering with Agg backend

### Development Guidelines

**Always run tests after making changes:**
```bash
pytest -q
```

The `.gitignore` file excludes pytest cache and coverage files. All tests should pass before committing changes.
