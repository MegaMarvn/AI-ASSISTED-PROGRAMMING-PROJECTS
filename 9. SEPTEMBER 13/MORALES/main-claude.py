#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
 NSCP 2015 REINFORCED CONCRETE BEAM DESIGN TOOL (with Seismic Detailing)
==============================================================================

Single-file Tkinter + Matplotlib desktop application that designs the
longitudinal and transverse (stirrup/hoop) reinforcement of a rectangular
reinforced-concrete beam per NSCP 2015 (which mirrors ACI 318-11/14 provisions
for flexure and shear, Chapter 4 "Special Provisions for Seismic Design").

Two seismic categories are supported:
    - OMF : Ordinary Moment Frame  (no special seismic detailing)
    - SMF : Special Moment Frame   (NSCP 2015 / ACI 318 Sec. 18.6 detailing)

FEATURES
--------
1. Flexural design (Whitney rectangular stress block) at 3 sections
   (Left support, Midspan, Right support), each with +M and -M capacity.
2. Shear design including the "Vc = 0" seismic rule inside plastic hinge
   zones (ACI 318-14 18.6.5.2 / NSCP 2015 sec. 421.6.5.2).
3. Seismic detailing checks for SMF beams:
       - min/max longitudinal reinforcement ratio (0.025 cap)
       - min 2 continuous top & bottom bars
       - positive Mn at joint face >= 50% of negative Mn at that face
       - Mn (+ or -) at any section >= 25% of the max Mn at either joint face
       - hoop spacing in the plastic hinge region (2h from face of support)
       - first hoop within 50 mm of the face of support
       - lap-splice location restriction (kept out of hinge zones)
4. 2D visualization: beam cross-section + longitudinal elevation with
   hoop/stirrup layout and shaded plastic hinge zones.
5. 3D visualization: extruded concrete beam (semi-transparent), longitudinal
   bars, and stirrup/hoop loops, rendered with an interactive matplotlib
   3D axis (rotate / zoom with the mouse).
6. Results summary tab listing every design step, applicable NSCP/ACI
   code clause, and a PASS/FAIL remark for every seismic check.
7. "Export Report" button writes a plain-text calculation report.

DEPENDENCIES (all common / pip-installable)
    - Python 3.8+
    - tkinter        (standard library GUI toolkit)
    - matplotlib      (2D & 3D plotting, embedded in Tkinter)
    - numpy

