from typing import List, Dict, Any
import os
import random
import datetime
from pathlib import Path

from .engine import Life3DRGB
from .visualize import render_voxels
from .death_switch import (
    list_step_frames, build_gif, delete_files,
    handle_extinction_cleanup, create_gif_after_extinction
)

try:
    import imageio.v2 as imageio
except Exception:
    imageio = None

# Import tkinter components for direct module imports (testing)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, colorchooser, simpledialog
except ImportError:
    # Will be handled by ui_main.py when used as entry point
    tk = ttk = messagebox = colorchooser = simpledialog = None

class ScrollableFrame(ttk.Frame):
    """A scrollable frame using canvas and scrollbar."""
    def __init__(self, container):
        super().__init__(container)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Bind mousewheel
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Layout
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def get_frame(self):
        """Return the inner scrollable frame for adding widgets."""
        return self.scrollable_frame

class SeedManager(ttk.Frame):
    def __init__(self, master, shape_getter, status_callback):
        super().__init__(master)
        self.shape_getter = shape_getter
        self.status_callback = status_callback
        self.seeds: List[Dict[str,Any]] = []

        self._create_widgets()
        self._update_info()

    def _create_widgets(self):
        # Info label
        self.info_label = ttk.Label(self, text="", foreground="blue")
        self.info_label.pack(anchor="w", pady=(0, 5))
        
        # Treeview with color swatches
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, pady=(0, 8))
        
        self.tree = ttk.Treeview(tree_frame, columns=("pos", "color"), show="tree headings", height=8)
        self.tree.heading("#0", text="Swatch")
        self.tree.heading("pos", text="Position")
        self.tree.heading("color", text="RGB")
        
        self.tree.column("#0", width=50, stretch=False)
        self.tree.column("pos", width=100, stretch=False)
        self.tree.column("color", width=100, stretch=False)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scrollbar.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.config(command=self.tree.yview)

        # Buttons in grid layout
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Add Seed", command=self.add_seed, width=12).grid(
            row=0, column=0, padx=(0, 5), pady=2, sticky="ew")
        ttk.Button(btn_frame, text="Randomize...", command=self.randomize_seeds, width=12).grid(
            row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Button(btn_frame, text="Delete Selected", command=self.del_selected, width=12).grid(
            row=1, column=0, padx=(0, 5), pady=2, sticky="ew")
        ttk.Button(btn_frame, text="Clear All", command=self.clear_all, width=12).grid(
            row=1, column=1, padx=5, pady=2, sticky="ew")
        
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

    def _get_max_seeds(self):
        """Calculate maximum allowed seeds (10% of grid, max 5000)"""
        Z, Y, X = self.shape_getter()
        total_cells = Z * Y * X
        max_seeds = min(int(total_cells * 0.1), 5000)
        return max(1, max_seeds)

    def _update_info(self):
        """Update the info label with current limits"""
        max_seeds = self._get_max_seeds()
        current = len(self.seeds)
        self.info_label.config(text=f"Seeds: {current} / {max_seeds}")

    def add_seed(self):
        Z, Y, X = self.shape_getter()
        if len(self.seeds) >= self._get_max_seeds():
            messagebox.showwarning("Seeds Full", f"Maximum {self._get_max_seeds()} seeds reached")
            return

        # Get coordinates
        z = simpledialog.askinteger("Add Seed", f"Z coordinate (0-{Z-1}):", 
                                   minvalue=0, maxvalue=Z-1, initialvalue=Z//2)
        if z is None: return
        
        y = simpledialog.askinteger("Add Seed", f"Y coordinate (0-{Y-1}):", 
                                   minvalue=0, maxvalue=Y-1, initialvalue=Y//2)
        if y is None: return
        
        x = simpledialog.askinteger("Add Seed", f"X coordinate (0-{X-1}):", 
                                   minvalue=0, maxvalue=X-1, initialvalue=X//2)
        if x is None: return

        # Get color
        color = colorchooser.askcolor(title="Choose seed color")
        if not color[0]: return

        r, g, b = [int(c) for c in color[0]]
        seed = {"z": z, "y": y, "x": x, "rgb": [r, g, b]}
        self.seeds.append(seed)
        self._refresh_list()
        self.status_callback(f"Added seed at ({z},{y},{x})")

    def randomize_seeds(self):
        count = simpledialog.askinteger("Randomize Seeds", 
                                       f"Number of seeds (1-{self._get_max_seeds()}):",
                                       minvalue=1, maxvalue=self._get_max_seeds(), 
                                       initialvalue=min(20, self._get_max_seeds()))
        if count is None: return

        Z, Y, X = self.shape_getter()
        self.seeds.clear()
        
        # Clustering algorithm 
        k = max(1, min(12, round(count/8) + 1))
        
        # Create cluster centers
        centers = []
        for _ in range(k):
            centers.append([
                random.randint(0, Z-1),
                random.randint(0, Y-1), 
                random.randint(0, X-1)
            ])
        
        # Add seeds around clusters
        for i in range(count):
            center = random.choice(centers)
            
            # Add jitter around center
            jitter = min(Z, Y, X) // 8
            z = max(0, min(Z-1, center[0] + random.randint(-jitter, jitter)))
            y = max(0, min(Y-1, center[1] + random.randint(-jitter, jitter)))
            x = max(0, min(X-1, center[2] + random.randint(-jitter, jitter)))
            
            # Check for collision
            collision = any(s["z"]==z and s["y"]==y and s["x"]==x for s in self.seeds)
            if collision:
                # Find nearby free spot
                for dz in range(-2, 3):
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            nz, ny, nx = z+dz, y+dy, x+dx
                            if 0 <= nz < Z and 0 <= ny < Y and 0 <= nx < X:
                                if not any(s["z"]==nz and s["y"]==ny and s["x"]==nx for s in self.seeds):
                                    z, y, x = nz, ny, nx
                                    break
                        else: continue
                        break
                    else: continue
                    break
            
            # Random vivid color
            r = random.randint(50, 255)
            g = random.randint(50, 255) 
            b = random.randint(50, 255)
            
            self.seeds.append({"z": z, "y": y, "x": x, "rgb": [r, g, b]})
        
        self._refresh_list()
        self.status_callback(f"Generated {len(self.seeds)} clustered seeds")

    def del_selected(self):
        sel = self.tree.selection()
        if sel:
            # Get the index of selected item
            idx = self.tree.index(sel[0])
            self.seeds.pop(idx)
            self._refresh_list()

    def clear_all(self):
        self.seeds.clear()
        self._refresh_list()
        self.status_callback("Cleared all seeds")

    def _refresh_list(self):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add seeds with color swatches
        for i, s in enumerate(self.seeds):
            color_hex = "#{:02x}{:02x}{:02x}".format(*s["rgb"])
            pos_text = f"({s['z']},{s['y']},{s['x']})"
            rgb_text = f"RGB({s['rgb'][0]},{s['rgb'][1]},{s['rgb'][2]})"
            
            # Create colored text swatch (using Unicode block character)
            swatch = "\u2588\u2588\u2588\u2588\u2588"  # 5 block characters for visual impact
            
            item = self.tree.insert("", "end", text=swatch, values=(pos_text, rgb_text))
            # Set color tag for the swatch (no need to set "#0" again since it's already set in text=)
            try:
                self.tree.tag_configure(f"color_{i}", foreground=color_hex)
                self.tree.item(item, tags=(f"color_{i}",))
            except tk.TclError:
                # Fallback if color is too dark
                pass
        
        self._update_info()

class IntegerEntry(ttk.Entry):
    """Entry widget that only accepts integers."""
    def __init__(self, parent, textvariable=None, min_val=None, max_val=None, **kwargs):
        super().__init__(parent, textvariable=textvariable, **kwargs)
        self.min_val = min_val
        self.max_val = max_val
        
        # Register validation function
        vcmd = (self.register(self._validate), '%P')
        self.configure(validate='key', validatecommand=vcmd)
        
        # Bind focus out to ensure valid value
        self.bind('<FocusOut>', self._on_focus_out)
    
    def _validate(self, value):
        """Validate that input is integer."""
        if value == "" or value == "-":
            return True
        try:
            int(value)
            return True
        except ValueError:
            return False
    
    def _on_focus_out(self, event):
        """Ensure value is within bounds when focus is lost."""
        try:
            val = int(self.get())
            if self.min_val is not None and val < self.min_val:
                self.delete(0, tk.END)
                self.insert(0, str(self.min_val))
            elif self.max_val is not None and val > self.max_val:
                self.delete(0, tk.END)  
                self.insert(0, str(self.max_val))
        except ValueError:
            # Set to minimum value if invalid
            default = self.min_val if self.min_val is not None else 1
            self.delete(0, tk.END)
            self.insert(0, str(default))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3D Life RGB with Enhanced UI & Presets")
        self.geometry("1000x750")
        self.resizable(True, True)

        # Variables
        self.Z = tk.IntVar(value=24)
        self.Y = tk.IntVar(value=24)
        self.X = tk.IntVar(value=24)
        self.steps = tk.IntVar(value=100)

        self.birth = tk.StringVar(value="6")
        self.survive = tk.StringVar(value="5,6,7")

        # Color inheritance
        self.color_mode = tk.StringVar(value="mean_r2")
        self.saturation_boost = tk.DoubleVar(value=1.3)
        self.saturation_floor = tk.DoubleVar(value=0.35)

        # Mutation controls
        self.mut_enable = tk.BooleanVar(value=True)
        self.mut_per_birth_enable = tk.BooleanVar(value=True)
        self.mut_per_birth_prob = tk.DoubleVar(value=0.15)
        self.mut_per_step_enable = tk.BooleanVar(value=True)
        self.mut_per_step_prob = tk.DoubleVar(value=0.2)
        self.mut_max_per_step = tk.IntVar(value=1)
        self.mut_std = tk.DoubleVar(value=30.0)
        self.mut_interval = tk.DoubleVar(value=0.15)

        # Output controls
        self.outdir = tk.StringVar(value="./out")
        self.render_final_only = tk.BooleanVar(value=True)
        self.make_gif = tk.BooleanVar(value=False)
        
        # Enhanced GIF controls
        self.gif_fps = tk.IntVar(value=8)
        self.gif_cleanup = tk.StringVar(value="keep")  # "keep" or "delete"

        self.hr_enable = tk.BooleanVar(value=True)
        self.hr_dpi = tk.IntVar(value=300)
        self.hr_width = tk.DoubleVar(value=12.0)
        self.hr_height = tk.DoubleVar(value=12.0)
        
        # Auto-stop safety controls
        self.auto_stop_enable = tk.BooleanVar(value=True)
        self.steady_state_threshold = tk.IntVar(value=50)

        # Age coloring controls
        self.color_by_age = tk.BooleanVar(value=False)
        self.age_cmap = tk.StringVar(value="inferno")
        self.age_alpha = tk.DoubleVar(value=0.6)
        
        # Camera rotation controls
        self.rotation_enable = tk.BooleanVar(value=False)
        self.rotation_degrees_per_step = tk.DoubleVar(value=2.0)
        self.rotation_elevation = tk.DoubleVar(value=20.0)
        
        # Preset system
        self.current_preset = tk.StringVar(value="None")

        # Define presets
        self.presets = {
            "None": {"description": "Use custom settings"},
            "Snowflake Fractals": {
                "description": "Symmetric fractal structures with high contrast colors",
                "birth": "5,6,7",
                "survive": "4,5,6", 
                "grid": (32, 32, 32),
                "color_mode": "hsv_boosted_mean",
                "rotation": True,
                "rotation_degrees": 2.0,
                "seeds": [
                    {"z": 16, "y": 16, "x": 16, "rgb": [255, 100, 100]},
                    {"z": 15, "y": 16, "x": 16, "rgb": [100, 255, 100]},
                    {"z": 17, "y": 16, "x": 16, "rgb": [100, 100, 255]},
                    {"z": 16, "y": 15, "x": 16, "rgb": [255, 255, 100]},
                    {"z": 16, "y": 17, "x": 16, "rgb": [255, 100, 255]},
                    {"z": 16, "y": 16, "x": 15, "rgb": [100, 255, 255]},
                    {"z": 16, "y": 16, "x": 17, "rgb": [255, 200, 100]}
                ],
                "mutation_birth": 0.15,
                "mutation_step": 0.05
            },
            "Squares": {
                "description": "Aligned geometric structures with sharp boundaries",
                "birth": "4,5",
                "survive": "3,4,5",
                "grid": (24, 24, 24),
                "color_mode": "random_parent",
                "rotation": False,
                "seeds": [
                    {"z": 12, "y": 8, "x": 8, "rgb": [255, 0, 0]},
                    {"z": 12, "y": 8, "x": 16, "rgb": [0, 255, 0]},
                    {"z": 12, "y": 16, "x": 8, "rgb": [0, 0, 255]},
                    {"z": 12, "y": 16, "x": 16, "rgb": [255, 255, 0]},
                    {"z": 8, "y": 12, "x": 12, "rgb": [255, 0, 255]},
                    {"z": 16, "y": 12, "x": 12, "rgb": [0, 255, 255]}
                ],
                "mutation_birth": 0.10,
                "mutation_step": 0.05
            },
            "Spheres": {
                "description": "Central cluster forming spherical growth patterns",
                "birth": "5,6,7,8",
                "survive": "4,5,6,7,8",
                "grid": (28, 28, 28),
                "color_mode": "two_parent_blend",
                "rotation": True,
                "rotation_degrees": 1.5,
                "seeds": [
                    {"z": 14, "y": 14, "x": 14, "rgb": [255, 150, 150]},
                    {"z": 13, "y": 14, "x": 14, "rgb": [150, 255, 150]},
                    {"z": 15, "y": 14, "x": 14, "rgb": [150, 150, 255]},
                    {"z": 14, "y": 13, "x": 14, "rgb": [255, 255, 150]},
                    {"z": 14, "y": 15, "x": 14, "rgb": [255, 150, 255]},
                    {"z": 14, "y": 14, "x": 13, "rgb": [150, 255, 255]},
                    {"z": 14, "y": 14, "x": 15, "rgb": [255, 200, 100]},
                    {"z": 13, "y": 13, "x": 13, "rgb": [200, 255, 100]},
                    {"z": 15, "y": 15, "x": 15, "rgb": [100, 200, 255]}
                ],
                "mutation_birth": 0.20,
                "mutation_step": 0.10
            },
            "Rainbow Arcs": {
                "description": "Arc-shaped cluster with high mutation and vibrant colors",
                "birth": "6",
                "survive": "5,6,7",
                "grid": (30, 30, 30),
                "color_mode": "hsv_boosted_mean",
                "rotation": True,
                "rotation_degrees": 3.0,
                "seeds": [
                    {"z": 15, "y": 10, "x": 15, "rgb": [255, 0, 0]},
                    {"z": 16, "y": 12, "x": 15, "rgb": [255, 127, 0]},
                    {"z": 17, "y": 14, "x": 15, "rgb": [255, 255, 0]},
                    {"z": 18, "y": 16, "x": 15, "rgb": [0, 255, 0]},
                    {"z": 17, "y": 18, "x": 15, "rgb": [0, 255, 255]},
                    {"z": 16, "y": 20, "x": 15, "rgb": [0, 0, 255]},
                    {"z": 15, "y": 22, "x": 15, "rgb": [127, 0, 255]}
                ],
                "mutation_birth": 0.35,
                "mutation_step": 0.20
            },
            "Crystal Bloom": {
                "description": "Radial burst from center with high mutation rates",
                "birth": "6,7",
                "survive": "4,5,6",
                "grid": (26, 26, 26),
                "color_mode": "hsv_boosted_mean",
                "rotation": True,
                "rotation_degrees": 2.5,
                "seeds": [
                    {"z": 13, "y": 13, "x": 13, "rgb": [255, 100, 200]},
                    {"z": 12, "y": 13, "x": 13, "rgb": [200, 255, 100]},
                    {"z": 14, "y": 13, "x": 13, "rgb": [100, 200, 255]},
                    {"z": 13, "y": 12, "x": 13, "rgb": [255, 200, 100]},
                    {"z": 13, "y": 14, "x": 13, "rgb": [200, 100, 255]}
                ],
                "mutation_birth": 0.40,
                "mutation_step": 0.25
            },
            "Checkerboard Chaos": {
                "description": "Dense alternating pattern with rapid oscillations",
                "birth": "3,4",
                "survive": "2,3",
                "grid": (20, 20, 20),
                "color_mode": "random_parent",
                "rotation": False,
                "seeds": [
                    {"z": 10, "y": 8, "x": 8, "rgb": [255, 0, 0]},
                    {"z": 10, "y": 8, "x": 12, "rgb": [0, 255, 0]},
                    {"z": 10, "y": 12, "x": 8, "rgb": [0, 0, 255]},
                    {"z": 10, "y": 12, "x": 12, "rgb": [255, 255, 0]},
                    {"z": 8, "y": 10, "x": 10, "rgb": [255, 0, 255]},
                    {"z": 12, "y": 10, "x": 10, "rgb": [0, 255, 255]},
                    {"z": 10, "y": 10, "x": 8, "rgb": [255, 127, 0]},
                    {"z": 10, "y": 10, "x": 12, "rgb": [127, 255, 0]},
                    {"z": 9, "y": 9, "x": 9, "rgb": [255, 0, 127]},
                    {"z": 11, "y": 11, "x": 11, "rgb": [0, 127, 255]}
                ],
                "mutation_birth": 0.25,
                "mutation_step": 0.15
            }
        }

        self._create_ui()
        self._setup_callbacks()
    
    def _apply_preset(self, preset_name):
        """Apply a preset configuration."""
        if preset_name == "None" or preset_name not in self.presets:
            return
        
        preset = self.presets[preset_name]
        
        # Apply rules
        if "birth" in preset:
            self.birth.set(preset["birth"])
        if "survive" in preset:
            self.survive.set(preset["survive"])
        
        # Apply grid size
        if "grid" in preset:
            z, y, x = preset["grid"]
            self.Z.set(z)
            self.Y.set(y)
            self.X.set(x)
        
        # Apply color mode
        if "color_mode" in preset:
            self.color_mode.set(preset["color_mode"])
        
        # Apply rotation settings
        if "rotation" in preset:
            self.rotation_enable.set(preset["rotation"])
            if "rotation_degrees" in preset:
                self.rotation_degrees_per_step.set(preset["rotation_degrees"])
        
        # Apply mutation settings
        if "mutation_birth" in preset:
            self.mut_per_birth_prob.set(preset["mutation_birth"])
        if "mutation_step" in preset:
            self.mut_per_step_prob.set(preset["mutation_step"])
        
        # Apply seeds
        if "seeds" in preset:
            self.seed_mgr.seeds = preset["seeds"][:]
            self.seed_mgr._refresh_list()
        
        self._set_status(f"Applied preset: {preset_name}")

    def _setup_callbacks(self):
        """Setup UI callbacks for dynamic behavior."""
        # GIF checkbox gating: only enabled when NOT rendering final only
        def update_gif_state(*args):
            if self.render_final_only.get():
                self.gif_checkbox.config(state="disabled")
                self.gif_fps_scale.config(state="disabled")
                self.gif_cleanup_keep.config(state="disabled")
                self.gif_cleanup_delete.config(state="disabled")
                self.make_gif.set(False)
            else:
                self.gif_checkbox.config(state="normal")
                if self.make_gif.get():
                    self.gif_fps_scale.config(state="normal")
                    self.gif_cleanup_keep.config(state="normal")
                    self.gif_cleanup_delete.config(state="normal")
        
        # GIF controls visibility based on checkbox
        def update_gif_controls(*args):
            if self.make_gif.get() and not self.render_final_only.get():
                self.gif_fps_scale.config(state="normal")
                self.gif_cleanup_keep.config(state="normal")
                self.gif_cleanup_delete.config(state="normal")
            else:
                self.gif_fps_scale.config(state="disabled")
                self.gif_cleanup_keep.config(state="disabled")
                self.gif_cleanup_delete.config(state="disabled")
        
        self.render_final_only.trace_add("write", update_gif_state)
        self.make_gif.trace_add("write", update_gif_controls)
        
        # Color mode controls: show/hide HSV controls
        def update_color_controls(*args):
            if self.color_mode.get() == "hsv_boosted_mean":
                self.hsv_frame.pack(fill="x", pady=5)
            else:
                self.hsv_frame.pack_forget()
        
        self.color_mode.trace_add("write", update_color_controls)
        
        # Update color mode display when internal value changes
        def update_color_mode_display(*args):
            internal_value = self.color_mode.get()
            display_value = self.color_mode_reverse_map.get(internal_value, "Mean RGB")
            # Only update if we have the combo box available
            if hasattr(self, 'color_mode_combo'):
                self.color_mode_combo.set(display_value)
        
        # Add trace to sync display when internal value changes (e.g., from presets)
        self.color_mode.trace_add("write", update_color_mode_display)
        
        # Preset selection callback
        def on_preset_change(*args):
            preset_name = self.current_preset.get()
            self._apply_preset(preset_name)
        
        self.current_preset.trace_add("write", on_preset_change)
        
        # Initialize states
        update_gif_state()
        update_gif_controls()
        update_color_controls()

    def _create_ui(self):
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Create tabs
        self._create_grid_tab()
        self._create_rules_tab()
        self._create_color_tab()  # New tab for color inheritance
        self._create_mutation_tab()
        self._create_seeds_tab()
        self._create_output_tab()

        # Footer with status and run button
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill="x")

        self.status_label = ttk.Label(footer_frame, text="Ready", foreground="green")
        self.status_label.pack(side="left")

        self.run_button = ttk.Button(footer_frame, text="🚀 Run Simulation", 
                                    command=self.run, style="Accent.TButton")
        self.run_button.pack(side="right", padx=(10, 0))

    def _create_grid_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Grid & Steps")
        content = frame.get_frame()

        # Preset selection at top
        preset_frame = ttk.LabelFrame(content, text="Quick Presets", padding=15)
        preset_frame.pack(fill="x", pady=(0, 15))
        
        preset_help = ("Presets provide starting values for interesting structures. " 
                      "You can tweak any values after selection.")
        ttk.Label(preset_frame, text=preset_help, foreground="gray", 
                 wraplength=400, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 10))
        
        preset_row = ttk.Frame(preset_frame)
        preset_row.pack(fill="x")
        ttk.Label(preset_row, text="Preset:", width=10).pack(side="left")
        preset_combo = ttk.Combobox(preset_row, textvariable=self.current_preset, 
                                   width=25, state="readonly")
        preset_combo['values'] = list(self.presets.keys())
        preset_combo.pack(side="left", padx=(0, 10))
        
        # Preset description label
        self.preset_desc_label = ttk.Label(preset_row, text="", foreground="blue", 
                                          font=("TkDefaultFont", 9))
        self.preset_desc_label.pack(side="left", padx=(10, 0))
        
        # Update description when preset changes
        def update_preset_desc(*args):
            preset_name = self.current_preset.get()
            if preset_name in self.presets:
                desc = self.presets[preset_name]["description"]
                self.preset_desc_label.config(text=desc)
            else:
                self.preset_desc_label.config(text="")
        
        self.current_preset.trace_add("write", update_preset_desc)
        update_preset_desc()  # Initialize

        # Help text
        help_text = ("Configure simulation grid size and number of steps. Enter any integer values - "
                    "no artificial limits. Larger grids support more complex patterns but run slower. "
                    "Examples: 8x8x8 (fast), 32x32x32 (detailed), 64x64x64 (high detail, slow).")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Grid size with integer entries
        grid_frame = ttk.LabelFrame(content, text="Grid Size (Z×Y×X)", padding=15)
        grid_frame.pack(fill="x", pady=(0, 15))

        for i, (label, var, example) in enumerate([
            ("Z (depth):", self.Z, "e.g., 24"), 
            ("Y (height):", self.Y, "e.g., 24"), 
            ("X (width):", self.X, "e.g., 24")
        ]):
            row_frame = ttk.Frame(grid_frame)
            row_frame.pack(fill="x", pady=3)
            ttk.Label(row_frame, text=label, width=12).pack(side="left")
            entry = IntegerEntry(row_frame, textvariable=var, width=8, min_val=1)
            entry.pack(side="left", padx=(0, 10))
            ttk.Label(row_frame, text=example, foreground="gray", font=("TkDefaultFont", 9)).pack(side="left")

        # Steps with integer entry
        steps_frame = ttk.LabelFrame(content, text="Simulation Steps", padding=15)
        steps_frame.pack(fill="x")

        steps_help = ("Number of simulation steps. Examples: 50 (quick test), 200 (medium), "
                     "1000+ (long evolution). Auto-stop will prevent infinite runs.")
        ttk.Label(steps_frame, text=steps_help, foreground="gray", 
                 wraplength=400, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 10))

        steps_row = ttk.Frame(steps_frame)
        steps_row.pack(fill="x")
        ttk.Label(steps_row, text="Steps:", width=12).pack(side="left")
        steps_entry = IntegerEntry(steps_row, textvariable=self.steps, width=8, min_val=1)
        steps_entry.pack(side="left", padx=(0, 10))
        ttk.Label(steps_row, text="e.g., 100", foreground="gray", font=("TkDefaultFont", 9)).pack(side="left")

    def _create_rules_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Rules")
        content = frame.get_frame()

        # Detailed help text
        help_text = ("Birth/Survival rules control the 3D cellular automaton evolution. Each cell has 26 neighbors "
                    "in 3D space. Rules determine when empty cells are born and when living cells survive to the next step.")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Rules frame with examples
        rules_frame = ttk.LabelFrame(content, text="Neighbor Rules (0-26 neighbors)", padding=15)
        rules_frame.pack(fill="x", pady=(0, 15))

        birth_frame = ttk.Frame(rules_frame)
        birth_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(birth_frame, text="Birth:", width=10).pack(side="left")
        ttk.Entry(birth_frame, textvariable=self.birth, width=20).pack(side="left", padx=(0, 10))
        ttk.Label(birth_frame, text="e.g., '6' or '5,6,7' (when empty cells become alive)", 
                 foreground="gray", font=("TkDefaultFont", 9)).pack(side="left")

        survive_frame = ttk.Frame(rules_frame)
        survive_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(survive_frame, text="Survive:", width=10).pack(side="left")
        ttk.Entry(survive_frame, textvariable=self.survive, width=20).pack(side="left", padx=(0, 10))
        ttk.Label(survive_frame, text="e.g., '5,6,7' or '2,3' (when living cells stay alive)", 
                 foreground="gray", font=("TkDefaultFont", 9)).pack(side="left")

        # Rule examples
        examples_frame = ttk.LabelFrame(content, text="Rule Examples", padding=15)
        examples_frame.pack(fill="x")
        
        examples_text = (
            "• B6/S5-7 (default): Balanced growth, creates interesting fractal structures\n"
            "• B4-5/S3-5: Geometric patterns, forms square-like structures\n"
            "• B5-8/S4-8: Explosive growth, creates sphere-like patterns\n"
            "• B3-4/S2-3: Chaotic oscillations, rapid changes\n"
            "• B6-7/S4-6: Crystal-like growth with controlled expansion"
        )
        ttk.Label(examples_frame, text=examples_text, foreground="blue", 
                 font=("TkDefaultFont", 9), justify="left").pack(anchor="w")

    def _create_color_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Color Inheritance")
        content = frame.get_frame()

        # Enhanced help text
        help_text = ("Color inheritance determines how newborn cells acquire their colors from living neighbors. "
                    "Different modes prevent grayscale drift and create distinct visual patterns. "
                    "Choose based on desired color evolution: vivid (HSV modes), sharp (random parent), or blended (parent modes).")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Color mode selection with improved dropdown
        mode_frame = ttk.LabelFrame(content, text="Inheritance Mode", padding=15)
        mode_frame.pack(fill="x", pady=(0, 15))

        mode_row = ttk.Frame(mode_frame)
        mode_row.pack(fill="x", pady=(0, 10))
        ttk.Label(mode_row, text="Color mode:", width=12).pack(side="left")
        
        mode_combo = ttk.Combobox(mode_row, textvariable=self.color_mode, width=25, state="readonly")
        mode_combo['values'] = (
            "Mean RGB", "HSV-boosted mean", "Random parent", "Distance-weighted average", "Two-parent blend"
        )
        
        # Map display names to internal names
        self.color_mode_map = {
            "Mean RGB": "mean_r2",
            "HSV-boosted mean": "hsv_boosted_mean", 
            "Random parent": "random_parent",
            "Distance-weighted average": "dist_weighted_mean",
            "Two-parent blend": "two_parent_blend"
        }
        
        # Map internal names back to display names
        self.color_mode_reverse_map = {v: k for k, v in self.color_mode_map.items()}
        
        # Set initial display value
        current_internal = self.color_mode.get()
        display_value = self.color_mode_reverse_map.get(current_internal, "Mean RGB")
        mode_combo.set(display_value)
        
        # Bind mode change to update internal value
        def on_mode_change(event):
            display_value = mode_combo.get()
            internal_value = self.color_mode_map.get(display_value, "mean_r2")
            self.color_mode.set(internal_value)
        
        mode_combo.bind("<<ComboboxSelected>>", on_mode_change)
        mode_combo.pack(side="left", padx=(0, 10))
        
        # Store reference for callback updates
        self.color_mode_combo = mode_combo

        # Detailed mode descriptions
        desc_frame = ttk.LabelFrame(content, text="Mode Descriptions", padding=15)
        desc_frame.pack(fill="x", pady=(0, 15))
        
        desc_text = (
            "• Mean RGB: Simple arithmetic average of all neighbors within radius 2.\n"
            "  ⚠️ Causes gradual drift toward gray over many generations.\n\n"
            "• HSV-boosted mean: Converts to HSV color space, boosts saturation.\n"
            "  ✅ Best anti-desaturation performance, maintains vivid colors 1000+ steps.\n\n"
            "• Random parent: Copies exact RGB from one random living neighbor.\n"
            "  ✅ Maintains sharp color boundaries, preserves distinct lineages.\n\n"
            "• Distance-weighted average: Weights neighbors by 1/(1+distance).\n"
            "  📍 Closer neighbors have more influence, reduces some gray drift.\n\n"
            "• Two-parent blend: Picks 2 random neighbors, averages their colors.\n"
            "  🧬 Simulates genetic inheritance, creates interesting patterns."
        )
        ttk.Label(desc_frame, text=desc_text, foreground="blue", 
                 font=("TkDefaultFont", 9), justify="left").pack(anchor="w")

        # HSV controls (shown only for hsv_boosted_mean)
        self.hsv_frame = ttk.LabelFrame(content, text="HSV Boosted Parameters", padding=15)
        
        hsv_help = ("Saturation boost multiplies mean saturation to enhance color vibrancy. "
                   "Saturation floor ensures minimum color intensity.")
        ttk.Label(self.hsv_frame, text=hsv_help, foreground="gray", 
                 wraplength=400, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(0, 10))
        
        boost_row = ttk.Frame(self.hsv_frame)
        boost_row.pack(fill="x", pady=3)
        ttk.Label(boost_row, text="Saturation boost:", width=15).pack(side="left")
        ttk.Scale(boost_row, from_=1.0, to=2.0, variable=self.saturation_boost, 
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(boost_row, textvariable=self.saturation_boost, width=5).pack(side="right")
        ttk.Label(boost_row, text="(1.3 recommended)", foreground="gray", 
                 font=("TkDefaultFont", 8)).pack(side="right", padx=(5, 0))

        floor_row = ttk.Frame(self.hsv_frame)
        floor_row.pack(fill="x", pady=3)
        ttk.Label(floor_row, text="Saturation floor:", width=15).pack(side="left")
        ttk.Scale(floor_row, from_=0.0, to=1.0, variable=self.saturation_floor,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(floor_row, textvariable=self.saturation_floor, width=5).pack(side="right")
        ttk.Label(floor_row, text="(0.35 recommended)", foreground="gray", 
                 font=("TkDefaultFont", 8)).pack(side="right", padx=(5, 0))

    def _create_mutation_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Mutations")
        content = frame.get_frame()

        # Enhanced help text
        help_text = ("Mutations add color diversity and prevent stagnation by randomly shifting RGB values. "
                    "Per-birth mutations affect individual newborns (recommended), while per-step mutations "
                    "affect random living cells globally. Higher mutation rates create more colorful but chaotic patterns.")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Enable mutations
        ttk.Checkbutton(content, text="Enable mutations", 
                       variable=self.mut_enable).pack(anchor="w", pady=(0, 15))

        # Per-birth mutations
        birth_mut_frame = ttk.LabelFrame(content, text="Per-Birth Mutations", padding=15)
        birth_mut_frame.pack(fill="x", pady=(0, 15))

        ttk.Checkbutton(birth_mut_frame, text="Mutate per birth (recommended)", 
                       variable=self.mut_per_birth_enable).pack(anchor="w", pady=(0, 10))

        prob_row = ttk.Frame(birth_mut_frame)
        prob_row.pack(fill="x", pady=3)
        ttk.Label(prob_row, text="Probability:", width=12).pack(side="left")
        ttk.Scale(prob_row, from_=0.0, to=0.5, variable=self.mut_per_birth_prob,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(prob_row, textvariable=self.mut_per_birth_prob, width=5).pack(side="right")

        # Per-step mutations (legacy)
        step_mut_frame = ttk.LabelFrame(content, text="Per-Step Mutations (Legacy)", padding=15)
        step_mut_frame.pack(fill="x", pady=(0, 15))

        ttk.Checkbutton(step_mut_frame, text="Mutate per step (global)", 
                       variable=self.mut_per_step_enable).pack(anchor="w", pady=(0, 10))

        step_prob_row = ttk.Frame(step_mut_frame)
        step_prob_row.pack(fill="x", pady=3)
        ttk.Label(step_prob_row, text="Probability:", width=12).pack(side="left")
        ttk.Scale(step_prob_row, from_=0.0, to=0.5, variable=self.mut_per_step_prob,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(step_prob_row, textvariable=self.mut_per_step_prob, width=5).pack(side="right")

        max_row = ttk.Frame(step_mut_frame)
        max_row.pack(fill="x", pady=3)
        ttk.Label(max_row, text="Max per step:", width=12).pack(side="left")
        ttk.Scale(max_row, from_=1, to=10, variable=self.mut_max_per_step,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(max_row, textvariable=self.mut_max_per_step, width=5).pack(side="right")

        # Common parameters
        common_frame = ttk.LabelFrame(content, text="Common Parameters", padding=15)
        common_frame.pack(fill="x")

        std_row = ttk.Frame(common_frame)
        std_row.pack(fill="x", pady=3)
        ttk.Label(std_row, text="Mutation std:", width=12).pack(side="left")
        ttk.Scale(std_row, from_=5.0, to=80.0, variable=self.mut_std,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(std_row, textvariable=self.mut_std, width=5).pack(side="right")

        interval_row = ttk.Frame(common_frame)
        interval_row.pack(fill="x", pady=3)
        ttk.Label(interval_row, text="Interval prob:", width=12).pack(side="left")
        ttk.Scale(interval_row, from_=0.0, to=0.5, variable=self.mut_interval,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(interval_row, textvariable=self.mut_interval, width=5).pack(side="right")

    def _create_seeds_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Seeds")
        content = frame.get_frame()

        # Enhanced help text
        help_text = ("Seed cells are the initial living cells that start the simulation. Position them strategically "
                    "to create interesting patterns. Color swatches show each seed's RGB value. "
                    "Randomize creates clustered seeds with vivid colors for complex structures.")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Seed manager
        seeds_frame = ttk.LabelFrame(content, text="Seed Management", padding=15)
        seeds_frame.pack(fill="both", expand=True)

        self.seed_mgr = SeedManager(seeds_frame, self._get_shape, self._set_status)
        self.seed_mgr.pack(fill="both", expand=True)

    def _create_output_tab(self):
        frame = ScrollableFrame(self.notebook)
        self.notebook.add(frame, text="Output")
        content = frame.get_frame()

        # Help text
        help_text = ("Final-only renders one high-res PNG (faster). All-steps creates a timestamped "
                    "subfolder with all frames. Animated GIF is created when rendering all steps.")
        ttk.Label(content, text=help_text, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 15))

        # Basic output
        basic_frame = ttk.LabelFrame(content, text="Basic Output", padding=15)
        basic_frame.pack(fill="x", pady=(0, 15))

        dir_frame = ttk.Frame(basic_frame)
        dir_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(dir_frame, text="Output directory:").pack(side="left")
        ttk.Entry(dir_frame, textvariable=self.outdir, width=30).pack(side="left", padx=(10, 0))

        ttk.Checkbutton(basic_frame, text="Render only final frame (faster)", 
                       variable=self.render_final_only).pack(anchor="w", pady=2)
        
        # GIF controls
        gif_main_frame = ttk.Frame(basic_frame)
        gif_main_frame.pack(fill="x", pady=2)
        
        self.gif_checkbox = ttk.Checkbutton(gif_main_frame, text="Create GIF animation", 
                                           variable=self.make_gif)
        self.gif_checkbox.pack(anchor="w")
        
        # GIF settings (nested frame)
        gif_settings_frame = ttk.Frame(basic_frame)
        gif_settings_frame.pack(fill="x", padx=(20, 0), pady=(5, 0))
        
        # FPS control
        fps_frame = ttk.Frame(gif_settings_frame)
        fps_frame.pack(fill="x", pady=2)
        ttk.Label(fps_frame, text="GIF FPS:", width=10).pack(side="left")
        self.gif_fps_scale = ttk.Scale(fps_frame, from_=1, to=30, variable=self.gif_fps, 
                                      orient="horizontal")
        self.gif_fps_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(fps_frame, textvariable=self.gif_fps, width=3).pack(side="right")
        
        # Cleanup options
        cleanup_frame = ttk.Frame(gif_settings_frame)
        cleanup_frame.pack(fill="x", pady=2)
        ttk.Label(cleanup_frame, text="After GIF:", width=10).pack(side="left")
        self.gif_cleanup_keep = ttk.Radiobutton(cleanup_frame, text="Keep frames", 
                                               variable=self.gif_cleanup, value="keep")
        self.gif_cleanup_keep.pack(side="left", padx=(10, 15))
        self.gif_cleanup_delete = ttk.Radiobutton(cleanup_frame, text="Delete frames", 
                                                 variable=self.gif_cleanup, value="delete")
        self.gif_cleanup_delete.pack(side="left")
        
        # GIF help text
        gif_help = ("Animated GIF is built from the rendered step_###.png frames. "
                   "If 'Delete' is selected, PNG frames are removed after GIF creation succeeds.")
        ttk.Label(gif_settings_frame, text=gif_help, foreground="gray", 
                 font=("TkDefaultFont", 8), wraplength=350).pack(anchor="w", pady=(5, 0))

        # High-res frame
        hr_frame = ttk.LabelFrame(content, text="High-Resolution Final", padding=15)
        hr_frame.pack(fill="x", pady=(0, 15))

        ttk.Checkbutton(hr_frame, text="Enable high-resolution final image", 
                       variable=self.hr_enable).pack(anchor="w", pady=(0, 10))

        # DPI
        dpi_frame = ttk.Frame(hr_frame)
        dpi_frame.pack(fill="x", pady=5)
        ttk.Label(dpi_frame, text="DPI:", width=12).pack(side="left")
        ttk.Entry(dpi_frame, textvariable=self.hr_dpi, width=8).pack(side="left", padx=(0, 10))
        ttk.Label(dpi_frame, text="(300+ for print quality)", foreground="gray").pack(side="left")

        # Width
        width_frame = ttk.Frame(hr_frame)
        width_frame.pack(fill="x", pady=5)
        ttk.Label(width_frame, text="Width (inches):", width=12).pack(side="left")
        ttk.Entry(width_frame, textvariable=self.hr_width, width=8).pack(side="left", padx=(0, 10))
        ttk.Label(width_frame, text="Image width", foreground="gray").pack(side="left")

        # Height
        height_frame = ttk.Frame(hr_frame)
        height_frame.pack(fill="x", pady=5)
        ttk.Label(height_frame, text="Height (inches):", width=12).pack(side="left")
        ttk.Entry(height_frame, textvariable=self.hr_height, width=8).pack(side="left", padx=(0, 10))
        ttk.Label(height_frame, text="Image height", foreground="gray").pack(side="left")
        
        # Auto-stop safety frame
        safety_frame = ttk.LabelFrame(content, text="Auto-Stop Safety", padding=15)
        safety_frame.pack(fill="x", pady=(15, 0))
        
        safety_help = ("Auto-stop prevents infinite simulations. Stops on extinction "
                      "(no living cells) or steady state (no changes for X steps).")
        ttk.Label(safety_frame, text=safety_help, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 10))
        
        ttk.Checkbutton(safety_frame, text="Enable auto-stop safety", 
                       variable=self.auto_stop_enable).pack(anchor="w", pady=2)
        
        threshold_frame = ttk.Frame(safety_frame)
        threshold_frame.pack(fill="x", pady=5)
        ttk.Label(threshold_frame, text="Steady state threshold:", width=18).pack(side="left")
        ttk.Entry(threshold_frame, textvariable=self.steady_state_threshold, width=8).pack(side="left", padx=(0, 10))
        ttk.Label(threshold_frame, text="consecutive identical steps", foreground="gray").pack(side="left")

        # Camera rotation frame
        rotation_frame = ttk.LabelFrame(content, text="Camera Rotation (GIF Only)", padding=15)
        rotation_frame.pack(fill="x", pady=(15, 0))
        
        rotation_help = ("Camera rotation creates dynamic GIFs by gradually changing the viewing angle. "
                        "Only applies when rendering all steps and creating GIF animations.")
        ttk.Label(rotation_frame, text=rotation_help, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 10))
        
        ttk.Checkbutton(rotation_frame, text="Enable camera rotation during GIF creation", 
                       variable=self.rotation_enable).pack(anchor="w", pady=2)
        
        degrees_frame = ttk.Frame(rotation_frame)
        degrees_frame.pack(fill="x", pady=5)
        ttk.Label(degrees_frame, text="Degrees per step:", width=15).pack(side="left")
        ttk.Scale(degrees_frame, from_=0.5, to=10.0, variable=self.rotation_degrees_per_step,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(degrees_frame, textvariable=self.rotation_degrees_per_step, width=5).pack(side="right")
        ttk.Label(degrees_frame, text="(2-3° recommended)", foreground="gray", 
                 font=("TkDefaultFont", 8)).pack(side="right", padx=(5, 0))
        
        elev_frame = ttk.Frame(rotation_frame)
        elev_frame.pack(fill="x", pady=5)
        ttk.Label(elev_frame, text="Elevation angle:", width=15).pack(side="left")
        ttk.Scale(elev_frame, from_=0, to=90, variable=self.rotation_elevation,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(elev_frame, textvariable=self.rotation_elevation, width=5).pack(side="right")
        ttk.Label(elev_frame, text="(20° default)", foreground="gray", 
                 font=("TkDefaultFont", 8)).pack(side="right", padx=(5, 0))

        # Age coloring frame
        age_frame = ttk.LabelFrame(content, text="Age Coloring (Visual Enhancement)", padding=15)
        age_frame.pack(fill="x", pady=(15, 0))
        
        age_help = ("Age coloring blends cell age with RGB colors for visual richness. "
                   "Does not affect simulation logic.")
        ttk.Label(age_frame, text=age_help, foreground="gray", wraplength=400).pack(
            anchor="w", pady=(0, 10))
        
        ttk.Checkbutton(age_frame, text="Color by age (enhances structure)", 
                       variable=self.color_by_age).pack(anchor="w", pady=2)
        
        cmap_frame = ttk.Frame(age_frame)
        cmap_frame.pack(fill="x", pady=5)
        ttk.Label(cmap_frame, text="Age colormap:", width=12).pack(side="left")
        cmap_combo = ttk.Combobox(cmap_frame, textvariable=self.age_cmap, width=15, state="readonly")
        cmap_combo['values'] = ("inferno", "plasma", "viridis", "hot", "cool", "winter", "spring")
        cmap_combo.pack(side="left", padx=(0, 10))
        
        alpha_frame = ttk.Frame(age_frame)
        alpha_frame.pack(fill="x", pady=5)
        ttk.Label(alpha_frame, text="Age blend:", width=12).pack(side="left")
        ttk.Scale(alpha_frame, from_=0.0, to=1.0, variable=self.age_alpha,
                 orient="horizontal").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(alpha_frame, textvariable=self.age_alpha, width=5).pack(side="right")

    def _get_shape(self):
        return (max(1, self.Z.get()), max(1, self.Y.get()), max(1, self.X.get()))

    def _set_status(self, message):
        self.status_label.config(text=message)
        self.after(3000, lambda: self.status_label.config(text="Ready"))

    def _parse_int_list(self, s: str):
        out = []
        for tok in s.split(","):
            tok = tok.strip()
            if tok:
                try:
                    out.append(int(tok))
                except ValueError:
                    pass
        return out

    def _list_run_frames(self, run_dir: Path) -> List[Path]:
        """List step frame files in natural order."""
        frames = []
        for file_path in run_dir.glob("step_*.png"):
            if file_path.name.startswith("step_") and not file_path.name.startswith("final_"):
                frames.append(file_path)
        
        # Sort by step number extracted from filename
        def extract_step_num(path):
            try:
                # Extract number from "step_XXX.png"
                stem = path.stem  # "step_XXX"
                return int(stem.split("_")[1])
            except (IndexError, ValueError):
                return 0
        
        frames.sort(key=extract_step_num)
        return frames

    def _build_animated_gif(self, frames: List[Path], output_gif: Path, fps: int) -> bool:
        """Build animated GIF from frame list. Returns True on success."""
        if len(frames) < 2:
            messagebox.showwarning("GIF Error", 
                                 f"Need at least 2 frames for animation, but only found {len(frames)}.")
            return False
        
        try:
            duration = 1.0 / max(1, fps)
            
            # Load images and create GIF
            images = []
            for frame_path in frames:
                img = imageio.imread(str(frame_path))
                images.append(img)
            
            imageio.mimsave(str(output_gif), images, duration=duration, loop=0)
            
            # Verify GIF was created and has nonzero size
            if output_gif.exists() and output_gif.stat().st_size > 0:
                return True
            else:
                return False
                
        except Exception as e:
            messagebox.showerror("GIF Error", f"Failed to create animated GIF:\n{str(e)}")
            return False

    def _delete_frames(self, frames: List[Path]) -> int:
        """Delete frame files safely. Returns count of successfully deleted files."""
        deleted_count = 0
        failed_files = []
        
        for frame_path in frames:
            try:
                if frame_path.exists():
                    frame_path.unlink()
                    deleted_count += 1
            except Exception as e:
                failed_files.append(f"{frame_path.name}: {str(e)}")
        
        if failed_files:
            error_msg = "Some frames could not be deleted:\n" + "\n".join(failed_files[:5])
            if len(failed_files) > 5:
                error_msg += f"\n... and {len(failed_files) - 5} more"
            messagebox.showwarning("Cleanup Warning", error_msg)
        
        return deleted_count

    def run(self):
        if not self.seed_mgr.seeds:
            if not messagebox.askyesno("No Seeds", 
                                     "No seeds defined. Create empty simulation?"):
                return

        self._set_status("Starting simulation...")
        self.run_button.config(state="disabled")

        shape = self._get_shape()
        steps = max(1, self.steps.get())
        rule = {
            "birth": self._parse_int_list(self.birth.get()),
            "survive": self._parse_int_list(self.survive.get())
        }
        
        # Build mutation config
        mutation = {
            "enable": bool(self.mut_enable.get()),
            "per_birth_mutation_prob": float(self.mut_per_birth_prob.get()) if self.mut_per_birth_enable.get() else 0.0,
            "per_step_mutation_prob": float(self.mut_per_step_prob.get()) if self.mut_per_step_enable.get() else 0.0,
            "max_mutants_per_step": int(self.mut_max_per_step.get()),
            "mutation_std": float(self.mut_std.get()),
            "p_interval": float(self.mut_interval.get())
        }
        
        # Color inheritance config
        color_params = {
            "saturation_boost": float(self.saturation_boost.get()),
            "saturation_floor": float(self.saturation_floor.get())
        }
        
        seeds = self.seed_mgr.seeds[:]
        base_outdir = Path(self.outdir.get().strip() or "./out")
        base_outdir.mkdir(exist_ok=True)
        
        # Create per-run folder when rendering all steps
        if not self.render_final_only.get():
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            outdir = base_outdir / f"run_{timestamp}"
            outdir.mkdir(exist_ok=True)
        else:
            outdir = base_outdir

        # Progress dialog
        progress = tk.Toplevel(self)
        progress.title("Running Simulation")
        progress.geometry("350x120")
        progress.transient(self)
        progress.grab_set()
        
        prog_label = ttk.Label(progress, text="Initializing simulation...")
        prog_label.pack(pady=15)
        
        prog_bar = ttk.Progressbar(progress, mode='indeterminate')
        prog_bar.pack(fill="x", padx=20, pady=10)
        prog_bar.start()
        
        self.update()

        try:
            sim = Life3DRGB(
                shape=shape, 
                rule=rule, 
                seed_cells=seeds, 
                mutation=mutation,
                color_inheritance_mode=self.color_mode.get(),
                color_params=color_params
            )
            
            # Configure auto-stop safety
            if self.auto_stop_enable.get():
                sim.set_steady_state_threshold(max(1, self.steady_state_threshold.get()))

            frames = []
            if not self.render_final_only.get():
                prog_label.config(text="Rendering initial frame...")
                self.update()
                # Use new render_voxels with age support and rotation
                initial_azimuth = 45
                if self.rotation_enable.get():
                    current_azimuth = initial_azimuth
                else:
                    current_azimuth = 45
                
                render_kwargs = {
                    "age": sim.age if self.color_by_age.get() else None,
                    "color_by_age": self.color_by_age.get(),
                    "age_cmap": self.age_cmap.get(),
                    "age_alpha": self.age_alpha.get(),
                    "elev": int(self.rotation_elevation.get()) if self.rotation_enable.get() else 20,
                    "azim": int(current_azimuth)
                }
                initial_frame = outdir / "step_000.png"
                render_voxels(sim.alive, sim.rgb, str(initial_frame), 
                             title="step 0", **render_kwargs)
                frames.append(str(initial_frame))

            actual_steps = 0
            auto_stop_reason = None
            extinct = False
            last_alive_step = 0
            
            for t in range(1, steps + 1):
                prog_label.config(text=f"Simulating step {t} of {steps}...")
                if t % 5 == 0:  # Update less frequently for performance
                    self.update()
                sim.step()
                actual_steps = t
                
                # Check for extinction BEFORE rendering (death switch logic)
                if sim.is_extinct():
                    extinct = True
                    auto_stop_reason = "extinction (no living cells)"
                    break
                
                # Update last alive step
                last_alive_step = t
                
                # Check other auto-stop conditions
                if self.auto_stop_enable.get():
                    if sim.is_steady_state():
                        auto_stop_reason = f"steady state ({self.steady_state_threshold.get()} identical steps)"
                        break
                
                if not self.render_final_only.get():
                    frame_path = outdir / f"step_{t:03d}.png"
                    
                    # Update azimuth for rotation
                    if self.rotation_enable.get():
                        rotation_per_step = self.rotation_degrees_per_step.get()
                        current_azimuth = (initial_azimuth + t * rotation_per_step) % 360
                    else:
                        current_azimuth = 45
                    
                    render_kwargs = {
                        "age": sim.age if self.color_by_age.get() else None,
                        "color_by_age": self.color_by_age.get(),
                        "age_cmap": self.age_cmap.get(),
                        "age_alpha": self.age_alpha.get(),
                        "elev": int(self.rotation_elevation.get()) if self.rotation_enable.get() else 20,
                        "azim": int(current_azimuth)
                    }
                    render_voxels(sim.alive, sim.rgb, str(frame_path), title=f"step {t}", **render_kwargs)
                    frames.append(str(frame_path))

            # Final frame (only render if not extinct or if final-only mode)
            final_path = None
            if not extinct or self.render_final_only.get():
                prog_label.config(text="Rendering final image...")
                self.update()
                
                # Use last_alive_step for final image if extinct, otherwise actual_steps
                final_step_num = last_alive_step if extinct else actual_steps
                final_path = outdir / f"final_step_{final_step_num:03d}.png"
                
                render_kwargs = {
                    "age": sim.age if self.color_by_age.get() else None,
                    "color_by_age": self.color_by_age.get(),
                    "age_cmap": self.age_cmap.get(),
                    "age_alpha": self.age_alpha.get()
                }
                
                # Only render final if there are living cells (avoid empty final image)
                if sim.alive.sum() > 0:
                    if self.render_final_only.get() and self.hr_enable.get():
                        figsize = (float(self.hr_width.get()), float(self.hr_height.get()))
                        dpi = int(self.hr_dpi.get())
                        render_voxels(sim.alive, sim.rgb, str(final_path), title=f"final (step {final_step_num})", 
                                    figsize=figsize, dpi=dpi, **render_kwargs)
                    else:
                        render_voxels(sim.alive, sim.rgb, str(final_path), title=f"final (step {final_step_num})",
                                    **render_kwargs)
                elif extinct:
                    # Don't create empty final image on extinction
                    final_path = None

            # Handle extinction cleanup if needed (death switch)
            valid_frames = None
            deleted_frames_count = 0
            
            if extinct and not self.render_final_only.get():
                # Clean up empty frames and get valid frames for GIF
                valid_frames, deleted_frames_count = handle_extinction_cleanup(
                    outdir=outdir,
                    current_step=last_alive_step + 1,  # The step where extinction occurred
                    last_alive_step=last_alive_step,
                    render_slices=False,  # UI doesn't render slices in the main loop
                    slice_every=0
                )
            
            # Enhanced GIF creation with death switch support
            gif_path = None
            frames_deleted = 0
            
            if imageio is not None and self.make_gif.get() and not self.render_final_only.get():
                prog_label.config(text="Creating animated GIF...")
                self.update()
                
                # Use valid frames from extinction cleanup if available, otherwise get all frames
                if valid_frames is not None:
                    frame_paths = valid_frames
                else:
                    frame_paths = list_step_frames(outdir)
                
                if len(frame_paths) >= 2:
                    gif_path = outdir / "evolution.gif"
                    fps = max(1, self.gif_fps.get())
                    
                    if extinct:
                        gif_success = create_gif_after_extinction(frame_paths, gif_path, fps)
                    else:
                        gif_success = build_gif(frame_paths, gif_path, fps)
                    
                    if gif_success:
                        # GIF created successfully
                        if self.gif_cleanup.get() == "delete":
                            prog_label.config(text="Cleaning up frame files...")
                            self.update()
                            frames_deleted = delete_files(frame_paths)
                    else:
                        gif_path = None
                elif len(frame_paths) == 1:
                    messagebox.showwarning("GIF Warning", 
                                         "Only 1 frame available. Cannot create animated GIF.")
                else:
                    messagebox.showwarning("GIF Warning", 
                                         "No step frames found for GIF creation.")

            progress.destroy()
            self.run_button.config(state="normal")

            # Enhanced results with death switch information
            alive_count = sim.alive.sum()
            total_cells = shape[0] * shape[1] * shape[2]
            
            result = f"✅ Simulation Complete!\n\n"
            result += f"Living cells: {alive_count:,} / {total_cells:,} ({alive_count/total_cells*100:.1f}%)\n"
            result += f"Steps simulated: {actual_steps}"
            if actual_steps < steps:
                result += f" of {steps} (auto-stopped)"
            result += "\n"
            if auto_stop_reason:
                result += f"🛑 Auto-stopped: {auto_stop_reason}\n"
            if extinct:
                result += f"💀 Death Switch activated - cleaned {deleted_frames_count} empty frame(s)\n"
            result += f"Grid size: {shape[0]}×{shape[1]}×{shape[2]}\n"
            result += f"Color mode: {self.color_mode.get()}\n\n"
            result += f"📁 Output:\n"
            if final_path:
                result += f"• {final_path}"
            elif extinct:
                result += f"• No final image (empty simulation)"
            
            if gif_path and gif_path.exists():
                result += f"\n• {gif_path} (animated GIF, {self.gif_fps.get()} FPS)"
                if extinct:
                    frame_count = len(valid_frames) if valid_frames else 0
                    result += f"\n• GIF created from {frame_count} non-empty frames"
                if frames_deleted > 0:
                    result += f"\n• Cleaned up {frames_deleted} frame files"
                elif self.gif_cleanup.get() == "keep":
                    frame_count = len(list_step_frames(outdir))
                    result += f"\n• Kept {frame_count} frame files"

            # Set status message with death switch info
            if extinct:
                status_msg = f"Population extinct at step {last_alive_step + 1}. Stopped early. Cleaned trailing empty frames."
                if gif_path and gif_path.exists():
                    status_msg += f" GIF created from non-empty frames."
                self._set_status(status_msg)
            else:
                if final_path:
                    self._set_status(f"Saved final image to {final_path.name}")
                else:
                    self._set_status("Simulation completed")
            
            messagebox.showinfo("Simulation Complete", result)

        except Exception as e:
            progress.destroy()
            self.run_button.config(state="normal")
            self._set_status("Simulation failed")
            messagebox.showerror("Error", f"Simulation failed:\n{str(e)}")

def main():
    """Main UI entry point with guarded Tkinter imports."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, colorchooser, simpledialog
    except ImportError:
        raise SystemExit(
            "Tkinter is not available in this environment. "
            "Install a Python build with Tcl/Tk (e.g., python.org or homebrew tcl-tk) and try again."
        )
    
    # Make Tkinter available to the App class
    globals().update({
        'tk': tk,
        'ttk': ttk,
        'messagebox': messagebox,
        'colorchooser': colorchooser,
        'simpledialog': simpledialog
    })
    
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()