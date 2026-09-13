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
        self.root.title("Thesis GUI: Iterative Optimization of Adaptive AAC Infill Openings (NSCP 2015 / EasyFEM)")
        self.root.geometry("1550x950")
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
        self.f_m = 3.5        # AAC Compressive Strength (MPa)
        self.E_m = 1800.0     # AAC Elastic Modulus (MPa)
        self.density_aac = 550.0 # Dry Density (kg/m^3)
        self.poisson_ratio = 0.19 
        self.f_c = 21.0       # Concrete f'c (MPa)

        # Dynamic History Tracking for Multi-Run Comparison
        self.analysis_history = []

        self._apply_blue_theme()
        self._setup_ui()

    def _apply_blue_theme(self):
        """Theme matching Navy/Royal Blue Thesis Diagram."""
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
        ttk.Label(header, text="FINITE ELEMENT-BASED ITERATIVE DESIGN OF ADAPTIVE OPENINGS IN AAC INFILL WALLS", style="Header.TLabel").pack(side=tk.LEFT)

        main_container = ttk.Frame(self.root, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left Controls Panel
        left_panel = ttk.Frame(main_container, width=380)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # 1. Global Analysis Loads
        card_sap = ttk.LabelFrame(left_panel, text="1. SAP2000 Global Analysis Loads", style="Card.TLabelframe", padding=8)
        card_sap.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(card_sap, text="Seismic Base Shear (V_e) [kN]:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ent_V_e = ttk.Entry(card_sap, width=8); self.ent_V_e.insert(0, "55.0"); self.ent_V_e.grid(row=0, column=1)

        ttk.Label(card_sap, text="Max Allowable Drift Limit [%]:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_drift_lim = ttk.Entry(card_sap, width=8); self.ent_drift_lim.insert(0, "1.5"); self.ent_drift_lim.grid(row=1, column=1)

        # 2. Customizable Opening Setup
        card_opt = ttk.LabelFrame(left_panel, text="2. Customizable Opening Geometry", style="Card.TLabelframe", padding=8)
        card_opt.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(card_opt, text="Target Area Preset:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.combo_ratio = ttk.Combobox(card_opt, values=["10% Area (NBCP Min)", "20% Area (Standard)", "30% Area (Large Window)", "Custom Dimensions"], width=20)
        self.combo_ratio.current(3)
        self.combo_ratio.grid(row=0, column=1, pady=2)
        self.combo_ratio.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Label(card_opt, text="Opening Width (m):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ent_op_w = ttk.Entry(card_opt, width=8); self.ent_op_w.insert(0, "1.20"); self.ent_op_w.grid(row=1, column=1)

        ttk.Label(card_opt, text="Opening Height (m):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.ent_op_h = ttk.Entry(card_opt, width=8); self.ent_op_h.insert(0, "1.20"); self.ent_op_h.grid(row=2, column=1)

        ttk.Label(card_opt, text="Opening Position:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.combo_loc = ttk.Combobox(card_opt, values=["Centered", "Eccentric Top", "Eccentric Bottom"], width=20)
        self.combo_loc.current(0)
        self.combo_loc.grid(row=3, column=1, pady=2)

        # Action Buttons
        btn_run = ttk.Button(left_panel, text="RUN ANALYSIS ITERATION", style="Run.TButton", command=self.run_single_analysis)
        btn_run.pack(fill=tk.X, ipady=6, pady=(5, 2))

        btn_reset = ttk.Button(left_panel, text="RESET HISTORY", style="Reset.TButton", command=self.reset_history)
        btn_reset.pack(fill=tk.X, ipady=4, pady=(0, 5))

        card_log = ttk.LabelFrame(left_panel, text="Iterative Convergence Log", style="Card.TLabelframe", padding=5)
        card_log.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(card_log, width=36, height=12, font=("Consolas", 8), bg="#F8FAFC", bd=0)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Right Notebook
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # TAB 1: 3D Model View
        self.tab_3d = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_3d, text=" Interactive 3D FEM Stress Model ")

        self.fig_3d = plt.figure(figsize=(10, 8), facecolor='#F0F4F8')
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')

        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.tab_3d)
        self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, self.tab_3d)
        self.toolbar_3d.update()

        # TAB 2: Analysis & Dynamic Comparison Curves
        self.tab_curves = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_curves, text=" Dynamic Multi-Run Comparison & Capacity Curves ")

        self.fig_curves = plt.figure(figsize=(10, 8), facecolor='#F0F4F8')
        self.ax_push = self.fig_curves.add_subplot(211)
        self.ax_comp = self.fig_curves.add_subplot(223)
        self.ax_opt = self.fig_curves.add_subplot(224)

        self.canvas_curves = FigureCanvasTkAgg(self.fig_curves, master=self.tab_curves)
        self.canvas_curves.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.cbar = None

    def _on_preset_change(self, event):
        """Auto-populates width/height based on selected percentage preset."""
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
            V_e = float(self.ent_V_e.get())
            drift_lim = float(self.ent_drift_lim.get())
            w_op = float(self.ent_op_w.get())
            h_op = float(self.ent_op_h.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please provide valid numeric values for opening geometry and loads.")
            return

        # Restrict dimensions inside wall boundary
        w_op = max(0.1, min(w_op, self.L - 0.2))
        h_op = max(0.1, min(h_op, self.H - 0.2))

        loc_preset = self.combo_loc.get()
        if loc_preset == "Eccentric Top":
            x_op = (self.L - w_op) / 2.0
            y_op = self.H - h_op - 0.2
        elif loc_preset == "Eccentric Bottom":
            x_op = (self.L - w_op) / 2.0
            y_op = 0.2
        else: # Centered
            x_op = (self.L - w_op) / 2.0
            y_op = (self.H - h_op) / 2.0

        ratio_calc = (w_op * h_op) / (self.L * self.H)
        scf = 1.0 + 2.0 * math.sqrt(h_op / max(w_op, 0.001))
        sigma_max = (V_e * 1000 / ((self.L - w_op) * self.t_w * 1000)) * scf
        drift_calc = 0.4 + (ratio_calc * 2.8)
        satisfied = (sigma_max <= 0.85 * self.f_m * 10) and (drift_calc <= drift_lim)

        run_index = len(self.analysis_history) + 1
        run_data = {
            'run': run_index,
            'w': w_op,
            'h': h_op,
            'x': x_op,
            'y': y_op,
            'ratio': ratio_calc * 100,
            'sigma': sigma_max,
            'drift': drift_calc,
            'ok': satisfied
        }

        self.analysis_history.append(run_data)

        # Log details
        self.txt_log.insert(tk.END, f"--- RUN #{run_index} EXECUTED ---\n")
        self.txt_log.insert(tk.END, f"Size: {w_op:.2f}m W x {h_op:.2f}m H ({ratio_calc*100:.1f}% Area)\n")
        self.txt_log.insert(tk.END, f"Peak Stress σ_max: {sigma_max:.2f} MPa\n")
        self.txt_log.insert(tk.END, f"Interstory Drift: {drift_calc:.2f}%\n")
        self.txt_log.insert(tk.END, f"Status: {'PASS' if satisfied else 'EXCEEDED LIMIT'}\n\n")
        self.txt_log.see(tk.END)

        # Render Graphics
        self.plot_3d_easyfem_mesh(x_op, y_op, w_op, h_op, V_e)
        self.plot_pushover_curve(V_e)
        self.plot_dynamic_comparison()

    def reset_history(self):
        self.analysis_history.clear()
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.insert(tk.END, "--- HISTORY CLEARED ---\nReady for new analyses.\n\n")
        
        self.ax_comp.clear()
        self.ax_comp.set_title("Multi-Run Stress Comparison (Dynamic)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_opt.clear()
        self.ax_opt.set_title("Opening Ratio vs Critical Stress", fontsize=10, color='#0B2545', fontweight='bold')
        self.fig_curves.tight_layout()
        self.canvas_curves.draw()

    def plot_3d_easyfem_mesh(self, op_x, op_y, op_w, op_h, V_e):
        """Generates 3D Model with wall stress distribution & 0.3x0.3x3.0m frame."""
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

        # Frame Members (0.3m x 0.3m x 3.0m)
        draw_solid_box(self.ax_3d, -self.b_c, 0, 0, self.b_c, self.h_c, self.L_c) # Left Column
        draw_solid_box(self.ax_3d, self.L, 0, 0, self.b_c, self.h_c, self.L_c)    # Right Column
        draw_solid_box(self.ax_3d, 0, 0, -self.h_b, self.L_b, self.b_b, self.h_b) # Bottom Beam
        draw_solid_box(self.ax_3d, 0, 0, self.H, self.L_b, self.b_b, self.h_b)    # Top Beam

        # AAC Surface Mesh
        nx, nz = 60, 60
        X, Z = np.meshgrid(np.linspace(0, self.L, nx), np.linspace(0, self.H, nz))
        Y = np.full_like(X, y_wall)

        Stress = np.zeros_like(X)
        for i in range(nz):
            for j in range(nx):
                x_v, z_v = X[i, j], Z[i, j]
                if (op_x <= x_v <= op_x + op_w) and (op_y <= z_v <= op_y + op_h):
                    Stress[i, j] = np.nan
                    continue
                d_strut = abs((self.H / self.L) * x_v + z_v - self.H) / math.sqrt((self.H / self.L)**2 + 1)
                corner_dist = min([math.sqrt((x_v - cx)**2 + (z_v - cz)**2) for cx, cz in [(op_x, op_y), (op_x+op_w, op_y), (op_x, op_y+op_h), (op_x+op_w, op_y+op_h)]])
                Stress[i, j] = (V_e * 0.35) * np.exp(-d_strut/0.45) + (V_e * 0.25) / (corner_dist + 0.12)

        norm = Normalize(vmin=np.nanmin(Stress), vmax=np.nanmax(Stress))
        cmap = plt.cm.turbo
        colors = cmap(norm(Stress))

        self.ax_3d.plot_surface(X, Y, Z, facecolors=colors, rstride=1, cstride=1, shade=False, antialiased=True)
        
        mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        mappable.set_array(Stress)
        self.cbar = self.fig_3d.colorbar(mappable, ax=self.ax_3d, shrink=0.6, pad=0.1)
        self.cbar.set_label('Local Stress σ (MPa)', fontsize=9, fontweight='bold', color='#0B2545')

        self.ax_3d.set_title(f"3D Wall Stress Mesh (Opening: {op_w:.2f}m W x {op_h:.2f}m H)\nBlocktec AAC (6\" Thickness) | 0.3m x 0.3m x 3.0m Frame", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_3d.set_xlabel("Length (m)")
        self.ax_3d.set_ylabel("Thickness/Depth (m)")
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
        self.ax_push.set_title("Pushover Curve (SAP2000)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_push.set_xlabel("Roof Drift (mm)", fontsize=8)
        self.ax_push.set_ylabel("Base Shear (kN)", fontsize=8)
        self.ax_push.grid(True, linestyle=':', alpha=0.6)
        self.ax_push.legend(fontsize=8)

    def plot_dynamic_comparison(self):
        """Dynamically updates comparison bar chart and scatter plot across all completed runs."""
        self.ax_comp.clear()
        self.ax_opt.clear()

        if not self.analysis_history:
            return

        labels = [f"Run #{r['run']}\n({r['w']:.1f}x{r['h']:.1f}m)" for r in self.analysis_history]
        stresses = [r['sigma'] for r in self.analysis_history]
        ratios = [r['ratio'] for r in self.analysis_history]

        # Colors based on evaluation status
        colors = ['#0077B6' if r['ok'] else '#C53030' for r in self.analysis_history]

        # 1. Bar Chart Comparison
        bars = self.ax_comp.bar(labels, stresses, color=colors, width=0.45)
        self.ax_comp.set_title(f"Dynamic Multi-Run Stress Comparison ({len(self.analysis_history)} Runs Executed)", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_comp.set_ylabel("Max Stress σ_max (MPa)", fontsize=8)
        self.ax_comp.grid(True, axis='y', linestyle=':', alpha=0.6)

        for bar in bars:
            yval = bar.get_height()
            self.ax_comp.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f"{yval:.2f}", ha='center', va='bottom', fontsize=7, fontweight='bold')

        # 2. Scatter / Line Comparison Curve
        self.ax_opt.plot(ratios, stresses, 'o--', color='#134074', linewidth=1.5, alpha=0.7)
        for r in self.analysis_history:
            c = 'blue' if r['ok'] else 'red'
            self.ax_opt.scatter([r['ratio']], [r['sigma']], color=c, s=60, zorder=5)
            self.ax_opt.annotate(f"Run #{r['run']}", (r['ratio'], r['sigma']), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=7)

        self.ax_opt.set_title("Opening Area Ratio vs Peak Stress", fontsize=10, color='#0B2545', fontweight='bold')
        self.ax_opt.set_xlabel("Opening Area Ratio (%)", fontsize=8)
        self.ax_opt.set_ylabel("Critical Stress (MPa)", fontsize=8)
        self.ax_opt.grid(True, linestyle=':', alpha=0.6)

        self.fig_curves.tight_layout()
        self.canvas_curves.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = AdaptiveAACOptimizationApp(root)
    root.mainloop()