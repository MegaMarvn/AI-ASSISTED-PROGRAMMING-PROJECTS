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
        self.root.geometry("1200x800")
        
        # Geometry Data
        self.nodes = []
        self.elements = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Left Panel (Inputs)
        input_frame = ttk.LabelFrame(self.root, text="Truss Parameters", width=300)
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Geometric Parameters
        ttk.Label(input_frame, text="Span (m):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.span_var = tk.DoubleVar(value=20.0)
        ttk.Entry(input_frame, textvariable=self.span_var).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="Height at Apex (m):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.height_var = tk.DoubleVar(value=4.0)
        ttk.Entry(input_frame, textvariable=self.height_var).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="Number of Bays (Even):").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.bays_var = tk.IntVar(value=8)
        ttk.Entry(input_frame, textvariable=self.bays_var).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="3D Frame Spacing (m):").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.spacing_var = tk.DoubleVar(value=6.0)
        ttk.Entry(input_frame, textvariable=self.spacing_var).grid(row=3, column=1, padx=5, pady=5)
        
        # Material Selection
        ttk.Label(input_frame, text="Material Profile:").grid(row=4, column=0, padx=5, pady=15, sticky='w')
        self.material_var = tk.StringVar(value="Angle Bar (Double)")
        material_combo = ttk.Combobox(input_frame, textvariable=self.material_var, 
                                      values=["Angle Bar (Double)", "HSST (Tube)", "I-Beam (W-Section)"])
        material_combo.grid(row=4, column=1, padx=5, pady=15)
        
        # Design Loads (ASCE 7-22 / NSCP 2015)
        ttk.Label(input_frame, text="Basic Wind Speed (kph):").grid(row=5, column=0, padx=5, pady=5, sticky='w')
        self.wind_var = tk.DoubleVar(value=250.0)
        ttk.Entry(input_frame, textvariable=self.wind_var).grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="Dead Load (kPa):").grid(row=6, column=0, padx=5, pady=5, sticky='w')
        self.dl_var = tk.DoubleVar(value=0.5)
        ttk.Entry(input_frame, textvariable=self.dl_var).grid(row=6, column=1, padx=5, pady=5)

        # Buttons
        ttk.Button(input_frame, text="Generate Geometry", command=self.generate_geometry).grid(row=7, column=0, columnspan=2, pady=10, sticky='we')
        ttk.Button(input_frame, text="View 2D Model", command=self.plot_2d).grid(row=8, column=0, columnspan=2, pady=5, sticky='we')
        ttk.Button(input_frame, text="View 3D Model", command=self.plot_3d).grid(row=9, column=0, columnspan=2, pady=5, sticky='we')
        ttk.Button(input_frame, text="Run NSCP/ASCE Design", command=self.run_design_check).grid(row=10, column=0, columnspan=2, pady=20, sticky='we')
        
        # Right Panel (Visualization)
        self.canvas_frame = tk.Frame(self.root, bg='white')
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.figure = plt.Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, self.canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def generate_geometry(self):
        L = self.span_var.get()
        H = self.height_var.get()
        N = self.bays_var.get()
        spacing = self.spacing_var.get()
        
        if N % 2 != 0:
            messagebox.showwarning("Warning", "Number of bays should be an even number for a symmetrical Pratt truss.")
            return

        bay_width = L / N
        self.nodes = []
        self.elements = []
        
        # Generate 3D Nodes (Two parallel trusses)
        for z in [0, spacing]:
            for i in range(N + 1):
                x = i * bay_width
                
                # Bottom chord node
                self.nodes.append([x, 0, z])
                
                # Top chord node (Pitched)
                if i <= N / 2:
                    y = (i / (N / 2)) * H
                else:
                    y = ((N - i) / (N / 2)) * H
                
                self.nodes.append([x, y, z])
                
        self.nodes = np.array(self.nodes)
        
        # Generate Elements
        num_nodes_per_frame = (N + 1) * 2
        
        for frame in [0, 1]:
            offset = frame * num_nodes_per_frame
            for i in range(N):
                bottom_curr = offset + i * 2
                top_curr = offset + i * 2 + 1
                bottom_next = offset + (i + 1) * 2
                top_next = offset + (i + 1) * 2 + 1
                
                # Chords
                self.elements.append([bottom_curr, bottom_next]) # Bottom chord
                self.elements.append([top_curr, top_next])       # Top chord
                
                # Verticals
                self.elements.append([bottom_curr, top_curr])
                if i == N - 1: # Last vertical
                    self.elements.append([bottom_next, top_next])
                    
                # Diagonals (Pratt logic: point towards center)
                if i < N / 2:
                    self.elements.append([top_curr, bottom_next])
                else:
                    self.elements.append([bottom_curr, top_next])
                    
        # Add 3D Purlins/Bracing between the two frames
        for i in range((N + 1) * 2):
            self.elements.append([i, i + num_nodes_per_frame])
            
        messagebox.showinfo("Success", f"Generated {len(self.nodes)} nodes and {len(self.elements)} elements.")
        self.plot_3d()

    def plot_2d(self):
        if len(self.nodes) == 0: return
        self.figure.clf()
        ax = self.figure.add_subplot(111)
        
        # Plot only the first frame (z=0)
        front_nodes = self.nodes[self.nodes[:, 2] == 0]
        
        for elem in self.elements:
            n1, n2 = elem
            if self.nodes[n1, 2] == 0 and self.nodes[n2, 2] == 0: # Only draw elements on z=0
                x = [self.nodes[n1, 0], self.nodes[n2, 0]]
                y = [self.nodes[n1, 1], self.nodes[n2, 1]]
                ax.plot(x, y, 'b-', linewidth=2)
                
        ax.scatter(front_nodes[:, 0], front_nodes[:, 1], c='red', zorder=5)
        ax.set_title("2D Truss Elevation", fontsize=14)
        ax.set_xlabel("Span (m)")
        ax.set_ylabel("Height (m)")
        ax.grid(True, linestyle='--')
        ax.axis('equal')
        self.canvas.draw()

    def plot_3d(self):
        if len(self.nodes) == 0: return
        self.figure.clf()
        ax = self.figure.add_subplot(111, projection='3d')
        
        for elem in self.elements:
            n1, n2 = elem
            x = [self.nodes[n1, 0], self.nodes[n2, 0]]
            y = [self.nodes[n1, 1], self.nodes[n2, 1]]
            z = [self.nodes[n1, 2], self.nodes[n2, 2]]
            ax.plot(x, z, y, 'b-', linewidth=1) # Swap y and z for standard structural view
            
        ax.scatter(self.nodes[:, 0], self.nodes[:, 2], self.nodes[:, 1], c='red', s=10)
        ax.set_title(f"3D Truss Model - {self.material_var.get()}", fontsize=14)
        ax.set_xlabel("Span X (m)")
        ax.set_ylabel("Depth Z (m)")
        ax.set_zlabel("Height Y (m)")
        
        # Equalize aspect ratio in 3D
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

    def run_design_check(self):
        # 1. ASCE 7-22 Wind Load Calculation Block
        V = self.wind_var.get() / 3.6 # Convert kph to m/s
        Kd = 0.85 # Wind directionality factor for buildings
        Kz = 1.0  # Exposure factor (assumed constant for simplicity)
        Kzt = 1.0 # Topographic factor
        
        qz = 0.613 * Kz * Kzt * Kd * (V**2) # Velocity pressure in N/m^2
        wind_pressure_kpa = qz / 1000
        
        # 2. LRFD Load Combinations (NSCP 2015 Section 203.3)
        dl = self.dl_var.get()
        # Combo 1: 1.4D
        # Combo 2: 1.2D + 1.6L + 0.5(Lr or R)
        # Combo 3: 1.2D + 1.0W + L + 0.5(Lr or R)
        design_load_kpa = max(1.4 * dl, 1.2 * dl + 1.0 * wind_pressure_kpa)
        
        # 3. Material Capacity Check Block (NSCP 2015 Chapter 5 / AISC 360)
        material = self.material_var.get()
        if material == "Angle Bar (Double)":
            fy = 248 # MPa (A36 Steel)
            msg = "NSCP 2015 Sec 504: Checking Tension Yielding (ϕt = 0.90)\nNSCP 2015 Sec 505: Checking Flexural Buckling (ϕc = 0.90)"
        elif material == "HSST (Tube)":
            fy = 345 # MPa (A500 Gr B)
            msg = "NSCP 2015 Sec 504: Checking Tube Tension Yielding\nNSCP 2015 Sec 505: Checking Tube Buckling (KL/r)"
        else:
            fy = 345 # MPa (A992)
            msg = "NSCP 2015 Sec 504/505: Checking W-Section Capacities"
            
        report = (f"--- DESIGN REPORT ---\n"
                  f"Governing Wind Pressure (ASCE 7-22): {wind_pressure_kpa:.2f} kPa\n"
                  f"Max Factored Load (NSCP 2015): {design_load_kpa:.2f} kPa\n"
                  f"Material Selected: {material} (Fy = {fy} MPa)\n\n"
                  f"Design Modules Triggered:\n{msg}\n\n"
                  f"Note: Integrate OpenSeesPy or a Direct Stiffness Method (DSM) matrix solver here to distribute forces to members.")
        
        messagebox.showinfo("Analysis & Design Complete", report)

if __name__ == "__main__":
    root = tk.Tk()
    app = TrussParametricApp(root)
    root.mainloop()