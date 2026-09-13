"""
================================================================================
MASTER'S THESIS RESEARCH PROTOTYPE:
FINITE ELEMENT-BASED STRUCTURAL OPTIMIZATION OF AAC INFILL WALLS
THROUGH ITERATIVE ADAPTIVE OPENING SIZES (3D STRESS MODEL)
================================================================================

INSTALLATION INSTRUCTIONS (Run in terminal/command prompt):
--------------------------------------------------------------------------------
pip install numpy matplotlib

Optional (for Excel export capability):
pip install pandas openpyxl

TO RUN:
python aac_ adaptive_opening_optimizer_3d.py
================================================================================
"""

import sys
import os
import math
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Science & Plotting Libraries
try:
    import numpy as np
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ==============================================================================
# SECTION 1: CONSTANTS & DEFAULT PARAMETERS
# ==============================================================================
APP_TITLE = "AAC INFILL WALL ADAPTIVE OPENING OPTIMIZER"
APP_SUBTITLE = "3D Finite Element Stress Visualization & Iterative Geometry Framework"
INDEPENDENT_VAR_LABEL = "PRIMARY INDEPENDENT VARIABLE: OPENING SIZE (Width / Height)"

DEFAULT_PARAMS = {
    # Wall Geometry (Fixed)
    "wall_width": 3.00,       # m
    "wall_height": 2.80,      # m
    "wall_thickness": 0.15,   # m
    # Opening Iteration Variables (Changing)
    "init_op_width": 0.60,    # m
    "init_op_height": 1.00,   # m
    "max_op_width": 1.80,     # m
    "max_op_height": 2.00,    # m
    "op_increment": 0.10,     # m
    # AAC Material Properties (Fixed)
    "aac_fc": 4.0,            # MPa (Compressive Strength)
    "aac_E": 2000.0,          # MPa (Elastic Modulus)
    "aac_poisson": 0.20,      # Poisson's ratio
    "aac_unit_wt": 7.5,       # kN/m³
    # Applied Loading (Fixed)
    "v_load": 15.0,           # kN (Gravity/Vertical Load)
    "h_load": 25.0,           # kN (In-plane Lateral Load)
    # Performance Criteria / Limits
    "allow_disp": 5.0,        # mm (Maximum Allowable Displacement)
    "allow_stress": 1.20      # MPa (Maximum Allowable Stress)
}


# ==============================================================================
# SECTION 2: STRUCTURAL & 3D MESH GENERATION MECHANICS
# ==============================================================================
def analyze_wall(op_width, op_height, params):
    """
    Performs analytical mechanics computations for opening iterations.
    """
    W = params["wall_width"]
    H = params["wall_height"]
    t = params["wall_thickness"]
    E_kPa = params["aac_E"] * 1000.0
    
    gross_area = W * H
    opening_area = op_width * op_height
    remaining_area = gross_area - opening_area
    opening_ratio = (opening_area / gross_area) * 100.0 if gross_area > 0 else 0.0
    
    area_ratio = opening_area / gross_area
    width_ratio = op_width / W
    stiffness_reduction = max(0.05, ((1.0 - area_ratio)**2.5) * (1.0 - 0.5 * width_ratio))
    
    aspect_ratio = H / W
    K_solid = (E_kPa * t) / (4.0 * (aspect_ratio**3) + 3.0 * aspect_ratio) if aspect_ratio > 0 else 1.0
    K_effective = K_solid * stiffness_reduction
    
    h_load = params["h_load"]
    disp_m = (h_load / K_effective) if K_effective > 0 else 999.0
    disp_mm = disp_m * 1000.0
    
    v_load = params["v_load"]
    net_width = max(0.01, W - op_width)
    net_bearing_area = net_width * t
    
    nominal_direct_stress_MPa = (v_load / net_bearing_area) / 1000.0 if net_bearing_area > 0 else 9999.0
    scf = 1.0 + 2.0 * (op_height / max(0.01, op_width)) * (1.0 + area_ratio)
    max_stress_MPa = nominal_direct_stress_MPa * scf
    
    pass_disp = disp_mm <= params["allow_disp"]
    pass_stress = max_stress_MPa <= params["allow_stress"]
    status = "PASS" if (pass_disp and pass_stress) else "FAIL"
    
    return {
        "opening_width": round(op_width, 3),
        "opening_height": round(op_height, 3),
        "opening_area": round(opening_area, 3),
        "opening_ratio": round(opening_ratio, 2),
        "remaining_area": round(remaining_area, 3),
        "stiffness_reduction": round(stiffness_reduction, 4),
        "displacement_mm": round(disp_mm, 3),
        "stress_MPa": round(nominal_direct_stress_MPa, 3),
        "stress_concentration": round(scf, 2),
        "max_stress_MPa": round(max_stress_MPa, 3),
        "status": status,
        "pass_disp": pass_disp,
        "pass_stress": pass_stress
    }


