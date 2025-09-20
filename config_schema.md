# Configuration Schema for CLI Mode

This document describes the JSON configuration options for running simulations via `python main.py --config file.json`.

## Required Fields

- **`shape`**: `[Z, Y, X]` - 3D grid dimensions (integers)
- **`steps`**: `integer` - Number of simulation steps to run
- **`rule`**: Object with `birth` and `survive` arrays of neighbor counts
- **`seeds`**: Array of seed cell objects with `z`, `y`, `x`, and `rgb` properties

## Core Options

```json
{
  "shape": [24, 24, 24],
  "steps": 100,
  "rule": {
    "birth": [6],
    "survive": [5, 6, 7]
  },
  "seeds": [
    {"z": 12, "y": 12, "x": 12, "rgb": [255, 100, 50]}
  ]
}
```

## Output Control

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `outdir` | string | `"./out"` | Output directory path |
| `render_every` | integer | `1` | Render step frames every N steps |
| `render_slices` | boolean | `false` | Enable slice rendering (opt-in) |
| `slice_every` | integer | `0` | Render slices every N steps (if `render_slices: true`) |

## GIF Creation

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `create_gif` | boolean | `false` | Create animated GIF from step frames |
| `gif_fps` | integer | `8` | GIF frame rate (1-30) |
| `delete_frames_after` | boolean | `false` | Delete PNG frames after successful GIF creation |

## Color and Mutation

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color_inheritance_mode` | string | `"mean_r2"` | Color inheritance: `"mean_r2"`, `"hsv_boosted_mean"`, `"random_parent"`, `"dist_weighted_mean"`, `"two_parent_blend"` |
| `color_params` | object | `{}` | Mode-specific parameters (e.g., saturation boost) |
| `mutation` | object | See below | Mutation configuration |

### Mutation Object

```json
{
  "mutation": {
    "enable": true,
    "per_birth_mutation_prob": 0.15,
    "per_step_mutation_prob": 0.2,
    "max_mutants_per_step": 1,
    "mutation_std": 30.0,
    "p_interval": 0.2
  }
}
```

## Other Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `verbose` | boolean | `false` | Print progress every 10 steps |
| `random_state` | integer | `null` | Random seed for reproducibility |

## Example: Full Configuration

```json
{
  "shape": [32, 32, 32],
  "steps": 150,
  "rule": {"birth": [6], "survive": [5, 6, 7]},
  "seeds": [
    {"z": 16, "y": 16, "x": 16, "rgb": [255, 100, 100]},
    {"z": 15, "y": 16, "x": 16, "rgb": [100, 255, 100]},
    {"z": 17, "y": 16, "x": 16, "rgb": [100, 100, 255]}
  ],
  "color_inheritance_mode": "hsv_boosted_mean",
  "color_params": {
    "saturation_boost": 1.3,
    "saturation_floor": 0.35
  },
  "mutation": {
    "enable": true,
    "per_birth_mutation_prob": 0.15,
    "mutation_std": 30.0
  },
  "outdir": "./results",
  "render_every": 1,
  "render_slices": false,
  "create_gif": true,
  "gif_fps": 10,
  "delete_frames_after": true,
  "verbose": false,
  "random_state": 42
}
```

## Notes

- **Slice rendering** is opt-in via `render_slices: true` to avoid unwanted slice files
- **GIF creation** builds only from `step_*.png` files, ignoring slice files
- **Frame deletion** only occurs after successful GIF creation
- **Color rendering** works correctly in CLI mode (fixed RGB normalization)
- **Diagnostics** show alive cell counts every 20 steps with early extinction detection