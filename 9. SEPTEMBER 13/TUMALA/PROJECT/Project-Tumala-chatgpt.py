"""
AAC INFILL WALL - ITERATIVE OPENING SIZE ANALYSIS
Research prototype for a 3 m x 3 m AAC infill wall enclosed by
0.30 m x 0.30 m RC beams and columns with fixed column bases.

Install:
    pip install numpy matplotlib

IMPORTANT:
This is a preliminary research prototype, NOT a validated FEM solver.
Seismic coefficients are user inputs and must be verified against the
complete applicable NSCP 2015 procedure. Final thesis results should be
obtained from a validated FEM/SAP2000 model.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import math
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle


def seismic_base_shear(p):
    """Preliminary equivalent-lateral-force proxy: V = Cs W.
    Cs is supplied from editable seismic parameters.
    Verify the complete NSCP 2015 procedure for the final thesis model.
    """
    if p["W"] <= 0:
        return 0.0, 0.0
    Cs = p["Z"] * p["Ca"] * p["I"] / p["R"]
    return Cs, Cs * p["W"]


def wall_weight(p):
    return p["wall_width"] * p["wall_height"] * p["wall_thickness"] * p["aac_weight"]


def analyze_opening(p, ow, oh):
    """Simplified research-prototype response.
    Replace this function with actual FEM/SAP2000 extracted results later.
    """
    wall_area = p["wall_width"] * p["wall_height"]
    opening_area = ow * oh
    remaining_area = wall_area - opening_area
    ratio = opening_area / wall_area

    effective_ratio = max(remaining_area / wall_area, 1e-8)
    effective_E = p["aac_E"] * effective_ratio

    gravity = p["dead_load"] + p["live_load"] + wall_weight(p)
    _, base_shear = seismic_base_shear(p)

    # Prototype stress model; not an NSCP equation.
    axial = gravity / max(remaining_area, 1e-8)
    shear = base_shear / max(remaining_area, 1e-8)
    scf = 1.0 + 3.0 * ratio + 2.0 * ratio**2
    stress = math.sqrt(axial**2 + 3.0 * shear**2) * scf

    # Prototype displacement model; not an NSCP equation.
    G = effective_E / (2.0 * (1.0 + p["nu"]))
    if G > 0:
        disp_m = (base_shear * p["wall_height"]) / (
            G * 1e6 * p["wall_thickness"] * max(remaining_area, 1e-8)
        )
    else:
        disp_m = float("inf")
    displacement = disp_m * 1000.0 * (1.0 + 4.0 * ratio)

    # In actual FEM, critical location comes from the maximum element stress.
    locations = [
        "Opening upper-left corner",
        "Opening upper-right corner",
        "Opening lower-left corner",
        "Opening lower-right corner",
    ]
    critical = locations[int((ow + oh) * 100) % 4]

    status = "PASS" if (
        stress <= p["allowable_stress"]
        and displacement <= p["allowable_disp"]
    ) else "FAIL"

    return {
        "opening_width": ow,
        "opening_height": oh,
        "opening_area": opening_area,
        "opening_ratio": ratio * 100.0,
        "remaining_area": remaining_area,
        "stiffness_ratio": effective_ratio,
        "effective_E": effective_E,
        "gravity_load": gravity,
        "base_shear": base_shear,
        "stress_concentration": scf,
        "max_stress": stress,
        "displacement": displacement,
        "critical_location": critical,
        "status": status,
    }


def stress_field(p, ow, oh):
    """Qualitative stress visualization, NOT an FEM contour."""
    W, H = p["wall_width"], p["wall_height"]
    x = np.linspace(0, W, 180)
    y = np.linspace(0, H, 180)
    X, Y = np.meshgrid(x, y)

    x0, x1 = (W - ow) / 2.0, (W + ow) / 2.0
    y0, y1 = (H - oh) / 2.0, (H + oh) / 2.0

    Z = np.ones_like(X) * 0.1
    for cx, cy in [(x0,y0), (x1,y0), (x0,y1), (x1,y1)]:
        d = np.sqrt((X-cx)**2 + (Y-cy)**2)
        Z += 0.08 / (d + 0.025)

    mask = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    Z[mask] = np.nan
    return X, Y, Z, (x0, y0, x1, y1)


class SAP2000Interface:
    """Future SAP2000 API integration placeholder."""
    def connect(self): return False
    def create_model(self, p): pass
    def create_opening(self, ow, oh): pass
    def apply_loads(self, p): pass
    def run_analysis(self): pass
    def extract_stress_results(self): return {}
    def extract_displacement_results(self): return {}
    def close(self): pass


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("AAC Infill Wall - Adaptive Opening Analysis")
        self.root.geometry("1500x900")
        self.root.minsize(1100, 700)
        self.entries = {}
        self.results = []
        self.optimum = None
        self.build()

    def build(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="AAC INFILL WALL - ADAPTIVE OPENING ANALYSIS",
                  font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(top, text="3.0 m x 3.0 m clear wall | 0.30 m x 0.30 m RC beams/columns | fixed column bases").pack(anchor="w")
        ttk.Label(top, text="PRIMARY CHANGING VARIABLE: OPENING SIZE",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=4)

        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=5)
        left, right = ttk.Frame(paned, padding=5), ttk.Frame(paned, padding=5)
        paned.add(left, weight=1); paned.add(right, weight=3)

        self.inputs(left)
        self.outputs(right)

    def section(self, parent, title, fields):
        f = ttk.LabelFrame(parent, text=title, padding=7)
        f.pack(fill="x", pady=5)
        for i, (label, default) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(f, width=14)
            e.insert(0, default)
            e.grid(row=i, column=1, sticky="ew", pady=2)
            self.entries[label] = e
        f.columnconfigure(1, weight=1)

    def inputs(self, parent):
        c = tk.Canvas(parent, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=c.yview)
        inner = ttk.Frame(c)
        inner.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0,0), window=inner, anchor="nw")
        c.configure(yscrollcommand=sb.set)
        c.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        self.section(inner, "WALL / BOUNDARY GEOMETRY", [
            ("Wall Width (m)", "3.0"), ("Wall Height (m)", "3.0"),
            ("AAC Wall Thickness (m)", "0.15"),
            ("RC Beam Size (m)", "0.30"), ("RC Column Size (m)", "0.30")])

        self.section(inner, "AAC MATERIAL", [
            ("AAC Compressive Strength (MPa)", "5.0"),
            ("AAC Elastic Modulus (MPa)", "3000"),
            ("Poisson Ratio", "0.20"), ("AAC Unit Weight (kN/m³)", "6.0")])

        self.section(inner, "GRAVITY LOADS", [
            ("Dead Load (kN)", "0"), ("Live Load (kN)", "0")])

        self.section(inner, "NSCP SEISMIC INPUTS", [
            ("Seismic Weight W (kN)", "100"), ("Z", "0.40"),
            ("Ca", "0.44"), ("Cv", "0.64"),
            ("Importance Factor I", "1.0"), ("Response Modification R", "5.0")])

        self.section(inner, "PERFORMANCE LIMITS", [
            ("Allowable Stress (MPa)", "1.0"),
            ("Allowable Displacement (mm)", "10")])

        self.section(inner, "OPENING ITERATION", [
            ("Initial Opening Width (m)", "0.60"),
            ("Initial Opening Height (m)", "1.00"),
            ("Final Opening Width (m)", "1.80"),
            ("Final Opening Height (m)", "1.80"),
            ("Opening Increment (m)", "0.10")])

        bf = ttk.LabelFrame(inner, text="COMMANDS", padding=8)
        bf.pack(fill="x", pady=7)
        commands = [
            ("CREATE 2D MODEL", self.create_model),
            ("RUN SINGLE ANALYSIS", self.single),
            ("RUN OPENING ITERATION", self.iterate),
            ("SHOW STRESS LOCATION", self.show_stress),
            ("EXPORT CSV", self.export),
            ("CLEAR RESULTS", self.clear)]
        for text, cmd in commands:
            ttk.Button(bf, text=text, command=cmd).pack(fill="x", pady=3)

        ttk.Label(inner, text=(
            "NSCP NOTE: seismic coefficients are editable user inputs. "
            "Verify the complete NSCP 2015 seismic procedure, load combinations, "
            "site parameters, period, Cs limits, and applicable structural-system provisions."
        ), wraplength=300, justify="left").pack(fill="x", pady=10)

    def outputs(self, parent):
        nb = ttk.Notebook(parent); nb.pack(fill="both", expand=True)
        self.model_tab, self.result_tab = ttk.Frame(nb), ttk.Frame(nb)
        self.graph_tab, self.summary_tab = ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.model_tab, text="2D MODEL")
        nb.add(self.result_tab, text="ITERATION RESULTS")
        nb.add(self.graph_tab, text="GRAPHS")
        nb.add(self.summary_tab, text="OPTIMUM")

        self.model_fig = Figure(figsize=(9,7), dpi=100)
        self.model_ax = self.model_fig.add_subplot(111)
        self.model_canvas = FigureCanvasTkAgg(self.model_fig, master=self.model_tab)
        self.model_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.model_info = ttk.Label(self.model_tab, text="No model created.",
                                    font=("Segoe UI", 11, "bold"))
        self.model_info.pack(fill="x", padx=8, pady=5)

        cols = ("it","w","h","ratio","stress","disp","scf","loc","status")
        self.tree = ttk.Treeview(self.result_tab, columns=cols, show="headings")
        heads = {"it":"Iteration","w":"Opening W (m)","h":"Opening H (m)",
                 "ratio":"Ratio (%)","stress":"Stress (MPa)","disp":"Disp. (mm)",
                 "scf":"SCF","loc":"Critical Stress Location","status":"Status"}
        widths = {"it":70,"w":100,"h":100,"ratio":90,"stress":100,"disp":100,
                  "scf":80,"loc":220,"status":80}
        for col in cols:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.pack(fill="both", expand=True)

        self.graph_fig = Figure(figsize=(9,8), dpi=100)
        self.ax1 = self.graph_fig.add_subplot(311)
        self.ax2 = self.graph_fig.add_subplot(312)
        self.ax3 = self.graph_fig.add_subplot(313)
        self.graph_canvas = FigureCanvasTkAgg(self.graph_fig, master=self.graph_tab)
        self.graph_canvas.get_tk_widget().pack(fill="both", expand=True)

        self.summary = tk.Text(self.summary_tab, font=("Consolas", 12), wrap="word")
        self.summary.pack(fill="both", expand=True, padx=12, pady=12)
        self.summary.insert("1.0", "Run the opening-size iteration to determine the optimum.")
        self.summary.config(state="disabled")

    def params(self):
        labels = [
            "Wall Width (m)","Wall Height (m)","AAC Wall Thickness (m)",
            "RC Beam Size (m)","RC Column Size (m)",
            "AAC Compressive Strength (MPa)","AAC Elastic Modulus (MPa)",
            "Poisson Ratio","AAC Unit Weight (kN/m³)","Dead Load (kN)",
            "Live Load (kN)","Seismic Weight W (kN)","Z","Ca","Cv",
            "Importance Factor I","Response Modification R",
            "Allowable Stress (MPa)","Allowable Displacement (mm)"]
        try:
            v = {x: float(self.entries[x].get()) for x in labels}
            if any(v[x] <= 0 for x in labels if x not in ["Dead Load (kN)","Live Load (kN)","Seismic Weight W (kN)"]):
                raise ValueError("Required positive input contains zero or a negative value.")
            if v["Dead Load (kN)"] < 0 or v["Live Load (kN)"] < 0 or v["Seismic Weight W (kN)"] < 0:
                raise ValueError("Loads cannot be negative.")
            return {
                "wall_width":v["Wall Width (m)"],"wall_height":v["Wall Height (m)"],
                "wall_thickness":v["AAC Wall Thickness (m)"],"beam_size":v["RC Beam Size (m)"],
                "column_size":v["RC Column Size (m)"],"aac_fc":v["AAC Compressive Strength (MPa)"],
                "aac_E":v["AAC Elastic Modulus (MPa)"],"nu":v["Poisson Ratio"],
                "aac_weight":v["AAC Unit Weight (kN/m³)"],"dead_load":v["Dead Load (kN)"],
                "live_load":v["Live Load (kN)"],"W":v["Seismic Weight W (kN)"],
                "Z":v["Z"],"Ca":v["Ca"],"Cv":v["Cv"],"I":v["Importance Factor I"],
                "R":v["Response Modification R"],"allowable_stress":v["Allowable Stress (MPa)"],
                "allowable_disp":v["Allowable Displacement (mm)"]}
        except Exception as e:
            messagebox.showerror("Input Error", str(e)); return None

    def openings(self):
        labels = ["Initial Opening Width (m)","Initial Opening Height (m)",
                  "Final Opening Width (m)","Final Opening Height (m)",
                  "Opening Increment (m)"]
        try:
            a = [float(self.entries[x].get()) for x in labels]
            if any(x <= 0 for x in a): raise ValueError("Opening values must be greater than zero.")
            return a
        except Exception as e:
            messagebox.showerror("Opening Error", str(e)); return None

    def validate(self, p, ow, oh):
        if ow >= p["wall_width"] or oh >= p["wall_height"]:
            raise ValueError("Opening must be smaller than the 3 m x 3 m clear wall.")

    def draw(self, p, ow, oh):
        self.model_ax.clear()
        W,H = p["wall_width"],p["wall_height"]
        b,c = p["beam_size"],p["column_size"]
        x0,y0=(W-ow)/2,(H-oh)/2

        self.model_ax.add_patch(Rectangle((0,0),W,H,fill=False,linewidth=2))
        self.model_ax.add_patch(Rectangle((x0,y0),ow,oh,fill=False,linewidth=3))
        self.model_ax.add_patch(Rectangle((-c,0),c,H,fill=False,linewidth=3))
        self.model_ax.add_patch(Rectangle((W,0),c,H,fill=False,linewidth=3))
        self.model_ax.add_patch(Rectangle((-c,H),W+2*c,b,fill=False,linewidth=3))
        self.model_ax.add_patch(Rectangle((-c,-b),W+2*c,b,fill=False,linewidth=3))

        for x in (-c/2,W+c/2):
            self.model_ax.plot([x-.08,x+.08],[-b-.06,-b-.06],linewidth=3)

        self.model_ax.text(W/2,H/2,"AAC INFILL",ha="center",va="center")
        self.model_ax.text(x0+ow/2,y0+oh/2,"OPENING",ha="center",va="center")
        self.model_ax.set_aspect("equal")
        self.model_ax.set_xlim(-1,W+1); self.model_ax.set_ylim(-.6,H+.8)
        self.model_ax.set_xlabel("Width (m)"); self.model_ax.set_ylabel("Height (m)")
        self.model_ax.set_title("3 m x 3 m AAC Infill Wall + 0.30 m RC Boundary Members")
        self.model_ax.grid(True,alpha=.25)
        self.model_canvas.draw()
        ratio=ow*oh/(W*H)*100
        self.model_info.config(text=f"Opening: {ow:.3f} x {oh:.3f} m | Area: {ow*oh:.3f} m² | Ratio: {ratio:.2f}%")

    def create_model(self):
        p,o=self.params(),self.openings()
        if not p or not o:return
        try:self.validate(p,o[0],o[1])
        except Exception as e:messagebox.showerror("Geometry Error",str(e));return
        self.draw(p,o[0],o[1])

    def single(self):
        p,o=self.params(),self.openings()
        if not p or not o:return
        try:self.validate(p,o[0],o[1])
        except Exception as e:messagebox.showerror("Geometry Error",str(e));return
        r=analyze_opening(p,o[0],o[1]);r["iteration"]=1
        self.results=[r];self.optimum=r if r["status"]=="PASS" else None
        self.refresh(p)

    def iterate(self):
        p,o=self.params(),self.openings()
        if not p or not o:return
        iw,ih,fw,fh,inc=o
        self.results=[];self.optimum=None
        for i in range(1,1001):
            try:self.validate(p,iw,ih)
            except Exception:break
            r=analyze_opening(p,iw,ih);r["iteration"]=i
            self.results.append(r)
            if iw>=fw and ih>=fh:break
            iw=min(iw+inc,fw);ih=min(ih+inc,fh)
        passing=[r for r in self.results if r["status"]=="PASS"]
        if passing:self.optimum=max(passing,key=lambda r:r["opening_area"])
        self.refresh(p)
        messagebox.showinfo("Iteration Complete",
            f"Iterations: {len(self.results)}\n"+
            (f"Optimum: {self.optimum['opening_width']:.3f} x {self.optimum['opening_height']:.3f} m"
             if self.optimum else "No acceptable opening found."))

    def refresh(self,p):
        for item in self.tree.get_children():self.tree.delete(item)
        for r in self.results:
            self.tree.insert("", "end", values=(
                r["iteration"],f"{r['opening_width']:.3f}",f"{r['opening_height']:.3f}",
                f"{r['opening_ratio']:.2f}",f"{r['max_stress']:.4f}",
                f"{r['displacement']:.4f}",f"{r['stress_concentration']:.3f}",
                r["critical_location"],r["status"]))
        self.update_graphs()
        self.update_summary()
        if self.results:
            r=self.results[-1];self.draw(p,r["opening_width"],r["opening_height"])

    def update_graphs(self):
        for ax in (self.ax1,self.ax2,self.ax3):ax.clear()
        if self.results:
            x=[r["opening_ratio"] for r in self.results]
            self.ax1.plot(x,[r["max_stress"] for r in self.results],marker="o")
            self.ax2.plot(x,[r["displacement"] for r in self.results],marker="o")
            self.ax3.plot(x,[r["stiffness_ratio"] for r in self.results],marker="o")
            self.ax1.set_title("Opening Ratio vs Maximum Stress")
            self.ax2.set_title("Opening Ratio vs Maximum Displacement")
            self.ax3.set_title("Opening Ratio vs Relative Stiffness")
            for ax in (self.ax1,self.ax2,self.ax3):
                ax.set_xlabel("Opening Ratio (%)");ax.grid(True,alpha=.3)
            self.ax1.set_ylabel("Stress (MPa)");self.ax2.set_ylabel("Displacement (mm)")
            self.ax3.set_ylabel("Relative Stiffness")
            if self.optimum:
                x0=self.optimum["opening_ratio"]
                self.ax1.scatter([x0],[self.optimum["max_stress"]],s=100)
                self.ax2.scatter([x0],[self.optimum["displacement"]],s=100)
                self.ax3.scatter([x0],[self.optimum["stiffness_ratio"]],s=100)
        self.graph_fig.tight_layout();self.graph_canvas.draw()

    def update_summary(self):
        self.summary.config(state="normal");self.summary.delete("1.0",tk.END)
        if not self.results:self.summary.insert("1.0","No analysis results.")
        else:
            p=self.params();Cs,V=seismic_base_shear(p)
            lines=["AAC INFILL WALL ADAPTIVE OPENING STUDY","="*55,
                   "Clear wall: 3.00 m x 3.00 m",
                   "RC beam: 0.30 m x 0.30 m",
                   "RC columns: 0.30 m x 0.30 m",
                   "Column bases: fixed","",
                   "Independent variable: OPENING SIZE","",
                   f"Preliminary Cs = {Cs:.4f}",f"Preliminary base shear V = {V:.3f} kN",
                   f"Iterations = {len(self.results)}",""]
            if self.optimum:
                r=self.optimum
                lines += ["OPTIMUM OPENING","-"*35,
                          f"Width = {r['opening_width']:.3f} m",
                          f"Height = {r['opening_height']:.3f} m",
                          f"Area = {r['opening_area']:.3f} m²",
                          f"Opening ratio = {r['opening_ratio']:.2f}%",
                          f"Maximum stress = {r['max_stress']:.4f} MPa",
                          f"Displacement = {r['displacement']:.4f} mm",
                          f"Critical location = {r['critical_location']}",
                          "Status = PASS"]
            else:lines += ["NO ACCEPTABLE OPENING FOUND"]
            lines += ["","DISCLAIMER: Simplified stress/displacement values are research-prototype estimates.",
                      "They are not actual FEM/SAP2000 contours. Replace them with validated FEM results for the thesis."]
            self.summary.insert("1.0","\n".join(lines))
        self.summary.config(state="disabled")

    def show_stress(self):
        p,o=self.params(),self.openings()
        if not p or not o:return
        try:self.validate(p,o[0],o[1])
        except Exception as e:messagebox.showerror("Geometry Error",str(e));return
        X,Y,Z,(x0,y0,x1,y1)=stress_field(p,o[0],o[1])
        fig=Figure(figsize=(9,7),dpi=100);ax=fig.add_subplot(111)
        cf=ax.contourf(X,Y,Z,levels=35)
        fig.colorbar(cf,ax=ax,label="Qualitative Estimated Stress")
        ax.add_patch(Rectangle((x0,y0),o[0],o[1],fill=False,linewidth=3))
        for x,y,label in [(x0,y0,"Lower Left"),(x1,y0,"Lower Right"),(x0,y1,"Upper Left"),(x1,y1,"Upper Right")]:
            ax.scatter([x],[y],s=60);ax.annotate(label,(x,y),xytext=(5,5),textcoords="offset points")
        ax.set_aspect("equal");ax.set_xlabel("Width (m)");ax.set_ylabel("Height (m)")
        ax.set_title("Qualitative Stress Concentration Around Opening")
        win=tk.Toplevel(self.root);win.title("Stress Location - Research Prototype");win.geometry("950x750")
        cv=FigureCanvasTkAgg(fig,master=win);cv.get_tk_widget().pack(fill="both",expand=True);cv.draw()
        ttk.Label(win,text="NOT AN ACTUAL FEM/SAP2000 STRESS CONTOUR. Use validated FEM results for the final thesis.",
                  wraplength=850,justify="center").pack(pady=5)

    def export(self):
        if not self.results:
            messagebox.showwarning("No Results","Run the iteration first.");return
        fn=filedialog.asksaveasfilename(defaultextension=".csv",initialfile="AAC_adaptive_opening_results.csv",
                                        filetypes=[("CSV files","*.csv")])
        if not fn:return
        fields=list(self.results[0].keys())
        with open(fn,"w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(self.results)
        messagebox.showinfo("Export Complete",f"Saved:\n{fn}")

    def clear(self):
        self.results=[];self.optimum=None
        for i in self.tree.get_children():self.tree.delete(i)
        self.update_graphs()
        self.model_ax.clear();self.model_canvas.draw()
        self.summary.config(state="normal");self.summary.delete("1.0",tk.END)
        self.summary.insert("1.0","Results cleared.");self.summary.config(state="disabled")


if __name__ == "__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()