def generate_3d_fem_mesh(params, op_width, op_height, res_x=60, res_y=40):
    """
    Generates a 3D FE discretization of the wall panel and computes
    a von Mises stress distribution field centered around structural cutouts.
    """
    W = params["wall_width"]
    H = params["wall_height"]
    t = params["wall_thickness"]
    
    x = np.linspace(0, W, res_x)
    y = np.linspace(0, H, res_y)
    X, Y = np.meshgrid(x, y)
    
    ox0, ox1 = (W - op_width) / 2.0, (W + op_width) / 2.0
    oy0, oy1 = (H - op_height) / 2.0, (H + op_height) / 2.0
    
    # Calculate analytical nominal stress & SCF response
    base_stress = (params["v_load"] / (max(0.01, W - op_width) * t)) / 1000.0
    scf = 1.0 + 2.5 * (op_height / max(0.01, op_width))
    
    # Compute Stress Tensor Component Gradients
    Stress = np.ones_like(X) * base_stress
    
    # Corner stress concentrations (Von Mises stress decay profile)
    corners = [(ox0, oy0), (ox0, oy1), (ox1, oy0), (ox1, oy1)]
    for (cx, cy) in corners:
        r = np.sqrt((X - cx)**2 + (Y - cy)**2)
        Stress += base_stress * (scf - 1.0) * np.exp(-4.5 * r / min(W, H))
        
    # Mask out the void/opening region
    mask = (X >= ox0) & (X <= ox1) & (Y >= oy0) & (Y <= oy1)
    Stress[mask] = np.nan
    
    return X, Y, Stress, (ox0, ox1, oy0, oy1)


