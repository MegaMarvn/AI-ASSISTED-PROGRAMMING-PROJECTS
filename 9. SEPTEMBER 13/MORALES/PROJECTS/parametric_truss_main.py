import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D

class TrussParametricApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Parametric Truss Designer (NSCP 2015 / ASCE 7-22)")
        self.root.geometry("1250x850")
        
        # Geometry & State Data
        self.nodes = []
        self.elements = []
        self.analyzed = False
        self.element_colors = []
        self.applied_loads = []
        
        # Built-in Structural Section Database
        # A: Cross-sectional Area in m^2, Fy: Yield Strength in kPa
        self.section_db = {
            "Angle Bar (Double)": {
                "2L 50x50x5": {"A": 0.000960, "Fy": 248000},  # A36 Steel
                "2L 75x75x6": {"A": 0.001728, "Fy": 248000},
                "2L 100x100x10": {"A": 0.003840, "Fy": 248000}
            },
            "HSST (Square Tube)": {
                "HSS 100x100x5": {"A": 0.001880, "Fy": 345000}, # A500 Gr B
                "HSS 150x150x6": {"A": 0.003440, "Fy": 345000},
                "HSS 200x200x8": {"A": 0.006080, "Fy": 345000}
            },
            "W-Section (I-Beam)": {
                "W150x13": {"A": 0.001730, "Fy": 345000},       # A992 Steel
                "W200x22": {"A": 0.002860, "Fy": 345000},
                "W310x39": {"A": 0.004930, "Fy": 345000}
            }
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        # Left Panel (Inputs)
        input_frame = ttk.LabelFrame(self.root, text="Truss Parameters", width=350)
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Geometric Parameters
        ttk.Label(input_frame, text="Span (m):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.span_var = tk.DoubleVar(value=20.0)
        ttk.Entry(input_frame, textvariable=self.span_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="Height at Apex (m):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.height_var = tk.DoubleVar(value=4.0)
        ttk.Entry(input_frame, textvariable=self.height_var, width=15).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="Number of Bays (Even):").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.bays_var = tk.IntVar(value=8)
        ttk.Entry(input_frame, textvariable=self.bays_var, width=15).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="3D Frame Spacing (m):").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.spacing_var = tk.DoubleVar(value=6.0)
        ttk.Entry(input_frame, textvariable=self.spacing_var, width=15).grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Separator(input_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Material Selection (Cascading Dropdowns)
        ttk.Label(input_frame, text="Material Category:").grid(row=5, column=0, padx=5, pady=5, sticky='w')
        self.category_var = tk.StringVar(value="Angle Bar (Double)")
        self.category_combo = ttk.Combobox(input_frame, textvariable=self.category_var, 
                                           values=list(self.section_db.keys()), width=18, state="readonly")
        self.category_combo.grid(row=5, column=1, padx=5, pady=5)
        self.category_combo.bind("<<ComboboxSelected>>", self.update_section_dropdown)
        
        ttk.Label(input_frame, text="Specific Section:").grid(row=6, column=0, padx=5, pady=5, sticky='w')
        self.section_var = tk.StringVar()
        self.section_combo = ttk.Combobox(input_frame, textvariable=self.section_var, width=18, state="readonly")
        self.section_combo.grid(row=6, column=1, padx=5, pady=5)
        self.update_section_dropdown() # Initialize the second dropdown
        
        ttk.Separator(input_frame, orient='horizontal').grid(row=7, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Design Loads
        ttk.Label(input_frame, text="Basic Wind Speed (kph):").grid(row=8, column=0, padx=5, pady=5, sticky='w')
        self.wind_var = tk.DoubleVar(value=250.0)
        ttk.Entry(input_frame, textvariable=self.wind_var, width=15).grid(row=8, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="Dead Load (kPa):").grid(row=9, column=0, padx=5, pady=5, sticky='w')
        self.dl_var = tk.DoubleVar(value=1.5)
        ttk.Entry(input_frame, textvariable=self.dl_var, width=15).grid(row=9, column=1, padx=5, pady=5)

        # Buttons
        ttk.Button(input_frame, text="Generate Geometry", command=self.generate_geometry).grid(row=10, column=0, columnspan=2, pady=10, sticky='we')
        ttk.Button(input_frame, text="View 2D Model", command=self.plot_2d).grid(row=11, column=0, columnspan=2, pady=5, sticky='we')
        ttk.Button(input_frame, text="View 3D Model", command=self.plot_3d).grid(row=12, column=0, columnspan=2, pady=5, sticky='we')
        
        btn_design = tk.Button(input_frame, text="Run NSCP/ASCE Design & Show Results", bg='#28a745', fg='white', font=('Arial', 9, 'bold'), command=self.run_design_check)
        btn_design.grid(row=13, column=0, columnspan=2, pady=20, sticky='we')
        
        # Right Panel (Visualization)
        self.canvas_frame = tk.Frame(self.root, bg='white')
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.figure = plt.Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, self.canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_section_dropdown(self, event=None):
        category = self.category_var.get()
        sections = list(self.section_db[category].keys())
        self.section_combo['values'] = sections
        self.section_combo.current(0) # Select the first one by default
        
    def generate_geometry(self):
        L = self.span_var.get()
        H = self.height_var.get()
        N = self.bays_var.get()
        spacing = self.spacing_var.get()
        
        if N % 2 != 0:
            messagebox.showwarning("Warning", "Number of bays should be an even number for a symmetrical Pratt truss.")
            return

        self.analyzed = False # Reset analysis state
        bay_width = L / N
        self.nodes = []
        self.elements = []
        
        # Generate 3D Nodes
        for z in [0, spacing]:
            for i in range(N + 1):
                x = i * bay_width
                self.nodes.append([x, 0, z]) # Bottom chord
                y = (i / (N / 2)) * H if i <= N / 2 else ((N - i) / (N / 2)) * H
                self.nodes.append([x, y, z]) # Top chord
                
        self.nodes = np.array(self.nodes)
        num_nodes_per_frame = (N + 1) * 2
        
        # Generate Elements
        for frame in [0, 1]:
            offset = frame * num_nodes_per_frame
            for i in range(N):
                b_curr, t_curr = offset + i * 2, offset + i * 2 + 1
                b_next, t_next = offset + (i + 1) * 2, offset + (i + 1) * 2 + 1
                
                self.elements.append([b_curr, b_next]) # Bottom chord
                self.elements.append([t_curr, t_next]) # Top chord
                self.elements.append([b_curr, t_curr]) # Verticals
                if i == N - 1: self.elements.append([b_next, t_next])
                
                # Diagonals (Pratt logic)
                if i < N / 2: self.elements.append([t_curr, b_next])
                else: self.elements.append([b_curr, t_next])
                    
        # Purlins/Bracing
        self.num_main_elements = len(self.elements)
        for i in range((N + 1) * 2):
            self.elements.append([i, i + num_nodes_per_frame])
            
        self.element_colors = ['#1f77b4'] * len(self.elements) # Default Blue
        self.plot_3d()

    def run_design_check(self):
        if len(self.nodes) == 0:
            messagebox.showerror("Error", "Generate geometry first.")
            return

        # 1. Loads (ASCE 7-22 / NSCP 2015)
        V = self.wind_var.get() / 3.6 # m/s
        qz = 0.613 * 1.0 * 1.0 * 0.85 * (V**2) / 1000 # kPa
        dl = self.dl_var.get()
        
        # Governing LRFD Combo: 1.2D + 1.0W
        design_load_kpa = 1.2 * dl + 1.0 * qz 
        
        # Tributary Area for one node = spacing * bay_width
        bay_width = self.span_var.get() / self.bays_var.get()
        trib_area = self.spacing_var.get() * bay_width
        nodal_load_kN = design_load_kpa * trib_area

        # 2. Fetch Material Properties from Database
        category = self.category_var.get()
        section_name = self.section_var.get()
        props = self.section_db[category][section_name]
        
        A = props["A"]
        Fy = props["Fy"]
        E = 200e6 # Modulus of Elasticity in kPa (200 GPa)

        # 3. Direct Stiffness Method (DSM) - 2D Solver
        front_idx = [i for i, n in enumerate(self.nodes) if n[2] == 0]
        n_nodes = len(front_idx)
        n_dof = n_nodes * 2
        K = np.zeros((n_dof, n_dof))
        F = np.zeros(n_dof)
        
        self.applied_loads = []

        # Apply nodal loads
        for i, global_id in enumerate(front_idx):
            if self.nodes[global_id][1] > 0:
                F[2*i + 1] = -nodal_load_kN
                self.applied_loads.append((*self.nodes[global_id], 0, -nodal_load_kN, 0))

        # Assemble Stiffness Matrix
        front_elements = []
        for elem_idx, (n1, n2) in enumerate(self.elements):
            if n1 in front_idx and n2 in front_idx:
                i1, i2 = front_idx.index(n1), front_idx.index(n2)
                front_elements.append((elem_idx, i1, i2))
                
                dx = self.nodes[n2][0] - self.nodes[n1][0]
                dy = self.nodes[n2][1] - self.nodes[n1][1]
                L = np.hypot(dx, dy)
                c, s = dx/L, dy/L
                
                k = (E*A/L) * np.array([
                    [c*c, c*s, -c*c, -c*s],
                    [c*s, s*s, -c*s, -s*s],
                    [-c*c, -c*s, c*c, c*s],
                    [-c*s, -s*s, c*s, s*s]
                ])
                
                dofs = [2*i1, 2*i1+1, 2*i2, 2*i2+1]
                for row in range(4):
                    for col in range(4):
                        K[dofs[row], dofs[col]] += k[row, col]

        # Boundary Conditions (Pin at left, Roller at right)
        left_id = front_idx.index(next(i for i in front_idx if self.nodes[i][0] == 0 and self.nodes[i][1] == 0))
        right_id = front_idx.index(next(i for i in front_idx if self.nodes[i][0] == self.span_var.get() and self.nodes[i][1] == 0))
        
        constrained_dofs = [2*left_id, 2*left_id+1, 2*right_id+1]
        free_dofs = [i for i in range(n_dof) if i not in constrained_dofs]
        
        U = np.zeros(n_dof)
        U[free_dofs] = np.linalg.solve(K[np.ix_(free_dofs, free_dofs)], F[free_dofs])

        # 4. Check Member Capacities
        max_dc = 0
        self.element_colors = ['lightgray'] * len(self.elements) 
        
        for elem_idx, i1, i2 in front_elements:
            dx = self.nodes[front_idx[i2]][0] - self.nodes[front_idx[i1]][0]
            dy = self.nodes[front_idx[i2]][1] - self.nodes[front_idx[i1]][1]
            L = np.hypot(dx, dy)
            c, s = dx/L, dy/L
            
            u_elem = np.array([U[2*i1], U[2*i1+1], U[2*i2], U[2*i2+1]])
            axial_force = (E*A/L) * np.dot([-c, -s, c, s], u_elem)
            
            # Capacity
            phi_t, phi_c = 0.9, 0.9
            capacity = (phi_t * Fy * A) if axial_force > 0 else (phi_c * Fy * A * 0.4)
            
            dc_ratio = abs(axial_force) / capacity
            max_dc = max(max_dc, dc_ratio)
            
            color = '#28a745' if dc_ratio <= 1.0 else '#dc3545'
            
            self.element_colors[elem_idx] = color
            back_elem_idx = elem_idx + (self.num_main_elements // 2)
            if back_elem_idx < self.num_main_elements:
                self.element_colors[back_elem_idx] = color

        self.analyzed = True
        self.plot_2d()
        
        messagebox.showinfo("Design Complete", 
                            f"Selected Section: {section_name}\n"
                            f"Area = {A*1000000:.0f} mm², Fy = {Fy/1000:.0f} MPa\n"
                            f"Factored Load Applied: {design_load_kpa:.2f} kPa\n\n"
                            f"Max Demand/Capacity (D/C) Ratio: {max_dc:.2f}\n"
                            f"{'✅ TRUSS PASSES' if max_dc <= 1.0 else '❌ TRUSS FAILS (See red members)'}\n\n"
                            f"Green = Pass (D/C ≤ 1.0)\nRed = Fail (D/C > 1.0)")

    def plot_2d(self):
        if len(self.nodes) == 0: return
        self.figure.clf()
        ax = self.figure.add_subplot(111)
        
        front_nodes = self.nodes[self.nodes[:, 2] == 0]
        
        for idx, elem in enumerate(self.elements):
            n1, n2 = elem
            if self.nodes[n1, 2] == 0 and self.nodes[n2, 2] == 0:
                x = [self.nodes[n1, 0], self.nodes[n2, 0]]
                y = [self.nodes[n1, 1], self.nodes[n2, 1]]
                ax.plot(x, y, color=self.element_colors[idx], linewidth=2.5)
                
        ax.scatter(front_nodes[:, 0], front_nodes[:, 1], c='black', zorder=5)
        
        if self.analyzed and self.applied_loads:
            for load in self.applied_loads:
                lx, ly = load[0], load[1]
                ax.arrow(lx, ly + 1.5, 0, -1.0, head_width=0.4, head_length=0.4, fc='magenta', ec='magenta', zorder=10)
            ax.plot([], [], color='magenta', label='Applied Loads')
            ax.plot([], [], color='#28a745', linewidth=3, label='Pass (D/C ≤ 1.0)')
            ax.plot([], [], color='#dc3545', linewidth=3, label='Fail (D/C > 1.0)')
            ax.legend(loc='upper right')

        section = self.section_var.get()
        ax.set_title(f"2D Truss Elevation - Analysis Results ({section})", fontsize=14)
        ax.set_xlabel("Span (m)")
        ax.set_ylabel("Height (m)")
        ax.grid(True, linestyle='--')
        ax.axis('equal')
        self.canvas.draw()

    def plot_3d(self):
        if len(self.nodes) == 0: return
        self.figure.clf()
        ax = self.figure.add_subplot(111, projection='3d')
        
        for idx, elem in enumerate(self.elements):
            n1, n2 = elem
            x = [self.nodes[n1, 0], self.nodes[n2, 0]]
            y = [self.nodes[n1, 1], self.nodes[n2, 1]]
            z = [self.nodes[n1, 2], self.nodes[n2, 2]]
            ax.plot(x, z, y, color=self.element_colors[idx], linewidth=2) 
            
        ax.scatter(self.nodes[:, 0], self.nodes[:, 2], self.nodes[:, 1], c='black', s=10)
        
        if self.analyzed and self.applied_loads:
            for load in self.applied_loads:
                lx, ly, lz = load[0], load[1], load[2]
                ax.quiver(lx, lz, ly + 1.5, 0, 0, -1.5, color='magenta', arrow_length_ratio=0.3)
                ax.quiver(lx, self.spacing_var.get(), ly + 1.5, 0, 0, -1.5, color='magenta', arrow_length_ratio=0.3)

        section = self.section_var.get()
        ax.set_title(f"3D Truss - {section}", fontsize=14)
        ax.set_xlabel("Span X (m)")
        ax.set_ylabel("Depth Z (m)")
        ax.set_zlabel("Height Y (m)")
        
        max_range = np.array([self.nodes[:,0].max()-self.nodes[:,0].min(), 
                              self.nodes[:,2].max()-self.nodes[:,2].min(), 
                              self.nodes[:,1].max()-self.nodes[:,1].min()]).max() / 2.0
        mid_x = (self.nodes[:,0].max()+self.nodes[:,0].min()) * 0.5
        mid_z = (self.nodes[:,2].max()+self.nodes[:,2].min()) * 0.5
        mid_y = (self.nodes[:,1].max()+self.nodes[:,1].min()) * 0.5
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_z - max_range, mid_z + max_range)
        ax.set_zlim(mid_y - max_range, mid_y + max_range)
        
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = TrussParametricApp(root)
    root.mainloop()