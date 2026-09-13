#!/usr/bin/env python3
# =============================================================================
#  REINFORCED CONCRETE BEAM DESIGNER  --  NSCP 2015 (Strength Design Method)
# -----------------------------------------------------------------------------
#  A single-file Tkinter desktop application for the preliminary design and
#  code-check of a rectangular, singly-reinforced concrete beam, including a
#  dimensioned cross-section view and an isometric 3D rebar-cage view.
#
#  Governing document: National Structural Code of the Philippines (NSCP) 2015,
#  Volume 1, Section 4 - "Structural Concrete" (mirrors ACI 318-14; section
#  numbers generally follow "4" + ACI chapter number, e.g. NSCP 409 <-> ACI
#  Ch.9 (Beams), NSCP 410 <-> ACI Ch.10 (Flexure/Axial), NSCP 421 <-> ACI
#  Ch.21 (Strength Reduction Factors), NSCP 422 <-> ACI Ch.22 (Sectional
#  Strength), NSCP 425 <-> ACI Ch.25 (Reinforcement Detailing)).
#
#  *** ENGINEERING DISCLAIMER ***
#  This program is an educational / preliminary CALCULATION AID ONLY. It uses
#  simplified span/support coefficients, code checks, and schematic (not to
#  fabrication tolerance) drawings. It is NOT a substitute for a complete
#  structural analysis and design performed and sealed by a duly licensed
#  Professional/Structural Civil Engineer. All results MUST be independently
#  verified before use in any construction document.
#
#  Dependencies:
#    - Python 3 standard library (tkinter, math, datetime) -- required.
#    - matplotlib (for the Cross-Section and 3D View tabs only) -- optional.
#      If matplotlib is not installed, the app still runs and the report tab
#      works normally; the two visualization tabs show install instructions
#      instead of a drawing.
# =============================================================================

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# --- Optional visualization dependency -------------------------------------
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.patches
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3D projection)
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# =============================================================================
# SECTION 1: ENGINEERING CONSTANTS AND REFERENCE DATA
# =============================================================================

ES = 200000.0                   # Modulus of elasticity of steel, MPa (NSCP 2015 420.2.2.2)
UNIT_WEIGHT_CONCRETE = 24.0      # kN/m^3, normal weight concrete (used for self-weight)
ECU = 0.003                      # Ultimate concrete strain (NSCP 2015 422.2.2.1)
LAYER_GAP = 25.0                 # mm, clear vertical spacing assumed between bar layers (425.2.2)

# Standard metric reinforcing bar sizes ("M" designation commonly referenced
# in local practice). diameter (mm) and cross-sectional area (mm^2).
BAR_DATA = {
    "10M": {"db": 11.3, "area": 100.0},
    "15M": {"db": 16.0, "area": 200.0},
    "20M": {"db": 19.5, "area": 300.0},
    "25M": {"db": 25.2, "area": 500.0},
    "30M": {"db": 29.9, "area": 700.0},
    "35M": {"db": 35.7, "area": 1000.0},
}
BAR_LIST = list(BAR_DATA.keys())

# Approximate moment/shear coefficients (M = wu*Ln^2/n) based on the ACI/NSCP
# approximate frame-analysis coefficients (NSCP 2015 Sec. 406.5). Simplified,
# single-span idealizations used here for preliminary design purposes.
SUPPORT_CONDITIONS = {
    "Simply Supported": {
        "Mpos": 8.0, "Mneg": None, "Vcoeff": 1.0, "left": "pin", "right": "roller",
        "desc": "M(+) = wuLn^2/8 ; V = wuLn/2"
    },
    "Cantilever": {
        "Mpos": None, "Mneg": 2.0, "Vcoeff": 1.0, "left": "fixed", "right": "free",
        "desc": "M(-) at support = wuLn^2/2 ; V = wuLn"
    },
    "One End Continuous": {
        "Mpos": 14.0, "Mneg": 10.0, "Vcoeff": 1.15, "left": "pin", "right": "continuous",
        "desc": "M(+) = wuLn^2/14 ; M(-) = wuLn^2/10 ; V = 1.15wuLn/2"
    },
    "Both Ends Continuous": {
        "Mpos": 16.0, "Mneg": 11.0, "Vcoeff": 1.0, "left": "continuous", "right": "continuous",
        "desc": "M(+) = wuLn^2/16 ; M(-) = wuLn^2/11 ; V = wuLn/2"
    },
}


# =============================================================================
# SECTION 2: CORE ENGINEERING CALCULATIONS
# =============================================================================

def beta1_factor(fc):
    """
    NSCP 2015 Sec. 422.2.2.4.3 (equiv. ACI 318-14 22.2.2.4.3):
    beta1 = 0.85 for f'c <= 28 MPa
    beta1 = 0.85 - 0.05*(f'c-28)/7, not less than 0.65, for f'c > 28 MPa
    """
    if fc <= 28.0:
        return 0.85
    b1 = 0.85 - 0.05 * (fc - 28.0) / 7.0
    return max(b1, 0.65)


def phi_flexure(et, fy):
    """
    Strength reduction factor for flexure (tension-controlled/transition/
    compression-controlled), per NSCP 2015 Sec. 421.2.2 (Table 421.2.2),
    for members with tied (non-spiral) transverse reinforcement.
    """
    ety = fy / ES  # strain at yield of tension steel
    if et >= 0.005:
        return 0.90                                   # Tension-controlled
    elif et <= ety:
        return 0.65                                   # Compression-controlled
    else:
        return 0.65 + (et - ety) * 0.25 / (0.005 - ety)  # Transition zone


