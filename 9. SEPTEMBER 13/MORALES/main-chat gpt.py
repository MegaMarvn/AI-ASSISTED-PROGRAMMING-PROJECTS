"""NSCP 2015 RC Beam Design Assistant (single-file GUI).

Run: python nscp2015_beam_design_gui.py
Requires only Python with tkinter (normally included with standard Windows Python).

Scope: preliminary rectangular, singly reinforced beam checks in SI units. The seismic
limits in CODE are exposed for review: verify every adopted value and applicability
against the official NSCP 2015 and have a licensed structural engineer approve final work.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import date

# REVIEW AGAINST THE OFFICIAL NSCP 2015 EDITION BEFORE DESIGN USE.
CODE = {
    "phi_flexure": 0.90, "phi_shear": 0.75, "beta1_min": 0.65,
    "max_stirrup_normal_mm": 300.0, "max_stirrup_seismic_mm": 100.0,
    "critical_zone_factor": 2.0,  # critical length = max(2h, span/6), illustrative default
    "seismic_vc_factor": 1.0,     # leave editable; code-specific conditions must be checked
    "min_clear_spacing_mm": 25.0,
}
BAR_AREAS = {"10": 78.5, "12": 113.1, "16": 201.1, "20": 314.2, "25": 490.9,
             "28": 615.8, "32": 804.2, "36": 1017.9, "40": 1256.6}


class BeamApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NSCP 2015 RC Beam Design Assistant")
        self.geometry("1200x810")
        self.minsize(980, 680)
        self.v = {}
        self.status = tk.StringVar(value="Ready. Load sample values, then calculate.")
        self._variables()
        self._build()
        self.calculate()

    def _variables(self):
        defaults = {
            "project": "Sample SMRF Beam", "member": "B-2", "fc": 28, "fy": 415,
            "b": 300, "h": 550, "span": 6000, "support": 400, "cover": 40,
            "agg": 20, "mu": 180, "vu": 125, "frame": "Special moment frame",
            "top_n": 2, "top_bar": "20", "bot_n": 4, "bot_bar": "25",
            "stirrup_bar": "10", "legs": 2, "s_end": 100, "s_mid": 200,
            "phi_m": CODE["phi_flexure"], "phi_v": CODE["phi_shear"],
            "s_seismic": CODE["max_stirrup_seismic_mm"],
        }
        self.defaults = defaults
        if not self.v:
            for key, value in defaults.items():
                self.v[key] = tk.StringVar(value=str(value))

    def _build(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for text, command in (("Calculate / Update", self.calculate), ("Load sample", self.load_sample),
                              ("Export report", self.export_report), ("Reset", self.reset), ("Exit", self.destroy)):
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 7))
        ttk.Label(toolbar, text="Preliminary tool only — engineer review required.", foreground="#a34a00").pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 5))
        self._inputs_tab()
        self._reinforcement_tab()
        self._results_tab()
        self._visual_tab()
        self._assumptions_tab()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=(8, 4)).pack(fill="x")

    def _entry(self, parent, row, label, key, unit=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(parent, textvariable=self.v[key], width=15).grid(row=row, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w")

    def _inputs_tab(self):
        tab = ttk.Frame(self, padding=12); self.nb.add(tab, text="Project & Actions")
        left, right = ttk.LabelFrame(tab, text="Project and materials", padding=10), ttk.LabelFrame(tab, text="Beam geometry and actions", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8)); right.grid(row=0, column=1, sticky="nsew")
        self._entry(left, 0, "Project", "project"); self._entry(left, 1, "Member ID", "member")
        self._entry(left, 2, "Concrete strength, f'c", "fc", "MPa"); self._entry(left, 3, "Steel yield strength, fy", "fy", "MPa")
        ttk.Label(left, text="Seismic system").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(left, textvariable=self.v["frame"], state="readonly", width=22,
                     values=("Ordinary moment frame", "Intermediate moment frame", "Special moment frame")).grid(row=4, column=1, columnspan=2, sticky="w")
        for r, (label, key, unit) in enumerate((("Width, b", "b", "mm"), ("Overall depth, h", "h", "mm"), ("Span", "span", "mm"),
                                                  ("Support width", "support", "mm"), ("Clear cover", "cover", "mm"),
                                                  ("Aggregate size", "agg", "mm"), ("Factored moment, Mu", "mu", "kN·m"),
                                                  ("Factored shear, Vu", "vu", "kN"))):
            self._entry(right, r, label, key, unit)
        ttk.Label(tab, text="Enter factored design actions. This version evaluates one governing positive-moment section; support negative-moment reinforcement should be checked separately.", wraplength=850).grid(row=1, column=0, columnspan=2, sticky="w", pady=16)

    def _reinforcement_tab(self):
        tab = ttk.Frame(self, padding=12); self.nb.add(tab, text="Reinforcement")
        a, b = ttk.LabelFrame(tab, text="Longitudinal bars", padding=10), ttk.LabelFrame(tab, text="Transverse reinforcement", padding=10)
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8)); b.grid(row=0, column=1, sticky="nsew")
        for r, label, key, vals in ((0, "Top bar count", "top_n", ["2", "3", "4", "5", "6"]), (1, "Top bar diameter", "top_bar", list(BAR_AREAS)),
                                    (2, "Bottom bar count", "bot_n", ["2", "3", "4", "5", "6", "7", "8"]), (3, "Bottom bar diameter", "bot_bar", list(BAR_AREAS))):
            ttk.Label(a, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=5)
            ttk.Combobox(a, textvariable=self.v[key], values=vals, state="readonly", width=12).grid(row=r, column=1, sticky="w")
        fields = (("Stirrup diameter", "stirrup_bar", list(BAR_AREAS), "mm"), ("Stirrup legs", "legs", ["2", "4"], ""),
                  ("End-zone spacing", "s_end", [], "mm"), ("Midspan spacing", "s_mid", [], "mm"))
        for r, (label, key, vals, unit) in enumerate(fields):
            ttk.Label(b, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=5)
            if vals: ttk.Combobox(b, textvariable=self.v[key], values=vals, state="readonly", width=12).grid(row=r, column=1, sticky="w")
            else: ttk.Entry(b, textvariable=self.v[key], width=14).grid(row=r, column=1, sticky="w")
            ttk.Label(b, text=unit).grid(row=r, column=2, sticky="w")
        ttk.Button(tab, text="Propose practical reinforcement", command=self.propose).grid(row=1, column=0, sticky="w", pady=18)
        ttk.Label(tab, text="End zones are drawn as confinement regions. Verify hoop geometry, hook angle, crossties, and splice restrictions against NSCP 2015.", wraplength=850).grid(row=2, column=0, columnspan=2, sticky="w")

    def _results_tab(self):
        tab = ttk.Frame(self, padding=8); self.nb.add(tab, text="Results report")
        self.report = tk.Text(tab, wrap="word", font=("Consolas", 10))
        sb = ttk.Scrollbar(tab, command=self.report.yview); self.report.configure(yscrollcommand=sb.set)
        self.report.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

    def _visual_tab(self):
        tab = ttk.Frame(self, padding=4); self.nb.add(tab, text="2D & 3D visualization")
        left, right = ttk.LabelFrame(tab, text="2D cross-section", padding=6), ttk.LabelFrame(tab, text="3D reinforcement concept", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4)); right.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self.canvas2d = tk.Canvas(left, background="white", highlightthickness=0)
        self.canvas3d = tk.Canvas(right, background="white", highlightthickness=0)
        self.canvas2d.pack(fill="both", expand=True); self.canvas3d.pack(fill="both", expand=True)

    def _assumptions_tab(self):
        tab = ttk.Frame(self, padding=12); self.nb.add(tab, text="Code assumptions")
        text = tk.Text(tab, wrap="word", height=24); text.pack(fill="both", expand=True)
        text.insert("1.0", "NSCP 2015 REVIEW REQUIRED\n\nThis program is a preliminary aid for a rectangular beam. It exposes its adopted coefficients in the CODE dictionary at the top of the single source file. Verify phi factors, minimum and maximum steel formulas, Vc/Vs equations, hoop spacing, critical-region length, hook and crosstie detailing, development length, lap-splice restrictions, and capacity-design seismic shear against the official NSCP 2015 and the governing seismic system.\n\nImplemented: flexural capacity using Whitney block; basic Vc + Vs shear model; basic bar clear-spacing and stirrup-spacing checks; visual confinement zones.\n\nNot fully implemented: T-beam action, compression steel, axial interaction, torsion, bar development and anchorage calculations, joint design, slab interaction, exact probable-strength seismic shear, all special seismic exceptions, and detailing drawings.\n\nFinal designs must be reviewed and approved by a licensed structural engineer using the official NSCP 2015.")
        text.configure(state="disabled")

    def f(self, key):
        return float(self.v[key].get())

    def calculate(self):
        try:
            b, h, fc, fy, cover = (self.f(k) for k in ("b", "h", "fc", "fy", "cover"))
            mu, vu, nbot, legs, s_end, s_mid = (self.f(k) for k in ("mu", "vu", "bot_n", "legs", "s_end", "s_mid"))
            db, ds = float(self.v["bot_bar"].get()), float(self.v["stirrup_bar"].get())
            if min(b, h, fc, fy, cover, nbot, legs, s_end, s_mid) <= 0 or h <= 2 * cover + ds + db:
                raise ValueError("Use positive dimensions; beam depth is insufficient for the specified cover and bars.")
            As = nbot * BAR_AREAS[self.v["bot_bar"].get()]
            Ast = legs * BAR_AREAS[self.v["stirrup_bar"].get()]
            d = h - cover - ds - db / 2
            beta1 = max(CODE["beta1_min"], min(0.85, 0.85 - 0.05 * max(fc - 28, 0) / 7))
            a = As * fy / (0.85 * fc * b)
            c = a / beta1
            mn = As * fy * (d - a / 2) / 1e6
            phi_mn = self.f("phi_m") * mn
            rho = As / (b * d)
            rho_min = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)
            vc = 0.17 * math.sqrt(fc) * b * d / 1000 * CODE["seismic_vc_factor"]
            vs = Ast * fy * d / s_end / 1000
            vn, phi_vn = vc + vs, self.f("phi_v") * (vc + vs)
            clear = (b - 2 * (cover + ds) - nbot * db) / max(nbot - 1, 1)
            crit = max(CODE["critical_zone_factor"] * h, self.f("span") / 6)
            checks = [
                ("Flexural strength", phi_mn >= mu, f"φMn = {phi_mn:.1f} kN·m; Mu = {mu:.1f} kN·m"),
                ("Shear strength", phi_vn >= vu, f"φVn = {phi_vn:.1f} kN; Vu = {vu:.1f} kN"),
                ("Minimum tension steel", rho >= rho_min, f"ρ = {rho:.4f}; ρmin = {rho_min:.4f}"),
                ("Compression-block depth", a < d, f"a = {a:.1f} mm; d = {d:.1f} mm"),
                ("Bottom-bar clear spacing", clear >= max(CODE["min_clear_spacing_mm"], db, self.f("agg") + 5), f"clear = {clear:.1f} mm"),
                ("End-zone stirrup spacing", s_end <= min(d / 4, self.f("s_seismic")), f"s = {s_end:.0f} mm; adopted limit = min(d/4, seismic input)"),
                ("Midspan stirrup spacing", s_mid <= min(d / 2, CODE["max_stirrup_normal_mm"]), f"s = {s_mid:.0f} mm; basic limit = min(d/2, 300 mm)"),
            ]
            self.last = dict(b=b, h=h, d=d, db=db, ds=ds, nbot=int(nbot), ntop=int(self.f("top_n")), topdb=float(self.v["top_bar"].get()), crit=crit, s_end=s_end, s_mid=s_mid)
            self.write_report(b, h, fc, fy, As, Ast, d, a, c, beta1, mn, phi_mn, vc, vs, vn, phi_vn, checks, crit)
            self.draw(); failures = sum(not ok for _, ok, _ in checks)
            self.status.set("Calculated: {} check(s) require attention.".format(failures) if failures else "Calculated: basic checks passed; engineer review still required.")
        except Exception as exc:
            self.status.set("Input error: " + str(exc)); messagebox.showerror("Cannot calculate", str(exc))

    def write_report(self, b, h, fc, fy, As, Ast, d, a, c, beta1, mn, phi_mn, vc, vs, vn, phi_vn, checks, crit):
        lines = [f"NSCP 2015 RC BEAM PRELIMINARY REPORT — {self.v['project'].get()} / {self.v['member'].get()}", f"Date: {date.today().isoformat()}", "=" * 72,
                 "INPUTS", f"b × h = {b:.0f} × {h:.0f} mm | span = {self.v['span'].get()} mm | f'c = {fc:.1f} MPa | fy = {fy:.1f} MPa",
                 f"Mu = {self.v['mu'].get()} kN·m | Vu = {self.v['vu'].get()} kN | System: {self.v['frame'].get()}",
                 f"Bottom bars: {self.v['bot_n'].get()}–{self.v['bot_bar'].get()} (As = {As:.1f} mm²); top bars: {self.v['top_n'].get()}–{self.v['top_bar'].get()}",
                 f"Stirrups: {self.v['legs'].get()} legs, {self.v['stirrup_bar'].get()} mm; end/mid spacing = {self.v['s_end'].get()} / {self.v['s_mid'].get()} mm", "",
                 "FLEXURE", f"d = {d:.1f} mm; β1 = {beta1:.3f}; a = {a:.1f} mm; c = {c:.1f} mm", f"Mn = {mn:.1f} kN·m; φMn = {phi_mn:.1f} kN·m", "",
                 "SHEAR", f"Vc = {vc:.1f} kN; Vs (end spacing) = {vs:.1f} kN; Vn = {vn:.1f} kN; φVn = {phi_vn:.1f} kN", "",
                 "SEISMIC DETAILING", f"Illustrated critical/end confinement-zone length = {crit:.0f} mm from each support.",
                 "Verify all special moment-frame hoop, crosstie, hook, longitudinal-continuity, splice, development, and capacity-design shear provisions against NSCP 2015.", "", "CHECKS"]
        for name, ok, detail in checks: lines.append(f"{'PASS' if ok else 'FAIL':5}  {name}: {detail}")
        lines += ["", "LIMITATIONS", "This is not a final structural design and does not replace code interpretation or professional engineering judgment."]
        self.report.configure(state="normal"); self.report.delete("1.0", "end"); self.report.insert("1.0", "\n".join(lines)); self.report.configure(state="disabled")

    def draw(self):
        x = self.last; b, h, cover, ds, db = x["b"], x["h"], self.f("cover"), x["ds"], x["db"]
        # 2D canvas: dimensions scaled to a compact fixed drawing area.
        c = self.canvas2d; c.delete("all"); sx, sy = 360 / b, 380 / h; ox, oy = 72, 42
        c.create_rectangle(ox, oy, ox+b*sx, oy+h*sy, outline="#333", width=2, fill="#f1f1f1")
        c.create_rectangle(ox+cover*sx, oy+cover*sy, ox+(b-cover)*sx, oy+(h-cover)*sy, outline="#e67e22", width=2)
        def oval(cx, cy, dia, fill):
            r = dia * sx / 2; c.create_oval(ox+cx*sx-r, oy+(h-cy)*sy-r, ox+cx*sx+r, oy+(h-cy)*sy+r, fill=fill, outline="")
        for i in range(x["nbot"]):
            px = cover+ds+db/2 + i*(b-2*(cover+ds+db/2))/max(x["nbot"]-1, 1); oval(px, cover+ds+db/2, db, "#2471a3")
        for i in range(x["ntop"]):
            px = cover+ds+x["topdb"]/2 + i*(b-2*(cover+ds+x["topdb"]/2))/max(x["ntop"]-1, 1); oval(px, h-cover-ds-x["topdb"]/2, x["topdb"], "#c0392b")
        c.create_text(250, 450, text=f"b = {b:.0f} mm", fill="#333"); c.create_text(34, 240, text=f"h = {h:.0f} mm", fill="#333", angle=90)
        c.create_text(250, 18, text="Red = top bars | Blue = bottom bars | Orange = stirrup", fill="#333")
        # 3D pseudo-isometric canvas (portable alternative to a plotting dependency).
        c = self.canvas3d; c.delete("all"); L = self.f("span"); scale = 420 / L; x0, y0, depth, rise = 45, 145, 75, 62; length = L * scale
        front = (x0, y0, x0+length, y0, x0+length, y0+155, x0, y0+155)
        c.create_polygon(front, fill="#f4f4f4", outline="#555"); c.create_polygon(x0, y0, x0+depth, y0-rise, x0+length+depth, y0-rise, x0+length, y0, fill="#e7e7e7", outline="#555")
        c.create_polygon(x0+length, y0, x0+length+depth, y0-rise, x0+length+depth, y0+155-rise, x0+length, y0+155, fill="#dddddd", outline="#555")
        for yy in (y0+35, y0+120): c.create_line(x0+10, yy, x0+length-10, yy, fill="#2471a3", width=4)
        for yy in (y0+18, y0+136): c.create_line(x0+10, yy, x0+length-10, yy, fill="#c0392b", width=4)
        crit_px = x["crit"] * scale
        positions = list(range(0, int(crit_px)+1, max(1, int(x["s_end"]*scale)))) + list(range(int(crit_px+x["s_mid"]*scale), int(length-crit_px), max(1, int(x["s_mid"]*scale)))) + list(range(int(length-crit_px), int(length)+1, max(1, int(x["s_end"]*scale))))
        for px in positions:
            c.create_rectangle(x0+px, y0+8, x0+px+2, y0+147, outline="#e67e22")
        c.create_text(255, 345, text="Orange hoops are denser in end confinement zones", fill="#333")
        c.create_text(255, 372, text="3D concept only — verify final detailing and bar layout", fill="#333")

    def propose(self):
        self.v["bot_n"].set("4"); self.v["bot_bar"].set("25"); self.v["top_n"].set("2"); self.v["top_bar"].set("20"); self.v["s_end"].set("100"); self.v["s_mid"].set("200"); self.calculate()

    def load_sample(self):
        for key, value in self.defaults.items():
            self.v[key].set(str(value))
        self.calculate()
    def reset(self):
        for var in self.v.values(): var.set("")
        self.report.configure(state="normal"); self.report.delete("1.0", "end"); self.report.configure(state="disabled"); self.status.set("Inputs cleared.")
    def export_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text report", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as out: out.write(self.report.get("1.0", "end-1c"))
            self.status.set("Report saved: " + path)


if __name__ == "__main__":
    BeamApp().mainloop()
