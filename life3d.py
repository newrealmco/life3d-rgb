import numpy as np
import colorsys
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

def _circular_mean_hue(hues):
    """Compute circular mean of hue values in [0,1]."""
    if len(hues) == 0:
        return 0.0
    # Convert to angles
    angles = hues * 2 * np.pi
    # Average unit vectors
    x = np.mean(np.cos(angles))
    y = np.mean(np.sin(angles))
    # Convert back to hue
    mean_angle = np.arctan2(y, x)
    if mean_angle < 0:
        mean_angle += 2 * np.pi
    return mean_angle / (2 * np.pi)

def _rgb_to_hsv_array(rgb):
    """Convert RGB array [3, ...] to HSV."""
    shape = rgb.shape[1:]
    hsv = np.zeros_like(rgb, dtype=np.float32)
    
    for idx in np.ndindex(shape):
        r, g, b = rgb[:, idx] / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        hsv[0, idx] = h
        hsv[1, idx] = s
        hsv[2, idx] = v
    
    return hsv

def _hsv_to_rgb_array(hsv):
    """Convert HSV array [3, ...] to RGB."""
    shape = hsv.shape[1:]
    rgb = np.zeros_like(hsv, dtype=np.uint8)
    
    for idx in np.ndindex(shape):
        h, s, v = hsv[:, idx]
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        rgb[0, idx] = np.clip(r * 255, 0, 255)
        rgb[1, idx] = np.clip(g * 255, 0, 255)
        rgb[2, idx] = np.clip(b * 255, 0, 255)
    
    return rgb