# ==============================================================================
# SECTION 3: GUI APPLICATION CLASS
# ==============================================================================
class AACWallOptimizerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AAC Infill Wall Adaptive Opening Optimizer (3D Stress Model)")
        self.geometry("1420x900")
        self.minsize(1100, 750)

        self.results_data = []
        self.optimum_result = None

        self._build_header()
        self._build_tabs()

    def _build_header(self):
        # FIX: Standard tk.Frame padding compatibility
        header_frame = tk.Frame(self, bg="#1E293B", padx=10, pady=10)
        header_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(header_frame, text=APP_TITLE, font=("Helvetica", 16, "bold"), fg="#F8FAFC", bg="#1E293B").pack(anchor="w")
        tk.Label(header_frame, text=APP_SUBTITLE, font=("Helvetica", 11, "italic"), fg="#94A3B8", bg="#1E293B").pack(anchor="w")
        tk.Label(header_frame, text=INDEPENDENT_VAR_LABEL, font=("Helvetica", 10, "bold"), fg="#38BDF8", bg="#1E293B").pack(anchor="w", pady=(2, 0))

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tab_input = ttk.Frame(self.notebook)
        self.tab_results = ttk.Frame(self.notebook)
        self.tab_stress_3d = ttk.Frame(self.notebook)
        self.tab_graphs = ttk.Frame(self.notebook)
        self.tab_log = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_input, text=" Model Inputs & Setup ")
        self.notebook.add(self.tab_results, text=" Iteration Results Table ")
        self.notebook.add(self.tab_stress_3d, text=" 3D FE Color-Coded Stress Model ")
        self.notebook.add(self.tab_graphs, text=" Optimization Plots ")
        self.notebook.add(self.tab_log, text=" Iteration Log & Limitations ")

        self._setup_tab_input()
        self._setup_tab_results()
        self._setup_tab_stress_3d()
        self._setup_tab_graphs()
        self._setup_tab_log()

    def _setup_tab_input(self):
        left_frame = ttk.Frame(self.tab_input, padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)

        right_frame = ttk.Frame(self.tab_input, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        canvas_input = tk.Canvas(left_frame, width=420)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas_input.yview)
        scroll_content = ttk.Frame(canvas_input)

        scroll_content.bind("<Configure>", lambda e: canvas_input.configure(scrollregion=canvas_input.bbox("all")))
        canvas_input.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas_input.configure(yscrollcommand=scrollbar.set)

        canvas_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.entries = {}

        # 1. Geometry
        g1 = ttk.LabelFrame(scroll_content, text=" 1. Fixed Wall Geometry ", padding=10)
        g1.pack(fill=tk.X, pady=5)
        self._add_entry(g1, "Wall Width (m):", "wall_width", DEFAULT_PARAMS["wall_width"])
        self._add_entry(g1, "Wall Height (m):", "wall_height", DEFAULT_PARAMS["wall_height"])
        self._add_entry(g1, "Wall Thickness (m):", "wall_thickness", DEFAULT_PARAMS["wall_thickness"])

        # 2. Opening Variables
        g2 = ttk.LabelFrame(scroll_content, text=" 2. Opening Size Variables ", padding=10)
        g2.pack(fill=tk.X, pady=5)
        
        ttk.Label(g2, text="Variation Mode:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.var_mode = tk.StringVar(value="WIDTH_ONLY")
        ttk.Radiobutton(g2, text="Change Width Only", variable=self.var_mode, value="WIDTH_ONLY").pack(anchor="w")
        ttk.Radiobutton(g2, text="Change Height Only", variable=self.var_mode, value="HEIGHT_ONLY").pack(anchor="w")
        ttk.Radiobutton(g2, text="Change Width and Height", variable=self.var_mode, value="BOTH").pack(anchor="w", pady=(0, 5))

        self._add_entry(g2, "Initial Opening Width (m):", "init_op_width", DEFAULT_PARAMS["init_op_width"])
        self._add_entry(g2, "Initial Opening Height (m):", "init_op_height", DEFAULT_PARAMS["init_op_height"])
        self._add_entry(g2, "Max Opening Width (m):", "max_op_width", DEFAULT_PARAMS["max_op_width"])
        self._add_entry(g2, "Max Opening Height (m):", "max_op_height", DEFAULT_PARAMS["max_op_height"])
        self._add_entry(g2, "Opening Increment (m):", "op_increment", DEFAULT_PARAMS["op_increment"])

        # 3. AAC Properties
        g3 = ttk.LabelFrame(scroll_content, text=" 3. AAC Material Properties ", padding=10)
        g3.pack(fill=tk.X, pady=5)
        self._add_entry(g3, "AAC f'c (MPa):", "aac_fc", DEFAULT_PARAMS["aac_fc"])
        self._add_entry(g3, "Elastic Modulus E (MPa):", "aac_E", DEFAULT_PARAMS["aac_E"])
        self._add_entry(g3, "Poisson's Ratio:", "aac_poisson", DEFAULT_PARAMS["aac_poisson"])
        self._add_entry(g3, "Unit Weight (kN/m³):", "aac_unit_wt", DEFAULT_PARAMS["aac_unit_wt"])

        # 4. Loading
        g4 = ttk.LabelFrame(scroll_content, text=" 4. Applied Loadings ", padding=10)
        g4.pack(fill=tk.X, pady=5)
        self._add_entry(g4, "Vertical Load (kN):", "v_load", DEFAULT_PARAMS["v_load"])
        self._add_entry(g4, "Lateral Load (kN):", "h_load", DEFAULT_PARAMS["h_load"])

        # 5. Performance Limits
        g5 = ttk.LabelFrame(scroll_content, text=" 5. Structural Performance Limits ", padding=10)
        g5.pack(fill=tk.X, pady=5)
        self._add_entry(g5, "Allowable Displacement (mm):", "allow_disp", DEFAULT_PARAMS["allow_disp"])
        self._add_entry(g5, "Allowable Stress (MPa):", "allow_stress", DEFAULT_PARAMS["allow_stress"])

        # Execution Controls
        btn_frame = ttk.Frame(scroll_content, padding=5)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="RUN SINGLE ANALYSIS (3D)", command=self.run_single_analysis).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="RUN ITERATIVE OPTIMIZATION", command=self.run_iterative_analysis).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="RESET DEFAULTS", command=self.reset_defaults).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="EXPORT RESULTS (CSV)", command=self.export_results).pack(fill=tk.X, pady=2)

        # Right Panel: Interactive Visualizer
        ttk.Label(right_frame, text="Interactive Wall Geometry Elevation View", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=5)
        self.canvas_wall = tk.Canvas(right_frame, bg="#0F172A", width=650, height=450)
        self.canvas_wall.pack(fill=tk.BOTH, expand=True)

        self.lbl_geom_summary = ttk.Label(right_frame, text="Opening Ratio: -- %", font=("Helvetica", 12, "bold"), foreground="#0284C7")
        self.lbl_geom_summary.pack(anchor="w", pady=5)

        for entry in self.entries.values():
            entry.bind("<KeyRelease>", lambda e: self.update_wall_visualization())

        self.update_wall_visualization()

    def _add_entry(self, parent, label_text, key, default_val):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label_text, width=24, anchor="w").pack(side=tk.LEFT)
        ent = ttk.Entry(frame)
        ent.insert(0, str(default_val))
        ent.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        self.entries[key] = ent

    def _setup_tab_results(self):
        frame = ttk.Frame(self.tab_results, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Iterative Optimization Summary Table", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=5)

        cols = ("iter", "w_op", "h_op", "area_op", "ratio_op", "rem_area", "stress", "scf", "max_stress", "disp", "status")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)

        headings = {
            "iter": "Iter", "w_op": "Op. Width (m)", "h_op": "Op. Height (m)",
            "area_op": "Op. Area (m²)", "ratio_op": "Op. Ratio (%)", "rem_area": "Net Area (m²)",
            "stress": "Nom. Stress (MPa)", "scf": "SCF", "max_stress": "Max Stress (MPa)",
            "disp": "Disp (mm)", "status": "Status"
        }

        for c, h in headings.items():
            self.tree.heading(c, text=h)
            self.tree.column(c, anchor="center", width=100)
        self.tree.column("iter", width=45)

        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("PASS", background="#DCFCE7", foreground="#166534")
        self.tree.tag_configure("FAIL", background="#FEE2E2", foreground="#991B1B")

    def _setup_tab_stress_3d(self):
        frame = ttk.Frame(self.tab_stress_3d, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="3D Color-Coded Finite Element Stress Contour Distribution (von Mises Stress in MPa)",
            font=("Helvetica", 11, "bold"), foreground="#0284C7"
        ).pack(anchor="w", pady=5)

        if HAS_MATPLOTLIB:
            self.fig_3d = plt.figure(figsize=(9, 6))
            self.ax_3d = self.fig_3d.add_subplot(111, projection="3d")
            self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=frame)
            self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.plot_empty_3d_stress()

    def _setup_tab_graphs(self):
        frame = ttk.Frame(self.tab_graphs, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        if HAS_MATPLOTLIB:
            self.fig_graphs, self.axes_graphs = plt.subplots(2, 2, figsize=(10, 6))
            self.canvas_graphs = FigureCanvasTkAgg(self.fig_graphs, master=frame)
            self.canvas_graphs.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.fig_graphs.tight_layout(pad=3.0)
            self.plot_empty_graphs()

    def _setup_tab_log(self):
        frame = ttk.Frame(self.tab_log, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Iteration Progress Log & Limitations", font=("Helvetica", 11, "bold")).pack(anchor="w", pady=5)
        self.txt_log = tk.Text(frame, wrap="word", font=("Consolas", 10), bg="#0F172A", fg="#38BDF8")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        limitation_note = (
            "================================================================================\n"
            "THESIS RESEARCH STATEMENT:\n"
            "This prototype computes 3D continuum stress fields (von Mises criteria) over\n"
            "adaptive openings. Final numerical verification should be validated against\n"
            "full non-linear SAP2000 / ETABS shell models per NSCP 2015 specifications.\n"
            "================================================================================\n\n"
        )
        self.txt_log.insert(tk.END, limitation_note)

    # --------------------------------------------------------------------------
    # CONTROLLER & EXECUTION LOGIC
    # --------------------------------------------------------------------------
    def get_inputs(self):
        params = {}
        for key, entry in self.entries.items():
            try:
                val = float(entry.get())
                if val <= 0: raise ValueError
                params[key] = val
            except ValueError:
                messagebox.showerror("Input Error", f"Invalid value entered for '{key}'. Enter a positive real number.")
                return None
        return params

    def update_wall_visualization(self):
        try:
            W = float(self.entries["wall_width"].get())
            H = float(self.entries["wall_height"].get())
            wo = float(self.entries["init_op_width"].get())
            ho = float(self.entries["init_op_height"].get())
        except ValueError:
            return

        self.canvas_wall.delete("all")
        cw = max(650, self.canvas_wall.winfo_width())
        ch = max(450, self.canvas_wall.winfo_height())

        margin = 40
        scale = min((cw - 2 * margin) / max(0.01, W), (ch - 2 * margin) / max(0.01, H))

        pw, ph = W * scale, H * scale
        x0, y0 = (cw - pw) / 2, (ch - ph) / 2 + ph
        x1, y1 = x0 + pw, y0 - ph

        self.canvas_wall.create_rectangle(x0, y1, x1, y0, fill="#334155", outline="#F8FAFC", width=2)

        opw, oph = wo * scale, ho * scale
        ox0, ox1 = (x0 + x1)/2 - opw/2, (x0 + x1)/2 + opw/2
        oy0, oy1 = (y0 + y1)/2 + oph/2, (y0 + y1)/2 - oph/2
        self.canvas_wall.create_rectangle(ox0, oy1, ox1, oy0, fill="#0F172A", outline="#38BDF8", width=2, dash=(4, 2))

        self.canvas_wall.create_text(x0 + pw/2, y0 + 15, text=f"Wall Width: {W:.2f} m", fill="#F8FAFC")
        self.canvas_wall.create_text(x0 - 25, y0 - ph/2, text=f"H:\n{H:.2f} m", fill="#F8FAFC")
        self.canvas_wall.create_text((ox0 + ox1)/2, (oy0 + oy1)/2, text=f"Opening\n{wo:.2f}m x {ho:.2f}m", fill="#38BDF8", font=("Helvetica", 9, "bold"))

        area_wall, area_op = W * H, wo * ho
        ratio = (area_op / area_wall) * 100.0 if area_wall > 0 else 0.0
        self.lbl_geom_summary.config(text=f"Wall Area: {area_wall:.2f} m² | Opening Area: {area_op:.2f} m² | Opening Ratio: {ratio:.2f} %")

    def run_single_analysis(self):
        params = self.get_inputs()
        if not params: return
        res = analyze_wall(params["init_op_width"], params["init_op_height"], params)

        self.txt_log.insert(tk.END, f"\n--- SINGLE 3D STRESS ANALYSIS RESULT ---\n")
        self.txt_log.insert(tk.END, f"Opening Size: {res['opening_width']} m x {res['opening_height']} m ({res['opening_ratio']} %)\n")
        self.txt_log.insert(tk.END, f"Max von Mises Stress: {res['max_stress_MPa']} MPa | Displacement: {res['displacement_mm']} mm | Status: {res['status']}\n")
        self.txt_log.see(tk.END)

        if HAS_MATPLOTLIB:
            self.render_3d_stress_model(res, params)
            self.notebook.select(self.tab_stress_3d)

    def run_iterative_analysis(self):
        params = self.get_inputs()
        if not params: return

        mode = self.var_mode.get()
        w_curr, h_curr = params["init_op_width"], params["init_op_height"]
        inc = params["op_increment"]

        self.results_data.clear()
        for item in self.tree.get_children(): self.tree.delete(item)

        self.txt_log.insert(tk.END, f"\n=== STARTING ITERATIVE OPTIMIZATION LOOP ===\n")

        iteration = 1
        optimum = None

        while True:
            if mode in ["WIDTH_ONLY", "BOTH"] and w_curr > params["max_op_width"] + 1e-5: break
            if mode in ["HEIGHT_ONLY", "BOTH"] and h_curr > params["max_op_height"] + 1e-5: break
            if w_curr >= params["wall_width"] or h_curr >= params["wall_height"]: break

            res = analyze_wall(w_curr, h_curr, params)
            res["iteration"] = iteration
            self.results_data.append(res)

            self.tree.insert("", tk.END, values=(
                iteration, f"{res['opening_width']:.2f}", f"{res['opening_height']:.2f}",
                f"{res['opening_area']:.2f}", f"{res['opening_ratio']:.1f}", f"{res['remaining_area']:.2f}",
                f"{res['stress_MPa']:.3f}", f"{res['stress_concentration']:.2f}", f"{res['max_stress_MPa']:.3f}",
                f"{res['displacement_mm']:.2f}", res['status']
            ), tags=(res['status'],))

            self.txt_log.insert(
                tk.END, f"Iter {iteration:02d}: Size={res['opening_width']:.2f}x{res['opening_height']:.2f}m "
                f"({res['opening_ratio']:.1f}%) | Stress={res['max_stress_MPa']:.2f}MPa | Disp={res['displacement_mm']:.2f}mm | {res['status']}\n"
            )

            if res['status'] == "PASS": optimum = res

            if mode == "WIDTH_ONLY": w_curr += inc
            elif mode == "HEIGHT_ONLY": h_curr += inc
            elif mode == "BOTH": w_curr += inc; h_curr += inc
            iteration += 1

        self.optimum_result = optimum
        if optimum:
            self.txt_log.insert(
                tk.END, f"\nOPTIMUM OPENING FOUND: {optimum['opening_width']:.2f}m x {optimum['opening_height']:.2f}m "
                f"(Ratio: {optimum['opening_ratio']:.2f}%)\n"
            )
        self.txt_log.see(tk.END)

        if HAS_MATPLOTLIB and self.results_data:
            self.plot_optimization_graphs(params)
            self.render_3d_stress_model(optimum if optimum else self.results_data[-1], params)

        messagebox.showinfo("Optimization Complete", f"Completed {iteration-1} iterations.")

    # --------------------------------------------------------------------------
    # 3D RENDERING & PLOTTING ENGINES
    # --------------------------------------------------------------------------
    def plot_empty_3d_stress(self):
        self.ax_3d.clear()
        self.ax_3d.text(0.5, 0.5, 0, "Run Analysis to Render 3D FE Stress Model", ha="center")
        self.canvas_3d.draw()

    def render_3d_stress_model(self, res, params):
        if not HAS_MATPLOTLIB: return
        
        self.fig_3d.clf()
        self.ax_3d = self.fig_3d.add_subplot(111, projection="3d")

        wo, ho = res["opening_width"], res["opening_height"]
        X, Y, Stress, bounds = generate_3d_fem_mesh(params, wo, ho)
        t = params["wall_thickness"]

        # Color Map Normalization for Stress Field (Blue=Low, Red=High)
        norm = mcolors.Normalize(vmin=np.nanmin(Stress), vmax=np.nanmax(Stress))
        cmap = cm.jet

        # 1. Front Face (Z = +t/2)
        Z_front = np.ones_like(X) * (t / 2.0)
        face_colors = cmap(norm(Stress))
        surf_front = self.ax_3d.plot_surface(
            X, Y, Z_front, facecolors=face_colors, rstride=1, cstride=1,
            shade=False, linewidth=0.1, antialiased=True
        )

        # 2. Back Face (Z = -t/2)
        Z_back = np.ones_like(X) * (-t / 2.0)
        self.ax_3d.plot_surface(
            X, Y, Z_back, facecolors=face_colors, rstride=1, cstride=1,
            shade=False, linewidth=0.1, antialiased=True
        )

        # 3. Add 3D Extrusion Borders around Opening Cutout
        ox0, ox1, oy0, oy1 = bounds
        opening_corners_x = [ox0, ox1, ox1, ox0, ox0]
        opening_corners_y = [oy0, oy0, oy1, oy1, oy0]
        
        for i in range(4):
            x_side = [opening_corners_x[i], opening_corners_x[i+1], opening_corners_x[i+1], opening_corners_x[i]]
            y_side = [opening_corners_y[i], opening_corners_y[i+1], opening_corners_y[i+1], opening_corners_y[i]]
            z_side = [-t/2, -t/2, t/2, t/2]
            verts = [list(zip(x_side, y_side, z_side))]
            poly = Poly3DCollection(verts, color="#1E293B", alpha=0.9, edgecolor="#38BDF8")
            self.ax_3d.add_collection3d(poly)

        # Labels, Colorbar, and Formatting
        self.ax_3d.set_xlabel("Wall Width X (m)")
        self.ax_3d.set_ylabel("Wall Height Y (m)")
        self.ax_3d.set_zlabel("Thickness Z (m)")
        self.ax_3d.set_title(f"3D FE von Mises Stress Field — Op: {wo:.2f}m x {ho:.2f}m (Max Stress: {res['max_stress_MPa']:.2f} MPa)", fontsize=10, pad=12)

        mappable = cm.ScalarMappable(norm=norm, cmap=cmap)
        mappable.set_array(Stress)
        cbar = self.fig_3d.colorbar(mappable, ax=self.ax_3d, shrink=0.6, pad=0.1)
        cbar.set_label("von Mises Stress (MPa)", fontsize=9)

        # View Angle Elevation
        self.ax_3d.view_init(elev=20, azim=-55)
        self.canvas_3d.draw()

    def plot_empty_graphs(self):
        for ax in self.axes_graphs.flat:
            ax.clear()
            ax.text(0.5, 0.5, "No Iteration Data", ha="center", va="center")
        self.canvas_graphs.draw()

    def plot_optimization_graphs(self, params):
        if not HAS_MATPLOTLIB or not self.results_data: return
        ratios = [d["opening_ratio"] for d in self.results_data]
        stresses = [d["max_stress_MPa"] for d in self.results_data]
        disps = [d["displacement_mm"] for d in self.results_data]
        stiffnesses = [d["stiffness_reduction"] * 100 for d in self.results_data]
        widths = [d["opening_width"] for d in self.results_data]

        for ax in self.axes_graphs.flat: ax.clear()

        # Plot 1: Stress vs Ratio
        self.axes_graphs[0, 0].plot(ratios, stresses, "o-b")
        self.axes_graphs[0, 0].axhline(y=params["allow_stress"], color="r", linestyle="--", label="Limit")
        self.axes_graphs[0, 0].set_title("Opening Ratio vs Max Stress (MPa)")
        self.axes_graphs[0, 0].grid(True)

        # Plot 2: Displacement vs Ratio
        self.axes_graphs[0, 1].plot(ratios, disps, "s-g")
        self.axes_graphs[0, 1].axhline(y=params["allow_disp"], color="r", linestyle="--", label="Limit")
        self.axes_graphs[0, 1].set_title("Opening Ratio vs Displacement (mm)")
        self.axes_graphs[0, 1].grid(True)

        # Plot 3: Status vs Size
        colors = ["green" if d["status"] == "PASS" else "red" for d in self.results_data]
        self.axes_graphs[1, 0].scatter(widths, ratios, c=colors, s=80)
        self.axes_graphs[1, 0].set_title("Opening Size vs Performance (Pass/Fail)")
        self.axes_graphs[1, 0].grid(True)

        # Plot 4: Stiffness vs Ratio
        self.axes_graphs[1, 1].plot(ratios, stiffnesses, "^-m")
        self.axes_graphs[1, 1].set_title("Opening Ratio vs Stiffness Ratio (%)")
        self.axes_graphs[1, 1].grid(True)

        if self.optimum_result:
            opt_r = self.optimum_result["opening_ratio"]
            self.axes_graphs[0, 0].plot(opt_r, self.optimum_result["max_stress_MPa"], "r*", markersize=12)
            self.axes_graphs[0, 1].plot(opt_r, self.optimum_result["displacement_mm"], "r*", markersize=12)

        self.fig_graphs.tight_layout(pad=2.0)
        self.canvas_graphs.draw()

    def reset_defaults(self):
        for k, e in self.entries.items():
            e.delete(0, tk.END)
            e.insert(0, str(DEFAULT_PARAMS[k]))
        self.var_mode.set("WIDTH_ONLY")
        self.update_wall_visualization()

    def export_results(self):
        if not self.results_data:
            messagebox.showwarning("Export Warning", "No iteration results available to export.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path: return

        with open(path, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.results_data[0].keys()))
            writer.writeheader()
            writer.writerows(self.results_data)

        messagebox.showinfo("Export Complete", f"Results exported successfully to {path}")


if __name__ == "__main__":
    app = AACWallOptimizerApp()
    app.mainloop()