DISCLAIMER
----------
This program is a drafting / learning aid.  It implements a simplified,
common-practice interpretation of NSCP 2015 / ACI 318 flexure, shear, and
seismic detailing provisions.  It does NOT replace the judgment, checking,
and sealing of a licensed civil / structural engineer.  Always verify all
outputs against the current, complete NSCP 2015 code text and any
project-specific requirements before use in an actual design.
==============================================================================
"""

import math
import datetime

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
import matplotlib.patches as mpatches


# ==============================================================================
# 1. CONSTANTS / BAR DATA
# ==============================================================================

# Standard metric rebar diameters (mm) -> cross-sectional area (mm^2)
BAR_AREAS = {
    10: math.pi / 4 * 10 ** 2,
    12: math.pi / 4 * 12 ** 2,
    16: math.pi / 4 * 16 ** 2,
    20: math.pi / 4 * 20 ** 2,
    25: math.pi / 4 * 25 ** 2,
    28: math.pi / 4 * 28 ** 2,
    32: math.pi / 4 * 32 ** 2,
}
BAR_SIZES = sorted(BAR_AREAS.keys())

PHI_FLEXURE = 0.90     # tension-controlled section, NSCP 2015 Sec 405.4.2
PHI_SHEAR = 0.75       # NSCP 2015 Sec 405.4.2
MAX_AGG_SPACING = 25.0  # mm, minimum clear spacing base value


# ==============================================================================
# 2. CORE DESIGN CALCULATION FUNCTIONS
#    (units: N, mm, MPa unless noted; moments input/returned in kN-m,
#     shears input/returned in kN)
# ==============================================================================

def required_steel_area(Mu_kNm, b, d, fc, fy, phi=PHI_FLEXURE):
    """
    Solve for the required tension steel area As (mm^2) using the Whitney
    rectangular stress block, given factored moment Mu (kN-m).

    Mu = phi * As * fy * (d - a/2),   a = As*fy / (0.85*fc*b)

    Rearranged into a quadratic in As:
        [phi*fy^2/(1.7*fc*b)] * As^2 - [phi*fy*d] * As + Mu = 0

    Returns:
        As (mm^2), or None if the section is too small (no real root),
        or 0.0 if Mu <= 0.
    """
    if Mu_kNm is None or Mu_kNm <= 0:
        return 0.0
    Mu = Mu_kNm * 1.0e6  # N-mm
    a_coef = phi * fy ** 2 / (1.7 * fc * b)
    b_coef = -phi * fy * d
    c_coef = Mu
    disc = b_coef ** 2 - 4 * a_coef * c_coef
    if disc < 0:
        return None
    As = (-b_coef - math.sqrt(disc)) / (2 * a_coef)
    return As


def phi_Mn(As, b, d, fc, fy, phi=PHI_FLEXURE):
    """Design moment capacity phi*Mn (kN-m) provided by area As (mm^2)."""
    if As is None or As <= 0:
        return 0.0
    a = As * fy / (0.85 * fc * b)
    Mn = As * fy * (d - a / 2.0)
    return phi * Mn / 1.0e6


def As_min_flexure(b, d, fc, fy):
    """NSCP 2015 Sec 409.6.1.2 / ACI 318 9.6.1.2 minimum flexural steel."""
    return max(1.4 / fy * b * d, 0.25 * math.sqrt(fc) / fy * b * d)


def As_max_seismic(b, d):
    """SMF beams: rho_max = 0.025 (ACI 318-14 18.6.3.1 / NSCP 2015 421.6.3.1)."""
    return 0.025 * b * d


def bars_needed(As_req, bar_dia, minimum_bars=2):
    """Number of bars (>=minimum_bars) of diameter bar_dia to satisfy As_req."""
    area = BAR_AREAS[bar_dia]
    n = max(minimum_bars, math.ceil(As_req / area)) if As_req > 0 else minimum_bars
    return n, n * area


def clear_spacing(b, cover, dstirrup, dbar, n):
    """Clear spacing (mm) between adjacent bars in a single layer of width b."""
    if n <= 1:
        return None
    avail = b - 2 * cover - 2 * dstirrup - n * dbar
    return avail / (n - 1)


def min_clear_spacing_required(dbar):
    """NSCP 2015 Sec 425.2.1: >= dbar, >= 25 mm, >= (4/3)*max aggregate size (~25mm assumed)."""
    return max(dbar, MAX_AGG_SPACING)


def Vc_concrete(b, d, fc, seismic_zero=False):
    """
    Concrete shear capacity Vc (N).
    seismic_zero=True forces Vc = 0, per ACI 318-14 18.6.5.2 / NSCP 2015
    421.6.5.2: within the plastic hinge region of an SMF beam, Vc is taken
    as zero when (a) the earthquake-induced shear represents >= 1/2 of the
    max required shear strength within that region, AND (b) the factored
    axial compressive force is small (< Ag*fc'/20).
    """
    if seismic_zero:
        return 0.0
    return 0.17 * math.sqrt(fc) * b * d  # N, lambda = 1.0 (normal weight)


def stirrup_spacing_required(Vu_kN, Vc_N, d, fy, Av, phi=PHI_SHEAR):
    """
    Required stirrup spacing s (mm) to provide Vs = Av*fy*d/s.
    Returns None if concrete + minimum reinforcement is already adequate
    (i.e., Vs_required <= 0), meaning spacing is governed by maximum
    spacing limits instead.
    """
    Vu = Vu_kN * 1.0e3
    Vs_req = Vu / phi - Vc_N
    if Vs_req <= 0:
        return None
    s = Av * fy * d / Vs_req
    return s


def hoop_spacing_max_hinge(d, db_long_min, db_hoop):
    """
    Maximum hoop spacing within the plastic hinge region of an SMF beam
    (ACI 318-14 18.6.4.4 / NSCP 2015 421.6.4.4):
        s <= min( d/4, 8*db_long(smallest), 24*db_hoop, 300 mm )
    """
    return min(d / 4.0, 8 * db_long_min, 24 * db_hoop, 300.0)


def stirrup_spacing_max_outside_hinge(d, db_hoop):
    """Non-seismic-zone maximum stirrup spacing, ACI 318 9.7.6.2.2: d/2, but
    <= 600 mm; a common practical cap of d/2 (<=300) is applied here."""
    return min(d / 2.0, 600.0)


# ==============================================================================
# 3. BEAM DESIGN "ENGINE" - drives all sections & assembles results
# ==============================================================================

class BeamDesign:
    """Container that runs the full design given an input dict, and stores
    every intermediate & final result needed for the summary and figures."""

    def __init__(self, inputs):
        self.inp = inputs
        self.log = []            # list of (section_title, [lines]) for report
        self.checks = []         # list of (description, passed(bool), remark)
        self.results = {}        # numeric results keyed by name
        self._design()

    # ---------------------------------------------------------------- utils
    def _add_log(self, title, lines):
        self.log.append((title, lines))

    def _add_check(self, desc, passed, remark=""):
        self.checks.append((desc, passed, remark))

    # ------------------------------------------------------------- design
    def _design(self):
        p = self.inp
        b, h, d, cover = p["b"], p["h"], p["d"], p["cover"]
        fc, fy = p["fc"], p["fy"]
        is_smf = p["seismic_cat"] == "SMF (Special Moment Frame)"
        dbar = p["dbar"]
        dstirrup = p["dstirrup"]
        ln = p["ln"]

        # ---- 1. Flexural design at each section / each sign of moment ----
        sections = ["Left Support", "Midspan", "Right Support"]
        moments = {
            "Left Support": {"neg": p["M_left_neg"], "pos": p["M_left_pos"]},
            "Midspan": {"neg": p["M_mid_neg"], "pos": p["M_mid_pos"]},
            "Right Support": {"neg": p["M_right_neg"], "pos": p["M_right_pos"]},
        }

        As_min = As_min_flexure(b, d, fc, fy)
        As_max = As_max_seismic(b, d) if is_smf else 0.04 * b * d  # 0.04 = OMF practical cap

        flex = {}
        lines = ["NSCP 2015 Sec 409.6 (Flexure) / 421.6.3 (Seismic longitudinal limits)",
                 f"As,min = max(1.4/fy*b*d , 0.25*sqrt(fc')/fy*b*d) = {As_min:,.0f} mm^2",
                 f"As,max ({'SMF: rho<=0.025' if is_smf else 'OMF practical cap rho<=0.04'}) = {As_max:,.0f} mm^2",
                 ""]
        for sec in sections:
            flex[sec] = {}
            for sign in ("neg", "pos"):
                Mu = moments[sec][sign]
                As_req_raw = required_steel_area(Mu, b, d, fc, fy)
                warn = None
                if As_req_raw is None:
                    warn = "Section too small for Mu -- increase b or h!"
                    As_req_raw = As_max  # fallback so program keeps running
                As_req = max(As_req_raw, As_min) if Mu > 0 else 0.0
                over_max = As_req > As_max
                n, As_prov = (bars_needed(As_req, dbar) if Mu > 0 else (2, 2 * BAR_AREAS[dbar]))
                # Always at least 2 continuous bars per SMF requirement / good practice
                phiMn_prov = phi_Mn(As_prov, b, d, fc, fy)
                dcr = (Mu / phiMn_prov) if phiMn_prov > 0 else 0.0
                cs = clear_spacing(b, cover, dstirrup, dbar, n)
                cs_min_req = min_clear_spacing_required(dbar)
                flex[sec][sign] = dict(Mu=Mu, As_req=As_req, n=n, As_prov=As_prov,
                                        phiMn=phiMn_prov, dcr=dcr, clear_spacing=cs,
                                        cs_min_req=cs_min_req, over_max=over_max, warn=warn)
                lines.append(
                    f"[{sec} | {'(-) top' if sign=='neg' else '(+) bottom'}]  Mu={Mu:6.1f} kN-m  "
                    f"As,req={As_req:7.0f} mm^2 -> {n}-{dbar}mm bars (As,prov={As_prov:7.0f} mm^2)  "
                    f"phiMn={phiMn_prov:6.1f} kN-m  DCR={dcr:0.2f}"
                )
                if warn:
                    lines.append(f"    ** WARNING: {warn} **")
                if cs is not None and cs < cs_min_req:
                    lines.append(f"    ** WARNING: clear spacing {cs:.1f} mm < required {cs_min_req:.1f} mm **")
        self._add_log("FLEXURAL DESIGN", lines)
        self.results["flex"] = flex
        self.results["As_min"] = As_min
        self.results["As_max"] = As_max

        # ---- 2. Shear design ----
        Av = 2 * BAR_AREAS[dstirrup]  # 2-legged stirrup
        hinge_len = 2 * h  # ACI 318-14 18.6.4.1 / NSCP 421.6.4.1
        db_long_min = dbar
        s_hinge_max = hoop_spacing_max_hinge(d, db_long_min, dstirrup) if is_smf else stirrup_spacing_max_outside_hinge(d, dstirrup)
        s_out_max = stirrup_spacing_max_outside_hinge(d, dstirrup)

        shear = {}
        lines = ["NSCP 2015 Sec 422.5 (Shear) / 421.6.4-421.6.5 (Seismic shear & hoops)",
                 f"Plastic hinge region length (2h from face of support) = {hinge_len:,.0f} mm",
                 f"Max hoop spacing IN hinge region  = {s_hinge_max:,.1f} mm  "
                 f"(min of d/4, 8*db_long, 24*db_hoop, 300mm)" if is_smf else
                 f"Max stirrup spacing (no seismic hinge requirement, OMF) = {s_hinge_max:,.1f} mm",
                 f"Max stirrup spacing OUTSIDE hinge region = {s_out_max:,.1f} mm", ""]
        for loc, Vu in (("Left", p["Vu_left"]), ("Right", p["Vu_right"])):
            seismic_zero = is_smf and p["seismic_shear_governs"]
            Vc = Vc_concrete(b, d, fc, seismic_zero=seismic_zero)
            s_req = stirrup_spacing_required(Vu, Vc, d, fy, Av)
            if s_req is None:
                s_final_hinge = s_hinge_max
            else:
                s_final_hinge = min(s_req, s_hinge_max)
            s_final_hinge = max(50.0, math.floor(s_final_hinge / 5.0) * 5.0)  # round down to 5mm, floor 50mm
            s_final_out = s_out_max if s_req is None else max(50.0, math.floor(min(s_req, s_out_max) / 5.0) * 5.0)
            shear[loc] = dict(Vu=Vu, Vc=Vc / 1e3, s_req=s_req, s_hinge=s_final_hinge, s_out=s_final_out,
                               seismic_zero=seismic_zero)
            lines.append(
                f"[{loc} end] Vu={Vu:6.1f} kN   Vc={Vc/1e3:6.1f} kN "
                f"{'(=0, seismic hinge rule governs)' if seismic_zero else ''}  "
                f"-> hoops @ {shear[loc]['s_hinge']:.0f} mm (hinge zone), "
                f"stirrups @ {shear[loc]['s_out']:.0f} mm (elsewhere)"
            )
        self._add_log("SHEAR DESIGN", lines)
        self.results["shear"] = shear
        self.results["hinge_len"] = hinge_len
        self.results["Av"] = Av

        # ---- 3. Seismic detailing checks (SMF only) ----
        if is_smf:
            lines = ["NSCP 2015 Sec 421.6.3 / ACI 318-14 18.6.3 -- Longitudinal reinforcement limits", ""]

            # (a) min 2 continuous top & bottom bars
            min_bars_ok = all(flex[s][sign]["n"] >= 2 for s in sections for sign in ("neg", "pos"))
            self._add_check("Minimum 2 continuous top AND bottom bars at every section",
                             min_bars_ok, "ACI 318-14 18.6.3.1 / NSCP 421.6.3.1")

            # (b) As within [As_min, As_max] wherever steel is required
            asrange_ok = True
            for s in sections:
                for sign in ("neg", "pos"):
                    As_prov = flex[s][sign]["As_prov"]
                    if As_prov < As_min - 1e-6 or As_prov > As_max + 1e-6:
                        asrange_ok = False
            self._add_check("As,provided within [As,min , As,max=0.025bd] at all sections",
                             asrange_ok, "ACI 318-14 18.6.3.1 / NSCP 421.6.3.1")

            # (c) positive Mn at joint face >= 0.5 * negative Mn at that face
            for s in ("Left Support", "Right Support"):
                Mn_pos = flex[s]["pos"]["phiMn"]
                Mn_neg = flex[s]["neg"]["phiMn"]
                ok = Mn_pos >= 0.5 * Mn_neg - 1e-6
                self._add_check(f"{s}: +Mn ({Mn_pos:.1f}) >= 0.5 x -Mn ({0.5*Mn_neg:.1f}) kN-m",
                                 ok, "ACI 318-14 18.6.3.2 / NSCP 421.6.3.2")

            # (d) Mn (either sign) at any section >= 0.25 * max Mn at either joint face
            end_moments = [flex["Left Support"]["neg"]["phiMn"], flex["Left Support"]["pos"]["phiMn"],
                           flex["Right Support"]["neg"]["phiMn"], flex["Right Support"]["pos"]["phiMn"]]
            Mn_max_end = max(end_moments)
            threshold = 0.25 * Mn_max_end
            mid_pos = flex["Midspan"]["pos"]["phiMn"]
            mid_neg = flex["Midspan"]["neg"]["phiMn"]
            ok = (mid_pos >= threshold - 1e-6) and (mid_neg >= threshold - 1e-6 if mid_neg > 0 else True)
            self._add_check(f"Midspan Mn >= 0.25 x max end Mn ({threshold:.1f} kN-m)",
                             ok, "ACI 318-14 18.6.3.2 / NSCP 421.6.3.2")

            # (e) first hoop within 50mm of face of support
            self._add_check("First hoop located within 50 mm of face of support (each end)",
                             True, "ACI 318-14 18.6.4.2 / NSCP 421.6.4.2 (enforced by detailing output)")

            # (f) hoop spacing check within hinge zone
            hoop_ok = all(shear[loc]["s_hinge"] <= s_hinge_max + 1e-6 for loc in ("Left", "Right"))
            self._add_check(f"Hoop spacing within plastic hinge region <= {s_hinge_max:.0f} mm",
                             hoop_ok, "ACI 318-14 18.6.4.4 / NSCP 421.6.4.4")

            # (g) lap splice restriction (informational / enforced by note in report)
            self._add_check("Lap splices located outside hinge zones, joints, and >= 2h from face of support",
                             True, "ACI 318-14 18.6.3.3 / NSCP 421.6.3.3 (must be enforced in detailing/shop drawings)")

            self._add_log("SEISMIC DETAILING CHECKS (SMF)", lines)
        else:
            self._add_log("SEISMIC DETAILING CHECKS",
                           ["Ordinary Moment Frame (OMF) selected -- special seismic detailing",
                            "of Sec 421.6 is NOT mandatory. Standard NSCP 2015 Chapter 4",
                            "shear/flexure provisions apply only."])

        self.results["is_smf"] = is_smf


# ==============================================================================
# 4. MAIN APPLICATION (Tkinter GUI)
# ==============================================================================

class BeamDesignApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NSCP 2015 RC Beam Design Tool (with Seismic Detailing)")
        self.geometry("1360x820")
        self.minsize(1150, 700)

        self.design = None  # last BeamDesign result

        self._build_layout()
        self._set_defaults()

    # ------------------------------------------------------------------ UI
    def _build_layout(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- left: scrollable input panel ----
        left_container = ttk.Frame(main, width=380)
        left_container.pack(side="left", fill="y", padx=(0, 6))
        left_container.pack_propagate(False)

        canvas = tk.Canvas(left_container, highlightthickness=0)
        vsb = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        self.left = ttk.Frame(canvas)
        self.left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.left, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.vars = {}
        self._build_geometry_frame()
        self._build_materials_frame()
        self._build_loads_frame()
        self._build_seismic_frame()
        self._build_bars_frame()
        self._build_buttons()

        # ---- right: tabbed results / visualizations ----
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)

        self.tab_summary = ttk.Frame(self.tabs)
        self.tab_2d = ttk.Frame(self.tabs)
        self.tab_3d = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_summary, text="Results Summary")
        self.tabs.add(self.tab_2d, text="2D View")
        self.tabs.add(self.tab_3d, text="3D View")

        self.txt_summary = scrolledtext.ScrolledText(self.tab_summary, wrap="word",
                                                       font=("Consolas", 10))
        self.txt_summary.pack(fill="both", expand=True)

        self.fig2d = Figure(figsize=(8, 7), dpi=100)
        self.canvas2d = FigureCanvasTkAgg(self.fig2d, master=self.tab_2d)
        self.canvas2d.get_tk_widget().pack(fill="both", expand=True)

        self.fig3d = Figure(figsize=(8, 7), dpi=100)
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=self.tab_3d)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

    def _labeled_entry(self, parent, label, key, default, width=10):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2, padx=4)
        ttk.Label(row, text=label, width=26).pack(side="left")
        var = tk.StringVar(value=str(default))
        ent = ttk.Entry(row, textvariable=var, width=width)
        ent.pack(side="left")
        self.vars[key] = var
        return ent

    def _build_geometry_frame(self):
        f = ttk.LabelFrame(self.left, text="1. Beam Geometry (mm)")
        f.pack(fill="x", padx=4, pady=4)
        self._labeled_entry(f, "Width, b", "b", 300)
        self._labeled_entry(f, "Overall depth, h", "h", 500)
        self._labeled_entry(f, "Effective depth, d", "d", 440)
        self._labeled_entry(f, "Clear cover", "cover", 40)
        self._labeled_entry(f, "Clear span, Ln", "ln", 6000)

    def _build_materials_frame(self):
        f = ttk.LabelFrame(self.left, text="2. Material Properties (MPa)")
        f.pack(fill="x", padx=4, pady=4)
        self._labeled_entry(f, "f'c (concrete)", "fc", 27.6)
        self._labeled_entry(f, "fy (main steel)", "fy", 414)
        self._labeled_entry(f, "fyt (stirrup steel)", "fyt", 275)

    def _build_loads_frame(self):
        f = ttk.LabelFrame(self.left, text="3. Factored Loads (Mu: kN-m, Vu: kN)")
        f.pack(fill="x", padx=4, pady=4)
        ttk.Label(f, text="(+M = bottom tension, -M = top tension)",
                  font=("", 8, "italic")).pack(anchor="w", padx=4)
        self._labeled_entry(f, "M(-) Left support", "M_left_neg", 220)
        self._labeled_entry(f, "M(+) Left support", "M_left_pos", 90)
        self._labeled_entry(f, "M(+) Midspan", "M_mid_pos", 160)
        self._labeled_entry(f, "M(-) Midspan", "M_mid_neg", 0)
        self._labeled_entry(f, "M(-) Right support", "M_right_neg", 210)
        self._labeled_entry(f, "M(+) Right support", "M_right_pos", 95)
        self._labeled_entry(f, "Vu Left end", "Vu_left", 240)
        self._labeled_entry(f, "Vu Right end", "Vu_right", 235)

    def _build_seismic_frame(self):
        f = ttk.LabelFrame(self.left, text="4. Seismic Category")
        f.pack(fill="x", padx=4, pady=4)
        row = ttk.Frame(f)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Frame type", width=26).pack(side="left")
        self.vars["seismic_cat"] = tk.StringVar(value="SMF (Special Moment Frame)")
        cb = ttk.Combobox(row, textvariable=self.vars["seismic_cat"], state="readonly", width=24,
                           values=["SMF (Special Moment Frame)", "OMF (Ordinary Moment Frame)"])
        cb.pack(side="left")

        row2 = ttk.Frame(f)
        row2.pack(fill="x", padx=4, pady=2)
        self.vars["seismic_shear_governs"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Earthquake shear >= 1/2 of Vu in hinge zone\n(triggers Vc = 0 rule)",
                         variable=self.vars["seismic_shear_governs"]).pack(anchor="w")

    def _build_bars_frame(self):
        f = ttk.LabelFrame(self.left, text="5. Bar Selection")
        f.pack(fill="x", padx=4, pady=4)
        row = ttk.Frame(f)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Longitudinal bar dia (mm)", width=26).pack(side="left")
        self.vars["dbar"] = tk.StringVar(value="25")
        ttk.Combobox(row, textvariable=self.vars["dbar"], state="readonly", width=8,
                     values=[str(x) for x in BAR_SIZES]).pack(side="left")

        row2 = ttk.Frame(f)
        row2.pack(fill="x", padx=4, pady=2)
        ttk.Label(row2, text="Stirrup/hoop bar dia (mm)", width=26).pack(side="left")
        self.vars["dstirrup"] = tk.StringVar(value="10")
        ttk.Combobox(row2, textvariable=self.vars["dstirrup"], state="readonly", width=8,
                     values=[str(x) for x in BAR_SIZES]).pack(side="left")

    def _build_buttons(self):
        f = ttk.Frame(self.left)
        f.pack(fill="x", padx=4, pady=10)
        ttk.Button(f, text="Calculate / Design", command=self.on_calculate).pack(fill="x", pady=2)
        ttk.Button(f, text="Reset to Defaults", command=self._set_defaults).pack(fill="x", pady=2)
        ttk.Button(f, text="Export Report (.txt)", command=self.on_export).pack(fill="x", pady=2)

    def _set_defaults(self):
        defaults = dict(b=300, h=500, d=440, cover=40, ln=6000, fc=27.6, fy=414, fyt=275,
                         M_left_neg=220, M_left_pos=90, M_mid_pos=160, M_mid_neg=0,
                         M_right_neg=210, M_right_pos=95, Vu_left=240, Vu_right=235,
                         dbar="25", dstirrup="10")
        for k, v in defaults.items():
            if k in self.vars:
                self.vars[k].set(str(v))
        self.vars["seismic_cat"].set("SMF (Special Moment Frame)")
        self.vars["seismic_shear_governs"].set(True)

    # ------------------------------------------------------------- actions
    def _read_inputs(self):
        try:
            p = {
                "b": float(self.vars["b"].get()),
                "h": float(self.vars["h"].get()),
                "d": float(self.vars["d"].get()),
                "cover": float(self.vars["cover"].get()),
                "ln": float(self.vars["ln"].get()),
                "fc": float(self.vars["fc"].get()),
                "fy": float(self.vars["fy"].get()),
                "fyt": float(self.vars["fyt"].get()),
                "M_left_neg": float(self.vars["M_left_neg"].get()),
                "M_left_pos": float(self.vars["M_left_pos"].get()),
                "M_mid_pos": float(self.vars["M_mid_pos"].get()),
                "M_mid_neg": float(self.vars["M_mid_neg"].get()),
                "M_right_neg": float(self.vars["M_right_neg"].get()),
                "M_right_pos": float(self.vars["M_right_pos"].get()),
                "Vu_left": float(self.vars["Vu_left"].get()),
                "Vu_right": float(self.vars["Vu_right"].get()),
                "seismic_cat": self.vars["seismic_cat"].get(),
                "seismic_shear_governs": self.vars["seismic_shear_governs"].get(),
                "dbar": int(self.vars["dbar"].get()),
                "dstirrup": int(self.vars["dstirrup"].get()),
            }
        except ValueError as e:
            raise ValueError(f"Please enter valid numeric values for all fields.\n({e})")

        if p["d"] >= p["h"]:
            raise ValueError("Effective depth d must be less than overall depth h.")
        if p["b"] <= 0 or p["h"] <= 0 or p["d"] <= 0:
            raise ValueError("Geometry values must be positive.")
        if p["fc"] <= 0 or p["fy"] <= 0:
            raise ValueError("Material strengths must be positive.")
        # fy used consistently for main bars; shear uses fyt
        p["fy_shear"] = p["fyt"]
        return p

    def on_calculate(self):
        try:
            p = self._read_inputs()
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return

        # use fyt for stirrup calcs
        design_inputs = dict(p)
        try:
            design = BeamDesign(design_inputs)
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Design failed:\n{e}")
            return

        self.design = design
        self._render_summary()
        self._render_2d()
        self._render_3d()
        self.tabs.select(self.tab_summary)

    def on_export(self):
        if self.design is None:
            messagebox.showwarning("No Results", "Run 'Calculate / Design' first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text file", "*.txt")],
                                             initialfile="NSCP2015_Beam_Design_Report.txt")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fobj:
            fobj.write(self.txt_summary.get("1.0", "end"))
        messagebox.showinfo("Exported", f"Report saved to:\n{path}")

    # -------------------------------------------------------- render: text
    def _render_summary(self):
        d = self.design
        p = d.inp
        out = []
        out.append("=" * 78)
        out.append(" NSCP 2015 REINFORCED CONCRETE BEAM DESIGN REPORT")
        out.append(f" Generated: {datetime.datetime.now():%Y-%m-%d %H:%M}")
        out.append("=" * 78)
        out.append("")
        out.append("INPUT SUMMARY")
        out.append("-" * 78)
        out.append(f"  b x h = {p['b']:.0f} x {p['h']:.0f} mm,  d = {p['d']:.0f} mm,  cover = {p['cover']:.0f} mm,"
                    f"  Ln = {p['ln']:.0f} mm")
        out.append(f"  f'c = {p['fc']:.1f} MPa,  fy = {p['fy']:.0f} MPa,  fyt = {p['fyt']:.0f} MPa")
        out.append(f"  Seismic category: {p['seismic_cat']}")
        out.append(f"  Long. bar: {p['dbar']} mm dia   |   Stirrup/hoop bar: {p['dstirrup']} mm dia")
        out.append("")

        for title, lines in d.log:
            out.append(title)
            out.append("-" * 78)
            out.extend(["  " + ln for ln in lines])
            out.append("")

        out.append("SEISMIC DETAILING CHECKLIST")
        out.append("-" * 78)
        if d.checks:
            for desc, passed, remark in d.checks:
                mark = "PASS" if passed else "FAIL"
                out.append(f"  [{mark}] {desc}")
                if remark:
                    out.append(f"          ref: {remark}")
        else:
            out.append("  (No seismic checks applicable -- OMF selected.)")
        out.append("")

        out.append("FINAL RECOMMENDED REINFORCEMENT")
        out.append("-" * 78)
        flex = d.results["flex"]
        for sec in ("Left Support", "Midspan", "Right Support"):
            top = flex[sec]["neg"]
            bot = flex[sec]["pos"]
            out.append(f"  {sec}:")
            out.append(f"      Top    : {top['n']}-{p['dbar']}mm  (As,prov={top['As_prov']:.0f} mm^2, "
                        f"phiMn={top['phiMn']:.1f} kN-m, DCR={top['dcr']:.2f})")
            out.append(f"      Bottom : {bot['n']}-{p['dbar']}mm  (As,prov={bot['As_prov']:.0f} mm^2, "
                        f"phiMn={bot['phiMn']:.1f} kN-m, DCR={bot['dcr']:.2f})")
        shear = d.results["shear"]
        hinge_len = d.results["hinge_len"]
        out.append("")
        out.append(f"  Stirrups/Hoops ({p['dstirrup']}mm dia, 2-legged):")
        for loc in ("Left", "Right"):
            s = shear[loc]
            out.append(f"      {loc} end: {p['dstirrup']}mm hoops @ {s['s_hinge']:.0f} mm o.c. "
                        f"within {hinge_len:.0f} mm of face of support,")
            out.append(f"                 then {p['dstirrup']}mm stirrups @ {s['s_out']:.0f} mm o.c. elsewhere")
        out.append("      First hoop/stirrup placed within 50 mm of face of support (each end).")
        out.append("")
        out.append("NOTE: Lap splices, if required, must be located outside the plastic hinge")
        out.append("      regions, away from joint faces, and per NSCP 2015 Sec 421.6.3.3 /")
        out.append("      ACI 318-14 18.6.3.3, with closed hoops through the splice length.")
        out.append("")
        out.append("=" * 78)
        out.append("DISCLAIMER: Drafting aid only -- verify against full NSCP 2015 code text")
        out.append("and have all designs checked/sealed by a licensed structural engineer.")
        out.append("=" * 78)

        self.txt_summary.delete("1.0", "end")
        self.txt_summary.insert("1.0", "\n".join(out))

    # --------------------------------------------------------- render: 2D
    def _render_2d(self):
        d = self.design
        p = d.inp
        b, h, dd, cover = p["b"], p["h"], p["d"], p["cover"]
        dbar, dstir = p["dbar"], p["dstirrup"]
        ln = p["ln"]
        flex = d.results["flex"]
        shear = d.results["shear"]
        hinge_len = d.results["hinge_len"]

        self.fig2d.clear()
        ax_sec = self.fig2d.add_subplot(211)
        ax_elev = self.fig2d.add_subplot(212)

        # ---- Cross-section (use Midspan bar counts as representative) ----
        n_top = flex["Midspan"]["neg"]["n"] if flex["Midspan"]["neg"]["n"] else 2
        n_bot = flex["Midspan"]["pos"]["n"]
        n_top = max(n_top, 2)
        n_bot = max(n_bot, 2)

        ax_sec.add_patch(mpatches.Rectangle((0, 0), b, h, fill=False, edgecolor="black", linewidth=1.6))
        # stirrup outline
        ax_sec.add_patch(mpatches.Rectangle((cover, cover), b - 2 * cover, h - 2 * cover,
                                             fill=False, edgecolor="tab:blue", linewidth=1.2))
        # top bars
        y_top = h - cover - dstir - dbar / 2.0
        xs_top = np.linspace(cover + dstir + dbar / 2.0, b - cover - dstir - dbar / 2.0, n_top) if n_top > 1 else [b / 2]
        for x in xs_top:
            ax_sec.add_patch(mpatches.Circle((x, y_top), dbar / 2.0, color="tab:red"))
        # bottom bars
        y_bot = cover + dstir + dbar / 2.0
        xs_bot = np.linspace(cover + dstir + dbar / 2.0, b - cover - dstir - dbar / 2.0, n_bot) if n_bot > 1 else [b / 2]
        for x in xs_bot:
            ax_sec.add_patch(mpatches.Circle((x, y_bot), dbar / 2.0, color="tab:red"))

        ax_sec.set_xlim(-40, b + 40)
        ax_sec.set_ylim(-40, h + 40)
        ax_sec.set_aspect("equal")
        ax_sec.set_title(f"Cross-Section (Midspan): {n_top}-{dbar}mm top, {n_bot}-{dbar}mm bottom, "
                          f"{dstir}mm hoops", fontsize=9)
        ax_sec.text(b / 2, -30, f"b = {b:.0f} mm", ha="center", va="top", fontsize=8)
        ax_sec.text(-30, h / 2, f"h = {h:.0f} mm", ha="right", va="center", fontsize=8, rotation=90)
        ax_sec.axis("off")

        # ---- Elevation ----
        ax_elev.add_patch(mpatches.Rectangle((0, 0), ln, h * 0.25, fill=False, edgecolor="black"))
        # shade hinge zones
        ax_elev.add_patch(mpatches.Rectangle((0, 0), hinge_len, h * 0.25,
                                              color="tab:orange", alpha=0.25))
        ax_elev.add_patch(mpatches.Rectangle((ln - hinge_len, 0), hinge_len, h * 0.25,
                                              color="tab:orange", alpha=0.25))
        ax_elev.text(hinge_len / 2, h * 0.25 + 15, "Hinge zone\n(Left)", ha="center", fontsize=7)
        ax_elev.text(ln - hinge_len / 2, h * 0.25 + 15, "Hinge zone\n(Right)", ha="center", fontsize=7)

        # draw stirrup tick marks
        def ticks(x0, x1, spacing):
            xs = []
            x = x0
            while x <= x1:
                xs.append(x)
                x += spacing
            return xs

        s_left_hinge = shear["Left"]["s_hinge"]
        s_right_hinge = shear["Right"]["s_hinge"]
        s_mid = max(shear["Left"]["s_out"], shear["Right"]["s_out"])

        tick_x = []
        tick_x += ticks(0, hinge_len, s_left_hinge)
        tick_x += ticks(hinge_len, ln - hinge_len, s_mid)
        tick_x += ticks(ln - hinge_len, ln, s_right_hinge)
        tick_x = sorted(set(min(max(x, 0), ln) for x in tick_x))
        for x in tick_x:
            ax_elev.plot([x, x], [0, h * 0.25], color="tab:blue", linewidth=0.8)

        ax_elev.set_xlim(-ln * 0.03, ln * 1.03)
        ax_elev.set_ylim(-h * 0.35, h * 0.55)
        ax_elev.set_title("Longitudinal Elevation - Hoop/Stirrup Layout "
                           "(orange = plastic hinge region)", fontsize=9)
        ax_elev.set_xlabel("Length along beam (mm)")
        ax_elev.set_yticks([])

        self.fig2d.tight_layout()
        self.canvas2d.draw()

    # --------------------------------------------------------- render: 3D
    def _render_3d(self):
        d = self.design
        p = d.inp
        b, h, dd, cover = p["b"], p["h"], p["d"], p["cover"]
        dbar, dstir = p["dbar"], p["dstirrup"]
        ln = p["ln"]
        flex = d.results["flex"]
        shear = d.results["shear"]
        hinge_len = d.results["hinge_len"]

        self.fig3d.clear()
        ax = self.fig3d.add_subplot(111, projection="3d")

        # ---- concrete box (semi-transparent) ----
        x0, x1 = 0, ln
        y0, y1 = -b / 2, b / 2
        z0, z1 = 0, h
        v = np.array([
            [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
        ])
        faces = [
            [v[0], v[1], v[2], v[3]],  # bottom
            [v[4], v[5], v[6], v[7]],  # top
            [v[0], v[1], v[5], v[4]],  # front
            [v[2], v[3], v[7], v[6]],  # back
            [v[1], v[2], v[6], v[5]],  # right
            [v[0], v[3], v[7], v[4]],  # left
        ]
        box = Poly3DCollection(faces, facecolor="lightgray", edgecolor="gray",
                                linewidths=0.5, alpha=0.18)
        ax.add_collection3d(box)

        # ---- longitudinal bars ----
        n_top = max(flex["Midspan"]["neg"]["n"], 2)
        n_bot = max(flex["Midspan"]["pos"]["n"], 2)
        z_top = h - cover - dstir - dbar / 2.0
        z_bot = cover + dstir + dbar / 2.0
        ys_top = np.linspace(y0 + cover + dstir + dbar / 2.0, y1 - cover - dstir - dbar / 2.0, n_top) \
            if n_top > 1 else [0.0]
        ys_bot = np.linspace(y0 + cover + dstir + dbar / 2.0, y1 - cover - dstir - dbar / 2.0, n_bot) \
            if n_bot > 1 else [0.0]

        for y in ys_top:
            ax.plot([x0, x1], [y, y], [z_top, z_top], color="tab:red", linewidth=2)
        for y in ys_bot:
            ax.plot([x0, x1], [y, y], [z_bot, z_bot], color="tab:red", linewidth=2)

        # ---- stirrup / hoop loops ----
        def hoop_positions(x0_, x1_, spacing):
            xs = []
            x = x0_
            while x <= x1_:
                xs.append(x)
                x += spacing
            return xs

        xs_hoops = []
        xs_hoops += hoop_positions(0, hinge_len, shear["Left"]["s_hinge"])
        xs_hoops += hoop_positions(hinge_len, ln - hinge_len,
                                    max(shear["Left"]["s_out"], shear["Right"]["s_out"]))
        xs_hoops += hoop_positions(ln - hinge_len, ln, shear["Right"]["s_hinge"])
        xs_hoops = sorted(set(min(max(x, 0), ln) for x in xs_hoops))

        yy0, yy1 = y0 + cover, y1 - cover
        zz0, zz1 = z0 + cover, z1 - cover
        for x in xs_hoops:
            loop_y = [yy0, yy1, yy1, yy0, yy0]
            loop_z = [zz0, zz0, zz1, zz1, zz0]
            loop_x = [x] * 5
            ax.plot(loop_x, loop_y, loop_z, color="tab:blue", linewidth=0.8)

        ax.set_xlabel("Length (mm)")
        ax.set_ylabel("Width (mm)")
        ax.set_zlabel("Depth (mm)")
        ax.set_title(f"3D Beam Model  |  {n_top}-{dbar}mm top, {n_bot}-{dbar}mm bottom, "
                      f"{dstir}mm hoops", fontsize=9)
        ax.set_box_aspect((ln / h, b / h, 1))  # roughly true proportions
        try:
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0 - 50, y1 + 50)
            ax.set_zlim(z0 - 50, z1 + 50)
        except Exception:
            pass

        self.fig3d.tight_layout()
        self.canvas3d.draw()


# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    app = BeamDesignApp()
    app.mainloop()