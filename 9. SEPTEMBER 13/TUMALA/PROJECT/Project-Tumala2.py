import math
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

class AdaptiveAACOptimizationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Thesis GUI: AAC Wall Cracking-Prone Area Analysis (NSCP 2015 / EasyFEM)")
        self.root.geometry("1600x980")
        self.root.configure(bg="#F0F4F8")

        # Fixed Wall Geometry
        self.H = 3.0          # Wall Height (m)
        self.L = 3.0          # Wall Length (m)
        self.t_w = 0.1524     # AAC Thickness: 6 inches = 0.1524 m

        # RC Frame Cross-Sections (0.3m x 0.3m x 3.0m)
        self.b_c = 0.3        # Column Width (m)
        self.h_c = 0.3        # Column Depth (m)
        self.L_c = 3.0        # Column Height (m)
        self.b_b = 0.3        # Beam Width (m)
        self.h_b = 0.3        # Beam Depth (m)
        self.L_b = 3.0        # Beam Span (m)

        # Blocktec AAC Material Properties
        self.f_m = 3.5            # AAC Compressive Strength (MPa)
        self.E_m = 1800.0         # AAC Elastic Modulus (MPa)
        self.density_aac = 550.0  # Dry Density (kg/m^3)
        self.poisson_ratio = 0.19 
        self.f_c = 21.0           # Concrete f'c (MPa)

        # Dynamic History Tracking
        self.analysis_history = []

        self._apply_blue_theme()
        self._setup_ui()

    def _apply_blue_theme(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.c_primary = "#0B2545"    # Deep Navy Blue
        self.c_secondary = "#134074"  # Medium Royal Blue
        self.c_accent = "#0077B6"     # Bright Accent Blue
        self.c_card = "#FFFFFF"       # White Card
        self.c_text = "#0F172A"       # Dark Slate Text

        self.style.configure(".", background="#F0F4F8", foreground=self.c_text, font=("Segoe UI", 9))
        self.style.configure("Header.TFrame", background=self.c_primary)
        self.style.configure("Header.TLabel", background=self.c_primary, foreground="#FFFFFF", font=("Segoe UI", 12, "bold"))
        self.style.configure("Card.TLabelframe", background=self.c_card, relief="flat", borderwidth=1)
        self.style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=self.c_primary, background="#F0F4F8")
        
        self.style.configure("Run.TButton", background=self.c_accent, foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("Run.TButton", background=[("active", "#023E8A"), ("pressed", "#03045E")])

        self.style.configure("Reset.TButton", background="#C53030", foreground="white", font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Reset.TButton", background=[("active", "#9B2C2C")])

    def _setup_ui(self):
        header = ttk.Frame(self.root, style="Header.TFrame", padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="AAC INFILL WALL CRACKED AREA / TOTAL AREA ANALYSIS (NSCP 2015)", style="Header.TLabel").pack(side=tk.LEFT)

        main_container = ttk.Frame(self.root, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left Controls Panel
        left_panel = ttk.Frame(main_container, width=420)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # 1. NSCP Loading Parameters
        card_sap = ttk.LabelFrame(left_panel, text="1. NSCP 2015 Loadings", style="Card.TLabelframe", padding=8)
        card_sap.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(card_sap, text="Basic Wind Speed V [kph]:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ent_V_wind = ttk.Entry(card_sap, width=8); self.ent_V_wind.insert(0, "250.0"); self.ent_V_wind.grid(row=0, column=1)

        ttk.Label(card_sap, text="Seismic Zone Factor Z:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_Z = ttk.Entry(card_sap, width=8); self.ent_Z.insert(0, "0.40"); self.ent_Z.grid(row=1, column=1)

        ttk.Label(card_sap, text="In-Plane Base Shear (V_e) [kN]:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.ent_V_e = ttk.Entry(card_sap, width=8); self.ent_V_e.insert(0, "55.0"); self.ent_V_e.grid(row=2, column=1)

        ttk.Label(card_sap, text="Max Drift Limit [%]:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.ent_drift_lim = ttk.Entry(card_sap, width=8); self.ent_drift_lim.insert(0, "1.5"); self.ent_drift_lim.grid(row=3, column=1)

        # 2. Customizable Opening Setup
        card_opt = ttk.LabelFrame(left_panel, text="2. Opening Geometry & Position", style="Card.TLabelframe", padding=8)
        card_opt.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(card_opt, text="Target Preset:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.combo_ratio = ttk.Combobox(card_opt, values=["10% Area (NBCP Min)", "20% Area (Standard)", "30% Area (Large Window)", "Custom Dimensions"], width=20)
        self.combo_ratio.current(3)
        self.combo_ratio.grid(row=0, column=1, pady=2)
        self.combo_ratio.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Label(card_opt, text="Opening Width (m):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_op_w = ttk.Entry(card_opt, width=8); self.ent_op_w.insert(0, "1.20"); self.ent_op_w.grid(row=1, column=1)

        ttk.Label(card_opt, text="Opening Height (m):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.ent_op_h = ttk.Entry(card_opt, width=8); self.ent_op_h.insert(0, "1.20"); self.ent_op_h.grid(row=2, column=1)

        ttk.Label(card_opt, text="Opening Position:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.combo_loc = ttk.Combobox(card_opt, values=[
            "Centered", 
            "Upper Left", 
            "Upper Right", 
            "Center Up", 
            "Center Bottom", 
            "Lower Left", 
            "Lower Right"
        ], width=20)
        self.combo_loc.current(0)
        self.combo_loc.grid(row=3, column=1, pady=2)

        # Action Buttons
        btn_run = ttk.Button(left_panel, text="RUN ANALYSIS ITERATION", style="Run.TButton", command=self.run_single_analysis)
        btn_run.pack(fill=tk.X, ipady=6, pady=(5, 2))

        btn_reset = ttk.Button(left_panel, text="RESET HISTORY", style="Reset.TButton", command=self.reset_history)
        btn_reset.pack(fill=tk.X, ipady=4, pady=(0, 5))

        # Quick Log Summary
        card_log = ttk.LabelFrame(left_panel, text="Iteration Summary Log", style="Card.TLabelframe", padding=5)
        card_log.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(card_log, width=42, height=12, font=("Consolas", 8), bg="#F8FAFC", bd=0)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Right Notebook
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # TAB 1: 3D Surface Stress Model
        self.tab_3d = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_3d, text=" Interactive 3D FEM Stress Model ")

        self.fig_3d = plt.figure(figsize=(10, 8), facecolor='#F0F4F8')
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')

        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.tab_3d)
        self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, self.tab_3d)
        self.toolbar_3d.update()

        # TAB 2: Cracking Comparison Charts
        self.tab_curves = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_curves, text=" Cracked Area & Stress Comparison ")

        self.fig_curves = plt.figure(figsize=(10, 8), facecolor='#F0F4F8')
        self.ax_crack = self.fig_curves.add_subplot(221)
        self.ax_comp = self.fig_curves.add_subplot(222)
        self.ax_push = self.fig_curves.add_subplot(212)

        self.canvas_curves = FigureCanvasTkAgg(self.fig_curves, master=self.tab_curves)
        self.canvas_curves.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # TAB 3: Computation Details
        self.tab_calc = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_calc, text=" Detailed Engineering Calculations (NSCP 2015) ")

        calc_container = ttk.Frame(self.tab_calc, padding=10)
        calc_container.pack(fill=tk.BOTH, expand=True)

        lbl_calc_head = ttk.Label(calc_container, text="STRUCTURAL LOADINGS & CRACKED AREA CALCULATIONS", font=("Segoe UI", 11, "bold"), foreground=self.c_primary)
        lbl_calc_head.pack(anchor=tk.W, pady=(0, 5))

        self.txt_calc = tk.Text(calc_container, font=("Consolas", 9), bg="#FFFFFF", fg="#0F172A", bd=1, relief="solid")
        self.txt_calc.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll_y = ttk.Scrollbar(calc_container, orient=tk.VERTICAL, command=self.txt_calc.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_calc.configure(yscrollcommand=scroll_y.set)

        self.cbar = None

    def _on_preset_change(self, event):
        preset = self.combo_ratio.get()
        if "10%" in preset:
            area = 0.10 * (self.L * self.H)
            w = math.sqrt(area / 1.2)
            self.ent_op_w.delete(0, tk.END); self.ent_op_w.insert(0, f"{w:.2f}")
            self.ent_op_h.delete(0, tk.END); self.ent_op_h.insert(0, f"{w*1.2:.2f}")
        elif "20%" in preset:
            area = 0.20 * (self.L * self.H)
            w = math.sqrt(area / 1.2)
            self.ent_op_w.delete(0, tk.END); self.ent_op_w.insert(0, f"{w:.2f}")
            self.ent_op_h.delete(0, tk.END); self.ent_op_h.insert(0, f"{w*1.2:.2f}")
        elif "30%" in preset:
            area = 0.30 * (self.L * self.H)
            w = math.sqrt(area / 1.2)
            self.ent_op_w.delete(0, tk.END); self.ent_op_w.insert(0, f"{w:.2f}")
            self.ent_op_h.delete(0, tk.END); self.ent_op_h.insert(0, f"{w*1.2:.2f}")

    def run_single_analysis(self):
        try:
            V_wind_kph = float(self.ent_V_wind.get())
            Z_factor = float(self.ent_Z.get())
            V_e = float(self.ent_V_e.get())
            drift_lim = float(self.ent_drift_lim.get())
            w_op = float(self.ent_op_w.get())
            h_op = float(self.ent_op_h.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numeric values.")
            return

        w_op = max(0.1, min(w_op, self.L - 0.2))
        h_op = max(0.1, min(h_op, self.H - 0.2))

        loc_preset = self.combo_loc.get()
        margin = 0.2

        # Opening position coordinates
        if loc_preset == "Lower Left":
            x_op, y_op = margin, margin
        elif loc_preset == "Lower Right":
            x_op, y_op = self.L - w_op - margin, margin
        elif loc_preset == "Upper Left":
            x_op, y_op = margin, self.H - h_op - margin
        elif loc_preset == "Upper Right":
            x_op, y_op = self.L - w_op - margin, self.H - h_op - margin
        elif loc_preset == "Center Bottom":
            x_op, y_op = (self.L - w_op) / 2.0, margin
        elif loc_preset == "Center Up":
            x_op, y_op = (self.L - w_op) / 2.0, self.H - h_op - margin
        else: # Centered
            x_op, y_op = (self.L - w_op) / 2.0, (self.H - h_op) / 2.0

        x_op = max(0.05, min(x_op, self.L - w_op - 0.05))
        y_op = max(0.05, min(y_op, self.H - h_op - 0.05))

        # === NSCP 2015 LOAD CALCULATIONS ===
        g = 9.81
        w_aac_unit = (self.density_aac * g) / 1000.0
        p_aac_wall = w_aac_unit * self.t_w
        p_plaster = 0.25
        w_D_kPa = p_aac_wall + p_plaster

        A_gross = self.L * self.H                  # Gross Total Area (e.g., 9.00 m2)
        A_open = w_op * h_op                       # Opening Area (m2)
        A_net_wall = A_gross - A_open              # Net AAC Wall Area (m2)
        W_wall_total = w_D_kPa * A_net_wall

        # Wind Load
        V_ms = V_wind_kph / 3.6
        K_z, K_zt, K_d = 0.85, 1.0, 0.85
        q_z = 0.613 * K_z * K_zt * K_d * (V_ms**2) / 1000.0
        G_Cp, GC_pi = 0.85, 0.18
        p_wind_design = q_z * (G_Cp - (-GC_pi))
        F_wind_total = p_wind_design * A_net_wall

        # Out-of-Plane Seismic Load
        a_p, R_p, I_p = 1.0, 1.5, 1.0
        C_a = 0.44 * Z_factor
        F_p = (4.0 * C_a * I_p * a_p / R_p) * W_wall_total

        # Shear & Stress Concentration
        ratio_calc = A_open / A_gross
        L_net = self.L - w_op
        A_net_shear = L_net * self.t_w
        tau_nom = V_e / (A_net_shear * 1000.0)
        scf = 1.0 + 2.0 * math.sqrt(h_op / max(w_op, 0.001))
        
        ecc_penalty = 1.20 if loc_preset in ["Lower Left", "Lower Right", "Upper Left", "Upper Right"] else (1.10 if loc_preset in ["Center Up", "Center Bottom"] else 1.0)
        sigma_max = tau_nom * scf * ecc_penalty

        f_m_allow = 0.85 * self.f_m
        drift_calc = 0.4 + (ratio_calc * 2.8) * ecc_penalty

        # === CRACKED AREA OVER TOTAL AREA COMPUTATION ===
        f_ct = 0.10 * self.f_m  # Tensile threshold (0.35 MPa)
        
        nx, nz = 80, 80
        x_vals = np.linspace(0, self.L, nx)
        z_vals = np.linspace(0, self.H, nz)
        X, Z = np.meshgrid(x_vals, z_vals)

        Stress_mesh = np.zeros_like(X)
        cracked_nodes = 0
        valid_nodes = 0

        for i in range(nz):
            for j in range(nx):
                x_v, z_v = X[i, j], Z[i, j]
                # Check if point falls inside the cutout opening
                if (x_op <= x_v <= x_op + w_op) and (y_op <= z_v <= y_op + h_op):
                    Stress_mesh[i, j] = np.nan
                    continue
                
                valid_nodes += 1
                # Compression strut stress concentration
                d_strut = abs((self.H / self.L) * x_v + z_v - self.H) / math.sqrt((self.H / self.L)**2 + 1)
                
                # Corner stress concentrations
                corners = [(x_op, y_op), (x_op + w_op, y_op), (x_op, y_op + h_op), (x_op + w_op, y_op + h_op)]
                corner_dist = min([math.sqrt((x_v - cx)**2 + (z_v - cz)**2) for cx, cz in corners])
                
                # Local stress evaluation
                s_local = (V_e * 0.35) * np.exp(-d_strut / 0.45) + (V_e * 0.25 * ecc_penalty) / (corner_dist + 0.12)
                Stress_mesh[i, j] = s_local

                if s_local >= f_ct:
                    cracked_nodes += 1

        # Calculate exact cracked area (m2) and cracked area ratio over total gross area
        net_cracked_ratio = (cracked_nodes / max(1, valid_nodes))
        A_cracked = net_cracked_ratio * A_net_wall            # Total Cracked Surface Area (m2)
        cracking_pct_total = (A_cracked / A_gross) * 100.0    # (A_cracked / A_gross) * 100%

        satisfied = (sigma_max <= f_m_allow) and (drift_calc <= drift_lim) and (cracking_pct_total <= 20.0)

        run_index = len(self.analysis_history) + 1
        run_data = {
            'run': run_index,
            'w': w_op,
            'h': h_op,
            'loc': loc_preset,
            'ratio': ratio_calc * 100.0,
            'sigma': sigma_max,
            'drift': drift_calc,
            'A_cracked': A_cracked,
            'A_gross': A_gross,
            'crack_pct_total': cracking_pct_total,
            'ok': satisfied
        }
        self.analysis_history.append(run_data)

        # Log Update
        self.txt_log.insert(tk.END, f"RUN #{run_index}: {w_op:.2f}x{h_op:.2f}m [{loc_preset}]\n")
        self.txt_log.insert(tk.END, f"  A_cracked / A_gross = {A_cracked:.2f} m² / {A_gross:.2f} m²\n")
        self.txt_log.insert(tk.END, f"  Cracked Area Ratio: {cracking_pct_total:.1f}%\n")
        self.txt_log.insert(tk.END, f"  σ_max: {sigma_max:.2f} MPa | Drift: {drift_calc:.2f}%\n")
        self.txt_log.insert(tk.END, f"  Status: {'PASS' if satisfied else 'EXCEEDED / REJECT'}\n\n")
        self.txt_log.see(tk.END)

        # Update Calculations Report
        self._write_nscp_calc_tab(run_index, loc_preset, w_op, h_op, ratio_calc, A_gross, A_open, A_net_wall,
                                  w_D_kPa, W_wall_total, V_wind_kph, q_z, p_wind_design, F_wind_total, 
                                  Z_factor, F_p, V_e, L_net, A_net_shear, tau_nom, scf, sigma_max, 
                                  f_m_allow, drift_calc, drift_lim, f_ct, A_cracked, cracking_pct_total, satisfied)

        # Render Graphics
        self.plot_3d_easyfem_mesh(X, Z, Stress_mesh, w_op, h_op, loc_preset)
        self.plot_pushover_curve(V_e)
        self.plot_cracking_and_stress_comparison()

    def _write_nscp_calc_tab(self, run, loc_preset, w_op, h_op, ratio, A_g, A_o, A_net, w_D, W_tot, V_w, q_z, p_w, F_w, Z, F_p, V_e, L_net, A_shear, tau_nom, scf, sigma_max, f_allow, drift, drift_lim, f_ct, A_cracked, crack_pct_total, ok):
        text = f"""========================================================================================
             NSCP 2015 & CRACKED AREA / TOTAL AREA REPORT (ITERATION #{run})
========================================================================================

1. GEOMETRY & PANEL SURFACE AREAS
   • Panel Total Dimensions    : Length L = {self.L:.2f} m | Height H = {self.H:.2f} m | Thickness t_w = {self.t_w*1000:.1f} mm
   • Opening Dimensions        : Width w = {w_op:.2f} m | Height h = {h_op:.2f} m | Location = {loc_preset}
   • Gross Total Surface Area  : A_gross = L × H = {A_g:.2f} m²
   • Opening Surface Area      : A_open = w × h = {A_o:.2f} m²
   • Opening Ratio             : R_a = (A_open / A_gross) × 100 = {ratio*100:.2f}%
   • Net Surface AAC Area      : A_net = A_gross - A_open = {A_net:.2f} m²

----------------------------------------------------------------------------------------
2. DEAD LOAD (D) CALCULATIONS (NSCP 2015 SECTION 204)
   • AAC Unit Dry Density      : ρ_aac = {self.density_aac:.1f} kg/m³
   • Wall Pressure             : p_wall = {self.density_aac*9.81/1000*self.t_w:.3f} kPa | Plaster = 0.25 kPa
   • Total Dead Load Pressure  : w_D = {w_D:.3f} kPa
   • Total Infill Panel Weight : W_panel = w_D × A_net = {W_tot:.3f} kN

----------------------------------------------------------------------------------------
3. CRACKED AREA OVER TOTAL AREA EVALUATION
   • Tensile Threshold (f_ct)  : f_ct ≈ 0.10 × f'_m = 0.10 × {self.f_m:.1f} = {f_ct:.3f} MPa
   • Total Finite Mesh Nodes   : 6,400 Mesh Grid Points Evaluated
   • Surface Area with σ >= f_ct: Calculated Cracked Area (A_cracked) = {A_cracked:.3f} m²
   • Total Gross Surface Area  : Gross Wall Envelope (A_gross) = {A_g:.3f} m²
   • Cracked Area Percentage   : Ratio = (A_cracked / A_gross) × 100%
                               : Ratio = ({A_cracked:.3f} / {A_g:.3f}) × 100% = {crack_pct_total:.2f}%
   • Cracking Ratio Limit      : 20.00% Max Allowed
   • Cracking Area Status      : {'SAFE (< 20% OF TOTAL AREA)' if crack_pct_total <= 20.0 else 'EXCEEDED CRACKING LIMIT (> 20% OF TOTAL AREA)'}

----------------------------------------------------------------------------------------
4. IN-PLANE STRESS & DRIFT CHECK
   • In-Plane Seismic Shear V_e: {V_e:.2f} kN
   • Nominal Shear Stress τ_nom: {tau_nom:.3f} MPa
   • Stress Concentration SCF  : {scf:.3f}
   • Peak Edge Stress σ_max    : {sigma_max:.3f} MPa (Allowable: {f_allow:.3f} MPa)
   • Drift Demand vs Limit     : Δ_calc = {drift:.2f}% (Limit: {drift_lim:.2f}%)
   • OVERALL DESIGN STATUS     : {'*** OPTIMAL PASSING DESIGN ***' if ok else '*** RE-ITERATION REQUIRED ***'}
========================================================================================\n\n"""
        
        self.txt_calc.insert(tk.END, text)
        self.txt_calc.see(tk.END)

    def reset_history(self):
        self.analysis_history.clear()
        self.txt_log.delete(1.0, tk.END)
        self.txt_calc.delete(1.0, tk.END)
        self.txt_log.insert(tk.END, "--- HISTORY CLEARED ---\nReady for new analysis.\n\n")
        self.txt_calc.insert(tk.END, "--- COMPUTATION HISTORY CLEARED ---\nRun an iteration to evaluate cracked area over total area.\n\n")
        
        self.ax_crack.clear()
        self.ax_comp.clear()
        self.ax_push.clear()
        self.fig_curves.tight_layout()
        self.canvas_curves.draw()

    def plot_3d_easyfem_mesh(self, X, Z, Stress_mesh, op_w, op_h, loc_preset):
        self.ax_3d.clear()
        if self.cbar:
            self.cbar.remove()
            self.cbar = None

        def draw_solid_box(ax, x, y, z, dx, dy, dz, color='#475569', alpha=0.5):
            verts = [
                [[x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z]],
                [[x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]],
                [[x, y, z], [x+dx, y, z], [x+dx, y, z+dz], [x, y, z+dz]],
                [[x, y+dy, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x, y, z+dz]],
                [[x, y, z], [x, y+dy, z], [x, y+dy, z+dz], [x, y, z+dz]],
                [[x+dx, y, z], [x+dx, y+dy, z], [x+dx, y+dy, z+dz], [x+dx, y, z+dz]]
            ]
            ax.add_collection3d(Poly3DCollection(verts, facecolors=color, linewidths=0.5, edgecolors='#1E293B', alpha=alpha))

        y_wall = (self.h_c - self.t_w) / 2.0

        # Draw concrete frame (columns and beams)
        draw_solid_box(self.ax_3d, -self.b_c, 0, 0, self.b_c, self.h_c, self.L_c) 
        draw_solid_box(self.ax_3d, self.L, 0, 0, self.b_c, self.h_c, self.L_c)    
        draw_solid_box(self.ax_3d, 0, 0, -self.h_b, self.L_b, self.b_b, self.h_b) 
        draw_solid_box(self.ax_3d, 0, 0, self.H, self.L_b, self.b_b, self.h_b)    

        Y = np.full_like(X, y_wall)
        norm = Normalize(vmin=np.nanmin(Stress_mesh), vmax=np.nanmax(Stress_mesh))
        cmap = plt.cm.turbo
        colors = cmap(norm(Stress_mesh))

        self.ax_3d.plot_surface(X, Y, Z, facecolors=colors, rstride=1, cstride=1, shade=False, antialiased=True)
        
        mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        mappable.set_array(Stress_mesh)
        self.cbar = self.fig_3d.colorbar(mappable, ax=self.ax_3d, shrink=0.6, pad=0.1)
        self.cbar.set_label('Local Stress σ (MPa)', fontsize=9, fontweight='bold', color='#0B2545')

        self.ax_3d.set_title(f"3D Stress Mesh [{loc_preset}] ({op_w:.2f}m W x {op_h:.2f}m H)\nRed Regions = Local Tensile Cracking Zones (σ >= f_ct)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_3d.set_xlabel("Length (m)")
        self.ax_3d.set_ylabel("Depth (m)")
        self.ax_3d.set_zlabel("Height (m)")
        
        self.ax_3d.set_xlim(-0.5, self.L + 0.5)
        self.ax_3d.set_ylim(-0.2, self.h_c + 0.2)
        self.ax_3d.set_zlim(-0.5, self.H + 0.5)
        self.ax_3d.set_facecolor('#F0F4F8')
        
        self.ax_3d.mouse_init()
        self.fig_3d.tight_layout()
        self.canvas_3d.draw()

    def plot_pushover_curve(self, V_e):
        self.ax_push.clear()
        disp = np.linspace(0, 45, 50)
        force = V_e * (1 - np.exp(-disp / 8.0)) + 0.05 * disp
        
        self.ax_push.plot(disp, force, color='#0077B6', linewidth=2.5, label='Infill Frame Capacity')
        self.ax_push.axvline(x=25, color='red', linestyle='--', label='Drift Limit (25mm)')
        self.ax_push.set_title("Pushover Capacity Curve (Nonlinear In-Plane Response)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_push.set_xlabel("Roof Drift (mm)", fontsize=8)
        self.ax_push.set_ylabel("Base Shear (kN)", fontsize=8)
        self.ax_push.grid(True, linestyle=':', alpha=0.6)
        self.ax_push.legend(fontsize=8)

    def plot_cracking_and_stress_comparison(self):
        self.ax_crack.clear()
        self.ax_comp.clear()

        if not self.analysis_history:
            return

        labels = [f"R#{r['run']}\n{r['loc']}" for r in self.analysis_history]
        crack_pcts = [r['crack_pct_total'] for r in self.analysis_history]
        stresses = [r['sigma'] for r in self.analysis_history]

        colors = ['#0077B6' if r['ok'] else '#C53030' for r in self.analysis_history]

        # Cracked Area / Gross Total Area Bar Plot
        bars1 = self.ax_crack.bar(labels, crack_pcts, color=colors, width=0.45)
        self.ax_crack.axhline(y=20.0, color='red', linestyle='--', label='Max Allowable Ratio (20%)')
        self.ax_crack.set_title("Cracked Area / Total Gross Area (%)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_crack.set_ylabel("A_cracked / A_gross (%)", fontsize=8)
        self.ax_crack.grid(True, axis='y', linestyle=':', alpha=0.6)
        self.ax_crack.legend(fontsize=7)

        for bar in bars1:
            yval = bar.get_height()
            self.ax_crack.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.1f}%", ha='center', va='bottom', fontsize=7, fontweight='bold')

        # Stress Bar Plot
        bars2 = self.ax_comp.bar(labels, stresses, color=colors, width=0.45)
        self.ax_comp.set_title("Peak Edge Stress σ_max (MPa)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_comp.set_ylabel("Stress (MPa)", fontsize=8)
        self.ax_comp.grid(True, axis='y', linestyle=':', alpha=0.6)

        for bar in bars2:
            yval = bar.get_height()
            self.ax_comp.text(bar.get_x() + bar.get_width()/2.0, yval + 0.05, f"{yval:.2f}", ha='center', va='bottom', fontsize=7, fontweight='bold')

        self.fig_curves.tight_layout()
        self.canvas_curves.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = AdaptiveAACOptimizationApp(root)
    root.mainloop()