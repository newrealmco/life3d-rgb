import numpy as np
from typing import Dict, List, Tuple, Optional

NeighborRule = Dict[str, List[int]]  # {"birth":[...], "survive":[...]}

def _roll_sum(mask: np.ndarray, offsets: List[Tuple[int,int,int]]) -> np.ndarray:
    """Sum a boolean/int array over 3D offsets using np.roll (toroidal)."""
    total = np.zeros_like(mask, dtype=np.int32)
    for dz, dy, dx in offsets:
        total += np.roll(np.roll(np.roll(mask, dz, axis=0), dy, axis=1), dx, axis=2)
    return total

def _generate_offsets(radius:int, include_center:bool=False) -> List[Tuple[int,int,int]]:
    """Chebyshev neighborhood offsets with given radius."""
    offs = []
    for dz in range(-radius, radius+1):
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                if not include_center and dz==0 and dy==0 and dx==0:
                    continue
                if max(abs(dz), abs(dy), abs(dx)) <= radius:
                    offs.append((dz,dy,dx))
    return offs

class Life3DRGB:
    """
    3D Game of Life variant:
    - 26-neighbor life/death.
    - Colors assigned ONLY on birth, as mean of living cells within Chebyshev radius 2.
    - Parallel updates. Toroidal edges.
    - Configurable B/S rules (default B6/S5-7).
    - Optional mutations on a single newborn per step, with optional 'interval' burstiness.
    """
    def __init__(
        self,
        shape: Tuple[int,int,int],
        rule: Optional[NeighborRule] = None,
        seed_cells: Optional[List[Dict]] = None,
        mutation: Optional[Dict] = None,
        random_state: Optional[int] = None
    ):
        """
        shape: (Z, Y, X)
        seed_cells: [{"z":int,"y":int,"x":int,"rgb":[r,g,b]}, ...] up to 10
        mutation:
          {
            "enable": bool,
            "per_step_birth_mutation_prob": float in [0,1],
            "std": float,     # Gaussian std for delta
            "p_interval": float  # probability to introduce a random cooldown gap (burstiness)
          }
        """
        self.rng = np.random.default_rng(random_state)
        self.Z,self.Y,self.X = shape
        self.alive = np.zeros(shape, dtype=np.uint8)
        self.rgb = np.zeros((3,)+shape, dtype=np.uint8)  # [3, Z, Y, X]
        self.rule = rule or {"birth":[6], "survive":[5,6,7]}
        self.mutation = mutation or {
            "enable": True,
            "per_step_birth_mutation_prob": 0.2,
            "std": 30.0,
            "p_interval": 0.2
        }
        if seed_cells:
            for c in seed_cells:
                z,y,x = int(c["z"])%self.Z, int(c["y"])%self.Y, int(c["x"])%self.X
                r,g,b = [int(v) for v in c["rgb"]]
                self.alive[z,y,x] = 1
                self.rgb[0,z,y,x] = np.uint8(np.clip(r,0,255))
                self.rgb[1,z,y,x] = np.uint8(np.clip(g,0,255))
                self.rgb[2,z,y,x] = np.uint8(np.clip(b,0,255))

        self.offsets_26 = _generate_offsets(1, include_center=False)
        self.offsets_r2  = _generate_offsets(2, include_center=False)

        self._interval_cooldown = 0  # for bursty mutations

    def step(self) -> Dict[str,int]:
        """Advance one generation. Returns stats dict."""
        neighbor_counts = _roll_sum(self.alive, self.offsets_26)

        birth_mask = (self.alive==0) & np.isin(neighbor_counts, self.rule["birth"])
        survive_mask = (self.alive==1) & np.isin(neighbor_counts, self.rule["survive"])
        next_alive = np.zeros_like(self.alive, dtype=np.uint8)
        next_alive[birth_mask | survive_mask] = 1

        next_rgb = np.copy(self.rgb)

        # Birth colors: mean of living cells within radius 2 (current state)
        bz, by, bx = np.where(birth_mask)
        num_born = bz.size
        if num_born > 0:
            alive_r2_counts = _roll_sum(self.alive, self.offsets_r2)

            rgb_sums = []
            for c in range(3):
                channel_alive = self.rgb[c].astype(np.int32) * self.alive.astype(np.int32)
                rgb_sums.append(_roll_sum(channel_alive, self.offsets_r2))
            rgb_sums = np.stack(rgb_sums, axis=0)  # [3, Z, Y, X]

            denom = alive_r2_counts[bz,by,bx].astype(np.float32)
            denom_safe = np.where(denom>0, denom, 1.0).astype(np.float32)

            r_new = (rgb_sums[0,bz,by,bx] / denom_safe).astype(np.float32)
            g_new = (rgb_sums[1,bz,by,bx] / denom_safe).astype(np.float32)
            b_new = (rgb_sums[2,bz,by,bx] / denom_safe).astype(np.float32)

            rnd = self.rng.integers(40, 216, size=(3, num_born))
            r_new = np.where(denom>0, r_new, rnd[0])
            g_new = np.where(denom>0, g_new, rnd[1])
            b_new = np.where(denom>0, b_new, rnd[2])

            next_rgb[0,bz,by,bx] = np.uint8(np.clip(r_new,0,255))
            next_rgb[1,bz,by,bx] = np.uint8(np.clip(g_new,0,255))
            next_rgb[2,bz,by,bx] = np.uint8(np.clip(b_new,0,255))

            # Mutate exactly one newborn per step with some probability (and interval burstiness)
            if self.mutation.get("enable", False) and num_born>0:
                # interval cooldown
                if self._interval_cooldown > 0:
                    self._interval_cooldown -= 1
                else:
                    if self.rng.random() < self.mutation.get("p_interval", 0.0):
                        self._interval_cooldown = int(self.rng.integers(1,4))

                if self._interval_cooldown == 0 and self.rng.random() < self.mutation.get("per_step_birth_mutation_prob", 0.0):
                    idx = int(self.rng.integers(0, num_born))
                    mz, my, mx = bz[idx], by[idx], bx[idx]
                    std = float(self.mutation.get("std", 25.0))
                    for ch in range(3):
                        delta = self.rng.normal(0.0, std)
                        val = int(next_rgb[ch, mz, my, mx]) + int(delta)
                        next_rgb[ch, mz, my, mx] = np.uint8(np.clip(val,0,255))

        stats = {"alive_before": int(self.alive.sum()), "born": int(num_born)}

        self.alive = next_alive
        self.rgb = next_rgb
        stats["alive_after"] = int(self.alive.sum())
        return stats