def effective_depth(h, cover, stirrup_db, bar_db, layers):
    """
    Compute effective depth 'd' (to centroid of tension steel) and 'dt'
    (to extreme tension layer, used for strain checks), for 1 or 2 layers
    of main bars. Assumes LAYER_GAP clear vertical spacing between bar
    layers (NSCP 2015 Sec. 425.2.2).
    """
    layer1 = h - cover - stirrup_db - bar_db / 2.0     # centroid of layer nearest tension face
    if layers == 1:
        return layer1, layer1
    layer2 = layer1 - (bar_db + LAYER_GAP)              # centroid of 2nd layer
    d = (layer1 + layer2) / 2.0
    dt = layer1
    return d, dt


def flexural_design(Mu_kNm, b, d, dt, fc, fy):
    """
    Design flexural (tension) reinforcement for a rectangular section using
    the NSCP 2015 strength design method (equiv. ACI 318-14 Ch. 22 nominal
    strength + Ch. 9/10 provisions for beams).

    Mu_kNm : factored moment (kN-m), always a positive magnitude
    b, d, dt : mm ;  fc, fy : MPa
    """
    beta1 = beta1_factor(fc)
    As_min = max(1.4 * b * d / fy,
                 (math.sqrt(fc) / 4.0) * b * d / fy)    # NSCP 2015 Sec. 409.6.1.2

    if Mu_kNm <= 0:
        return {
            "Mu": 0, "As_req": 0, "As_min": As_min, "As_final": As_min,
            "phi": 0.90, "et": 1.0, "c": 0, "a": 0, "beta1": beta1,
            "As_max_004": None, "status": "N/A (no moment)", "notes": []
        }

    Mu_Nmm = Mu_kNm * 1.0e6
    notes = []

    phi = 0.90
    As = As_min
    c = a = et = 0.0
    rho = 0.0
    for _ in range(25):
        Ru = Mu_Nmm / (phi * b * d ** 2)
        discriminant = 1.0 - (2.0 * Ru) / (0.85 * fc)
        if discriminant < 0:
            return {
                "Mu": Mu_kNm, "As_req": None, "As_min": As_min, "As_final": None,
                "phi": phi, "et": None, "c": None, "a": None, "beta1": beta1,
                "As_max_004": None, "status": "FAIL - section too small (Ru exceeds capacity)",
                "notes": ["Increase beam width/depth or increase f'c."]
            }
        rho = (0.85 * fc / fy) * (1.0 - math.sqrt(discriminant))
        As_req = rho * b * d
        As = max(As_req, As_min)
        a = As * fy / (0.85 * fc * b)
        c = a / beta1
        et = ECU * (dt - c) / c if c > 0 else 1.0
        phi_new = phi_flexure(et, fy)
        if abs(phi_new - phi) < 1.0e-4:
            phi = phi_new
            break
        phi = phi_new

    if As_min > rho * b * d:
        notes.append("Minimum reinforcement (NSCP 2015 409.6.1.2) governs over As required by strength.")

    # Maximum reinforcement check: minimum net tensile strain = 0.004
    # (NSCP 2015 Sec. 410.4.4, non-prestressed flexural members)
    c_004 = (ECU / (ECU + 0.004)) * dt
    a_004 = beta1 * c_004
    As_max_004 = 0.85 * fc * a_004 * b / fy

    if As > As_max_004:
        status = "FAIL - section over-reinforced (et < 0.004); enlarge section or add compression steel"
    elif et < 0.004:
        status = "FAIL - net tensile strain < 0.004 (NSCP 2015 410.4.4)"
    else:
        status = "OK"

    return {
        "Mu": Mu_kNm, "As_req": As, "As_min": As_min, "As_final": As,
        "phi": phi, "et": et, "c": c, "a": a, "beta1": beta1,
        "As_max_004": As_max_004, "status": status, "notes": notes
    }


def bar_layout(b, cover, stirrup_db, bar_db, n, layers):
    """
    Returns a list of (x, y_from_face) tuples for the reinforcing bars in a
    tension steel group, where y_from_face is measured from the concrete
    face nearest that steel group (i.e. the bottom face for bottom steel, or
    the top face for top steel). x is measured from the left face of the
    beam. Used both for spacing checks and for drawing.
    """
    avail_width = b - 2 * cover - 2 * stirrup_db
    if layers == 1:
        counts = [n]
    else:
        n1 = math.ceil(n / 2)
        counts = [n1, n - n1]

    coords = []
    for i, cnt in enumerate(counts):
        y = cover + stirrup_db + bar_db / 2.0 + i * (bar_db + LAYER_GAP)
        if cnt <= 0:
            continue
        if cnt == 1:
            xs = [b / 2.0]
        else:
            start = cover + stirrup_db + bar_db / 2.0
            end = b - start
            xs = [start + j * (end - start) / (cnt - 1) for j in range(cnt)]
        for x in xs:
            coords.append((x, y))
    return coords


