# 3D Life (RGB + Anti-Desaturation) — with UI & High-Res Final

![CI](https://github.com/ramipinku/life3d-rgb/actions/workflows/ci.yml/badge.svg)

Conway-inspired cellular automaton in **3D** (26-neighbor / Moore) with advanced color inheritance modes to prevent grayscale drift. Each cell has:
- `alive` (1/0)
- `RGB` (0..255) assigned **only on birth** using configurable inheritance modes
- `age` tracking for optional render-time coloring

Key Features:
- **Anti-desaturation**: Multiple color inheritance modes prevent gray drift over long runs
- **Parallel** updates with **toroidal** wrap edges (via `np.roll`)
- Default rule: **B6/S5-7** (configurable)
- **Enhanced mutations**: Per-birth and per-step mutation options
- **Age coloring**: Optional age-based visual enhancement
- **Auto-stop safety**: Extinction and steady-state detection
- **Advanced UI**: Integer-only inputs, color swatches, verbose help text
- **Camera rotation**: Dynamic GIFs with configurable rotation
- **Preset system**: Quick presets for snowflakes, spheres, fractals, and more

## Install & Run

### Install from PyPI
```bash
pip install life3d-rgb
```

### GUI Mode (Interactive)
```bash
life3d-rgb-ui
```

### CLI Mode (Headless)
```bash
# Use built-in presets
life3d-rgb --preset starburst
life3d-rgb --preset sample

# List available presets
life3d-rgb --list-presets

# Use custom config
life3d-rgb --config path/to/config.json
```

### Python Module
```bash
python -m life3d_rgb --preset starburst
```

### Development Install
```bash
git clone https://github.com/your-repo/life3d-rgb
cd life3d-rgb
pip install -e .
```

## Configuration Reference

See built-in presets for examples. Key parameters:

- **shape**: `[Z,Y,X]` - 3D grid dimensions
- **steps**: Number of simulation iterations  
- **rule**: `{"birth": [6], "survive": [5,6,7]}` - Cellular automaton rules
- **color_inheritance_mode**: Color blending method (hsv_boosted_mean recommended)
- **seeds**: `[{z,y,x,rgb}, ...]` - Initial living cells
- **create_gif**: Generate animated output
- **auto_stop_extinction**: Stop when population dies out

For complete documentation, use `life3d-rgb --preset sample` to see a fully documented configuration.

## User Interface Features

### Advanced Controls
- **Integer-only inputs**: Grid size and steps accept any integer value (no artificial limits)
- **Color swatches**: Seed list shows visual color previews for each seed
- **Verbose help text**: Every control includes examples and detailed explanations
- **Preset system**: Quick-start configurations for common patterns

### Quick Presets
The UI includes predefined configurations for interesting structures:
- **Snowflake Fractals**: Symmetric patterns with high-contrast colors and rotation
- **Squares**: Geometric structures with sharp color boundaries
- **Spheres**: Central cluster forming spherical growth patterns  
- **Rainbow Arcs**: Arc-shaped seeds with high mutation and vibrant colors
- **Crystal Bloom**: Radial burst patterns with enhanced mutation rates
- **Checkerboard Chaos**: Dense alternating patterns with rapid oscillations

Each preset automatically configures birth/survival rules, grid size, seeds, color modes, mutation rates, and rotation settings. Users can still modify any values after selecting a preset.

### Output Features
- **Animated GIF**: Built from rendered step frames with configurable FPS (1-30)
- **Frame management**: Choose to keep or delete PNG frames after GIF creation
- **Camera rotation**: Optional dynamic rotation during GIF creation (degrees per step)
- **High-resolution final**: Configurable DPI and dimensions for print quality
- **Death Switch**: Automatic extinction handling that stops simulation, cleans empty frames, and creates GIFs from non-empty frames only

## Command Line Interface

The CLI mode (`main.py`) provides automated batch processing with JSON configuration files.

### Basic Usage

```bash
# Run with default config
python main.py --config example_config.json

# Use custom config
python main.py --config my_simulation.json
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `shape` | `[Z,Y,X]` | **Required** | 3D grid dimensions |
| `steps` | `integer` | **Required** | Number of simulation steps |
| `rule` | `object` | **Required** | Birth/survive neighbor counts |
| `seeds` | `array` | **Required** | Initial seed cells with positions and colors |
| `render_slices` | `boolean` | `false` | Enable slice rendering (opt-in only) |
| `create_gif` | `boolean` | `false` | Create animated GIF from step frames |
| `gif_fps` | `integer` | `8` | GIF frame rate (1-30 FPS) |
| `delete_frames_after` | `boolean` | `false` | Delete PNG frames after successful GIF creation |

### Example Configuration

```json
{
  "shape": [32, 32, 32],
  "steps": 100,
  "rule": {"birth": [6], "survive": [5, 6, 7]},
  "seeds": [
    {"z": 16, "y": 16, "x": 16, "rgb": [255, 100, 100]},
    {"z": 15, "y": 16, "x": 16, "rgb": [100, 255, 100]}
  ],
  "color_inheritance_mode": "hsv_boosted_mean",
  "outdir": "./results",
  "create_gif": true,
  "gif_fps": 12,
  "delete_frames_after": true,
  "verbose": true
}
```

### CLI Features

- ✅ **Fixed color rendering**: Produces properly colored voxel images (not black/empty)
- ✅ **Slice control**: Only renders slices when explicitly enabled via `render_slices: true`
- ✅ **Smart GIF creation**: Builds animations from step frames only, ignoring slice files
- ✅ **Safe frame deletion**: Only deletes frames after successful GIF creation
- ✅ **Live diagnostics**: Shows alive cell counts every 20 steps with extinction detection
- ✅ **Death Switch**: Automatically detects extinction, stops simulation, removes empty frames, and creates GIFs from valid frames only
- ✅ **Robust error handling**: Comprehensive validation and user-friendly error messages

### Advanced CLI Options

```json
{
  "color_inheritance_mode": "hsv_boosted_mean",
  "color_params": {
    "saturation_boost": 1.3,
    "saturation_floor": 0.35
  },
  "mutation": {
    "enable": true,
    "per_birth_mutation_prob": 0.15,
    "per_step_mutation_prob": 0.1,
    "mutation_std": 30.0
  },
  "render_every": 1,
  "slice_every": 10,
  "render_slices": false,
  "random_state": 42
}
```

See `config_schema.md` for complete configuration documentation.

## Color Inheritance Modes

The system offers five color inheritance modes to control how newborn cells acquire their colors. This is crucial for preventing grayscale drift over long simulations.

### Available Modes

**`Mean RGB` (Original)**
- Simple arithmetic average of all neighbors within radius 2
- ⚠️ Causes gradual drift toward gray over many generations
- Use only for short simulations or when gray drift is acceptable

**`Distance-weighted average`**
- Weights neighbors by `w = 1 / (1 + distance)` where distance is Chebyshev distance
- 📍 Closer neighbors have more influence on newborn color
- Reduces gray drift compared to simple mean

**`Two-parent blend` (Genetic-Style)**
- Picks 2 random living neighbors and averages their colors
- 🧬 Simulates genetic inheritance with two parents
- Creates interesting color patterns with moderate diversity

**`Random parent` (Sharp Inheritance)**
- Copies exact RGB from one random living neighbor
- ✅ Maintains sharp color boundaries and prevents blending
- Best for preserving distinct color lineages

**`HSV-boosted mean` (Recommended)**
- Converts to HSV, computes circular mean for hue, boosts saturation
- **Saturation boost**: Multiplies mean saturation (default 1.3)
- **Saturation floor**: Minimum saturation level (default 0.35)
- ✅ **Best anti-desaturation performance** - maintains vivid colors over 1000+ steps

### Recommended Settings

For **vivid long-term simulations**:
```
Color mode: hsv_boosted_mean
Saturation boost: 1.3
Saturation floor: 0.35
Per-birth mutations: 0.15 probability
```

For **sharp color boundaries**:
```
Color mode: random_parent
Per-birth mutations: 0.10 probability
```

For **genetic-like inheritance**:
```
Color mode: two_parent_blend
Per-birth mutations: 0.20 probability
```

## Mutation Systems

### Per-Birth Mutations (Recommended)
- Each newborn cell independently mutates with given probability
- Preserves color diversity without overwhelming noise
- Default: 15% probability, 30.0 standard deviation

### Per-Step Mutations (Legacy)
- At most N cells mutate per simulation step globally
- Includes "burstiness" intervals for realistic mutation patterns  
- Default: 20% probability, max 1 mutant per step

### Combined Approach
Enable both systems for maximum diversity:
- Per-birth: 0.15 probability (sustains diversity)
- Per-step: 0.10 probability (adds occasional large changes)

## Input Rules and Usage

### Grid Size and Steps
- **No artificial limits**: Enter any integer values for grid dimensions and steps
- **Examples**: 8×8×8 (fast testing), 32×32×32 (detailed patterns), 64×64×64 (high detail, slower)
- **Auto-stop safety**: Prevents infinite runs via extinction and steady-state detection

### Rules Format
- **Birth**: Comma-separated neighbor counts for cell birth (e.g., "6" or "5,6,7")
- **Survive**: Comma-separated neighbor counts for cell survival (e.g., "5,6,7")
- **Examples**: B6/S5-7 (balanced), B4-5/S3-5 (geometric), B5-8/S4-8 (explosive)

### Camera Rotation
- **Enable**: Checkbox to activate camera rotation during GIF creation
- **Degrees per step**: How much to rotate camera between frames (2-3° recommended)
- **Elevation**: Fixed vertical viewing angle (20° default)
- **GIF only**: Rotation only applies when creating animated GIFs, not final-only renders

## Age Coloring

Optional render-time enhancement that blends cell age with RGB colors:
- Does **not** affect simulation logic - purely visual
- Reveals structure and flow patterns
- Configurable colormap (inferno, plasma, viridis, etc.)
- Adjustable blend factor (0.0 = pure RGB, 1.0 = pure age)

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
pytest tests/test_color_modes.py
pytest tests/test_visualize.py

# Run tests with coverage
pytest --cov=life3d --cov=visualize
```

### Test Coverage

- **Neighbor rules**: Birth/death based on 26-neighbor counts
- **Color inheritance**: All 5 color modes including anti-desaturation testing
- **Mutation logic**: Both per-birth and per-step mutations with bounds checking
- **Age tracking**: Cell age progression and newborn age reset
- **Determinism**: Fixed random seeds produce identical results
- **Visualization**: PNG rendering with Agg backend, age coloring support
- **UI components**: Tkinter import, App/SeedManager creation, variable initialization

### Development Guidelines

**Always run tests after making changes:**
```bash
pytest -q
```

The `.gitignore` file excludes pytest cache and coverage files. All tests should pass before committing changes.

## Death Switch: Automatic Extinction Handling

The **Death Switch** is an automatic feature that activates when the simulation reaches extinction (no living cells). This prevents empty frames from cluttering output and ensures clean GIF creation.

### How It Works

1. **Extinction Detection**: After each simulation step, the system checks if `alive.sum() == 0`
2. **Immediate Stop**: When extinction is detected, the simulation stops immediately
3. **Frame Cleanup**: Any empty frames that would represent the extinct state are deleted
4. **Smart GIF Creation**: GIFs are built only from frames with living cells (non-empty frames)
5. **Clear Reporting**: Both UI and CLI modes report extinction details

### Behavior by Mode

**CLI Mode:**
```
⚠️  Population extinct at step 4. Stopping early.
[extinction] step=4, removed_empty_frames=0
[extinction] valid_frames_remaining=4 (up to step 3)
✅ [extinction] Created GIF: evolution.gif (4 frames, 8 FPS)

💀 [DEATH SWITCH ACTIVATED]
   Population extinct at step 4
   Removed 0 empty frame(s)
   GIF created (4 frames)
```

**UI Mode:**
- Shows extinction message in status bar and result dialog
- Updates progress indicator with extinction details
- Displays frame cleanup and GIF creation status

### Edge Cases Handled

- **Extinction at step 0**: No GIF created, reports immediate extinction
- **Extinction at step 1**: Only initial frame kept, GIF creation skipped (< 2 frames)
- **Final-only mode**: Avoids creating empty final image if simulation is extinct
- **Slice files**: Also removes corresponding slice files when present
- **Frame deletion**: Only applies "delete frames after GIF" to successfully created GIFs

### Configuration Impact

No configuration changes needed - the Death Switch works automatically with all existing settings:
- Respects `create_gif`, `gif_fps`, and `delete_frames_after` options
- Works with `render_slices` and cleans up slice files appropriately
- Compatible with all color modes, mutation settings, and rule configurations

The Death Switch ensures clean, professional output by automatically handling the common case of simulation extinction without user intervention.

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

## Continuous Integration

Tests run automatically on GitHub Actions for every push and pull request:

- **OS**: Ubuntu Latest
- **Python versions**: 3.10, 3.11, 3.12
- **Test suite**: All tests with coverage reporting
- **Headless**: Uses matplotlib Agg backend + xvfb for Tkinter UI tests
- **Display**: Virtual X11 display (xvfb) enables GUI tests in headless CI

### Tkinter Testing Strategy

The project uses a dual approach for Tkinter UI testing:

1. **CI Environment**: Uses `xvfb-run` to provide a virtual display for full UI testing
2. **Local Fallback**: Automatically skips UI tests on headless Linux systems without `$DISPLAY`
3. **Cross-platform**: Works on macOS/Windows (native display) and Linux (X11/Wayland)

The CI workflow installs both runtime and development dependencies, ensures headless operation with virtual display support, and runs the complete test suite with coverage. Build status is shown in the badge above.
