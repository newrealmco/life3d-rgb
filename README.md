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
