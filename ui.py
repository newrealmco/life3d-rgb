import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from typing import List, Dict, Any
import os

from life3d import Life3DRGB
from visualize import render_voxels

try:
    import imageio.v2 as imageio
except Exception:
    imageio = None

class SeedManager(ttk.Frame):
    def __init__(self, master, shape_getter):
        super().__init__(master)
        self.shape_getter = shape_getter
        self.seeds: List[Dict[str,Any]] = []

        self.listbox = tk.Listbox(self, height=7, width=60)
        self.listbox.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=4)

        ttk.Button(self, text="Add seed", command=self.add_seed).grid(row=1, column=0, sticky="w", padx=2)
        ttk.Button(self, text="Delete selected", command=self.del_selected).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Button(self, text="Clear all", command=self.clear_all).grid(row=1, column=2, sticky="e", padx=2)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def add_seed(self):
        if len(self.seeds) >= 10:
            messagebox.showwarning("Limit", "You can define up to 10 seeds.")
            return

        dlg = tk.Toplevel(self); dlg.title("Add seed")
        z_var = tk.IntVar(value=0); y_var = tk.IntVar(value=0); x_var = tk.IntVar(value=0)
        rgb = [255,255,255]

        ttk.Label(dlg, text="z:").grid(row=0, column=0, sticky="e"); ttk.Entry(dlg, textvariable=z_var, width=8).grid(row=0, column=1)
        ttk.Label(dlg, text="y:").grid(row=1, column=0, sticky="e"); ttk.Entry(dlg, textvariable=y_var, width=8).grid(row=1, column=1)
        ttk.Label(dlg, text="x:").grid(row=2, column=0, sticky="e"); ttk.Entry(dlg, textvariable=x_var, width=8).grid(row=2, column=1)
        ttk.Button(dlg, text="Choose color", command=lambda: self._pick_color(rgb)).grid(row=0, column=2, rowspan=2, padx=10)

        def on_ok():
            Z,Y,X = self.shape_getter()
            z = z_var.get() % max(Z,1); y = y_var.get() % max(Y,1); x = x_var.get() % max(X,1)
            seed = {"z":z,"y":y,"x":x,"rgb":rgb.copy()}
            self.seeds.append(seed)
            self.listbox.insert(tk.END, f"({z},{y},{x}) RGB={tuple(rgb)}")
            dlg.destroy()

        ttk.Button(dlg, text="OK", command=on_ok).grid(row=3, column=0, pady=6)
        ttk.Button(dlg, text="Cancel", command=dlg.destroy).grid(row=3, column=1, pady=6)
        dlg.grab_set(); dlg.transient(self)

    def _pick_color(self, rgb_ref):
        c = colorchooser.askcolor(color="#%02x%02x%02x" % tuple(rgb_ref))
        if c and c[0] is not None:
            r,g,b = [int(round(v)) for v in c[0]]
            rgb_ref[0], rgb_ref[1], rgb_ref[2] = r,g,b

    def del_selected(self):
        sel = list(self.listbox.curselection()); sel.reverse()
        for idx in sel:
            self.listbox.delete(idx)
            del self.seeds[idx]

    def clear_all(self):
        self.listbox.delete(0, tk.END)
        self.seeds.clear()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3D Life (RGB+Mutations)")
        self.geometry("760x560")

        # Params
        self.Z = tk.IntVar(value=24); self.Y = tk.IntVar(value=24); self.X = tk.IntVar(value=24)
        self.steps = tk.IntVar(value=60)

        self.birth = tk.StringVar(value="6")
        self.survive = tk.StringVar(value="5,6,7")

        self.mut_enable = tk.BooleanVar(value=True)
        self.mut_prob = tk.DoubleVar(value=0.25)
        self.mut_std = tk.DoubleVar(value=35.0)
        self.mut_interval = tk.DoubleVar(value=0.15)

        self.outdir = tk.StringVar(value="./out")
        self.render_final_only = tk.BooleanVar(value=True)
        self.make_gif = tk.BooleanVar(value=False)

        # High-res final (when final-only)
        self.hr_enable = tk.BooleanVar(value=True)
        self.hr_dpi = tk.IntVar(value=300)
        self.hr_size = tk.DoubleVar(value=12.0)  # inches (square)

        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=10, pady=10)

        # Grid & steps
        gs = ttk.LabelFrame(frm, text="Grid (Z,Y,X) & Steps"); gs.grid(row=0, column=0, sticky="nw", padx=6, pady=6)
        for i,(lbl,var) in enumerate([("Z",self.Z),("Y",self.Y),("X",self.X),("Steps",self.steps)]):
            ttk.Label(gs, text=lbl).grid(row=0, column=2*i, sticky="e")
            ttk.Entry(gs, textvariable=var, width=6).grid(row=0, column=2*i+1, padx=4)

        # Rules
        rl = ttk.LabelFrame(frm, text="Rules (B/S)"); rl.grid(row=1, column=0, sticky="nw", padx=6, pady=6)
        ttk.Label(rl, text="Birth (comma-separated)").grid(row=0, column=0, sticky="w")
        ttk.Entry(rl, textvariable=self.birth, width=20).grid(row=0, column=1, padx=4)
        ttk.Label(rl, text="Survive (comma-separated)").grid(row=1, column=0, sticky="w")
        ttk.Entry(rl, textvariable=self.survive, width=20).grid(row=1, column=1, padx=4)

        # Mutation
        mt = ttk.LabelFrame(frm, text="Mutation"); mt.grid(row=2, column=0, sticky="nw", padx=6, pady=6)
        ttk.Checkbutton(mt, text="Enable", variable=self.mut_enable).grid(row=0, column=0, sticky="w")
        ttk.Label(mt, text="Per-step prob").grid(row=1, column=0, sticky="e"); ttk.Entry(mt, textvariable=self.mut_prob, width=8).grid(row=1, column=1)
        ttk.Label(mt, text="Std-dev").grid(row=1, column=2, sticky="e"); ttk.Entry(mt, textvariable=self.mut_std, width=8).grid(row=1, column=3)
        ttk.Label(mt, text="Interval p").grid(row=1, column=4, sticky="e"); ttk.Entry(mt, textvariable=self.mut_interval, width=8).grid(row=1, column=5)

        # Seeds
        sd = ttk.LabelFrame(frm, text="Seeds (up to 10)"); sd.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=6, pady=6)
        self.seed_mgr = SeedManager(sd, self._get_shape); self.seed_mgr.pack(fill="both", expand=True)

        # Output
        out = ttk.LabelFrame(frm, text="Output"); out.grid(row=3, column=0, sticky="nw", padx=6, pady=6)
        ttk.Label(out, text="Out dir").grid(row=0, column=0, sticky="e"); ttk.Entry(out, textvariable=self.outdir, width=22).grid(row=0, column=1, padx=4)
        ttk.Checkbutton(out, text="Render only final frame", variable=self.render_final_only).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(out, text="Also make GIF (requires imageio)", variable=self.make_gif).grid(row=2, column=0, columnspan=2, sticky="w")

        ttk.Checkbutton(out, text="High-res final (only when final-only)", variable=self.hr_enable).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(out, text="Final DPI").grid(row=4, column=0, sticky="e"); ttk.Entry(out, textvariable=self.hr_dpi, width=8).grid(row=4, column=1, sticky="w")
        ttk.Label(out, text="Final Size (inches)").grid(row=5, column=0, sticky="e"); ttk.Entry(out, textvariable=self.hr_size, width=8).grid(row=5, column=1, sticky="w")

        # Run
        ttk.Button(frm, text="Run Simulation", command=self.run).grid(row=3, column=1, sticky="se", padx=6, pady=6)

        frm.grid_rowconfigure(0, weight=0); frm.grid_rowconfigure(2, weight=0); frm.grid_rowconfigure(3, weight=1)
        frm.grid_columnconfigure(1, weight=1)

    def _get_shape(self):
        return (max(1,self.Z.get()), max(1,self.Y.get()), max(1,self.X.get()))

    def _parse_int_list(self, s: str):
        out = []
        for tok in s.split(","):
            tok = tok.strip()
            if tok:
                try: out.append(int(tok))
                except ValueError: pass
        return out

    def run(self):
        shape = self._get_shape()
        steps = max(1, self.steps.get())
        rule = {"birth": self._parse_int_list(self.birth.get()),
                "survive": self._parse_int_list(self.survive.get())}
        mutation = {
            "enable": bool(self.mut_enable.get()),
            "per_step_birth_mutation_prob": float(self.mut_prob.get()),
            "std": float(self.mut_std.get()),
            "p_interval": float(self.mut_interval.get())
        }
        seeds = self.seed_mgr.seeds[:]
        outdir = self.outdir.get().strip() or "./out"
        os.makedirs(outdir, exist_ok=True)

        sim = Life3DRGB(shape=shape, rule=rule, seed_cells=seeds, mutation=mutation)

        frames = []
        # Only render intermediate frames if not final-only
        if not self.render_final_only.get():
            from visualize import render_voxels as rv
            rv(sim.alive, sim.rgb, os.path.join(outdir, f"step_000.png"), title="step 0")

        for t in range(1, steps+1):
            sim.step()
            if not self.render_final_only.get():
                p = os.path.join(outdir, f"step_{t:03d}.png")
                render_voxels(sim.alive, sim.rgb, p, title=f"step {t}")
                if imageio is not None and self.make_gif.get():
                    frames.append(p)

        # Final frame (always)
        final_path = os.path.join(outdir, f"final_step_{steps:03d}.png")
        if self.render_final_only.get() and self.hr_enable.get():
            fs = (float(self.hr_size.get()), float(self.hr_size.get()))
            dpi = int(self.hr_dpi.get())
            render_voxels(sim.alive, sim.rgb, final_path, title=f"final (step {steps})", figsize=fs, dpi=dpi)
        else:
            render_voxels(sim.alive, sim.rgb, final_path, title=f"final (step {steps})")

        if imageio is not None and self.make_gif.get() and frames:
            imgs = [imageio.imread(p) for p in frames]
            gif_path = os.path.join(outdir, f"evolution_{steps:03d}.gif")
            imageio.mimsave(gif_path, imgs, duration=0.12)
            messagebox.showinfo("Done", f"Saved final image:\n{final_path}\n\nand GIF:\n{gif_path}")
        else:
            messagebox.showinfo("Done", f"Saved final image:\n{final_path}")

if __name__ == "__main__":
    App().mainloop()
