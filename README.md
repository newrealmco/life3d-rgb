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
- **UI components**: Tkinter import, App/SeedManager creation, variable initialization

### Development Guidelines

**Always run tests after making changes:**
```bash
pytest -q
```

The `.gitignore` file excludes pytest cache and coverage files. All tests should pass before committing changes.

## Troubleshooting

### macOS: "ModuleNotFoundError: No module named '_tkinter'"

If you're using Homebrew Python and get a tkinter error when running `python ui.py`:

**Solution 1 (Recommended)**: Install tkinter via Homebrew
```bash
brew install python-tk
```

**Solution 2**: Use system Python (which includes tkinter)
```bash
/usr/bin/python3 ui.py
```

**Solution 3**: Create virtual environment with system Python
```bash
/usr/bin/python3 -m venv venv-system
source venv-system/bin/activate
pip install -r requirements.txt
python ui.py
```

### Linux: Missing tkinter

On Ubuntu/Debian:
```bash
sudo apt-get install python3-tk
```

On RHEL/CentOS/Fedora:
```bash
sudo dnf install tkinter
# or: sudo yum install tkinter
```
