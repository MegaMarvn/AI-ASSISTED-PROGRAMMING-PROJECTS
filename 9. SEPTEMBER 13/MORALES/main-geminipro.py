import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math

class BeamDesignApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NSCP 2015 RC Beam Reinforcement Calculator")
        self.root.geometry("1000x700")

        # UI Setup: Notebook for Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tabs
        self.tab_input = ttk.Frame(self.notebook)
        self.tab_2d = ttk.Frame(self.notebook)
        self.tab_3d = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_input, text="Inputs & Results")
        self.notebook.add(self.tab_2d, text="2D Visualization")
        self.notebook.add(self.tab_3d, text="3D Visualization")

        self.setup_input_tab()
        
        # Placeholders for plotting figures
        self.fig_2d, (self.ax_cross, self.ax_elev) = plt.subplots(1, 2, figsize=(10, 5))
        self.canvas_2d = FigureCanvasTkAgg(self.fig_2d, master=self.tab_2d)
        self.canvas_2d.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.fig_3d = plt.figure(figsize=(8, 6))
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')
        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.tab_3d)
        self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Initialize stored calculation variables
        self.calc_data = None

    def setup_input_tab(self):
        input_frame = ttk.LabelFrame(self.tab_input, text="Design Parameters")
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        result_frame = ttk.LabelFrame(self.tab_input, text="Calculated Results")
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.result_text = tk.Text(result_frame, width=50, height=35, state=tk.DISABLED, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Dictionary to store entry widgets
        self.entries = {}
        
        # Define Input Fields (Now including Beam Span)
        fields = [
            ("Material Properties", None),
            ("Concrete f'c (MPa)", "28"),
            ("Main Rebar fy (MPa)", "414"),
            ("Stirrup fyt (MPa)", "275"),
            ("Beam Geometry", None),
            ("Width b (mm)", "250"),
            ("Depth h (mm)", "400"),
            ("Beam Span L (mm)", "4000"),
            ("Clear Cover (mm)", "40"),
            ("Loading / Demands", None),
            ("Factored Moment Support (kN-m)", "150"),
            ("Factored Moment Midspan (kN-m)", "80"),
            ("Factored Shear Vu (kN)", "120"),
            ("Rebar Preferences", None),
            ("Main Bar Dia (mm)", "16"),
            ("Stirrup Dia (mm)", "10")
        ]

        row = 0
        for label, default in fields:
            if default is None:
                ttk.Label(input_frame, text=label, font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(10, 2), sticky="w")
                row += 1
            else:
                ttk.Label(input_frame, text=label).grid(row=row, column=0, padx=5, pady=2, sticky="e")
                entry = ttk.Entry(input_frame, width=15)
                entry.insert(0, default)
                entry.grid(row=row, column=1, padx=5, pady=2)
                self.entries[label] = entry
                row += 1

        ttk.Label(input_frame, text="Seismic Detailing").grid(row=row, column=0, padx=5, pady=2, sticky="e")
        self.seismic_combo = ttk.Combobox(input_frame, values=["Ordinary (OMRF)", "Intermediate (IMRF)", "Special (SMRF)"], state="readonly", width=13)
        self.seismic_combo.current(2)
        self.seismic_combo.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        calc_btn = ttk.Button(input_frame, text="Calculate & Render", command=self.calculate)
        calc_btn.grid(row=row, column=0, columnspan=2, pady=20)

    def calculate(self):
        try:
            # 1. Parse Inputs
            fc = float(self.entries["Concrete f'c (MPa)"].get())
            fy = float(self.entries["Main Rebar fy (MPa)"].get())
            fyt = float(self.entries["Stirrup fyt (MPa)"].get())
            b = float(self.entries["Width b (mm)"].get())
            h = float(self.entries["Depth h (mm)"].get())
            L = float(self.entries["Beam Span L (mm)"].get())
            cover = float(self.entries["Clear Cover (mm)"].get())
            Mu_sup = float(self.entries["Factored Moment Support (kN-m)"].get()) * 1e6 # N-mm
            Mu_mid = float(self.entries["Factored Moment Midspan (kN-m)"].get()) * 1e6 # N-mm
            Vu = float(self.entries["Factored Shear Vu (kN)"].get()) * 1000 # N
            db = float(self.entries["Main Bar Dia (mm)"].get())
            dt = float(self.entries["Stirrup Dia (mm)"].get())
            framing = self.seismic_combo.get()

            # Input checks
            if min(fc, fy, fyt, b, h, L, db, dt) <= 0:
                raise ValueError("Values must be greater than zero.")

            # Effective depth (d)
            d = h - cover - dt - (db / 2)

            # NSCP Reduction factors
            phi_f = 0.90 # Flexure
            phi_v = 0.75 # Shear

            # 2. Flexure Calculations (NSCP Section 409 / ACI 318)
            def calc_flexure(Mu):
                Rn = Mu / (phi_f * b * (d**2))
                rho = (0.85 * fc / fy) * (1 - math.sqrt(1 - (2 * Rn) / (0.85 * fc)))
                rho_min = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)
                rho = max(rho, rho_min)
                As_req = rho * b * d
                n_bars = math.ceil(As_req / (math.pi * (db**2) / 4))
                return max(n_bars, 2) # At least 2 bars required for cage corners

            n_top_sup = calc_flexure(Mu_sup)
            n_bot_mid = calc_flexure(Mu_mid)
            
            # Continuous bars required (simplified assumption)
            n_top_mid = max(2, math.ceil(n_top_sup / 3)) 
            n_bot_sup = max(2, math.ceil(n_bot_mid / 2))

            # 3. Shear and Seismic Detailing Calculations (NSCP Section 418 / 422)
            Vc = 0.17 * math.sqrt(fc) * b * d
            Vs_req = max(0, (Vu / phi_v) - Vc)
            Av = 2 * (math.pi * (dt**2) / 4) # 2 legs of shear reinforcement
            
            s_req_shear = (Av * fyt * d) / Vs_req if Vs_req > 0 else 300

            if "Special (SMRF)" in framing:
                l_0 = 2 * h
                # NSCP 418.6.4.4: SMRF Hoop spacing limits
                s1_max = min(d / 4, 6 * db, 150)
                s1 = min(s_req_shear, s1_max)
                s2 = d / 2
            elif "Intermediate (IMRF)" in framing:
                l_0 = 2 * h
                s1_max = min(d / 4, 8 * db, 24 * dt, 300)
                s1 = min(s_req_shear, s1_max)
                s2 = d / 2
            else: # OMRF
                l_0 = h # Arbitrary nominal zone for ordinary
                s1 = min(s_req_shear, d/2)
                s2 = min(s_req_shear, d/2)

            # Round down spacings to nearest 10mm for constructability
            s1 = max(math.floor(s1 / 10) * 10, 50)
            s2 = max(math.floor(s2 / 10) * 10, 50)

            # 4. Save results for rendering
            self.calc_data = {
                'b': b, 'h': h, 'd': d, 'cover': cover, 'db': db, 'dt': dt,
                'n_top_sup': n_top_sup, 'n_bot_mid': n_bot_mid, 
                'n_bot_sup': n_bot_sup, 'n_top_mid': n_top_mid,
                'l_0': l_0, 's1': s1, 's2': s2, 'L': L
            }

            self.display_results()
            self.plot_2d()
            self.plot_3d()

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input detected. Please enter numeric values.\nDetails: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"An error occurred during calculation.\nDetails: {e}")

    def display_results(self):
        cd = self.calc_data
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        report = (
            f"--- NSCP 2015 DESIGN RESULTS ---\n\n"
            f"FLEXURAL REINFORCEMENT:\n"
            f"Support (Top Bars):    {cd['n_top_sup']} - {cd['db']}mm Ø\n"
            f"Support (Bottom Bars): {cd['n_bot_sup']} - {cd['db']}mm Ø (Min.)\n"
            f"Midspan (Bottom Bars): {cd['n_bot_mid']} - {cd['db']}mm Ø\n"
            f"Midspan (Top Bars):    {cd['n_top_mid']} - {cd['db']}mm Ø (Min.)\n\n"
            f"SHEAR & SEISMIC DETAILING (SMRF):\n"
            f"Confinement Length (l_0): {cd['l_0']:.1f} mm\n"
            f"Spacing in l_0 (s1):      {cd['s1']:.1f} mm\n"
            f"Spacing outside (s2):     {cd['s2']:.1f} mm\n"
            f"Stirrup Size:             {cd['dt']}mm Ø\n"
        )
        self.result_text.insert(tk.END, report)
        self.result_text.config(state=tk.DISABLED)

    def plot_2d(self):
        cd = self.calc_data
        self.ax_cross.clear()
        self.ax_elev.clear()

        # --- CROSS SECTION ---
        b, h, cover = cd['b'], cd['h'], cd['cover']
        
        # Concrete outline
        self.ax_cross.plot([0, b, b, 0, 0], [0, 0, h, h, 0], 'k-', lw=2)
        
        # Stirrup
        x_st = [cover, b-cover, b-cover, cover, cover]
        y_st = [cover, cover, h-cover, h-cover, cover]
        self.ax_cross.plot(x_st, y_st, 'r-', lw=1.5, label='Stirrup')

        # Rebars (Top Support scenario assumed for plot)
        top_y = h - cover - cd['dt'] - cd['db']/2
        bot_y = cover + cd['dt'] + cd['db']/2
        
        def draw_bars(ax, n_bars, y_pos, color):
            if n_bars == 1:
                x_pos = [b/2]
            else:
                spacing = (b - 2*cover - 2*cd['dt'] - cd['db']) / (n_bars - 1)
                x_pos = [cover + cd['dt'] + cd['db']/2 + i*spacing for i in range(n_bars)]
            ax.scatter(x_pos, [y_pos]*n_bars, s=80, c=color, zorder=5)

        draw_bars(self.ax_cross, cd['n_top_sup'], top_y, 'blue')
        draw_bars(self.ax_cross, cd['n_bot_mid'], bot_y, 'green')

        self.ax_cross.set_aspect('equal')
        self.ax_cross.set_title('Cross-Section View')
        self.ax_cross.axis('off')

        # --- ELEVATION VIEW ---
        L = cd['L']
        l_0, s1, s2 = cd['l_0'], cd['s1'], cd['s2']

        # Concrete outline
        self.ax_elev.plot([0, L, L, 0, 0], [0, 0, h, h, 0], 'k-', lw=2)

        # Generate stirrup positions
        stirrup_x = []
        # Left l_0 zone
        x = 50 # 50mm from face of support
        while x <= l_0 and x < (L/2):
            stirrup_x.append(x)
            x += s1
        # Middle zone
        while x < (L - l_0):
            stirrup_x.append(x)
            x += s2
        # Right l_0 zone
        x = max(L - l_0, x)
        while x < L - 50:
            stirrup_x.append(x)
            x += s1

        for sx in stirrup_x:
            self.ax_elev.plot([sx, sx], [cover, h-cover], 'r-', lw=1)

        # Longitudinal bars
        self.ax_elev.plot([0, L], [top_y, top_y], 'b-', lw=2, label='Top Bars')
        self.ax_elev.plot([0, L], [bot_y, bot_y], 'g-', lw=2, label='Bot Bars')

        self.ax_elev.set_aspect('equal', adjustable='datalim')
        self.ax_elev.set_title(f'Elevation View ({L/1000:.1f}m Span)')
        self.ax_elev.set_xlabel('Length (mm)')
        self.ax_elev.set_ylabel('Depth (mm)')

        self.fig_2d.tight_layout()
        self.canvas_2d.draw()

    def plot_3d(self):
        cd = self.calc_data
        self.ax_3d.clear()

        b, h, L, cover = cd['b'], cd['h'], cd['L'], cd['cover']
        l_0, s1, s2 = cd['l_0'], cd['s1'], cd['s2']

        # Draw translucent concrete box
        X, Y = np.meshgrid([0, b], [0, h])
        Z_back = np.full_like(X, 0)
        Z_front = np.full_like(X, L)
        self.ax_3d.plot_surface(X, Z_back, Y, alpha=0.1, color='gray')
        self.ax_3d.plot_surface(X, Z_front, Y, alpha=0.1, color='gray')
        
        # Longitudinal bars
        top_y = h - cover - cd['dt'] - cd['db']/2
        bot_y = cover + cd['dt'] + cd['db']/2
        x_left = cover + cd['dt'] + cd['db']/2
        x_right = b - cover - cd['dt'] - cd['db']/2

        bars_pos = [
            (x_left, top_y, 'b'), (x_right, top_y, 'b'),
            (x_left, bot_y, 'g'), (x_right, bot_y, 'g')
        ]
        
        for bx, by, c in bars_pos:
            self.ax_3d.plot([bx, bx], [0, L], [by, by], color=c, lw=3)

        # Draw 3D stirrups
        x = 50
        stirrup_zs = []
        while x <= l_0 and x < (L/2): 
            stirrup_zs.append(x)
            x += s1
        while x < (L - l_0): 
            stirrup_zs.append(x)
            x += s2
        x = max(L - l_0, x)
        while x < L - 50: 
            stirrup_zs.append(x)
            x += s1

        for sz in stirrup_zs:
            xs = [cover, b-cover, b-cover, cover, cover]
            ys = [cover, cover, h-cover, h-cover, cover]
            zs = [sz] * 5
            self.ax_3d.plot(xs, zs, ys, color='r', lw=1.5)

        # Use an automated aspect ratio limit to prevent extreme distortion on very long beams
        z_scale = L if L < 5000 else 5000
        self.ax_3d.set_box_aspect([b/z_scale, 1, h/z_scale]) 
        
        self.ax_3d.set_xlabel('Width (mm)')
        self.ax_3d.set_ylabel('Length Span (mm)')
        self.ax_3d.set_zlabel('Depth (mm)')
        self.ax_3d.set_title(f'3D Rebar Cage Isometric View ({L/1000:.1f}m Span)')

        self.fig_3d.tight_layout()
        self.canvas_3d.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = BeamDesignApp(root)
    root.mainloop()