def select_bars(As_final, b, cover, stirrup_db, bar_key, h):
    """
    Selects the number of main bars (single bar size) required to provide at
    least As_final, checking whether they fit in one layer (else 2 layers),
    per minimum clear-spacing rules of NSCP 2015 Sec. 425.2.1:
        clear spacing >= max(db, 25 mm)

    bar_key : bar size designation string (e.g. "20M").
    stirrup_db : stirrup bar diameter in mm.
    """
    bar_area = BAR_DATA[bar_key]["area"]
    db = BAR_DATA[bar_key]["db"]
    n = max(2, math.ceil(As_final / bar_area))          # min. 2 bars for a beam
    min_clear = max(db, 25.0)

    avail_width = b - 2 * cover - 2 * stirrup_db
    max_per_layer = int((avail_width + min_clear) // (db + min_clear))
    max_per_layer = max(max_per_layer, 1)

    if n <= max_per_layer:
        layers = 1
        clear_spacing = (avail_width - n * db) / (n - 1) if n > 1 else avail_width - db
        fits = clear_spacing >= min_clear - 1e-6
    else:
        layers = 2
        n1 = math.ceil(n / 2)
        clear_spacing = (avail_width - n1 * db) / (n1 - 1) if n1 > 1 else avail_width - db
        fits = clear_spacing >= min_clear - 1e-6 and n1 <= max_per_layer

    As_prov = n * bar_area
    coords = bar_layout(b, cover, stirrup_db, db, n, layers)
    return {
        "n": n, "bar": bar_key, "db": db, "As_prov": As_prov, "layers": layers,
        "clear_spacing": clear_spacing, "fits": fits, "min_clear_req": min_clear,
        "coords": coords
    }


def shear_design(Vu_kN, b, d, fc, fy, stirrup_db_key):
    """
    Shear design per NSCP 2015 Sec. 422.5 (equiv. ACI 318-14 Ch. 22.5) and
    Sec. 409.7 (beam shear reinforcement detailing rules). Two-legged
    stirrups (single closed stirrup) are assumed.
    """
    Vu_N = Vu_kN * 1000.0
    stirrup_db = BAR_DATA[stirrup_db_key]["db"]

    Vc_N = 0.17 * math.sqrt(fc) * b * d                   # NSCP 2015 Eq. 422.5.5.1 (simplified)
    phi_v = 0.75                                          # NSCP 2015 Table 421.2.1 (shear)
    phiVc_N = phi_v * Vc_N
    Av = 2 * BAR_DATA[stirrup_db_key]["area"]             # 2-legged stirrup area

    result = {"Vu": Vu_kN, "Vc": Vc_N / 1000.0, "phiVc": phiVc_N / 1000.0,
              "Av": Av, "stirrup": stirrup_db_key, "stirrup_db": stirrup_db}

    Vs_max_N = 0.66 * math.sqrt(fc) * b * d               # NSCP 2015 Sec. 422.5.1.2 upper limit

    if Vu_N <= 0.5 * phiVc_N:
        result.update({"case": "No stirrups required by calculation (Vu <= 0.5*phiVc)",
                        "s_req": None, "s_final": max(d / 2.0, 100.0),
                        "status": "OK - nominal/practical stirrup spacing shown for construction"})
        return result

    Vs_needed_N = max(0.0, (Vu_N / phi_v) - Vc_N)

    if Vs_needed_N > Vs_max_N:
        result.update({"case": "Vs required exceeds maximum permitted", "s_req": None,
                        "s_final": None,
                        "status": "FAIL - increase beam cross-section (Vs > 0.66*sqrt(f'c)*b*d)"})
        return result

    if Vu_N <= phiVc_N:
        Vs_needed_N = 0.0   # only minimum shear reinforcement is theoretically required

    light_case = Vs_needed_N <= 0.33 * math.sqrt(fc) * b * d
    smax_spacing_limit = min(d / 2.0 if light_case else d / 4.0, 600.0 if light_case else 300.0)

    s_strength = (Av * fy * d / Vs_needed_N) if Vs_needed_N > 0 else smax_spacing_limit

    s_avmin_1 = Av * fy / (0.062 * math.sqrt(fc) * b)     # NSCP 2015 Sec. 409.6.3.3
    s_avmin_2 = Av * fy / (0.35 * b)
    s_avmin = min(s_avmin_1, s_avmin_2)

    s_final = min(s_strength, smax_spacing_limit, s_avmin)
    s_final = math.floor(s_final / 10.0) * 10.0
    s_final = max(s_final, 50.0)

    result.update({
        "case": "Stirrups required by calculation",
        "Vs_req": Vs_needed_N / 1000.0, "Vs_max": Vs_max_N / 1000.0,
        "s_req_strength": s_strength, "s_max_spacing_rule": smax_spacing_limit,
        "s_max_avmin_rule": s_avmin, "s_final": s_final, "status": "OK"
    })
    return result


def development_length(bar_db_key, fc, fy):
    """
    Simplified tension development length, NSCP 2015 Sec. 425.4.2.2, for
    the common case of bars with adequate spacing/cover or minimum stirrups
    provided along the development length. psi_t = psi_e = lambda = 1.0.
    """
    db = BAR_DATA[bar_db_key]["db"]
    if db <= 20.0:
        ld = fy / (2.1 * math.sqrt(fc)) * db
    else:
        ld = fy / (1.7 * math.sqrt(fc)) * db
    return max(ld, 300.0)   # NSCP 2015 Sec. 425.4.2.1 absolute minimum = 300 mm


# =============================================================================
# SECTION 3: MAIN CALCULATION DRIVER
# =============================================================================

def design_beam(inputs):
    """
    Runs the full design sequence and returns (report_text, results_dict).
    `results_dict` also carries all geometric data needed by the drawing
    routines (Section 4).
    """
    b, h = inputs["b"], inputs["h"]
    fc, fy = inputs["fc"], inputs["fy"]
    cover = inputs["cover"]
    DL, LL, L = inputs["DL"], inputs["LL"], inputs["L"]
    support = inputs["support"]
    main_bar, stirrup_bar = inputs["main_bar"], inputs["stirrup_bar"]

    lines = []
    W = lines.append

    W("=" * 78)
    W(" REINFORCED CONCRETE BEAM DESIGN REPORT -- NSCP 2015 STRENGTH DESIGN METHOD")
    W("=" * 78)
    W(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    W("-" * 78)
    W(" DISCLAIMER: This is a preliminary engineering calculation aid only.")
    W(" It must be independently checked and sealed by a licensed Professional")
    W(" Structural/Civil Engineer before use in construction documents.")
    W("-" * 78)

    W("\n1. INPUT DATA")
    W(f"   Beam width, b            = {b:.0f} mm")
    W(f"   Overall depth, h         = {h:.0f} mm")
    W(f"   f'c                      = {fc:.1f} MPa")
    W(f"   fy                       = {fy:.1f} MPa")
    W(f"   Clear concrete cover     = {cover:.0f} mm")
    W(f"   Dead load (superimposed) = {DL:.2f} kN/m")
    W(f"   Live load                = {LL:.2f} kN/m")
    W(f"   Clear span, Ln           = {L:.2f} m")
    W(f"   Support condition        = {support}")
    W(f"   Trial main bar size      = {main_bar}")
    W(f"   Stirrup bar size         = {stirrup_bar}")

    self_weight = (b / 1000.0) * (h / 1000.0) * UNIT_WEIGHT_CONCRETE
    wd_total = DL + self_weight
    wu = 1.2 * wd_total + 1.6 * LL   # NSCP 2015 Sec. 203.3.1, Eq. 203-1/203-2

    W("\n2. FACTORED LOADS (NSCP 2015 Sec. 203.3 - Load Combinations)")
    W(f"   Beam self-weight            = {self_weight:.3f} kN/m")
    W(f"   Total service dead load, wd = {wd_total:.3f} kN/m")
    W(f"   Total service live load, wl = {LL:.3f} kN/m")
    W(f"   Factored load, wu = 1.2wd + 1.6wl = {wu:.3f} kN/m")

    cond = SUPPORT_CONDITIONS[support]
    Mu_pos = wu * L ** 2 / cond["Mpos"] if cond["Mpos"] else 0.0
    Mu_neg = wu * L ** 2 / cond["Mneg"] if cond["Mneg"] else 0.0
    Vu_face = wu * L if support == "Cantilever" else cond["Vcoeff"] * wu * L / 2.0

    W("\n3. DESIGN MOMENTS AND SHEAR (approximate coefficients, NSCP 2015 Sec. 406.5)")
    W(f"   Coefficients used: {cond['desc']}")
    W(f"   Positive design moment, Mu(+) = {Mu_pos:.2f} kN-m")
    W(f"   Negative design moment, Mu(-) = {Mu_neg:.2f} kN-m")
    W(f"   Max factored shear at support face, Vu = {Vu_face:.2f} kN")

    results = {"inputs": inputs, "wu": wu, "Mu_pos": Mu_pos, "Mu_neg": Mu_neg,
               "Vu_face": Vu_face, "self_weight": self_weight,
               "beta1": beta1_factor(fc), "support_info": cond}

    def do_flexure_block(Mu, title, tag):
        W(f"\n4.{tag} FLEXURAL DESIGN -- {title} (NSCP 2015 Sec. 409/410, 422.2)")
        if Mu <= 0:
            W("   Not applicable for this support condition (Mu = 0).")
            return None
        stirrup_db = BAR_DATA[stirrup_bar]["db"]
        bar_db = BAR_DATA[main_bar]["db"]
        d1, dt1 = effective_depth(h, cover, stirrup_db, bar_db, layers=1)
        fd = flexural_design(Mu, b, d1, dt1, fc, fy)

        if fd["As_req"] is None:
            W(f"   d (1 layer) = {d1:.1f} mm")
            W(f"   >>> {fd['status']}")
            for n in fd["notes"]:
                W("   " + n)
            return fd

        bars = select_bars(fd["As_final"], b, cover, stirrup_db, main_bar, h)
        d_used, dt_used = d1, dt1
        if bars["layers"] == 2:
            d2, dt2 = effective_depth(h, cover, stirrup_db, bar_db, layers=2)
            fd = flexural_design(Mu, b, d2, dt2, fc, fy)
            bars = select_bars(fd["As_final"], b, cover, stirrup_db, main_bar, h)
            d_used, dt_used = d2, dt2

        W(f"   Effective depth used, d  = {d_used:.1f} mm  (dt = {dt_used:.1f} mm)")
        W(f"   beta1                    = {fd['beta1']:.3f}")
        W(f"   As,min (409.6.1.2)       = {fd['As_min']:.0f} mm^2")
        W(f"   As,max @ et=0.004 limit  = {fd['As_max_004']:.0f} mm^2")
        W(f"   As required (governs)    = {fd['As_final']:.0f} mm^2")
        W(f"   Neutral axis depth, c    = {fd['c']:.1f} mm")
        W(f"   Net tensile strain, et   = {fd['et']:.4f}")
        strain_class = ('Tension-controlled' if fd['et'] >= 0.005 else
                         ('Compression-controlled' if fd['et'] <= fy / ES else 'Transition zone'))
        W(f"   Strength reduction, phi  = {fd['phi']:.3f}  ({strain_class})")
        W(f"   Selected bars            = {bars['n']} - {bars['bar']} ({bars['layers']} layer(s))")
        W(f"   As provided              = {bars['As_prov']:.0f} mm^2  "
          f"({'>= As required -> OK' if bars['As_prov'] >= fd['As_final'] else '< As required -> NOT OK'})")
        W(f"   Clear bar spacing        = {bars['clear_spacing']:.1f} mm "
          f"(min. required = {bars['min_clear_req']:.1f} mm) --> "
          f"{'OK' if bars['fits'] else 'NOT OK - bars do not fit, use larger beam or two layers'}")
        W(f"   Strain / ductility check : {fd['status']}")
        for n in fd["notes"]:
            W("   " + n)
        fd["bars"] = bars
        fd["d"] = d_used
        fd["dt"] = dt_used
        return fd

    fd_pos = do_flexure_block(Mu_pos, "Positive Moment (Bottom Steel)", "1")
    fd_neg = do_flexure_block(Mu_neg, "Negative Moment (Top Steel)", "2") if Mu_neg > 0 else None
    results["fd_pos"] = fd_pos
    results["fd_neg"] = fd_neg

    W("\n5. SHEAR DESIGN (NSCP 2015 Sec. 422.5, 409.6.3, 409.7.6)")
    if fd_pos and fd_pos.get("d"):
        d_for_shear = fd_pos["d"]
    else:
        d_for_shear = effective_depth(h, cover, BAR_DATA[stirrup_bar]["db"],
                                       BAR_DATA[main_bar]["db"], 1)[0]

    Vu_d = max(0.0, Vu_face - wu * (d_for_shear / 1000.0))  # crit. section at d from support face (409.4.3.2)
    W(f"   Effective depth, d (for shear) = {d_for_shear:.1f} mm")
    W(f"   Vu at critical section (d from support face) = {Vu_d:.2f} kN")

    sd = shear_design(Vu_d, b, d_for_shear, fc, fy, stirrup_bar)
    results["shear"] = sd
    results["d_for_shear"] = d_for_shear
    W(f"   Vc (concrete shear strength)   = {sd['Vc']:.2f} kN")
    W(f"   phi*Vc                         = {sd['phiVc']:.2f} kN")
    W(f"   Condition: {sd['case']}")
    if sd.get("Vs_req") is not None:
        W(f"   Vs required                    = {sd['Vs_req']:.2f} kN")
        W(f"   Vs,max permitted (422.5.1.2)   = {sd['Vs_max']:.2f} kN")
    if sd["s_final"] is not None:
        W(f"   Stirrup bar / legs             = {stirrup_bar}, 2-legged (Av = {sd['Av']:.0f} mm^2)")
        if "s_req_strength" in sd:
            W(f"   Spacing by strength             = {sd['s_req_strength']:.0f} mm")
            W(f"   Max spacing (code limit)        = {sd['s_max_spacing_rule']:.0f} mm")
            W(f"   Max spacing (Av,min governs)    = {sd['s_max_avmin_rule']:.0f} mm")
        W(f"   >>> PROVIDE: {stirrup_bar} stirrups @ {sd['s_final']:.0f} mm o.c.")
    W(f"   Shear check status: {sd['status']}")

    W("\n6. DEVELOPMENT LENGTH CHECK (NSCP 2015 Sec. 425.4.2)")
    ld_main = development_length(main_bar, fc, fy)
    avail_embed = (L / 2.0) * 1000.0
    W(f"   Basic tension development length, ld ({main_bar}) = {ld_main:.0f} mm")
    W(f"   Approx. available embedment (Ln/2)                = {avail_embed:.0f} mm")
    dev_status = ("OK - sufficient length available" if avail_embed >= ld_main else
                  "CHECK - verify bar cutoff points/hooks; embedment may be insufficient")
    W(f"   Development length check: {dev_status}")
    W("   NOTE: Actual detailing (bar cutoffs, hooks, splices) must be verified")
    W("   individually per NSCP 2015 Sec. 425.4 through 425.5.")
    results["ld_main"] = ld_main
    results["dev_status"] = dev_status

    W("\n7. SUMMARY OF PASS/FAIL CHECKS")
    checks = []
    if fd_pos:
        checks.append(("Flexure (positive moment)", fd_pos["status"]))
    if fd_neg:
        checks.append(("Flexure (negative moment)", fd_neg["status"]))
    checks.append(("Shear design", sd["status"]))
    checks.append(("Development length", dev_status))
    all_ok = True
    for name, stat in checks:
        mark = "PASS" if stat.startswith("OK") else "REVIEW/FAIL"
        if mark != "PASS":
            all_ok = False
        W(f"   [{mark:^11}] {name:30s} - {stat}")

    W("\n" + "=" * 78)
    W(f" OVERALL RESULT: {'ALL CHECKS SATISFIED (subject to professional review)' if all_ok else 'ONE OR MORE ITEMS REQUIRE REVIEW / REDESIGN'}")
    W("=" * 78)
    W(" This output is generated by an automated calculation aid and requires")
    W(" verification by a licensed Professional/Structural Civil Engineer prior")
    W(" to use for construction, in accordance with NSCP 2015 and RA 544.")
    W("=" * 78)

    return "\n".join(lines), results


# =============================================================================
# SECTION 4: DRAWING ROUTINES (matplotlib) -- cross-section and 3D views
# =============================================================================
# These routines are purely illustrative/schematic. Bar and stirrup positions
# are drawn to scale from the calculated geometry, but the drawings are not
# intended as fabrication or shop drawings.

CONCRETE_COLOR = "#d9d3c7"
STIRRUP_COLOR = "#2b6cb0"
MAIN_BAR_COLOR = "#c0392b"
TOP_BAR_COLOR = "#7d3c98"


def draw_cross_section(fig, results):
    """Draws a dimensioned beam cross-section: outline, cover, stirrup, and
    main reinforcement (bottom / top), with dimension callouts."""
    fig.clf()
    ax = fig.add_subplot(111)
    inp = results["inputs"]
    b, h, cover = inp["b"], inp["h"], inp["cover"]
    stirrup_db = BAR_DATA[inp["stirrup_bar"]]["db"]

    # Concrete outline
    ax.add_patch(matplotlib.patches.Rectangle((0, 0), b, h, facecolor=CONCRETE_COLOR,
                                               edgecolor="black", linewidth=1.5, zorder=1))
    # Stirrup outline (rounded rectangle approximated with a plain rectangle)
    sx0, sy0 = cover, cover
    sx1, sy1 = b - cover, h - cover
    ax.add_patch(matplotlib.patches.Rectangle((sx0, sy0), sx1 - sx0, sy1 - sy0,
                                               facecolor="none", edgecolor=STIRRUP_COLOR,
                                               linewidth=2.0, zorder=2))

    # Bottom (positive moment) bars
    fd_pos = results.get("fd_pos")
    if fd_pos and fd_pos.get("bars"):
        for (x, y) in fd_pos["bars"]["coords"]:
            ax.add_patch(matplotlib.patches.Circle((x, y), fd_pos["bars"]["db"] / 2.0,
                                                     facecolor=MAIN_BAR_COLOR, edgecolor="black",
                                                     linewidth=0.6, zorder=3))
        n, size = fd_pos["bars"]["n"], fd_pos["bars"]["bar"]
        ax.text(b / 2.0, cover * 0.6, f"{n}-{size} (bottom)", ha="center", va="center",
                fontsize=9, color=MAIN_BAR_COLOR, fontweight="bold")

    # Top (negative moment) bars, drawn mirrored from the top face
    fd_neg = results.get("fd_neg")
    if fd_neg and fd_neg.get("bars"):
        for (x, y_from_top) in fd_neg["bars"]["coords"]:
            y = h - y_from_top
            ax.add_patch(matplotlib.patches.Circle((x, y), fd_neg["bars"]["db"] / 2.0,
                                                     facecolor=TOP_BAR_COLOR, edgecolor="black",
                                                     linewidth=0.6, zorder=3))
        n, size = fd_neg["bars"]["n"], fd_neg["bars"]["bar"]
        ax.text(b / 2.0, h - cover * 0.6, f"{n}-{size} (top)", ha="center", va="center",
                fontsize=9, color=TOP_BAR_COLOR, fontweight="bold")

    # Dimension lines: width (below) and height (right side)
    _dim_line(ax, (0, -0.08 * h), (b, -0.08 * h), f"b = {b:.0f} mm")
    _dim_line(ax, (b * 1.08, 0), (b * 1.08, h), f"h = {h:.0f} mm", vertical=True)
    ax.annotate("", xy=(cover, cover), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="dimgray", lw=1))
    ax.text(cover * 1.1, cover * 1.1, f"cover = {cover:.0f} mm", fontsize=8, color="dimgray")

    sd = results.get("shear")
    stirrup_label = f"{inp['stirrup_bar']} stirrup"
    if sd and sd.get("s_final"):
        stirrup_label += f" @ {sd['s_final']:.0f} mm o.c."
    ax.text(b * 1.30, h * 0.5, stirrup_label, rotation=90, va="center", ha="left",
            fontsize=8, color=STIRRUP_COLOR)

    ax.set_xlim(-0.15 * b, b * 1.55)
    ax.set_ylim(-0.20 * h, h * 1.12)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Beam Cross-Section (schematic, to scale)", fontsize=11)
    fig.tight_layout()


def _dim_line(ax, p0, p1, label, vertical=False):
    ax.annotate("", xy=p1, xytext=p0,
                arrowprops=dict(arrowstyle="<->", color="dimgray", lw=1))
    mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
    if vertical:
        ax.text(mx + 4, my, label, rotation=90, va="center", ha="left", fontsize=8, color="dimgray")
    else:
        ax.text(mx, my - 4, label, va="top", ha="center", fontsize=8, color="dimgray")


def draw_3d_view(fig, results):
    """Draws an isometric 3D view of a representative beam segment showing
    the concrete envelope (semi-transparent), longitudinal bars, and
    stirrups spaced at the calculated spacing (capped for legibility)."""
    fig.clf()
    ax = fig.add_subplot(111, projection="3d")
    inp = results["inputs"]
    b, h = inp["b"], inp["h"]
    cover = inp["cover"]
    stirrup_db = BAR_DATA[inp["stirrup_bar"]]["db"]

    # Model length: show full span if short, otherwise a representative
    # segment so bar/stirrup detail remains legible.
    L_mm = inp["L"] * 1000.0
    model_len = min(L_mm, 3000.0)

    # --- Concrete envelope (semi-transparent box) --------------------------
    verts = _box_faces(0, model_len, 0, b, 0, h)
    box = Poly3DCollection(verts, facecolor=CONCRETE_COLOR, edgecolor="gray",
                            linewidths=0.5, alpha=0.25)
    ax.add_collection3d(box)

    # --- Longitudinal bars --------------------------------------------------
    fd_pos = results.get("fd_pos")
    if fd_pos and fd_pos.get("bars"):
        for (x, y) in fd_pos["bars"]["coords"]:
            ax.plot([0, model_len], [x, x], [y, y], color=MAIN_BAR_COLOR, linewidth=2.2)

    fd_neg = results.get("fd_neg")
    if fd_neg and fd_neg.get("bars"):
        for (x, y_from_top) in fd_neg["bars"]["coords"]:
            y = h - y_from_top
            ax.plot([0, model_len], [x, x], [y, y], color=TOP_BAR_COLOR, linewidth=2.2)

    # --- Stirrups (closed rectangular loops at intervals) -------------------
    sd = results.get("shear")
    spacing = sd["s_final"] if sd and sd.get("s_final") else max(h / 2.0, 100.0)
    spacing = max(spacing, 40.0)
    n_stirrups = min(int(model_len // spacing) + 1, 18)   # cap drawn count for legibility
    sx0, sy0 = cover, cover
    sx1, sy1 = b - cover, h - cover
    loop_y = [sx0, sx1, sx1, sx0, sx0]
    loop_z = [sy0, sy0, sy1, sy1, sy0]
    for i in range(n_stirrups):
        x = i * spacing if n_stirrups <= 1 else i * (model_len / (n_stirrups - 1))
        ax.plot([x] * 5, loop_y, loop_z, color=STIRRUP_COLOR, linewidth=1.3)

    # --- Support symbols (schematic) ----------------------------------------
    cond = results["support_info"]
    _draw_support_symbol(ax, 0, b, h, cond["left"])
    _draw_support_symbol(ax, model_len, b, h, cond["right"])

    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.yaxis.set_major_locator(MaxNLocator(3))
    ax.zaxis.set_major_locator(MaxNLocator(3))
    ax.set_xlabel("Length (mm)", labelpad=8)
    ax.set_ylabel("Width (mm)", labelpad=6)
    ax.set_zlabel("Depth (mm)", labelpad=6)

    # Use a clamped (non-physical) aspect ratio so the cross-section remains
    # legible even for long, slender beams -- this is a schematic view, not
    # a true-to-scale model.
    scale_ref = max(b, h)
    len_ratio = min(model_len / scale_ref, 2.6)
    len_ratio = max(len_ratio, 1.5)
    ax.set_box_aspect((len_ratio, b / scale_ref, h / scale_ref))
    try:
        ax.set_proj_type("ortho")   # flatter, less distorted isometric-style projection
    except AttributeError:
        pass

    ax.set_title("Isometric 3D View of Reinforcement Cage", fontsize=11, pad=2)
    if L_mm > model_len:
        ax.text2D(0.5, 0.94, f"(showing {model_len:.0f} mm of {L_mm:.0f} mm span; "
                              f"schematic proportions, not to true scale)",
                   transform=ax.transAxes, ha="center", fontsize=8, color="dimgray")
    ax.view_init(elev=22, azim=-50)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.05)


def _box_faces(x0, x1, y0, y1, z0, z1):
    p = {
        "000": (x0, y0, z0), "100": (x1, y0, z0), "110": (x1, y1, z0), "010": (x0, y1, z0),
        "001": (x0, y0, z1), "101": (x1, y0, z1), "111": (x1, y1, z1), "011": (x0, y1, z1),
    }
    faces = [
        [p["000"], p["100"], p["110"], p["010"]],  # bottom
        [p["001"], p["101"], p["111"], p["011"]],  # top
        [p["000"], p["100"], p["101"], p["001"]],  # front
        [p["010"], p["110"], p["111"], p["011"]],  # back
        [p["000"], p["010"], p["011"], p["001"]],  # left
        [p["100"], p["110"], p["111"], p["101"]],  # right
    ]
    return faces


def _draw_support_symbol(ax, x, b, h, kind):
    """Small schematic marker at the beam end indicating the boundary
    condition (pin / roller / fixed / continuous / free)."""
    ymid = b / 2.0
    if kind == "fixed":
        ax.plot([x] * 5, [0, b, b, 0, 0], [0, 0, h, h, 0], color="black", linewidth=2.5)
    elif kind in ("pin", "roller"):
        ax.plot([x], [ymid], [0], marker="^", color="black", markersize=10)
    elif kind == "continuous":
        ax.plot([x], [ymid], [0], marker="s", color="dimgray", markersize=7)
    # "free" (cantilever tip): no symbol drawn


# =============================================================================
# SECTION 5: GRAPHICAL USER INTERFACE (Tkinter)
# =============================================================================

class BeamDesignApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RC Beam Designer - NSCP 2015 Strength Design")
        self.geometry("1200x760")
        self.minsize(1000, 650)
        self.last_report = ""
        self.last_results = None

        self._build_style()
        self._build_layout()

    # -------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Disclaimer.TLabel", foreground="#b00000", font=("Segoe UI", 9, "italic"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))

    # -------------------------------------------------------------------
    def _build_layout(self):
        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Reinforced Concrete Beam Designer (NSCP 2015)",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(top,
                  text="Engineering calculation aid only - requires review and sealing by a "
                       "licensed Professional Structural/Civil Engineer.",
                  style="Disclaimer.TLabel").pack(anchor="w")

        main = ttk.Frame(self, padding=(12, 4, 12, 12))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_input_panel(left)
        self._build_output_panel(right)

    # -------------------------------------------------------------------
    def _build_input_panel(self, parent):
        self.vars = {}

        geo = ttk.Labelframe(parent, text="Geometry & Materials", padding=10,
                              style="Section.TLabelframe")
        geo.pack(fill="x", pady=(0, 8))
        self._add_entry(geo, "Width, b (mm)", "b", "300")
        self._add_entry(geo, "Overall depth, h (mm)", "h", "500")
        self._add_entry(geo, "Clear cover (mm)", "cover", "40")
        self._add_entry(geo, "f'c (MPa)", "fc", "27.6")
        self._add_entry(geo, "fy (MPa)", "fy", "414")

        loads = ttk.Labelframe(parent, text="Loads & Span", padding=10,
                                style="Section.TLabelframe")
        loads.pack(fill="x", pady=(0, 8))
        self._add_entry(loads, "Dead load, DL (kN/m)\n(superimposed, excl. self-wt.)", "DL", "10")
        self._add_entry(loads, "Live load, LL (kN/m)", "LL", "15")
        self._add_entry(loads, "Clear span, Ln (m)", "L", "6.0")

        ttk.Label(loads, text="Support condition").grid(sticky="w", pady=(6, 2))
        self.support_var = tk.StringVar(value="Simply Supported")
        ttk.Combobox(loads, textvariable=self.support_var, state="readonly",
                     values=list(SUPPORT_CONDITIONS.keys()), width=22).grid(sticky="ew", pady=(0, 4))

        reinf = ttk.Labelframe(parent, text="Reinforcement Selection", padding=10,
                                style="Section.TLabelframe")
        reinf.pack(fill="x", pady=(0, 8))

        ttk.Label(reinf, text="Trial main bar size").grid(sticky="w", pady=(2, 2))
        self.main_bar_var = tk.StringVar(value="20M")
        ttk.Combobox(reinf, textvariable=self.main_bar_var, state="readonly",
                     values=BAR_LIST, width=10).grid(sticky="w", pady=(0, 6))

        ttk.Label(reinf, text="Stirrup bar size").grid(sticky="w", pady=(2, 2))
        self.stirrup_bar_var = tk.StringVar(value="10M")
        ttk.Combobox(reinf, textvariable=self.stirrup_bar_var, state="readonly",
                     values=BAR_LIST, width=10).grid(sticky="w", pady=(0, 4))

        btns = ttk.Frame(parent)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Design / Calculate", command=self.on_calculate)\
            .pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Save Report as .txt", command=self.on_save)\
            .pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Clear Results", command=self.on_clear)\
            .pack(fill="x")

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(parent, text="Note: install 'matplotlib' to enable the\n"
                                    "Cross-Section and 3D View tabs\n(pip install matplotlib).",
                      foreground="#b00000", font=("Segoe UI", 8, "italic"),
                      wraplength=220, justify="left").pack(fill="x", pady=(10, 0))

    def _add_entry(self, parent, label, key, default):
        ttk.Label(parent, text=label).grid(sticky="w", pady=(4, 2))
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=16).grid(sticky="ew", pady=(0, 2))
        self.vars[key] = var

    # -------------------------------------------------------------------
    def _build_output_panel(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # --- Tab 1: text report ---
        report_tab = ttk.Frame(self.notebook, padding=6)
        report_tab.rowconfigure(0, weight=1)
        report_tab.columnconfigure(0, weight=1)
        self.text = ScrolledText(report_tab, wrap="word", font=("Consolas", 10))
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.insert("1.0",
                          "Enter beam parameters on the left, then click "
                          "'Design / Calculate' to generate the design report, "
                          "cross-section, and 3D view.\n\n"
                          "Reminder: this tool is an aid only and does not replace "
                          "independent professional engineering review.")
        self.text.configure(state="disabled")
        self.notebook.add(report_tab, text="Calculation Report")

        # --- Tab 2 & 3: cross-section / 3D view ---
        self.section_tab = ttk.Frame(self.notebook, padding=6)
        self.view3d_tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.section_tab, text="Cross-Section View")
        self.notebook.add(self.view3d_tab, text="3D Reinforcement View")

        if MATPLOTLIB_AVAILABLE:
            self.fig_section = Figure(figsize=(6, 5), dpi=100)
            self.canvas_section = FigureCanvasTkAgg(self.fig_section, master=self.section_tab)
            self.canvas_section.get_tk_widget().pack(fill="both", expand=True)

            self.fig_3d = Figure(figsize=(6, 5), dpi=100)
            self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.view3d_tab)
            self.canvas_3d.get_tk_widget().pack(fill="both", expand=True)
        else:
            msg = ("matplotlib is not installed, so this view is unavailable.\n\n"
                   "Install it with:\n    pip install matplotlib\n\n"
                   "then restart the application.")
            ttk.Label(self.section_tab, text=msg, justify="center",
                      font=("Segoe UI", 11)).pack(expand=True)
            ttk.Label(self.view3d_tab, text=msg, justify="center",
                      font=("Segoe UI", 11)).pack(expand=True)

    # -------------------------------------------------------------------
    def _collect_inputs(self):
        try:
            b = float(self.vars["b"].get())
            h = float(self.vars["h"].get())
            cover = float(self.vars["cover"].get())
            fc = float(self.vars["fc"].get())
            fy = float(self.vars["fy"].get())
            DL = float(self.vars["DL"].get())
            LL = float(self.vars["LL"].get())
            L = float(self.vars["L"].get())
        except ValueError:
            raise ValueError("Please enter valid numeric values for all fields.")

        if min(b, h, cover, fc, fy, L) <= 0:
            raise ValueError("All dimensions, strengths, and span must be positive numbers.")
        if DL < 0 or LL < 0:
            raise ValueError("Loads cannot be negative.")
        if cover >= h:
            raise ValueError("Cover must be less than the overall beam depth.")

        return {
            "b": b, "h": h, "cover": cover, "fc": fc, "fy": fy,
            "DL": DL, "LL": LL, "L": L,
            "support": self.support_var.get(),
            "main_bar": self.main_bar_var.get(),
            "stirrup_bar": self.stirrup_bar_var.get(),
        }

    # -------------------------------------------------------------------
    def on_calculate(self):
        try:
            inputs = self._collect_inputs()
            report_text, results = design_beam(inputs)
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return
        except ZeroDivisionError:
            messagebox.showerror("Calculation Error",
                                  "A division by zero occurred - check that the neutral axis "
                                  "depth and section properties are physically valid.")
            return
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An error occurred:\n{e}")
            return

        self.last_report = report_text
        self.last_results = results

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", report_text)
        self.text.configure(state="disabled")

        if MATPLOTLIB_AVAILABLE:
            try:
                draw_cross_section(self.fig_section, results)
                self.canvas_section.draw()
                draw_3d_view(self.fig_3d, results)
                self.canvas_3d.draw()
            except Exception as e:
                messagebox.showwarning("Visualization Warning",
                                        f"The report was generated, but the drawings could not "
                                        f"be rendered:\n{e}")

    # -------------------------------------------------------------------
    def on_save(self):
        if not self.last_report:
            messagebox.showinfo("Nothing to Save", "Please run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt")],
            initialfile="RC_Beam_Design_Report.txt",
            title="Save Design Report"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.last_report)
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")
        except OSError as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")

    # -------------------------------------------------------------------
    def on_clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.last_report = ""
        self.last_results = None
        if MATPLOTLIB_AVAILABLE:
            self.fig_section.clf()
            self.canvas_section.draw()
            self.fig_3d.clf()
            self.canvas_3d.draw()


# =============================================================================
# SECTION 6: ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = BeamDesignApp()
    app.mainloop()