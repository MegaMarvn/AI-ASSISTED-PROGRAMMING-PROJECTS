import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import matplotlib.gridspec as gridspec

class RCColumnApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Biaxial RC Column Design & SMRF Detailing (NSCP 2015 / ACI 318)")
        self.root.geometry("1450x850")
        
        # --- Variables ---
        # Geometry & Materials
        self.b_var = tk.DoubleVar(value=400.0)
        self.h_var = tk.DoubleVar(value=500.0)
        self.lu_var = tk.DoubleVar(value=3000.0) # Column Clear Height
        self.fc_var = tk.DoubleVar(value=28.0)
        self.fy_var = tk.DoubleVar(value=414.0)
        
        # Reinforcement
        self.rebar_dia_var = tk.DoubleVar(value=20.0)
        self.tie_dia_var = tk.DoubleVar(value=10.0)
        self.nx_var = tk.IntVar(value=4)
        self.ny_var = tk.IntVar(value=5)
        self.clear_cover_var = tk.DoubleVar(value=40.0)
        
        # Applied Loads
        self.pu_var = tk.DoubleVar(value=1200.0)
        self.mux_var = tk.DoubleVar(value=150.0)
        self.muy_var = tk.DoubleVar(value=80.0)
        
        self.setup_ui()
        
    def setup_ui(self):
        # --- Main Layout ---
        input_frame = ttk.Frame(self.root, width=350, padding="10")
        input_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        
        plot_frame = ttk.Frame(self.root, padding="10")
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # --- Input Frame Elements ---
        ttk.Label(input_frame, text="Geometry (mm)", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0,5))
        self.add_entry(input_frame, "Width, b:", self.b_var)
        self.add_entry(input_frame, "Depth, h:", self.h_var)
        self.add_entry(input_frame, "Clear Height, lu:", self.lu_var)
        
        ttk.Label(input_frame, text="Materials (MPa)", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10,5))
        self.add_entry(input_frame, "Concrete f'c:", self.fc_var)
        self.add_entry(input_frame, "Steel fy:", self.fy_var)
        
        ttk.Label(input_frame, text="Reinforcement", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10,5))
        self.add_entry(input_frame, "Main Rebar Dia (mm):", self.rebar_dia_var)
        self.add_entry(input_frame, "Tie Dia (mm):", self.tie_dia_var)
        self.add_entry(input_frame, "Bars along width (Nx):", self.nx_var)
        self.add_entry(input_frame, "Bars along depth (Ny):", self.ny_var)
        self.add_entry(input_frame, "Clear Cover (mm):", self.clear_cover_var)
        
        ttk.Label(input_frame, text="Applied Loads (Factored)", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10,5))
        self.add_entry(input_frame, "Axial Load Pu (kN):", self.pu_var)
        self.add_entry(input_frame, "Moment Mux (kN-m):", self.mux_var)
        self.add_entry(input_frame, "Moment Muy (kN-m):", self.muy_var)
        
        ttk.Button(input_frame, text="Analyze & Plot", command=self.analyze).pack(fill=tk.X, pady=15)
        
        # Output Text Area for Detailing Report
        ttk.Label(input_frame, text="Seismic Detailing Report (SMRF):", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.report_text = tk.Text(input_frame, height=13, width=40, font=('Consolas', 9))
        self.report_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # --- Plot Frame Elements ---
        self.fig = plt.Figure(figsize=(14, 8.5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial empty plot draw
        self.analyze()
        
    def add_entry(self, parent, label_text, variable):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label_text, width=22).pack(side=tk.LEFT)
        ttk.Entry(frame, textvariable=variable, width=12).pack(side=tk.RIGHT)

    def generate_rebar_layout(self):
        b, h = self.b_var.get(), self.h_var.get()
        nx, ny = self.nx_var.get(), self.ny_var.get()
        cover = self.clear_cover_var.get() + self.tie_dia_var.get() + self.rebar_dia_var.get()/2.0
        
        cx, cy = b/2 - cover, h/2 - cover
        rebars = []
        ab = np.pi * (self.rebar_dia_var.get()**2) / 4.0
        
        x_coords = np.linspace(-cx, cx, nx)
        for x in x_coords:
            rebars.append((x, cy, ab))
            rebars.append((x, -cy, ab))
            
        y_coords = np.linspace(-cy, cy, ny)[1:-1]
        for y in y_coords:
            rebars.append((-cx, y, ab))
            rebars.append((cx, y, ab))
            
        return rebars
        
    def calculate_pm_curve(self, b, h, fc, fy, rebars, axis='x'):
        beta1 = max(0.65, min(0.85, 0.85 - 0.05 * (fc - 28.0) / 7.0))
        Es = 200000.0 # MPa
        ecu = 0.003
        
        c_vals = np.concatenate([
            np.linspace(1, h, 100), 
            np.linspace(h, h*5, 30)
        ])
        
        P_des, M_des = [], []
        
        Ast = sum(r[2] for r in rebars)
        Pt = -Ast * fy
        P_des.append(Pt * 0.9 / 1000.0) 
        M_des.append(0.0)
        
        for c in c_vals:
            a = min(beta1 * c, h)
            Cc = 0.85 * fc * b * a
            Mc = Cc * (h/2.0 - a/2.0)
            
            Fs, Ms = 0, 0
            max_et = 0
            
            for rx, ry, ra in rebars:
                y_i = ry if axis == 'x' else rx
                d_i = h/2.0 - y_i
                
                strain = ecu * (c - d_i) / c
                if strain < max_et: max_et = strain
                
                stress = max(-fy, min(fy, strain * Es))
                force = stress * ra
                
                if d_i < a and stress > 0:
                    force -= 0.85 * fc * ra
                    
                Fs += force
                Ms += force * y_i
                
            Pn = Cc + Fs
            Mn = abs(Mc + Ms)
            
            et = -max_et 
            ey = fy / Es
            if et >= 0.005: phi = 0.90
            elif et <= ey: phi = 0.65
            else: phi = 0.65 + 0.25 * (et - ey) / (0.005 - ey)
                
            phi_Pn = phi * Pn / 1000.0
            phi_Mn = phi * Mn / 1000000.0
            
            Po = (0.85 * fc * (b*h - Ast) + Ast * fy) / 1000.0
            phi_Pn_max = 0.80 * 0.65 * Po
            
            if phi_Pn <= phi_Pn_max:
                P_des.append(phi_Pn)
                M_des.append(phi_Mn)
        
        sort_idx = np.argsort(P_des)
        return np.array(P_des)[sort_idx], np.array(M_des)[sort_idx]

    def compute_seismic_detailing(self):
        b, h = self.b_var.get(), self.h_var.get()
        lu = self.lu_var.get()
        dia = self.rebar_dia_var.get()
        cover = self.clear_cover_var.get()
        
        # 1. Plastic hinge length (lo)
        lo = max(b, h, lu/6.0, 450.0)
        
        # 2. Hoops spacing within lo (s0)
        hx = max((b - 2*cover), (h - 2*cover)) / 2
        sx = 100 + (350 - hx) / 3.0
        sx = max(100, min(150, sx))
        s0_raw = min(b/4.0, h/4.0, 6*dia, sx)
        
        # 3. Hoops spacing outside lo
        s1_raw = min(6*dia, 150.0)
        
        # Rounding for practical construction (nearest lower 10mm)
        s0 = max(50.0, (s0_raw // 10) * 10)
        s1 = max(50.0, (s1_raw // 10) * 10)
        
        return {'lo': lo, 's0': s0, 's1': s1, 'lu': lu}

    def generate_detailing_report(self):
        b, h = self.b_var.get(), self.h_var.get()
        tie = self.tie_dia_var.get()
        d = self.compute_seismic_detailing()
        
        report = (
            "--- SEISMIC DETAILING (SMRF) ---\n"
            f"Code Ref: NSCP 2015 418.7 / ACI 318 18.7\n\n"
            f"1. Column Clear Height (lu):\n"
            f"   lu = {d['lu']:.0f} mm\n\n"
            f"2. Plastic Hinge Length (lo):\n"
            f"   lo = {d['lo']:.0f} mm from joint faces\n\n"
            f"3. Hoop Spacing within lo (s0):\n"
            f"   Use {tie:.0f}mm hoops @ {d['s0']:.0f} mm O.C.\n\n"
            f"4. Hoop Spacing outside lo (s1):\n"
            f"   Use {tie:.0f}mm hoops @ {d['s1']:.0f} mm O.C.\n\n"
            f"5. Reinforcement Ratio:\n"
            f"   Ast = {sum(r[2] for r in self.generate_rebar_layout()):.0f} mm²\n"
            f"   rho = {(sum(r[2] for r in self.generate_rebar_layout())/(b*h)*100):.2f}% (Limit 1%-6%)"
        )
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def analyze(self):
        try:
            b, h = self.b_var.get(), self.h_var.get()
            fc, fy = self.fc_var.get(), self.fy_var.get()
            pu, mux, muy = self.pu_var.get(), self.mux_var.get(), self.muy_var.get()
            cover, tie = self.clear_cover_var.get(), self.tie_dia_var.get()
            
            rebars = self.generate_rebar_layout()
            
            Px, Mx = self.calculate_pm_curve(b, h, fc, fy, rebars, axis='x')
            Py, My = self.calculate_pm_curve(h, b, fc, fy, rebars, axis='y')
            
            self.fig.clf()
            gs = gridspec.GridSpec(2, 3, figure=self.fig, width_ratios=[1, 1, 1.2])
            
            # --- Plot 1: Cross Section ---
            ax_sec = self.fig.add_subplot(gs[0, 0])
            ax_sec.set_title("Cross Section & Rebar")
            ax_sec.add_patch(Rectangle((-b/2, -h/2), b, h, fill=True, color='#f0f0f0', ec='black', lw=1.5))
            
            ax_sec.scatter([r[0] for r in rebars], [r[1] for r in rebars], 
                           color='black', s=self.rebar_dia_var.get()*4, zorder=5)
            
            t_b, t_h = b - 2*cover, h - 2*cover
            ax_sec.add_patch(Rectangle((-t_b/2, -t_h/2), t_b, t_h, fill=False, color='red', ls='-', lw=1.5))
            
            ax_sec.set_xlim(-b/2 - 50, b/2 + 50)
            ax_sec.set_ylim(-h/2 - 50, h/2 + 50)
            ax_sec.set_aspect('equal')
            ax_sec.grid(True, linestyle=':', alpha=0.6)
            
            # --- Plot 2: Elevation (Visual Detailing) ---
            ax_elev = self.fig.add_subplot(gs[0, 1])
            d = self.compute_seismic_detailing()
            lo, s0, s1, lu = d['lo'], d['s0'], d['s1'], d['lu']
            
            ax_elev.set_title(f"Elevation (Face Width: {b:.0f}mm)")
            
            # Concrete Body
            ax_elev.add_patch(Rectangle((-b/2, 0), b, lu, fill=True, color='#e0e0e0', ec='black', lw=1.5))
            
            # Rebars (simplified to edge bars)
            ax_elev.plot([-t_b/2, -t_b/2], [0, lu], color='black', lw=2.5, zorder=3)
            ax_elev.plot([t_b/2, t_b/2], [0, lu], color='black', lw=2.5, zorder=3)
            
            # Hinge Highlights
            ax_elev.axhspan(0, lo, xmin=0.2, xmax=0.8, color='orange', alpha=0.3, lw=0)
            ax_elev.axhspan(lu-lo, lu, xmin=0.2, xmax=0.8, color='orange', alpha=0.3, lw=0)
            
            # Ties logic
            y_tie = s0 / 2.0
            while y_tie <= lo:
                ax_elev.plot([-t_b/2, t_b/2], [y_tie, y_tie], color='red', lw=1.5, zorder=4)
                y_tie += s0
                
            y_tie = lo + s1 / 2.0
            while y_tie < (lu - lo):
                ax_elev.plot([-t_b/2, t_b/2], [y_tie, y_tie], color='blue', lw=1, zorder=4)
                y_tie += s1
                
            y_tie = lu - lo + s0 / 2.0
            while y_tie <= (lu - s0/2.0):
                ax_elev.plot([-t_b/2, t_b/2], [y_tie, y_tie], color='red', lw=1.5, zorder=4)
                y_tie += s0

            # Detailing Annotations
            bbox_props = dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=0.5)
            ax_elev.annotate(f"Hinge lo: {lo:.0f}mm\nHoops: s0={s0:.0f}mm", xy=(0, lu - lo/2), 
                             xytext=(0, lu + lu*0.08), ha='center', va='bottom', fontsize=8,
                             arrowprops=dict(arrowstyle='->', color='red'), bbox=bbox_props)
                             
            ax_elev.annotate(f"Mid-span\nHoops: s1={s1:.0f}mm", xy=(0, lu/2), 
                             xytext=(b*1.2, lu/2), ha='left', va='center', fontsize=8,
                             arrowprops=dict(arrowstyle='->', color='blue'), bbox=bbox_props)
            
            ax_elev.annotate(f"Hinge lo: {lo:.0f}mm\nHoops: s0={s0:.0f}mm", xy=(0, lo/2), 
                             xytext=(0, -lu*0.08), ha='center', va='top', fontsize=8,
                             arrowprops=dict(arrowstyle='->', color='red'), bbox=bbox_props)

            ax_elev.set_xlim(-b*2, b*2.5) # Dynamic padding
            ax_elev.set_ylim(-lu*0.15, lu*1.15)
            ax_elev.axis('off')
            
            # --- Plot 3: 2D P-Mx ---
            ax_px = self.fig.add_subplot(gs[0, 2])
            ax_px.plot(Mx, Px, color='blue', lw=2, label='Capacity φPn-φMnx')
            ax_px.scatter(mux, pu, color='red', s=50, label='Applied (Pu, Mux)')
            ax_px.set_title("2D Interaction (Major Axis)")
            ax_px.set_xlabel("Moment Mx (kN-m)")
            ax_px.set_ylabel("Axial Load P (kN)")
            ax_px.grid(True)
            ax_px.axhline(0, color='black', lw=1)
            ax_px.axvline(0, color='black', lw=1)
            ax_px.legend(loc="upper right", fontsize=8)
            
            # --- Plot 4: 3D Biaxial Interaction Surface ---
            ax_3d = self.fig.add_subplot(gs[1, :], projection='3d')
            
            P_min = max(np.min(Px), np.min(Py))
            P_max = min(np.max(Px), np.max(Py))
            P_grid = np.linspace(P_min, P_max, 35)
            
            Mnx_interp = np.interp(P_grid, Px, Mx)
            Mny_interp = np.interp(P_grid, Py, My)
            
            theta = np.linspace(0, 2*np.pi, 35)
            P_surf, Mx_surf, My_surf = [], [], []
            alpha = 1.5
            
            for i, p in enumerate(P_grid):
                mx_cap = max(Mnx_interp[i], 0.001)
                my_cap = max(Mny_interp[i], 0.001)
                
                P_row, Mx_row, My_row = [], [], []
                for t in theta:
                    cost, sint = abs(np.cos(t)), abs(np.sin(t))
                    r = 1.0 / ( (cost/mx_cap)**alpha + (sint/my_cap)**alpha )**(1/alpha)
                    
                    P_row.append(p)
                    Mx_row.append(r * np.cos(t))
                    My_row.append(r * np.sin(t))
                    
                P_surf.append(P_row)
                Mx_surf.append(Mx_row)
                My_surf.append(My_row)
                
            ax_3d.plot_surface(np.array(Mx_surf), np.array(My_surf), np.array(P_surf), 
                               cmap='viridis', alpha=0.6, edgecolor='none')
            
            ax_3d.scatter(mux, muy, pu, color='red', s=100, label='Applied Load', zorder=10)
            
            # Safety DCR Check
            interp_mx_cap = np.interp(pu, Px, Mx)
            interp_my_cap = np.interp(pu, Py, My)
            
            if pu > P_max or pu < P_min or interp_mx_cap <= 0 or interp_my_cap <= 0:
                safety = "Outside axial limits!"
                color = 'red'
            else:
                ratio = (abs(mux)/interp_mx_cap)**alpha + (abs(muy)/interp_my_cap)**alpha
                if ratio <= 1.0:
                    safety = f"SAFE (DCR: {ratio:.2f})"
                    color = 'green'
                else:
                    safety = f"UNSAFE (DCR: {ratio:.2f})"
                    color = 'red'
            
            ax_3d.set_title(f"3D Biaxial Surface - Status: {safety}", color=color, fontweight='bold')
            ax_3d.set_xlabel("Mx (kN-m)")
            ax_3d.set_ylabel("My (kN-m)")
            ax_3d.set_zlabel("Pu (kN)")
            ax_3d.legend()
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            self.generate_detailing_report()
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred.\nDetails: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = RCColumnApp(root)
    root.mainloop()