class Life3DRGB:
    """
    3D Game of Life variant:
    - 26-neighbor life/death.
    - Configurable color inheritance modes to prevent grayscale drift.
    - Parallel updates. Toroidal edges.
    - Configurable B/S rules (default B6/S5-7).
    - Per-birth and per-step mutation options.
    - Age tracking for optional render-time coloring.
    """
    def __init__(
        self,
        shape: Tuple[int,int,int],
        rule: Optional[NeighborRule] = None,
        seed_cells: Optional[List[Dict]] = None,
        mutation: Optional[Dict] = None,
        color_inheritance_mode: str = "mean_r2",
        color_params: Optional[Dict] = None,
        random_state: Optional[int] = None
    ):
        """
        shape: (Z, Y, X)
        seed_cells: [{"z":int,"y":int,"x":int,"rgb":[r,g,b]}, ...]
        mutation:
          {
            "enable": bool,
            # Per-step mutation (legacy)
            "per_step_mutation_prob": float,
            "max_mutants_per_step": int,
            # Per-birth mutation  
            "per_birth_mutation_prob": float,
            "mutation_std": float,
            "p_interval": float  # burstiness for per-step
          }
        color_inheritance_mode: "mean_r2", "dist_weighted_mean", "two_parent_blend", 
                               "random_parent", "hsv_boosted_mean"
        color_params: dict with mode-specific parameters
        """
        self.rng = np.random.default_rng(random_state)
        self.Z, self.Y, self.X = shape
        self.alive = np.zeros(shape, dtype=np.uint8)
        self.rgb = np.zeros((3,)+shape, dtype=np.uint8)  # [3, Z, Y, X]
        self.age = np.zeros(shape, dtype=np.uint16)  # Age tracking
        
        self.rule = rule or {"birth":[6], "survive":[5,6,7]}
        
        # Updated mutation defaults
        self.mutation = mutation or {
            "enable": True,
            "per_step_mutation_prob": 0.2,
            "max_mutants_per_step": 1,
            "per_birth_mutation_prob": 0.15,
            "mutation_std": 30.0,
            "p_interval": 0.2
        }
        
        self.color_inheritance_mode = color_inheritance_mode
        self.color_params = color_params or {
            "saturation_boost": 1.3,
            "saturation_floor": 0.35
        }
        
        if seed_cells:
            for c in seed_cells:
                z,y,x = int(c["z"])%self.Z, int(c["y"])%self.Y, int(c["x"])%self.X
                r,g,b = [int(v) for v in c["rgb"]]
                self.alive[z,y,x] = 1
                self.rgb[0,z,y,x] = np.uint8(np.clip(r,0,255))
                self.rgb[1,z,y,x] = np.uint8(np.clip(g,0,255))
                self.rgb[2,z,y,x] = np.uint8(np.clip(b,0,255))
                self.age[z,y,x] = 0  # New cells start at age 0

        self.offsets_26 = _generate_offsets(1, include_center=False)
        self.offsets_r2 = _generate_offsets(2, include_center=False)
        
        # For distance-weighted mode, precompute distances
        self.offset_distances = {}
        for offset in self.offsets_r2:
            dist = max(abs(offset[0]), abs(offset[1]), abs(offset[2]))
            self.offset_distances[offset] = dist

        self._interval_cooldown = 0  # for bursty mutations
        
        # Auto-stop safety features
        self._history = []  # Store recent states for steady state detection
        self._steady_state_threshold = 50  # Default consecutive steps for steady state

    def _assign_birth_colors(self, birth_positions):
        """Assign colors to newborn cells based on inheritance mode."""
        bz, by, bx = birth_positions
        num_born = len(bz)
        if num_born == 0:
            return np.zeros((3, 0), dtype=np.uint8)
        
        new_colors = np.zeros((3, num_born), dtype=np.uint8)
        
        if self.color_inheritance_mode == "mean_r2":
            new_colors = self._assign_mean_r2_colors(bz, by, bx)
        elif self.color_inheritance_mode == "dist_weighted_mean":
            new_colors = self._assign_dist_weighted_colors(bz, by, bx)
        elif self.color_inheritance_mode == "two_parent_blend":
            new_colors = self._assign_two_parent_colors(bz, by, bx)
        elif self.color_inheritance_mode == "random_parent":
            new_colors = self._assign_random_parent_colors(bz, by, bx)
        elif self.color_inheritance_mode == "hsv_boosted_mean":
            new_colors = self._assign_hsv_boosted_colors(bz, by, bx)
        else:
            # Fallback to mean_r2
            new_colors = self._assign_mean_r2_colors(bz, by, bx)
        
        return new_colors

    def _assign_mean_r2_colors(self, bz, by, bx):
        """Original mean RGB within radius 2."""
        num_born = len(bz)
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

        # Fallback to soft random if no neighbors
        rnd = self.rng.integers(40, 216, size=(3, num_born))
        r_new = np.where(denom>0, r_new, rnd[0])
        g_new = np.where(denom>0, g_new, rnd[1])
        b_new = np.where(denom>0, b_new, rnd[2])

        return np.array([
            np.uint8(np.clip(r_new, 0, 255)),
            np.uint8(np.clip(g_new, 0, 255)),
            np.uint8(np.clip(b_new, 0, 255))
        ])

    def _assign_dist_weighted_colors(self, bz, by, bx):
        """Distance-weighted mean with w = 1 / (1 + d)."""
        num_born = len(bz)
        new_colors = np.zeros((3, num_born), dtype=np.uint8)
        
        for i in range(num_born):
            z, y, x = bz[i], by[i], bx[i]
            weights = []
            colors = []
            
            for offset in self.offsets_r2:
                nz = (z + offset[0]) % self.Z
                ny = (y + offset[1]) % self.Y  
                nx = (x + offset[2]) % self.X
                
                if self.alive[nz, ny, nx]:
                    dist = self.offset_distances[offset]
                    weight = 1.0 / (1 + dist)
                    weights.append(weight)
                    colors.append(self.rgb[:, nz, ny, nx])
            
            if colors:
                weights = np.array(weights)
                colors = np.array(colors).T  # [3, num_neighbors]
                weights_sum = np.sum(weights)
                weighted_color = np.sum(colors * weights, axis=1) / weights_sum
                new_colors[:, i] = np.uint8(np.clip(weighted_color, 0, 255))
            else:
                # Fallback
                new_colors[:, i] = self.rng.integers(40, 216, size=3, dtype=np.uint8)
        
        return new_colors

    def _assign_two_parent_colors(self, bz, by, bx):
        """Two random parent blend."""
        num_born = len(bz)
        new_colors = np.zeros((3, num_born), dtype=np.uint8)
        
        for i in range(num_born):
            z, y, x = bz[i], by[i], bx[i]
            neighbors = []
            
            for offset in self.offsets_r2:
                nz = (z + offset[0]) % self.Z
                ny = (y + offset[1]) % self.Y
                nx = (x + offset[2]) % self.X
                
                if self.alive[nz, ny, nx]:
                    neighbors.append(self.rgb[:, nz, ny, nx])
            
            if len(neighbors) >= 2:
                # Pick 2 random parents
                parents = self.rng.choice(len(neighbors), size=2, replace=False)
                parent1 = neighbors[parents[0]]
                parent2 = neighbors[parents[1]]
                blend = (parent1.astype(np.float32) + parent2.astype(np.float32)) / 2
                new_colors[:, i] = np.uint8(np.clip(blend, 0, 255))
            elif len(neighbors) == 1:
                # Copy single parent
                new_colors[:, i] = neighbors[0]
            else:
                # Fallback
                new_colors[:, i] = self.rng.integers(40, 216, size=3, dtype=np.uint8)
        
        return new_colors

    def _assign_random_parent_colors(self, bz, by, bx):
        """Copy from random living neighbor."""
        num_born = len(bz)
        new_colors = np.zeros((3, num_born), dtype=np.uint8)
        
        for i in range(num_born):
            z, y, x = bz[i], by[i], bx[i]
            neighbors = []
            
            for offset in self.offsets_r2:
                nz = (z + offset[0]) % self.Z
                ny = (y + offset[1]) % self.Y
                nx = (x + offset[2]) % self.X
                
                if self.alive[nz, ny, nx]:
                    neighbors.append(self.rgb[:, nz, ny, nx])
            
            if neighbors:
                # Pick random parent
                parent_idx = self.rng.integers(0, len(neighbors))
                new_colors[:, i] = neighbors[parent_idx]
            else:
                # Fallback
                new_colors[:, i] = self.rng.integers(40, 216, size=3, dtype=np.uint8)
        
        return new_colors

    def _assign_hsv_boosted_colors(self, bz, by, bx):
        """HSV-based with saturation boost."""
        num_born = len(bz)
        new_colors = np.zeros((3, num_born), dtype=np.uint8)
        
        saturation_boost = self.color_params.get("saturation_boost", 1.3)
        saturation_floor = self.color_params.get("saturation_floor", 0.35)
        
        for i in range(num_born):
            z, y, x = bz[i], by[i], bx[i]
            neighbor_colors = []
            
            for offset in self.offsets_r2:
                nz = (z + offset[0]) % self.Z
                ny = (y + offset[1]) % self.Y
                nx = (x + offset[2]) % self.X
                
                if self.alive[nz, ny, nx]:
                    rgb = self.rgb[:, nz, ny, nx] / 255.0
                    h, s, v = colorsys.rgb_to_hsv(rgb[0], rgb[1], rgb[2])
                    neighbor_colors.append([h, s, v])
            
            if neighbor_colors:
                neighbor_colors = np.array(neighbor_colors)
                
                # Circular mean for hue
                mean_hue = _circular_mean_hue(neighbor_colors[:, 0])
                
                # Boosted saturation
                mean_sat = np.mean(neighbor_colors[:, 1])
                boosted_sat = max(mean_sat * saturation_boost, saturation_floor)
                boosted_sat = min(boosted_sat, 1.0)
                
                # Mean value
                mean_val = np.mean(neighbor_colors[:, 2])
                
                # Convert back to RGB
                r, g, b = colorsys.hsv_to_rgb(mean_hue, boosted_sat, mean_val)
                new_colors[:, i] = np.uint8(np.clip([r*255, g*255, b*255], 0, 255))
            else:
                # Fallback
                new_colors[:, i] = self.rng.integers(40, 216, size=3, dtype=np.uint8)
        
        return new_colors

    def _apply_per_birth_mutations(self, new_colors):
        """Apply per-birth mutations."""
        if not self.mutation.get("enable", False):
            return new_colors
        
        per_birth_prob = self.mutation.get("per_birth_mutation_prob", 0.0)
        mutation_std = self.mutation.get("mutation_std", 30.0)
        
        if per_birth_prob <= 0:
            return new_colors
        
        num_born = new_colors.shape[1]
        for i in range(num_born):
            if self.rng.random() < per_birth_prob:
                for c in range(3):
                    delta = self.rng.normal(0.0, mutation_std)
                    val = int(new_colors[c, i]) + int(delta)
                    new_colors[c, i] = np.uint8(np.clip(val, 0, 255))
        
        return new_colors

    def _apply_per_step_mutations(self, next_rgb, birth_positions):
        """Apply legacy per-step mutations."""
        bz, by, bx = birth_positions
        num_born = len(bz)
        
        if not self.mutation.get("enable", False) or num_born == 0:
            return
        
        # Interval cooldown (burstiness)
        if self._interval_cooldown > 0:
            self._interval_cooldown -= 1
        else:
            if self.rng.random() < self.mutation.get("p_interval", 0.0):
                self._interval_cooldown = int(self.rng.integers(1, 4))

        if self._interval_cooldown == 0:
            per_step_prob = self.mutation.get("per_step_mutation_prob", 0.0)
            max_mutants = self.mutation.get("max_mutants_per_step", 1)
            
            if self.rng.random() < per_step_prob:
                n_mutants = min(max_mutants, num_born)
                mutant_indices = self.rng.choice(num_born, size=n_mutants, replace=False)
                
                mutation_std = self.mutation.get("mutation_std", 30.0)
                
                for idx in mutant_indices:
                    mz, my, mx = bz[idx], by[idx], bx[idx]
                    for ch in range(3):
                        delta = self.rng.normal(0.0, mutation_std)
                        val = int(next_rgb[ch, mz, my, mx]) + int(delta)
                        next_rgb[ch, mz, my, mx] = np.uint8(np.clip(val, 0, 255))

    def step(self) -> Dict[str,int]:
        """Advance one generation. Returns stats dict."""
        neighbor_counts = _roll_sum(self.alive, self.offsets_26)

        birth_mask = (self.alive==0) & np.isin(neighbor_counts, self.rule["birth"])
        survive_mask = (self.alive==1) & np.isin(neighbor_counts, self.rule["survive"])
        next_alive = np.zeros_like(self.alive, dtype=np.uint8)
        next_alive[birth_mask | survive_mask] = 1

        next_rgb = np.copy(self.rgb)
        next_age = np.copy(self.age)
        
        # Update age: increment for survivors, reset for births
        next_age[survive_mask] += 1
        next_age[birth_mask] = 0
        
        # Handle deaths (age becomes 0 for dead cells)
        death_mask = (self.alive == 1) & (next_alive == 0)
        next_age[death_mask] = 0

        # Birth colors using new inheritance system
        bz, by, bx = np.where(birth_mask)
        num_born = bz.size
        if num_born > 0:
            new_colors = self._assign_birth_colors((bz, by, bx))
            new_colors = self._apply_per_birth_mutations(new_colors)
            
            # Assign colors
            next_rgb[0, bz, by, bx] = new_colors[0]
            next_rgb[1, bz, by, bx] = new_colors[1]
            next_rgb[2, bz, by, bx] = new_colors[2]
            
            # Apply per-step mutations
            self._apply_per_step_mutations(next_rgb, (bz, by, bx))

        stats = {"alive_before": int(self.alive.sum()), "born": int(num_born)}

        self.alive = next_alive
        self.rgb = next_rgb
        self.age = next_age
        stats["alive_after"] = int(self.alive.sum())
        
        # Update history for steady state detection
        self._update_history()
        
        return stats
    
    def _update_history(self) -> None:
        """Update history with current state for steady state detection."""
        current_state = (self.alive.copy(), self.rgb.copy())
        self._history.append(current_state)
        
        # Keep only last threshold+1 states to check for steady state
        if len(self._history) > self._steady_state_threshold + 1:
            self._history.pop(0)
    
    def is_extinct(self) -> bool:
        """Check if all cells are dead (extinction)."""
        return self.alive.sum() == 0
    
    def is_steady_state(self, threshold: Optional[int] = None) -> bool:
        """Check if the simulation has reached a steady state.
        
        Args:
            threshold: Number of consecutive identical steps to consider steady state.
                      If None, uses self._steady_state_threshold.
        
        Returns:
            True if the last 'threshold' steps are identical.
        """
        if threshold is None:
            threshold = self._steady_state_threshold
            
        if len(self._history) < threshold:
            return False
        
        # Check if the last 'threshold' states are all identical
        recent_states = self._history[-threshold:]
        base_alive, base_rgb = recent_states[0]
        
        for alive_state, rgb_state in recent_states[1:]:
            if not np.array_equal(alive_state, base_alive):
                return False
            if not np.array_equal(rgb_state, base_rgb):
                return False
        
        return True
    
    def set_steady_state_threshold(self, threshold: int) -> None:
        """Set the threshold for steady state detection."""
        self._steady_state_threshold = max(1, threshold)