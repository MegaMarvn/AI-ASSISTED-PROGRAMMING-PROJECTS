"""
================================================================================
  NSCP 2015 RC BEAM STUDIO
  Reinforced Concrete Beam Design Workbench  (Strength Design / USD)
================================================================================

  Single-file Python desktop application.  Standard library only (tkinter, math,
  datetime).  Runs locally / offline.  Units: mm, MPa, kN, kN-m.
  Reinforcing bars: Canadian metric "M" bars (10M ... 35M).

  --------------------------------------------------------------------------
  ENGINEERING LIMITATION / DISCLAIMER
  This software is an engineering calculation aid. The engineer remains
  responsible for verifying the applicable NSCP 2015 provisions, project
  loads, structural analysis, load combinations, detailing requirements,
  seismic provisions, development and anchorage requirements, and final
  design.  Not every NSCP 2015 provision is automatically covered.
  --------------------------------------------------------------------------

  NSCP 2015 provisions referenced (aligned with ACI 318-14):
    203.3.1       Factored load combinations
    406.5         Approximate moments/shears for continuous members
    409.3.1.1     Minimum depth for deflection control (Table)
    409.3.3.1     Minimum net tensile strain for beams (>= 0.004)
    409.6.1.2     Minimum flexural reinforcement
    409.6.3.3     Minimum shear reinforcement
    409.7.6.2.2   Maximum stirrup spacing
    410 / 422.2   Balanced ratio, Whitney stress block, nominal flexure
    421.2         Strength-reduction factors (phi)
    422.2.2.4.3   Stress-block factor beta1
    422.5.5.1     Concrete shear strength Vc
    422.5.1.1/2   Vn = Vc + Vs and Vs upper limit
    425.2.1       Minimum clear spacing of parallel bars
    425.4.2.2     Development length of deformed bars (tension)
    425.4.3.1     Development length of standard hooks (tension)
================================================================================
"""

import math
from datetime import date, datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


# =============================================================================
#  THEME
# =============================================================================
class T:
    BG       = "#0e1621"   # app background
    HEADER   = "#0a1017"   # header bar
    SIDEBAR  = "#0b131c"   # sidebar
    CARD     = "#16212e"   # card / panel
    CARD2    = "#1d2b3a"   # nested panel
    STROKE   = "#243342"   # borders
    TEXT     = "#e6edf3"   # primary text
    MUTED    = "#8a99a8"   # secondary text
    ACCENT   = "#3b82f6"   # blue accent
    ACCENT2  = "#22d3ee"   # cyan
    PASS     = "#22c55e"   # green
    WARN     = "#eab308"   # amber
    FAIL     = "#ef4444"   # red
    CONCRETE = "#9fb0c0"   # 3D concrete
    REBAR_B  = "#38bdf8"   # bottom bars (cyan-blue)
    REBAR_T  = "#f59e0b"   # top bars (orange)
    STIRRUP  = "#4ade80"   # stirrups (green)

    F_TITLE  = ("Segoe UI Semibold", 15)
    F_SUB    = ("Segoe UI", 10)
    F_H      = ("Segoe UI Semibold", 11)
    F_LBL    = ("Segoe UI", 10)
    F_BIG    = ("Segoe UI Semibold", 20)
    F_HUGE   = ("Segoe UI Semibold", 26)
    F_MONO   = ("Consolas", 10)
    F_MONO_S = ("Consolas", 9)


# =============================================================================
#  CODE CONSTANTS
# =============================================================================
ES            = 200000.0    # steel modulus, MPa            (NSCP 420.2.2.2)
EPS_CU        = 0.003       # ultimate concrete strain      (NSCP 422.2.2.1)
EPS_TC        = 0.005       # tension-controlled strain
EPS_MIN_FLEX  = 0.004       # min beam net tensile strain   (NSCP 409.3.3.1)
PHI_TENSION   = 0.90        # phi flexure (tension-ctrl)    (NSCP Table 421.2.2)
PHI_COMP      = 0.65        # phi compression-controlled (tied)
PHI_SHEAR     = 0.75        # phi shear                     (NSCP Table 421.2.1)
CONC_UNIT_WT  = 24.0        # kN/m3, normal-weight RC
FYT_MAX       = 420.0       # max fyt for shear             (NSCP 422.5.1.2)
VCLEAR        = 25.0        # vertical clear spacing between layers, mm

# Canadian metric bars: area (mm^2), diameter (mm)
BARS = {
    "10M": {"area": 100.0,  "dia": 11.3},
    "15M": {"area": 200.0,  "dia": 16.0},
    "20M": {"area": 300.0,  "dia": 19.5},
    "25M": {"area": 500.0,  "dia": 25.2},
    "30M": {"area": 700.0,  "dia": 29.9},
    "35M": {"area": 1000.0, "dia": 35.7},
}
MAIN_BARS  = ["10M", "15M", "20M", "25M", "30M", "35M"]
STIR_BARS  = ["10M", "15M", "20M"]
SUPPORTS   = ["Simply Supported", "Continuous", "Fixed", "Cantilever"]
LOAD_TYPES = ["Uniform", "Point", "Combination"]


# =============================================================================
#  DESIGN ENGINE  (pure functions - GUI-independent, testable)
# =============================================================================
def beta1(fc):
    """Stress-block factor beta1.  NSCP 2015 Eq. 422.2.2.4.3."""
    if fc <= 28.0:
        return 0.85
    if fc <= 55.0:
        return max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)
    return 0.65


def factored_loads(wD, wL):
    """Governing factored UDL, kN/m.  NSCP 203.3.1 (Eq. 203-1, 203-2)."""
    u1 = 1.4 * wD
    u2 = 1.2 * wD + 1.6 * wL
    return max(u1, u2), u1, u2


def factored_point(pD, pL):
    """Governing factored point load, kN.  NSCP 203.3.1."""
    return max(1.4 * pD, 1.2 * pD + 1.6 * pL)


def internal_forces(wu, Pu, a, L, condition, load_type):
    """
    Return (Mu, Vu, notes list, moment-location text).
    wu  = factored UDL (kN/m), Pu = factored point load (kN),
    a   = point-load location from left support (m), L = span (m).
    Continuous / Fixed with a point load use approximate coefficients
    (NSCP 406.5) and are flagged for verification.
    """
    notes = []
    Mu_w = Vu_w = 0.0
    Mu_p = Vu_p = 0.0

    use_udl = load_type in ("Uniform", "Combination")
    use_pt  = load_type in ("Point", "Combination")

    # ---- UDL contribution --------------------------------------------------
    if use_udl:
        if condition == "Simply Supported":
            Mu_w, Vu_w = wu * L ** 2 / 8.0, wu * L / 2.0
        elif condition == "Cantilever":
            Mu_w, Vu_w = wu * L ** 2 / 2.0, wu * L
        elif condition == "Fixed":
            Mu_w, Vu_w = wu * L ** 2 / 12.0, wu * L / 2.0
        elif condition == "Continuous":
            # ACI/NSCP approximate coefficients (governing envelope)
            Mu_w, Vu_w = wu * L ** 2 / 10.0, 1.15 * wu * L / 2.0
            notes.append("Continuous UDL uses approximate coefficients "
                         "wuL^2/10 and 1.15 wuL/2 (NSCP 406.5).")

    # ---- Point-load contribution ------------------------------------------
    if use_pt:
        a = min(max(a, 0.0), L)
        b = L - a
        if condition == "Simply Supported":
            Mu_p = Pu * a * b / L if L > 0 else 0.0
            Vu_p = max(Pu * b / L, Pu * a / L) if L > 0 else 0.0
        elif condition == "Cantilever":
            Mu_p, Vu_p = Pu * a, Pu
        elif condition == "Fixed":
            if L > 0:
                Mab = Pu * a * b ** 2 / L ** 2
                Mba = Pu * a ** 2 * b / L ** 2
                Mu_p = max(Mab, Mba)
                R1 = Pu * b ** 2 * (3 * a + b) / L ** 3
                Vu_p = max(R1, Pu - R1)
            notes.append("Fixed-end point-load moments/shears are exact elastic "
                         "values; verify continuity assumptions.")
        elif condition == "Continuous":
            Mu_p = Pu * a * b / L if L > 0 else 0.0
            Vu_p = 1.15 * (max(Pu * b / L, Pu * a / L) if L > 0 else 0.0)
            notes.append("Continuous point-load effects are approximated from "
                         "simple-span results x1.15 (verify by analysis).")

    Mu = Mu_w + Mu_p
    Vu = Vu_w + Vu_p
    m_loc = {"Simply Supported": "midspan (+)", "Cantilever": "fixed support (-)",
             "Fixed": "support (-)", "Continuous": "support (-)"}[condition]
    return Mu, Vu, notes, m_loc


def min_depth_for_deflection(L_mm, condition, fy):
    """
    Minimum overall depth for deflection control (non-prestressed beams).
    NSCP 409.3.1.1 Table (fy=420 base): SS L/16, one-end cont. L/18.5,
    both-end cont. L/21, cantilever L/8. Modified for fy != 420.
    """
    base = {"Simply Supported": 16.0, "Continuous": 18.5,
            "Fixed": 21.0, "Cantilever": 8.0}[condition]
    hmin = L_mm / base
    if abs(fy - 420.0) > 1.0:                    # fy modification (Table note)
        hmin *= (0.4 + fy / 700.0)
    return hmin


def eff_depth(h, cover, stir_dia, bar_dia, layers):
    """Effective depth d for 1 or 2 tension layers (centroid estimate)."""
    d1 = h - cover - stir_dia - bar_dia / 2.0
    if layers <= 1:
        return d1
    # two layers separated by clear VCLEAR: centroid drops by ~(bar_dia+VCLEAR)/2
    return h - cover - stir_dia - bar_dia / 2.0 - (bar_dia + VCLEAR) / 2.0


def rho_balanced(fc, fy):
    """Balanced reinforcement ratio.  NSCP 410 / classic USD."""
    return 0.85 * beta1(fc) * (fc / fy) * (600.0 / (600.0 + fy))


def required_As(Mu, b, d, fc, fy):
    """Required As assuming tension-controlled (phi=0.90). Returns (As,rho,Rn) or None."""
    if d <= 0:
        return None
    Rn = (Mu * 1.0e6) / (PHI_TENSION * b * d ** 2)
    inner = 1.0 - (2.0 * Rn) / (0.85 * fc)
    if inner < 0.0:
        return None
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(inner))
    return rho * b * d, rho, Rn


def As_min_flex(b, d, fc, fy):
    """Minimum flexural steel.  NSCP 409.6.1.2."""
    return max(0.25 * math.sqrt(fc) / fy, 1.4 / fy) * b * d


def As_max_flex(b, d, fc, fy):
    """Max steel at eps_t = 0.004 ductility limit.  NSCP 409.3.3.1."""
    c_d = EPS_CU / (EPS_CU + EPS_MIN_FLEX)
    return 0.85 * beta1(fc) * (fc / fy) * c_d * b * d


def section_response(As, b, d, fc, fy):
    """Compute a, c, eps_t, phi, class, Mn, phiMn for provided As."""
    a = As * fy / (0.85 * fc * b)
    c = a / beta1(fc)
    eps_t = EPS_CU * (d - c) / c if c > 0 else 1.0
    eps_ty = fy / ES
    if eps_t >= EPS_TC:
        phi, cls = PHI_TENSION, "Tension-controlled"
    elif eps_t > eps_ty:
        phi = PHI_COMP + 0.25 * (eps_t - eps_ty) / (EPS_TC - eps_ty)
        cls = "Transition"
    else:
        phi, cls = PHI_COMP, "Compression-controlled"
    Mn = As * fy * (d - a / 2.0) / 1.0e6
    return dict(a=a, c=c, eps_t=eps_t, eps_ty=eps_ty, phi=phi,
                cls=cls, Mn=Mn, phiMn=phi * Mn)


def bars_per_layer(b, cover, stir_dia, bar_dia):
    """How many bars of one size fit across the width in a single layer."""
    clear = max(25.0, bar_dia)                        # NSCP 425.2.1
    usable = b - 2.0 * cover - 2.0 * stir_dia + clear
    return max(1, int(math.floor(usable / (bar_dia + clear))))


def choose_flexural_bars(Mu, b, h, cover, stir_dia, fc, fy, bar_name):
    """
    Select bar count/layers for the governing moment, refining d for layering.
    Returns a dict with n, layers, As_prov, d, section response, As_req/min/max.
    """
    area = BARS[bar_name]["area"]
    db = BARS[bar_name]["dia"]

    # pass 1: single-layer d
    d = eff_depth(h, cover, stir_dia, db, 1)
    req = required_As(Mu, b, d, fc, fy)
    if req is None:
        return {"fatal": "Mu exceeds max singly-reinforced capacity.",
                "d": d, "As_req": None}
    As_req, rho_req, Rn = req
    As_min = As_min_flex(b, d, fc, fy)
    target = max(As_req, As_min)
    n = max(2, math.ceil(target / area))
    per = bars_per_layer(b, cover, stir_dia, db)
    layers = max(1, math.ceil(n / per))

    # pass 2: if 2 layers, recompute d and As
    if layers >= 2:
        d = eff_depth(h, cover, stir_dia, db, 2)
        req = required_As(Mu, b, d, fc, fy)
        if req is None:
            return {"fatal": "Mu exceeds capacity even with revised depth.",
                    "d": d, "As_req": None}
        As_req, rho_req, Rn = req
        As_min = As_min_flex(b, d, fc, fy)
        target = max(As_req, As_min)
        n = max(2, math.ceil(target / area))
        layers = max(1, math.ceil(n / per))

    As_max = As_max_flex(b, d, fc, fy)

    # keep ductile: step back if over-reinforced (eps_t < 0.004)
    while n > 2 and section_response(n * area, b, d, fc, fy)["eps_t"] < EPS_MIN_FLEX:
        n -= 1

    As_prov = n * area
    sec = section_response(As_prov, b, d, fc, fy)
    clear = max(25.0, db)
    req_width = 2 * cover + 2 * stir_dia + min(n, per) * db + (min(n, per) - 1) * clear
    return dict(n=n, layers=layers, per_layer=per, area=area, db=db,
                As_prov=As_prov, d=d, section=sec, As_req=As_req,
                rho_req=rho_req, Rn=Rn, As_min=As_min, As_max=As_max,
                req_width=req_width)


def nominal_top_bars(b, cover, stir_dia):
    """Pick 2 practical hanger/compression bars (opposite the tension face)."""
    # smallest bar that comfortably fits 2 across the width
    for name in ["15M", "10M", "20M"]:
        if bars_per_layer(b, cover, stir_dia, BARS[name]["dia"]) >= 2:
            return 2, name
    return 2, "10M"


def design_shear(Vu, wu, b, d, fc, fy, stir_name, use_crit):
    """Full stirrup design.  NSCP 422.5, 409.6.3.3, 409.7.6.2.2."""
    fyt = min(fy, FYT_MAX)
    sq = math.sqrt(fc)
    d_m = d / 1000.0
    Vu_d = max(Vu - wu * d_m, 0.0) if use_crit else Vu

    Vc = 0.17 * 1.0 * sq * b * d / 1000.0
    phiVc = PHI_SHEAR * Vc
    Av = 2.0 * BARS[stir_name]["area"]
    Vs_max = 0.66 * sq * b * d / 1000.0
    Vs_third = 0.33 * sq * b * d / 1000.0
    av_over_s_min = max(0.062 * sq * b / fyt, 0.35 * b / fyt)
    s_max_min = Av / av_over_s_min

    R = dict(fyt=fyt, Vu_d=Vu_d, Vc=Vc, phiVc=phiVc, Av=Av, Vs_max=Vs_max,
             Vs_third=Vs_third, Vs_req=0.0, ok=True, phiVn=phiVc,
             s_strength=None, s_max_min=s_max_min, s_max_code=None,
             spacing=None, case="")

    if Vu_d <= 0.5 * phiVc:
        R["case"] = "No stirrups required (Vu <= 0.5 phiVc); provide nominal ties."
        R["s_max_code"] = min(d / 2.0, 600.0)
        R["spacing"] = _round_s(min(s_max_min, d / 2.0, 600.0))
        R["phiVn"] = phiVc
        return R
    if Vu_d <= phiVc:
        R["case"] = "Minimum shear reinforcement (0.5 phiVc < Vu <= phiVc)."
        R["s_max_code"] = min(d / 2.0, 600.0)
        R["spacing"] = _round_s(min(s_max_min, d / 2.0, 600.0))
        R["phiVn"] = phiVc
        return R

    Vs_req = (Vu_d - phiVc) / PHI_SHEAR
    R["Vs_req"] = Vs_req
    if Vs_req > Vs_max:
        R["ok"] = False
        R["case"] = "Vs,req exceeds 0.66 sqrt(f'c) b d -> ENLARGE SECTION (422.5.1.2)."
        return R

    s_str = Av * fyt * d / (Vs_req * 1000.0)
    s_code = min(d / 2.0, 600.0) if Vs_req <= Vs_third else min(d / 4.0, 300.0)
    spacing = _round_s(min(s_str, s_max_min, s_code))
    Vs_prov = Av * fyt * d / spacing / 1000.0
    R.update(case="Stirrups required for shear (Vu > phiVc).", s_strength=s_str,
             s_max_code=s_code, spacing=spacing,
             phiVn=PHI_SHEAR * (Vc + Vs_prov))
    return R


def _round_s(s):
    """Round spacing DOWN to practical 25 mm increment (min 50 mm)."""
    return max(50.0, math.floor(max(50.0, s) / 25.0) * 25.0)


def dev_length_tension(fy, fc, db):
    """Straight tension development length.  NSCP 425.4.2.2 (psi=1)."""
    sq = min(math.sqrt(fc), 8.3)
    coef = 2.1 if db <= 20.0 else 1.7
    return max(fy / (coef * 1.0 * sq) * db, 300.0)


def dev_length_hook(fy, fc, db):
    """Standard 90-deg hook development length.  NSCP 425.4.3.1."""
    sq = min(math.sqrt(fc), 8.3)
    return max(0.24 * fy / (1.0 * sq) * db, 8.0 * db, 150.0)


def lap_splice_tension(ld):
    """Class B tension lap splice = 1.3 ld  (NSCP 425.5.2.1)."""
    return max(1.3 * ld, 300.0)


# ---------------------------------------------------------------------------
#  Master routine
# ---------------------------------------------------------------------------
def run_design(I):
    """
    I = dict of validated inputs.  Returns a results dict R with keys used by
    the GUI: forces, flexure, shear, detailing, checks, warnings, calc_steps.
    """
    b, h, cover = I["b"], I["h"], I["cover"]
    fc, fy, lam = I["fc"], I["fy"], I["lam"]
    span, cond = I["span"], I["condition"]
    ltype = I["load_type"]
    main, stir = I["main_bar"], I["stir_bar"]

    stir_dia = BARS[stir]["dia"]

    # ---- loads -------------------------------------------------------------
    w_self = (b * h * 1e-6) * CONC_UNIT_WT if I["self_weight"] else 0.0
    wD = I["wD"] + I["wD_add"] + w_self
    wL = I["wL"]
    wu, u1, u2 = factored_loads(wD, wL)
    Pu = factored_point(I["pD"], I["pL"]) if ltype in ("Point", "Combination") else 0.0
    Mu, Vu, fnotes, m_loc = internal_forces(wu, Pu, I["p_loc"], span, cond, ltype)

    R = {"wD": wD, "wL": wL, "w_self": w_self, "wu": wu, "u1": u1, "u2": u2,
         "Pu": Pu, "Mu": Mu, "Vu": Vu, "m_loc": m_loc, "notes": list(fnotes)}

    warnings, checks, steps = [], [], []

    # ---- calc steps: loads -------------------------------------------------
    steps.append(("FACTORED LOADS  (NSCP 203.3.1)",
        "wD = DL + added DL + self wt = %.2f + %.2f + %.2f = %.2f kN/m"
        % (I["wD"], I["wD_add"], w_self, wD),
        "U1 = 1.4wD = %.2f    U2 = 1.2wD + 1.6wL = %.2f\nGoverning wu = %.2f kN/m"
        % (u1, u2, wu)))
    if Pu > 0:
        steps.append(("FACTORED POINT LOAD  (NSCP 203.3.1)",
            "Pu = max(1.4PD, 1.2PD + 1.6PL) = %.2f kN  @ a = %.2f m" % (Pu, I["p_loc"]), ""))

    mform = {"Simply Supported": "wu L^2/8", "Cantilever": "wu L^2/2",
             "Fixed": "wu L^2/12", "Continuous": "wu L^2/10"}[cond]
    steps.append(("DESIGN MOMENT & SHEAR  (%s)" % cond,
        "Mu = %s (+ point-load effects) = %.2f kN-m  @ %s" % (mform, Mu, m_loc),
        "Vu = %.2f kN  (at support face)" % Vu))

    # ---- deflection depth check -------------------------------------------
    h_min = min_depth_for_deflection(span * 1000.0, cond, fy)
    ok_depth = h >= h_min
    checks.append(("Deflection depth (h >= h,min)", ok_depth,
                   "h=%.0f vs h,min=%.0f mm" % (h, h_min)))
    if not ok_depth:
        warnings.append(("WARN", "Beam depth may be insufficient for deflection "
                                 "(h,min = %.0f mm, NSCP 409.3.1.1)." % h_min))
    steps.append(("MIN DEPTH FOR DEFLECTION  (NSCP 409.3.1.1)",
        "h,min = L / factor (fy-adjusted) = %.0f mm" % h_min,
        "Provided h = %.0f mm -> %s" % (h, "OK" if ok_depth else "REVIEW")))

    # ---- flexure -----------------------------------------------------------
    pick = choose_flexural_bars(Mu, b, h, cover, stir_dia, fc, fy, main)
    R["flex"] = pick
    if pick.get("fatal"):
        warnings.append(("FAIL", "Section inadequate for flexure: " + pick["fatal"]))
        checks.append(("Flexural capacity", False, pick["fatal"]))
        R.update(checks=checks, warnings=warnings, steps=steps,
                 status="FAIL", top=(0, "-"), rho_bal=rho_balanced(fc, fy))
        return R

    d = pick["d"]
    sec = pick["section"]
    rho_bal = rho_balanced(fc, fy)
    n_top, top_name = nominal_top_bars(b, cover, stir_dia)

    # tension face depends on moment sign convention
    tension_bottom = cond in ("Simply Supported", "Continuous")
    R["tension_bottom"] = tension_bottom
    R["bottom"] = (pick["n"], main) if tension_bottom else (n_top, top_name)
    R["top"]    = (n_top, top_name) if tension_bottom else (pick["n"], main)
    R["rho_bal"] = rho_bal
    R["d"] = d

    steps.append(("EFFECTIVE DEPTH",
        "d = h - cover - d,stir - d,bar/2 %s"
        % ("(2 layers adj.)" if pick["layers"] >= 2 else ""),
        "d = %.1f mm  (%d layer(s))" % (d, pick["layers"])))
    steps.append(("FLEXURE - REQUIRED STEEL  (NSCP 422.2)",
        "Rn = Mu/(phi b d^2) = %.3f MPa ;  rho = 0.85f'c/fy [1 - sqrt(1-2Rn/0.85f'c)] = %.5f"
        % (pick["Rn"], pick["rho_req"]),
        "As,req = rho b d = %.0f mm^2" % pick["As_req"]))
    steps.append(("REINF. LIMITS",
        "As,min = max[0.25sqrt(f'c)/fy, 1.4/fy] b d = %.0f mm^2   (409.6.1.2)"
        % pick["As_min"],
        "rho,bal = 0.85 b1 (f'c/fy)(600/(600+fy)) = %.5f ;  As,max(eps=0.004) = %.0f mm^2"
        % (rho_bal, pick["As_max"])))
    steps.append(("STRESS BLOCK & STRAIN  (NSCP 422.2.2)",
        "a = As fy/(0.85 f'c b) = %.1f mm ;  c = a/b1 = %.1f mm" % (sec["a"], sec["c"]),
        "eps_t = 0.003(d-c)/c = %.5f  (%s) ;  phi = %.3f" % (sec["eps_t"], sec["cls"], sec["phi"])))
    steps.append(("FLEXURAL STRENGTH",
        "Mn = As fy (d - a/2) = %.1f kN-m" % sec["Mn"],
        "phiMn = %.1f kN-m   vs   Mu = %.1f kN-m -> %s"
        % (sec["phiMn"], Mu, "OK" if sec["phiMn"] >= Mu else "NG")))

    # flexural checks
    checks.append(("As >= As,min", pick["As_prov"] >= pick["As_min"],
                   "As=%.0f >= %.0f mm^2" % (pick["As_prov"], pick["As_min"])))
    ductile = pick["As_prov"] <= pick["As_max"] and sec["eps_t"] >= EPS_MIN_FLEX
    checks.append(("As <= As,max (ductility)", ductile,
                   "eps_t=%.4f >= 0.004 ; As<=%.0f" % (sec["eps_t"], pick["As_max"])))
    tc = sec["eps_t"] >= EPS_TC
    checks.append(("Tension-controlled", tc,
                   "eps_t=%.4f (%s), phi=%.3f" % (sec["eps_t"], sec["cls"], sec["phi"])))
    checks.append(("phiMn >= Mu", sec["phiMn"] >= Mu,
                   "phiMn=%.1f >= Mu=%.1f kN-m" % (sec["phiMn"], Mu)))
    if not tc and ductile:
        warnings.append(("WARN", "Section is not tension-controlled (transition zone); "
                                 "phi reduced to %.3f." % sec["phi"]))
    if not ductile:
        warnings.append(("FAIL", "Section over-reinforced / brittle (eps_t < 0.004). "
                                 "Increase depth or f'c."))

    # ---- shear -------------------------------------------------------------
    shear = design_shear(Vu, wu, b, d, fc, fy, stir, I["crit_shear"])
    R["shear"] = shear
    steps.append(("SHEAR - CONCRETE  (NSCP 422.5.5.1)",
        "Vc = 0.17 lambda sqrt(f'c) b d = %.1f kN ; phiVc = %.1f kN"
        % (shear["Vc"], shear["phiVc"]),
        ("Vu@d = %.1f kN" % shear["Vu_d"]) if I["crit_shear"] else "Vu = %.1f kN" % Vu))
    if shear["Vs_req"] > 0:
        steps.append(("SHEAR - STIRRUPS  (NSCP 422.5.10)",
            "Vs,req = (Vu - phiVc)/phi = %.1f kN ; Vs,max = 0.66 sqrt(f'c) b d = %.1f kN"
            % (shear["Vs_req"], shear["Vs_max"]),
            "s = Av fyt d / Vs ; provide %s @ %s mm"
            % (stir, ("%.0f" % shear["spacing"]) if shear["spacing"] else "-")))
    else:
        steps.append(("SHEAR - STIRRUPS", shear["case"],
            "Provide %s @ %s mm" % (stir, ("%.0f" % shear["spacing"]) if shear["spacing"] else "-")))

    checks.append(("phiVn >= Vu", shear["phiVn"] >= shear["Vu_d"],
                   "phiVn=%.1f >= Vu=%.1f kN" % (shear["phiVn"], shear["Vu_d"])))
    checks.append(("Vs <= Vs,max (section)", shear["ok"],
                   ("Vs,req=%.1f <= %.1f" % (shear["Vs_req"], shear["Vs_max"]))
                   if shear["Vs_req"] > 0 else "n/a"))
    if not shear["ok"]:
        warnings.append(("FAIL", "Shear capacity inadequate: Vs required exceeds the "
                                 "code upper limit. Enlarge the section."))

    # ---- detailing ---------------------------------------------------------
    db = pick["db"]
    ld = dev_length_tension(fy, fc, db)
    ldh = dev_length_hook(fy, fc, db)
    lap = lap_splice_tension(ld)
    fits1 = pick["req_width"] <= b
    congested = pick["layers"] >= 2 or (pick["req_width"] > 0.95 * b)
    detail = dict(ld=ld, ldh=ldh, lap=lap, clear=max(25.0, db),
                  fits1=fits1, req_width=pick["req_width"],
                  per_layer=pick["per_layer"], layers=pick["layers"],
                  congested=congested)
    R["detail"] = detail
    steps.append(("DEVELOPMENT / ANCHORAGE  (NSCP 425.4)",
        "ld(tension) = %.0f mm ; std hook ldh = %.0f mm" % (ld, ldh),
        "Class B lap = 1.3 ld = %.0f mm ; min clear bar spacing = %.0f mm"
        % (lap, max(25.0, db))))

    checks.append(("Bars fit (layers <= 2)", pick["layers"] <= 2,
                   "%d bar(s), %d/layer, %d layer(s)"
                   % (pick["n"], pick["per_layer"], pick["layers"])))
    if pick["layers"] > 2:
        warnings.append(("FAIL", "Required reinforcement exceeds a practical 2-layer "
                                 "arrangement. Use larger bars or a wider/deeper section."))
    elif congested:
        warnings.append(("WARN", "Reinforcement congestion detected; verify clear "
                                 "spacing and concrete placement."))

    # ---- overall status ----------------------------------------------------
    any_fail = any(not c[1] for c in checks)
    any_warn = any(w[0] == "WARN" for w in warnings)
    status = "FAIL" if any_fail else ("WARN" if any_warn else "PASS")
    if status == "PASS":
        warnings.append(("PASS", "Design satisfies the implemented NSCP 2015 checks."))
    R.update(checks=checks, warnings=warnings, steps=steps, status=status)
    return R


# =============================================================================
#  REPORT
# =============================================================================
def build_report(I, R):
    def ln(c="-", n=76): return c * n
    o = []
    o.append(ln("="))
    o.append("  NSCP 2015 RC BEAM DESIGN REPORT")
    o.append("  Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    o.append(ln("="))
    o.append("\n[ PROJECT INFORMATION ]")
    o.append("  Project : %s" % I["proj"])
    o.append("  Beam ID : %s" % I["beam_id"])
    o.append("  Designer: %s" % I["designer"])
    o.append("  Date    : %s" % I["pdate"])
    if I["notes"].strip():
        o.append("  Notes   : %s" % I["notes"])

    o.append("\n[ GEOMETRY & MATERIALS ]")
    o.append("  b=%.0f mm  h=%.0f mm  span=%.3f m  cover=%.0f mm  support=%s"
             % (I["b"], I["h"], I["span"], I["cover"], I["condition"]))
    o.append("  f'c=%.1f MPa  fy=%.1f MPa  lambda=%.2f  (normal weight assumed)"
             % (I["fc"], I["fy"], I["lam"]))

    o.append("\n[ LOADS ]  (load type: %s)" % I["load_type"])
    o.append("  Dead=%.2f  Added dead=%.2f  Self wt=%.2f  ->  wD=%.2f kN/m"
             % (I["wD"], I["wD_add"], R["w_self"], R["wD"]))
    o.append("  Live=%.2f kN/m" % I["wL"])
    if R["Pu"] > 0:
        o.append("  Point: PD=%.2f  PL=%.2f  @ a=%.2f m  ->  Pu=%.2f kN"
                 % (I["pD"], I["pL"], I["p_loc"], R["Pu"]))
    o.append("  Factored: 1.4D=%.2f  1.2D+1.6L=%.2f  ->  wu=%.2f kN/m"
             % (R["u1"], R["u2"], R["wu"]))
    o.append("  Mu=%.2f kN-m @ %s   Vu=%.2f kN" % (R["Mu"], R["m_loc"], R["Vu"]))

    o.append("\n[ CALCULATION STEPS ]")
    for title, a, b_ in R["steps"]:
        o.append("  * " + title)
        if a: o.append("      " + a.replace("\n", "\n      "))
        if b_: o.append("      " + b_.replace("\n", "\n      "))

    if not R["flex"].get("fatal"):
        p = R["flex"]; sec = p["section"]
        o.append("\n[ FLEXURAL DESIGN ]")
        o.append("  d=%.1f mm  As,req=%.0f  As,min=%.0f  As,max=%.0f mm^2"
                 % (p["d"], p["As_req"], p["As_min"], p["As_max"]))
        o.append("  rho,req=%.5f  rho,bal=%.5f" % (p["rho_req"], R["rho_bal"]))
        o.append("  a=%.1f mm  c=%.1f mm  eps_t=%.5f (%s)  phi=%.3f"
                 % (sec["a"], sec["c"], sec["eps_t"], sec["cls"], sec["phi"]))
        o.append("  Mn=%.1f  phiMn=%.1f kN-m" % (sec["Mn"], sec["phiMn"]))
        o.append("  BOTTOM: %d-%s      TOP: %d-%s"
                 % (R["bottom"][0], R["bottom"][1], R["top"][0], R["top"][1]))

        s = R["shear"]
        o.append("\n[ SHEAR DESIGN ]")
        o.append("  Vc=%.1f  phiVc=%.1f  Vs,req=%.1f  Vs,max=%.1f kN"
                 % (s["Vc"], s["phiVc"], s["Vs_req"], s["Vs_max"]))
        o.append("  phiVn=%.1f kN   %s" % (s["phiVn"], s["case"]))
        if s["spacing"]:
            o.append("  STIRRUPS: 2-%s @ %.0f mm" % (I["stir_bar"], s["spacing"]))

        de = R["detail"]
        o.append("\n[ DETAILING (PRELIMINARY - VERIFY) ]")
        o.append("  ld=%.0f mm  hook ldh=%.0f mm  Class-B lap=%.0f mm  clear spc=%.0f mm"
                 % (de["ld"], de["ldh"], de["lap"], de["clear"]))
        o.append("  bars/layer=%d  layers=%d  req width=%.0f mm (b=%.0f)"
                 % (de["per_layer"], de["layers"], de["req_width"], I["b"]))

    o.append("\n[ DESIGN CHECKS ]")
    for label, ok, note in R["checks"]:
        o.append("  [%s] %-26s %s" % ("PASS" if ok else "FAIL", label, note))
    o.append("\n  OVERALL STATUS: %s" % R["status"])

    o.append("\n[ WARNINGS / NOTES ]")
    for tag, msg in R["warnings"]:
        o.append("  (%s) %s" % (tag, msg))
    for nte in R["notes"]:
        o.append("  (note) " + nte)

    o.append("\n[ NSCP 2015 BASIS ]")
    o.append("  203.3.1 loads; 421.2 phi; 422.2 flexure; 422.2.2.4.3 beta1;")
    o.append("  409.3.1.1 depth; 409.3.3.1 strain; 409.6.1.2 As,min; 410 balanced;")
    o.append("  422.5 shear; 409.6.3.3 min shear reinf; 409.7.6.2.2 max spacing;")
    o.append("  425.2.1 spacing; 425.4.2.2 ld; 425.4.3.1 hook; 425.5.2.1 laps.")

    o.append("\n[ LIMITATIONS & ASSUMPTIONS ]")
    o.append("  - Singly-reinforced rectangular section; top steel nominal only.")
    o.append("  - Continuous/fixed forces use approximate coefficients (406.5).")
    o.append("  - Deflection check is depth-based (no explicit deflection calc).")
    o.append("  - Seismic detailing, torsion, and bar cut-offs NOT included.")
    o.append("  - Development/anchorage/lap values are simplified (psi=1.0).")
    o.append(ln("="))
    o.append("  ENGINEERING CALCULATION AID. The engineer remains responsible for")
    o.append("  verifying all NSCP 2015 provisions, loads, analysis, load")
    o.append("  combinations, detailing, seismic provisions, development and")
    o.append("  anchorage, and the final design.")
    o.append(ln("="))
    return "\n".join(o)


# =============================================================================
#  GUI HELPERS
# =============================================================================
class Tooltip:
    """Lightweight hover tooltip."""
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=self.text, bg="#0a1017", fg=T.TEXT, font=T.F_SUB,
                 relief="solid", bd=1, padx=6, pady=3, justify="left",
                 wraplength=280).pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def card(parent, title=None):
    """A titled panel."""
    outer = tk.Frame(parent, bg=T.CARD, highlightbackground=T.STROKE,
                     highlightthickness=1)
    if title:
        tk.Label(outer, text=title, bg=T.CARD, fg=T.ACCENT2, font=T.F_H,
                 anchor="w").pack(fill="x", padx=12, pady=(9, 2))
    inner = tk.Frame(outer, bg=T.CARD)
    inner.pack(fill="both", expand=True, padx=12, pady=(2, 10))
    return outer, inner


# =============================================================================
#  MAIN APPLICATION
# =============================================================================
class BeamStudio:
    def __init__(self, root):
        self.root = root
        root.title("NSCP 2015 RC Beam Studio")
        root.geometry("1240x800")
        root.minsize(1080, 720)
        root.configure(bg=T.BG)

        self.vars = {}
        self.result_widgets = {}
        self.R = None
        self.report_text = ""

        # 3D view state
        self.ax, self.ay = 0.44, -0.62      # rotation (rad)
        self.zoom = 150.0
        self.panx, self.pany = 0.0, 0.0
        self.show_conc = tk.BooleanVar(value=True)
        self.show_rebar = tk.BooleanVar(value=True)
        self._last = None

        self._make_vars()
        self._build_header()
        self._build_body()
        self._show_page("Project")
        self.recompute()

    # -- default variable set ----------------------------------------------
    def _make_vars(self):
        d = {
            "proj": "Sample Project", "beam_id": "B-1",
            "designer": "", "pdate": date.today().isoformat(), "notes": "",
            "b": "300", "h": "500", "span": "6.0", "cover": "40",
            "condition": "Simply Supported",
            "fc": "28", "fy": "420", "lam": "1.0",
            "wD": "15", "wD_add": "0", "wL": "20",
            "pD": "0", "pL": "0", "p_loc": "3.0", "load_type": "Uniform",
            "main_bar": "25M", "stir_bar": "10M",
        }
        for k, v in d.items():
            self.vars[k] = tk.StringVar(value=v)
        self.self_weight = tk.BooleanVar(value=True)
        self.crit_shear = tk.BooleanVar(value=True)
        self.defaults = dict(d)

    # -- header ------------------------------------------------------------
    def _build_header(self):
        hd = tk.Frame(self.root, bg=T.HEADER, height=62)
        hd.pack(fill="x", side="top")
        hd.pack_propagate(False)
        left = tk.Frame(hd, bg=T.HEADER)
        left.pack(side="left", padx=16)
        tk.Label(left, text="\u25A3  RC BEAM STUDIO", bg=T.HEADER, fg=T.TEXT,
                 font=T.F_TITLE).pack(anchor="w", pady=(8, 0))
        tk.Label(left, text="NSCP 2015  \u2022  RC BEAM DESIGN  \u2022  Strength Design (USD)",
                 bg=T.HEADER, fg=T.MUTED, font=T.F_SUB).pack(anchor="w")

        right = tk.Frame(hd, bg=T.HEADER)
        right.pack(side="right", padx=16)
        tk.Label(right, text="DESIGN STATUS", bg=T.HEADER, fg=T.MUTED,
                 font=("Segoe UI", 8)).pack(anchor="e", pady=(10, 0))
        self.status_lbl = tk.Label(right, text="  \u2014  ", bg=T.MUTED, fg="#0a1017",
                                   font=T.F_H, padx=14, pady=3)
        self.status_lbl.pack(anchor="e")

    # -- body: sidebar + content ------------------------------------------
    def _build_body(self):
        body = tk.Frame(self.root, bg=T.BG)
        body.pack(fill="both", expand=True)

        # sidebar
        sb = tk.Frame(body, bg=T.SIDEBAR, width=176)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self.nav_btns = {}
        self.pages = {}
        names = ["Project", "Geometry", "Materials", "Loads", "Flexure",
                 "Shear", "Detailing", "3D View", "Calculations", "Report"]
        for nm in names:
            btn = tk.Label(sb, text="   " + nm, bg=T.SIDEBAR, fg=T.MUTED,
                           font=T.F_LBL, anchor="w", padx=10, pady=9, cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, n=nm: self._show_page(n))
            self.nav_btns[nm] = btn

        tk.Frame(sb, bg=T.STROKE, height=1).pack(fill="x", pady=6)
        tk.Button(sb, text="Recompute", command=self.recompute, bg=T.ACCENT,
                  fg="white", font=T.F_H, relief="flat", cursor="hand2"
                  ).pack(fill="x", padx=10, pady=4)
        tk.Button(sb, text="Reset Defaults", command=self.reset_defaults,
                  bg=T.CARD2, fg=T.TEXT, relief="flat", cursor="hand2"
                  ).pack(fill="x", padx=10, pady=2)

        # content area (pages stacked, raised on demand)
        self.content = tk.Frame(body, bg=T.BG)
        self.content.pack(side="right", fill="both", expand=True)
        for nm in names:
            pg = tk.Frame(self.content, bg=T.BG)
            pg.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[nm] = pg
        self._build_project(self.pages["Project"])
        self._build_geometry(self.pages["Geometry"])
        self._build_materials(self.pages["Materials"])
        self._build_loads(self.pages["Loads"])
        self._build_flexure(self.pages["Flexure"])
        self._build_shear(self.pages["Shear"])
        self._build_detailing(self.pages["Detailing"])
        self._build_3d(self.pages["3D View"])
        self._build_calcs(self.pages["Calculations"])
        self._build_report(self.pages["Report"])

    def _show_page(self, name):
        for nm, b in self.nav_btns.items():
            sel = nm == name
            b.configure(bg=T.ACCENT if sel else T.SIDEBAR,
                        fg="white" if sel else T.MUTED)
        self.pages[name].tkraise()

    # -- input widget factory ---------------------------------------------
    def _field(self, parent, r, label, key, tip="", width=14, combo=None):
        tk.Label(parent, text=label, bg=T.CARD, fg=T.TEXT, font=T.F_LBL,
                 anchor="w").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 8))
        if combo:
            w = ttk.Combobox(parent, textvariable=self.vars[key], values=combo,
                             state="readonly", width=width - 2)
        else:
            w = tk.Entry(parent, textvariable=self.vars[key], width=width,
                         bg=T.CARD2, fg=T.TEXT, insertbackground=T.TEXT,
                         relief="flat", highlightthickness=1,
                         highlightbackground=T.STROKE)
        w.grid(row=r, column=1, sticky="w", pady=4)
        if tip:
            Tooltip(w, tip)
        return w

    # -- PROJECT page ------------------------------------------------------
    def _build_project(self, pg):
        self._page_title(pg, "Project Information",
                         "Identify the beam and designer for the report header.")
        c, inner = card(pg, "Project Details")
        c.pack(fill="x", padx=16, pady=8)
        self._field(inner, 0, "Project name", "proj", width=34)
        self._field(inner, 1, "Beam ID", "beam_id", width=20)
        self._field(inner, 2, "Designer", "designer", width=34)
        self._field(inner, 3, "Date", "pdate", width=20)
        tk.Label(inner, text="Notes", bg=T.CARD, fg=T.TEXT, font=T.F_LBL,
                 anchor="w").grid(row=4, column=0, sticky="nw", pady=4)
        self.notes_txt = tk.Text(inner, height=4, width=44, bg=T.CARD2, fg=T.TEXT,
                                 relief="flat", insertbackground=T.TEXT,
                                 highlightthickness=1, highlightbackground=T.STROKE)
        self.notes_txt.grid(row=4, column=1, sticky="w", pady=4)
        self._disclaimer(pg)

    # -- GEOMETRY page -----------------------------------------------------
    def _build_geometry(self, pg):
        self._page_title(pg, "Geometry", "Section and span dimensions (mm, m).")
        c, inner = card(pg, "Beam Geometry")
        c.pack(fill="x", padx=16, pady=8)
        self._field(inner, 0, "Beam width b (mm)", "b", "Web width")
        self._field(inner, 1, "Overall depth h (mm)", "h", "Total section depth")
        self._field(inner, 2, "Span L (m)", "span", "Clear/eff. span")
        self._field(inner, 3, "Clear cover (mm)", "cover", "To stirrup, NSCP 420.6.1")
        self._field(inner, 4, "Support condition", "condition", combo=SUPPORTS, width=20)
        # live cross-section preview
        c2, in2 = card(pg, "Cross-Section Preview")
        c2.pack(fill="both", expand=True, padx=16, pady=8)
        self.geo_canvas = tk.Canvas(in2, bg=T.CARD, highlightthickness=0, height=260)
        self.geo_canvas.pack(fill="both", expand=True)
        self.geo_canvas.bind("<Configure>", lambda e: self._draw_section(self.geo_canvas))

    # -- MATERIALS page ----------------------------------------------------
    def _build_materials(self, pg):
        self._page_title(pg, "Materials", "Concrete and reinforcing steel.")
        c, inner = card(pg, "Material Properties")
        c.pack(fill="x", padx=16, pady=8)
        self._field(inner, 0, "Concrete f'c (MPa)", "fc", "Cylinder strength")
        self._field(inner, 1, "Steel fy (MPa)", "fy", "Yield strength")
        self._field(inner, 2, "Lightweight factor lambda", "lam",
                    "1.0 normal weight; <1.0 lightweight (422.2.2.2)")
        tk.Checkbutton(inner, text="Normal-weight concrete assumption",
                       variable=tk.BooleanVar(value=True), state="disabled",
                       bg=T.CARD, fg=T.MUTED, selectcolor=T.CARD2,
                       activebackground=T.CARD).grid(row=3, column=0, columnspan=2,
                                                     sticky="w", pady=4)
        c2, in2 = card(pg, "Reinforcement Selection")
        c2.pack(fill="x", padx=16, pady=8)
        self._field(in2, 0, "Main bar", "main_bar", combo=MAIN_BARS, width=12)
        self._field(in2, 1, "Stirrup bar", "stir_bar", combo=STIR_BARS, width=12)
        tk.Label(in2, text="Bars: 10M/15M/20M/25M/30M/35M (Canadian metric)",
                 bg=T.CARD, fg=T.MUTED, font=T.F_SUB).grid(row=2, column=0,
                                                           columnspan=2, sticky="w")
        self._disclaimer(pg)

    # -- LOADS page --------------------------------------------------------
    def _build_loads(self, pg):
        self._page_title(pg, "Loads", "Service loads; factored automatically per 203.3.1.")
        c, inner = card(pg, "Applied Loads")
        c.pack(fill="x", padx=16, pady=8)
        self._field(inner, 0, "Dead load wD (kN/m)", "wD")
        self._field(inner, 1, "Additional dead (kN/m)", "wD_add", "Superimposed dead")
        self._field(inner, 2, "Live load wL (kN/m)", "wL")
        tk.Checkbutton(inner, text="Add beam self-weight automatically",
                       variable=self.self_weight, bg=T.CARD, fg=T.TEXT,
                       selectcolor=T.CARD2, activebackground=T.CARD,
                       command=self.recompute).grid(row=3, column=0, columnspan=2,
                                                    sticky="w", pady=(6, 0))
        tk.Checkbutton(inner, text="Design shear at d from support (409.4.3.2)",
                       variable=self.crit_shear, bg=T.CARD, fg=T.TEXT,
                       selectcolor=T.CARD2, activebackground=T.CARD,
                       command=self.recompute).grid(row=4, column=0, columnspan=2,
                                                    sticky="w")
        c2, in2 = card(pg, "Load Type / Point Load")
        c2.pack(fill="x", padx=16, pady=8)
        self._field(in2, 0, "Load type", "load_type", combo=LOAD_TYPES, width=16)
        self._field(in2, 1, "Point dead PD (kN)", "pD")
        self._field(in2, 2, "Point live PL (kN)", "pL")
        self._field(in2, 3, "Point location a (m)", "p_loc", "From left support")

        c3, in3 = card(pg, "Diagrams (elevation / SFD / BMD)")
        c3.pack(fill="both", expand=True, padx=16, pady=8)
        self.diag_canvas = tk.Canvas(in3, bg=T.CARD, highlightthickness=0, height=300)
        self.diag_canvas.pack(fill="both", expand=True)
        self.diag_canvas.bind("<Configure>", lambda e: self._draw_diagrams())

    # -- result label helper ----------------------------------------------
    def _metric(self, parent, r, key, label, unit=""):
        tk.Label(parent, text=label, bg=T.CARD, fg=T.MUTED, font=T.F_SUB,
                 anchor="w").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=2)
        v = tk.Label(parent, text="-", bg=T.CARD, fg=T.TEXT, font=T.F_MONO,
                     anchor="w")
        v.grid(row=r, column=1, sticky="w", pady=2)
        if unit:
            tk.Label(parent, text=unit, bg=T.CARD, fg=T.MUTED, font=T.F_SUB
                     ).grid(row=r, column=2, sticky="w", padx=4)
        self.result_widgets[key] = v
        return v

    # -- FLEXURE page ------------------------------------------------------
    def _build_flexure(self, pg):
        self._page_title(pg, "Flexural Design", "NSCP 422.2 / 409.6.1.2 / 409.3.3.1")
        top = tk.Frame(pg, bg=T.BG)
        top.pack(fill="x", padx=16, pady=8)

        # big selected-reinforcement card
        cbig, inbig = card(top, "Selected Flexural Reinforcement")
        cbig.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.flex_bottom = tk.Label(inbig, text="-", bg=T.CARD, fg=T.REBAR_B,
                                    font=T.F_HUGE)
        self.flex_bottom.pack(anchor="w")
        tk.Label(inbig, text="BOTTOM", bg=T.CARD, fg=T.MUTED, font=T.F_SUB).pack(anchor="w")
        self.flex_top = tk.Label(inbig, text="-", bg=T.CARD, fg=T.REBAR_T, font=T.F_BIG)
        self.flex_top.pack(anchor="w", pady=(8, 0))
        tk.Label(inbig, text="TOP", bg=T.CARD, fg=T.MUTED, font=T.F_SUB).pack(anchor="w")
        self.flex_verdict = tk.Label(inbig, text="", bg=T.CARD, font=T.F_H)
        self.flex_verdict.pack(anchor="w", pady=(10, 0))

        # metrics card
        cm, inm = card(top, "Flexure Results")
        cm.pack(side="left", fill="both", expand=True)
        rows = [("Mu", "Mu", "kN-m"), ("d", "d", "mm"), ("As,req", "As_req", "mm^2"),
                ("As,min", "As_min", "mm^2"), ("As,max", "As_max", "mm^2"),
                ("As,prov", "As_prov", "mm^2"), ("rho", "rho", ""),
                ("rho,bal", "rho_bal", ""), ("a", "a", "mm"), ("c", "c", "mm"),
                ("eps_t", "eps_t", ""), ("phi", "phi", ""),
                ("Mn", "Mn", "kN-m"), ("phiMn", "phiMn", "kN-m")]
        for i, (lab, key, u) in enumerate(rows):
            self._metric(inm, i, "flex_" + key, lab, u)

        # cross-section + BMD
        c2, in2 = card(pg, "Cross-Section & Bending Moment")
        c2.pack(fill="both", expand=True, padx=16, pady=8)
        self.flex_canvas = tk.Canvas(in2, bg=T.CARD, highlightthickness=0, height=240)
        self.flex_canvas.pack(fill="both", expand=True)
        self.flex_canvas.bind("<Configure>", lambda e: self._draw_flex_canvas())

    # -- SHEAR page --------------------------------------------------------
    def _build_shear(self, pg):
        self._page_title(pg, "Shear Design", "NSCP 422.5 / 409.6.3.3 / 409.7.6.2.2")
        top = tk.Frame(pg, bg=T.BG)
        top.pack(fill="x", padx=16, pady=8)
        cbig, inbig = card(top, "Selected Stirrups")
        cbig.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.shear_sel = tk.Label(inbig, text="-", bg=T.CARD, fg=T.STIRRUP, font=T.F_HUGE)
        self.shear_sel.pack(anchor="w")
        self.shear_verdict = tk.Label(inbig, text="", bg=T.CARD, font=T.F_H)
        self.shear_verdict.pack(anchor="w", pady=(10, 0))
        self.shear_case = tk.Label(inbig, text="", bg=T.CARD, fg=T.MUTED,
                                   font=T.F_SUB, wraplength=280, justify="left")
        self.shear_case.pack(anchor="w", pady=(6, 0))

        cm, inm = card(top, "Shear Results")
        cm.pack(side="left", fill="both", expand=True)
        rows = [("Vu (design)", "Vu_d", "kN"), ("Vc", "Vc", "kN"),
                ("phiVc", "phiVc", "kN"), ("Vs,req", "Vs_req", "kN"),
                ("Vs,max", "Vs_max", "kN"), ("phiVn", "phiVn", "kN"),
                ("s (strength)", "s_strength", "mm"), ("s,max code", "s_max_code", "mm"),
                ("s,max min-reinf", "s_max_min", "mm"), ("Provided s", "spacing", "mm")]
        for i, (lab, key, u) in enumerate(rows):
            self._metric(inm, i, "shear_" + key, lab, u)

        c2, in2 = card(pg, "Shear Force Diagram")
        c2.pack(fill="both", expand=True, padx=16, pady=8)
        self.sfd_canvas = tk.Canvas(in2, bg=T.CARD, highlightthickness=0, height=220)
        self.sfd_canvas.pack(fill="both", expand=True)
        self.sfd_canvas.bind("<Configure>", lambda e: self._draw_sfd())

    # -- DETAILING page ----------------------------------------------------
    def _build_detailing(self, pg):
        self._page_title(pg, "Detailing (Preliminary)",
                         "Simplified checks - final verification by engineer required.")
        c, inm = card(pg, "Development / Spacing")
        c.pack(fill="x", padx=16, pady=8)
        rows = [("ld (tension)", "ld", "mm"), ("Std hook ldh", "ldh", "mm"),
                ("Class-B lap", "lap", "mm"), ("Min clear spacing", "clear", "mm"),
                ("Bars per layer", "per_layer", ""), ("Layers", "layers", ""),
                ("Req. width", "req_width", "mm")]
        for i, (lab, key, u) in enumerate(rows):
            self._metric(inm, i, "det_" + key, lab, u)
        c2, in2 = card(pg, "Detailing Checklist")
        c2.pack(fill="both", expand=True, padx=16, pady=8)
        self.detail_box = tk.Text(in2, bg=T.CARD2, fg=T.TEXT, font=T.F_MONO,
                                  relief="flat", height=12, wrap="word",
                                  highlightthickness=1, highlightbackground=T.STROKE)
        self.detail_box.pack(fill="both", expand=True)

    # -- 3D page -----------------------------------------------------------
    def _build_3d(self, pg):
        self._page_title(pg, "3D Beam Model",
                         "Drag: rotate  \u2022  Scroll: zoom  \u2022  Right-drag: pan")
        bar = tk.Frame(pg, bg=T.BG)
        bar.pack(fill="x", padx=16, pady=(4, 0))
        for txt, cmd in [("Isometric", self._view_iso), ("Front", self._view_front),
                         ("Side", self._view_side), ("Top", self._view_top),
                         ("Zoom +", lambda: self._zoom(1.2)),
                         ("Zoom -", lambda: self._zoom(1 / 1.2)),
                         ("Reset", self._view_reset)]:
            tk.Button(bar, text=txt, command=cmd, bg=T.CARD2, fg=T.TEXT,
                      relief="flat", padx=8, cursor="hand2").pack(side="left", padx=3)
        tk.Checkbutton(bar, text="Concrete", variable=self.show_conc, bg=T.BG,
                       fg=T.TEXT, selectcolor=T.CARD2, activebackground=T.BG,
                       command=self._draw_3d).pack(side="left", padx=(14, 3))
        tk.Checkbutton(bar, text="Rebar", variable=self.show_rebar, bg=T.BG,
                       fg=T.TEXT, selectcolor=T.CARD2, activebackground=T.BG,
                       command=self._draw_3d).pack(side="left", padx=3)

        c, inn = card(pg, None)
        c.pack(fill="both", expand=True, padx=16, pady=8)
        self.cv3d = tk.Canvas(inn, bg="#0a0f16", highlightthickness=0)
        self.cv3d.pack(fill="both", expand=True)
        self.cv3d.bind("<Configure>", lambda e: self._draw_3d())
        self.cv3d.bind("<ButtonPress-1>", self._start_drag)
        self.cv3d.bind("<B1-Motion>", self._rotate_drag)
        self.cv3d.bind("<ButtonPress-3>", self._start_drag)
        self.cv3d.bind("<B3-Motion>", self._pan_drag)
        self.cv3d.bind("<MouseWheel>", lambda e: self._zoom(1.1 if e.delta > 0 else 1/1.1))
        self.cv3d.bind("<Button-4>", lambda e: self._zoom(1.1))
        self.cv3d.bind("<Button-5>", lambda e: self._zoom(1/1.1))

    # -- CALCULATIONS page -------------------------------------------------
    def _build_calcs(self, pg):
        self._page_title(pg, "Calculations",
                         "Equations with substituted values, in design order.")
        c, inn = card(pg, None)
        c.pack(fill="both", expand=True, padx=16, pady=8)
        self.calc_box = tk.Text(inn, bg=T.CARD2, fg=T.TEXT, font=T.F_MONO,
                                relief="flat", wrap="word", highlightthickness=1,
                                highlightbackground=T.STROKE)
        self.calc_box.pack(fill="both", expand=True)

    # -- REPORT page -------------------------------------------------------
    def _build_report(self, pg):
        self._page_title(pg, "Report", "Generate and save a .txt calculation report.")
        bar = tk.Frame(pg, bg=T.BG)
        bar.pack(fill="x", padx=16, pady=6)
        tk.Button(bar, text="Generate Report", command=self.generate_report,
                  bg=T.ACCENT, fg="white", font=T.F_H, relief="flat",
                  padx=12, cursor="hand2").pack(side="left")
        tk.Button(bar, text="Save as .txt", command=self.save_report,
                  bg=T.CARD2, fg=T.TEXT, relief="flat", padx=12,
                  cursor="hand2").pack(side="left", padx=8)
        c, inn = card(pg, None)
        c.pack(fill="both", expand=True, padx=16, pady=8)
        self.report_box = tk.Text(inn, bg=T.CARD2, fg=T.TEXT, font=T.F_MONO_S,
                                  relief="flat", wrap="none", highlightthickness=1,
                                  highlightbackground=T.STROKE)
        self.report_box.pack(fill="both", expand=True)

    # -- shared page chrome ------------------------------------------------
    def _page_title(self, pg, title, sub):
        top = tk.Frame(pg, bg=T.BG)
        top.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(top, text=title, bg=T.BG, fg=T.TEXT, font=T.F_TITLE).pack(anchor="w")
        tk.Label(top, text=sub, bg=T.BG, fg=T.MUTED, font=T.F_SUB).pack(anchor="w")
        tk.Frame(pg, bg=T.STROKE, height=1).pack(fill="x", padx=16, pady=(8, 0))

    def _disclaimer(self, pg):
        f = tk.Frame(pg, bg=T.BG)
        f.pack(fill="x", side="bottom", padx=16, pady=8)
        tk.Label(f, text="Engineering calculation aid only \u2014 all results require "
                 "verification by a licensed structural engineer.",
                 bg=T.BG, fg=T.WARN, font=T.F_SUB, wraplength=760,
                 justify="left").pack(anchor="w")

    # ======================================================================
    #  INPUT READING + VALIDATION
    # ======================================================================
    def _read_inputs(self):
        def f(key, name, pos=True, nonneg=False):
            try:
                val = float(self.vars[key].get())
            except ValueError:
                raise ValueError("'%s' must be a number." % name)
            if pos and val <= 0:
                raise ValueError("'%s' must be greater than zero." % name)
            if nonneg and val < 0:
                raise ValueError("'%s' cannot be negative." % name)
            return val

        I = dict(
            proj=self.vars["proj"].get(), beam_id=self.vars["beam_id"].get(),
            designer=self.vars["designer"].get(), pdate=self.vars["pdate"].get(),
            notes=self.notes_txt.get("1.0", "end").strip()
            if hasattr(self, "notes_txt") else "",
            b=f("b", "Beam width"), h=f("h", "Overall depth"),
            span=f("span", "Span"), cover=f("cover", "Clear cover"),
            condition=self.vars["condition"].get(),
            fc=f("fc", "f'c"), fy=f("fy", "fy"), lam=f("lam", "lambda"),
            wD=f("wD", "Dead load", pos=False, nonneg=True),
            wD_add=f("wD_add", "Additional dead", pos=False, nonneg=True),
            wL=f("wL", "Live load", pos=False, nonneg=True),
            pD=f("pD", "Point dead", pos=False, nonneg=True),
            pL=f("pL", "Point live", pos=False, nonneg=True),
            p_loc=f("p_loc", "Point location", pos=False, nonneg=True),
            load_type=self.vars["load_type"].get(),
            main_bar=self.vars["main_bar"].get(), stir_bar=self.vars["stir_bar"].get(),
            self_weight=self.self_weight.get(), crit_shear=self.crit_shear.get(),
        )
        d_est = I["h"] - I["cover"] - BARS[I["stir_bar"]]["dia"] \
            - BARS[I["main_bar"]]["dia"] / 2.0
        if d_est <= 0:
            raise ValueError("Effective depth non-positive; increase h or reduce cover.")
        if I["lam"] <= 0 or I["lam"] > 1.0:
            raise ValueError("lambda must be between 0 and 1.0.")
        if I["p_loc"] > I["span"]:
            raise ValueError("Point-load location exceeds the span.")
        return I

    # ======================================================================
    #  RECOMPUTE + REFRESH
    # ======================================================================
    def recompute(self, _=None):
        try:
            I = self._read_inputs()
        except Exception as e:            # noqa: BLE001
            self._set_status("FAIL")
            messagebox.showerror("Input Error", str(e))
            return
        try:
            self.I = I
            self.R = run_design(I)
        except Exception as e:            # noqa: BLE001
            self._set_status("FAIL")
            messagebox.showerror("Calculation Error", str(e))
            return
        self._refresh_all()

    def _set_status(self, status):
        color = {"PASS": T.PASS, "WARN": T.WARN, "FAIL": T.FAIL}.get(status, T.MUTED)
        self.status_lbl.configure(text="  %s  " % status, bg=color)

    def _refresh_all(self):
        R = self.R
        self._set_status(R["status"])
        self._refresh_flexure()
        self._refresh_shear()
        self._refresh_detailing()
        self._refresh_calcs()
        # redraw all canvases
        self._draw_section(self.geo_canvas)
        self._draw_diagrams()
        self._draw_flex_canvas()
        self._draw_sfd()
        self._draw_3d()

    def _put(self, key, txt, color=None):
        w = self.result_widgets.get(key)
        if w:
            w.configure(text=txt, fg=color or T.TEXT)

    def _refresh_flexure(self):
        R = self.R
        self._put("flex_Mu", "%.1f" % R["Mu"])
        if R["flex"].get("fatal"):
            self.flex_bottom.configure(text="SECTION NG")
            self.flex_top.configure(text="")
            self.flex_verdict.configure(text="FLEXURE FAIL", fg=T.FAIL)
            for k in ["d", "As_req", "As_min", "As_max", "As_prov", "rho",
                      "rho_bal", "a", "c", "eps_t", "phi", "Mn", "phiMn"]:
                self._put("flex_" + k, "-")
            return
        p = R["flex"]; sec = p["section"]
        self._put("flex_d", "%.1f" % p["d"])
        self._put("flex_As_req", "%.0f" % p["As_req"])
        self._put("flex_As_min", "%.0f" % p["As_min"])
        self._put("flex_As_max", "%.0f" % p["As_max"])
        self._put("flex_As_prov", "%.0f" % p["As_prov"])
        self._put("flex_rho", "%.5f" % (p["As_prov"] / (self.I["b"] * p["d"])))
        self._put("flex_rho_bal", "%.5f" % R["rho_bal"])
        self._put("flex_a", "%.1f" % sec["a"])
        self._put("flex_c", "%.1f" % sec["c"])
        tc_color = T.PASS if sec["eps_t"] >= EPS_TC else (
            T.WARN if sec["eps_t"] >= EPS_MIN_FLEX else T.FAIL)
        self._put("flex_eps_t", "%.5f" % sec["eps_t"], tc_color)
        self._put("flex_phi", "%.3f" % sec["phi"])
        self._put("flex_Mn", "%.1f" % sec["Mn"])
        ok = sec["phiMn"] >= R["Mu"]
        self._put("flex_phiMn", "%.1f" % sec["phiMn"], T.PASS if ok else T.FAIL)
        self.flex_bottom.configure(text="%d-%s" % R["bottom"])
        self.flex_top.configure(text="%d-%s" % R["top"])
        fok = all(c[1] for c in R["checks"] if c[0] in
                  ("As >= As,min", "As <= As,max (ductility)", "phiMn >= Mu"))
        self.flex_verdict.configure(text="FLEXURE " + ("PASS" if fok else "CHECK"),
                                    fg=T.PASS if fok else T.FAIL)

    def _refresh_shear(self):
        R = self.R
        if R["flex"].get("fatal"):
            self.shear_sel.configure(text="-")
            self.shear_verdict.configure(text="")
            self.shear_case.configure(text="Resolve flexure first.")
            for k in ["Vu_d", "Vc", "phiVc", "Vs_req", "Vs_max", "phiVn",
                      "s_strength", "s_max_code", "s_max_min", "spacing"]:
                self._put("shear_" + k, "-")
            return
        s = R["shear"]
        for k in ["Vu_d", "Vc", "phiVc", "Vs_req", "Vs_max", "phiVn"]:
            self._put("shear_" + k, "%.1f" % s[k])
        for k in ["s_strength", "s_max_code", "s_max_min", "spacing"]:
            self._put("shear_" + k, "%.0f" % s[k] if s[k] else "-")
        if s["spacing"]:
            self.shear_sel.configure(text="2-%s @ %.0f" % (self.I["stir_bar"], s["spacing"]))
        else:
            self.shear_sel.configure(text="-")
        ok = s["ok"] and s["phiVn"] >= s["Vu_d"]
        self.shear_verdict.configure(text="SHEAR " + ("PASS" if ok else "FAIL"),
                                     fg=T.PASS if ok else T.FAIL)
        self.shear_case.configure(text=s["case"])

    def _refresh_detailing(self):
        R = self.R
        if R["flex"].get("fatal"):
            for k in ["ld", "ldh", "lap", "clear", "per_layer", "layers", "req_width"]:
                self._put("det_" + k, "-")
            self.detail_box.delete("1.0", "end")
            self.detail_box.insert("1.0", "Resolve flexure first.")
            return
        de = R["detail"]
        self._put("det_ld", "%.0f" % de["ld"])
        self._put("det_ldh", "%.0f" % de["ldh"])
        self._put("det_lap", "%.0f" % de["lap"])
        self._put("det_clear", "%.0f" % de["clear"])
        self._put("det_per_layer", "%d" % de["per_layer"])
        self._put("det_layers", "%d" % de["layers"], T.PASS if de["layers"] <= 2 else T.FAIL)
        self._put("det_req_width", "%.0f" % de["req_width"],
                  T.PASS if de["fits1"] else T.WARN)
        # checklist
        self.detail_box.delete("1.0", "end")
        items = [
            ("Clear bar spacing >= max(25, db) (425.2.1)", de["fits1"] or de["layers"] >= 2),
            ("Bar layering within 2 layers", de["layers"] <= 2),
            ("Clear cover provided (input)", self.I["cover"] >= 20),
            ("Development length ld computed (425.4.2.2)", True),
            ("Std. hook anchorage ldh computed (425.4.3.1)", True),
            ("Class-B lap splice length (425.5.2.1)", True),
            ("Stirrup max spacing satisfied (409.7.6.2.2)",
             not R["flex"].get("fatal")),
            ("No reinforcement congestion", not de["congested"]),
        ]
        for label, ok in items:
            tag = "[PASS] " if ok else "[CHECK] "
            self.detail_box.insert("end", tag + label + "\n")
        self.detail_box.insert("end",
            "\nNOTE: Detailing checks are simplified and preliminary. Final "
            "development, anchorage, cut-off, and lap-splice detailing must be "
            "verified by the engineer per NSCP 2015 Chapter 425.")

    def _refresh_calcs(self):
        R = self.R
        self.calc_box.delete("1.0", "end")
        for i, (title, a, b_) in enumerate(R["steps"], 1):
            self.calc_box.insert("end", "%d.  %s\n" % (i, title))
            if a: self.calc_box.insert("end", "       %s\n" % a)
            if b_: self.calc_box.insert("end", "       %s\n" % b_)
            self.calc_box.insert("end", "\n")
        if R["warnings"]:
            self.calc_box.insert("end", "-" * 60 + "\nWARNINGS / NOTES:\n")
            for tag, msg in R["warnings"]:
                self.calc_box.insert("end", "  (%s) %s\n" % (tag, msg))

    # ======================================================================
    #  CANVAS DRAWINGS (2D)
    # ======================================================================
    def _draw_section(self, cv, region=None):
        """Draw the RC cross-section with bars, stirrup, cover, labels."""
        cv.delete("all")
        W = cv.winfo_width() or 400
        H = cv.winfo_height() or 260
        if not self.R:
            return
        b, h, cover = self.I["b"], self.I["h"], self.I["cover"]
        # region: optional (x0,y0,x1,y1) to draw within
        if region:
            x0, y0, x1, y1 = region
        else:
            x0, y0, x1, y1 = 20, 20, W - 20, H - 20
        aw, ah = (x1 - x0), (y1 - y0)
        sc = min(aw / b, ah / h) * 0.72
        bw, bh = b * sc, h * sc
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        left, top = cx - bw / 2, cy - bh / 2
        # concrete
        cv.create_rectangle(left, top, left + bw, top + bh, fill=T.CARD2,
                            outline=T.CONCRETE, width=2)
        stir_dia = BARS[self.I["stir_bar"]]["dia"]
        off = (cover + stir_dia) * sc
        # stirrup
        cv.create_rectangle(left + cover * sc, top + cover * sc,
                            left + bw - cover * sc, top + bh - cover * sc,
                            outline=T.STIRRUP, width=2)
        if self.R["flex"].get("fatal"):
            cv.create_text(cx, cy, text="SECTION NG", fill=T.FAIL, font=T.F_H)
            return
        db = self.R["flex"]["db"]; r = max(3, db * sc / 2)
        # bottom / top bar counts
        nb, bname = self.R["bottom"]
        nt, tname = self.R["top"]
        rb = max(3, BARS[bname]["dia"] * sc / 2)
        rt = max(3, BARS[tname]["dia"] * sc / 2)

        def spread(n, y, rr, color):
            xa = left + off + rr
            xb = left + bw - off - rr
            if n == 1:
                xs = [(xa + xb) / 2]
            else:
                xs = [xa + (xb - xa) * k / (n - 1) for k in range(n)]
            for xx in xs:
                cv.create_oval(xx - rr, y - rr, xx + rr, y + rr, fill=color, outline="")
        # place up to per-layer count on a row; extra bars form second row
        per = self.R["detail"]["per_layer"]
        yb = top + bh - off - rb
        yt = top + off + rt
        n1 = min(nb, per)
        spread(n1, yb, rb, T.REBAR_B)
        if nb > per:
            spread(nb - n1, yb - (db + VCLEAR) * sc, rb, T.REBAR_B)
        spread(nt, yt, rt, T.REBAR_T)
        # labels
        cv.create_text(cx, top + bh + 12, text="b = %.0f mm" % b, fill=T.MUTED,
                       font=T.F_SUB)
        cv.create_text(left - 10, cy, text="h = %.0f" % h, fill=T.MUTED,
                       font=T.F_SUB, angle=90)
        cv.create_text(left + bw - 4, top + bh - off / 2, text="cover %.0f" % cover,
                       fill=T.MUTED, font=("Segoe UI", 7), anchor="e")
        cv.create_text(cx, top + bh - off - rb - 8, text="%d-%s" % (nb, bname),
                       fill=T.REBAR_B, font=T.F_SUB)
        cv.create_text(cx, top + off + rt + 8, text="%d-%s" % (nt, tname),
                       fill=T.REBAR_T, font=T.F_SUB)

    def _draw_flex_canvas(self):
        cv = self.flex_canvas
        cv.delete("all")
        W = cv.winfo_width() or 600
        H = cv.winfo_height() or 240
        if not self.R:
            return
        # left half: cross-section ; right half: BMD
        self._draw_section(cv, region=(10, 10, W // 2 - 10, H - 10))
        self._draw_curve(cv, region=(W // 2 + 10, 10, W - 10, H - 10),
                         kind="BMD")

    def _draw_diagrams(self):
        cv = self.diag_canvas
        cv.delete("all")
        W = cv.winfo_width() or 700
        H = cv.winfo_height() or 300
        if not self.R:
            return
        third = H / 3
        self._draw_elevation(cv, (10, 6, W - 10, third - 6))
        self._draw_curve(cv, (10, third + 4, W - 10, 2 * third - 6), "SFD")
        self._draw_curve(cv, (10, 2 * third + 4, W - 10, H - 6), "BMD")

    def _draw_sfd(self):
        cv = self.sfd_canvas
        cv.delete("all")
        W = cv.winfo_width() or 600
        H = cv.winfo_height() or 220
        if self.R:
            self._draw_curve(cv, (10, 10, W - 10, H - 10), "SFD")

    def _draw_elevation(self, cv, region):
        x0, y0, x1, y1 = region
        cv.create_text((x0 + x1) / 2, y0 + 8, text="BEAM ELEVATION", fill=T.MUTED,
                       font=T.F_SUB)
        L = self.I["span"]
        bx0, bx1 = x0 + 40, x1 - 40
        by = (y0 + y1) / 2 + 6
        depth = min(26, (y1 - y0) * 0.35)
        cv.create_rectangle(bx0, by - depth / 2, bx1, by + depth / 2,
                            outline=T.CONCRETE, fill=T.CARD2, width=2)
        # supports
        cond = self.I["condition"]
        def tri(x):
            cv.create_polygon(x, by + depth / 2, x - 8, by + depth / 2 + 12,
                              x + 8, by + depth / 2 + 12, fill=T.MUTED, outline="")
        if cond == "Cantilever":
            cv.create_rectangle(bx0 - 6, by - depth / 2 - 6, bx0,
                                by + depth / 2 + 6, fill=T.MUTED, outline="")
        else:
            tri(bx0); tri(bx1)
        # UDL arrows
        if self.I["load_type"] in ("Uniform", "Combination"):
            for k in range(9):
                ax = bx0 + (bx1 - bx0) * k / 8
                cv.create_line(ax, by - depth / 2 - 14, ax, by - depth / 2 - 2,
                               fill=T.ACCENT, arrow="last")
        # point load
        if self.I["load_type"] in ("Point", "Combination") and self.R["Pu"] > 0:
            px = bx0 + (bx1 - bx0) * (self.I["p_loc"] / L if L else 0.5)
            cv.create_line(px, by - depth / 2 - 24, px, by - depth / 2 - 2,
                           fill=T.REBAR_T, arrow="last", width=2)
        cv.create_text((bx0 + bx1) / 2, by + depth / 2 + 20,
                       text="L = %.2f m  (%s)" % (L, cond), fill=T.MUTED, font=T.F_SUB)

    def _draw_curve(self, cv, region, kind):
        """Draw an SFD or BMD sampled along the span."""
        x0, y0, x1, y1 = region
        title = "SHEAR FORCE DIAGRAM (kN)" if kind == "SFD" else "BENDING MOMENT DIAGRAM (kN-m)"
        cv.create_text((x0 + x1) / 2, y0 + 8, text=title, fill=T.MUTED, font=T.F_SUB)
        gx0, gx1 = x0 + 46, x1 - 12
        gy0, gy1 = y0 + 18, y1 - 16
        base = (gy0 + gy1) / 2
        cv.create_line(gx0, base, gx1, base, fill=T.STROKE)      # x-axis
        cv.create_line(gx0, gy0, gx0, gy1, fill=T.STROKE)        # y-axis
        xs, ys = self._diagram_samples(kind)
        if not xs:
            return
        vmax = max(1e-6, max(abs(v) for v in ys))
        span = self.I["span"]
        half = (gy1 - gy0) / 2 * 0.92
        pts = []
        for x, v in zip(xs, ys):
            px = gx0 + (gx1 - gx0) * (x / span if span else 0)
            py = base - (v / vmax) * half
            pts.append((px, py))
        # filled polygon to baseline
        poly = [(pts[0][0], base)] + pts + [(pts[-1][0], base)]
        color = T.ACCENT2 if kind == "SFD" else T.ACCENT
        cv.create_polygon([c for p in poly for c in p], fill=color, stipple="gray25",
                          outline="")
        for i in range(len(pts) - 1):
            cv.create_line(*pts[i], *pts[i + 1], fill=color, width=2)
        # extreme value label
        vext = max(ys, key=abs)
        cv.create_text(gx1, gy0 + 6, text="max |%.1f|" % abs(vext), fill=T.TEXT,
                       font=T.F_SUB, anchor="e")

    def _diagram_samples(self, kind):
        """Approximate V(x) and M(x) for the elevation diagrams."""
        I, R = self.I, self.R
        L = I["span"]
        if L <= 0:
            return [], []
        wu = R["wu"]
        Pu = R["Pu"]
        a = min(max(I["p_loc"], 0.0), L)
        cond = I["condition"]
        N = 41
        xs = [L * k / (N - 1) for k in range(N)]
        V, M = [], []
        use_udl = I["load_type"] in ("Uniform", "Combination")
        use_pt = I["load_type"] in ("Point", "Combination") and Pu > 0

        if cond == "Cantilever":
            for x in xs:
                v = m = 0.0
                if use_udl:
                    v += wu * (L - x)
                    m -= wu * (L - x) ** 2 / 2.0
                if use_pt and x <= a:
                    v += Pu
                    m -= Pu * (a - x)
                V.append(v); M.append(m)
        else:
            # simple-span statics for shape (continuous/fixed shown as SS shape)
            Rl = 0.0
            if use_udl:
                Rl += wu * L / 2.0
            if use_pt:
                Rl += Pu * (L - a) / L
            for x in xs:
                v = Rl
                m = Rl * x
                if use_udl:
                    v -= wu * x
                    m -= wu * x * x / 2.0
                if use_pt and x > a:
                    v -= Pu
                    m -= Pu * (x - a)
                V.append(v); M.append(m)
        return xs, (V if kind == "SFD" else M)

    # ======================================================================
    #  3D VIEW
    # ======================================================================
    def _rot(self, p):
        x, y, z = p
        cy, sy = math.cos(self.ay), math.sin(self.ay)
        x, z = x * cy + z * sy, -x * sy + z * cy
        cx, sx = math.cos(self.ax), math.sin(self.ax)
        y, z = y * cx - z * sx, y * sx + z * cx
        return x, y, z

    def _proj(self, p, cx, cy):
        x, y, z = self._rot(p)
        return cx + x * self.zoom + self.panx, cy - y * self.zoom + self.pany

    def _draw_3d(self):
        cv = self.cv3d
        cv.delete("all")
        if not self.R:
            return
        W = cv.winfo_width() or 800
        H = cv.winfo_height() or 500
        cx, cy = W / 2, H / 2
        I = self.I
        h = I["h"]
        # normalized half-extents (depth=1 unit)
        HY = 0.5                                   # depth (vertical)
        HZ = 0.5 * I["b"] / h                       # width
        span_r = I["span"] * 1000.0 / h
        HX = min(span_r, 7.0) / 2.0                 # compress long spans
        compressed = span_r > 7.0

        # box corners (x=length, y=depth-up, z=width)
        C = {}
        for i, sx in enumerate((-HX, HX)):
            for j, sy in enumerate((-HY, HY)):
                for k, sz in enumerate((-HZ, HZ)):
                    C[(i, j, k)] = self._proj((sx, sy, sz), cx, cy)
        edges = [((0,0,0),(1,0,0)),((0,1,0),(1,1,0)),((0,0,1),(1,0,1)),((0,1,1),(1,1,1)),
                 ((0,0,0),(0,1,0)),((1,0,0),(1,1,0)),((0,0,1),(0,1,1)),((1,0,1),(1,1,1)),
                 ((0,0,0),(0,0,1)),((1,0,0),(1,0,1)),((0,1,0),(0,1,1)),((1,1,0),(1,1,1))]

        # concrete faces (filled, stippled so rebar shows through)
        if self.show_conc.get():
            faces = [
                [(0,0,0),(1,0,0),(1,0,1),(0,0,1)],   # bottom
                [(0,1,0),(1,1,0),(1,1,1),(0,1,1)],   # top
                [(0,0,0),(0,1,0),(0,1,1),(0,0,1)],   # left end
                [(1,0,0),(1,1,0),(1,1,1),(1,0,1)],   # right end
                [(0,0,1),(1,0,1),(1,1,1),(0,1,1)],   # front
                [(0,0,0),(1,0,0),(1,1,0),(0,1,0)],   # back
            ]
            # sort by average rotated depth (painter's algorithm)
            def facedepth(f):
                return sum(self._rot((
                    (-HX if c[0]==0 else HX),
                    (-HY if c[1]==0 else HY),
                    (-HZ if c[2]==0 else HZ)))[2] for c in f) / 4.0
            for f in sorted(faces, key=facedepth):
                pts = [C[c] for c in f]
                cv.create_polygon([v for p in pts for v in p], fill=T.CARD2,
                                  outline=T.CONCRETE, width=1, stipple="gray25")
        # edges
        for e in edges:
            cv.create_line(*C[e[0]], *C[e[1]], fill=T.CONCRETE, width=1)

        if self.show_rebar.get() and not self.R["flex"].get("fatal"):
            cov_r = (I["cover"] + BARS[I["stir_bar"]]["dia"]) / h
            nb, bname = self.R["bottom"]
            nt, tname = self.R["top"]
            per = self.R["detail"]["per_layer"]
            dbn = BARS[bname]["dia"] / h

            def zline(n):
                za = -HZ + cov_r
                zb = HZ - cov_r
                if n <= 1:
                    return [(za + zb) / 2]
                return [za + (zb - za) * k / (n - 1) for k in range(n)]

            def bar(y, z, color):
                p0 = self._proj((-HX + cov_r, y, z), cx, cy)
                p1 = self._proj((HX - cov_r, y, z), cx, cy)
                cv.create_line(*p0, *p1, fill=color, width=3)
            # bottom (may be 2 rows)
            yb = -HY + cov_r
            n1 = min(nb, per)
            for z in zline(n1):
                bar(yb, z, T.REBAR_B)
            if nb > per:
                for z in zline(nb - n1):
                    bar(yb + dbn + VCLEAR / h, z, T.REBAR_B)
            # top
            yt = HY - cov_r
            for z in zline(nt):
                bar(yt, z, T.REBAR_T)
            # stirrups
            s = self.R["shear"]["spacing"] or 200.0
            span_mm = I["span"] * 1000.0
            n_st = max(3, min(14, int(span_mm / s)))
            yy = HY - cov_r; zz = HZ - cov_r
            for m in range(n_st + 1):
                xx = -HX + cov_r + (2 * (HX - cov_r)) * m / n_st
                corners = [(-yy, -zz), (-yy, zz), (yy, zz), (yy, -zz), (-yy, -zz)]
                pts = [self._proj((xx, yc, zc), cx, cy) for yc, zc in corners]
                for i in range(len(pts) - 1):
                    cv.create_line(*pts[i], *pts[i + 1], fill=T.STIRRUP, width=1)

        # HUD text
        nb, bname = self.R["bottom"]; nt, tname = self.R["top"]
        s = self.R["shear"]["spacing"]
        info = "b x h = %.0f x %.0f mm   L = %.2f m" % (I["b"], I["h"], I["span"])
        cv.create_text(14, 16, anchor="w", fill=T.TEXT, font=T.F_SUB, text=info)
        if not self.R["flex"].get("fatal"):
            cv.create_text(14, 34, anchor="w", fill=T.REBAR_B, font=T.F_SUB,
                           text="Bottom: %d-%s" % (nb, bname))
            cv.create_text(14, 50, anchor="w", fill=T.REBAR_T, font=T.F_SUB,
                           text="Top: %d-%s" % (nt, tname))
            if s:
                cv.create_text(14, 66, anchor="w", fill=T.STIRRUP, font=T.F_SUB,
                               text="Stirrups: 2-%s @ %.0f mm" % (I["stir_bar"], s))
        if compressed:
            cv.create_text(W - 12, H - 12, anchor="se", fill=T.MUTED,
                           font=("Segoe UI", 8), text="length compressed for display")

    # 3D interaction
    def _start_drag(self, e):
        self._last = (e.x, e.y)

    def _rotate_drag(self, e):
        if not self._last:
            return
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self.ay += dx * 0.01
        self.ax += dy * 0.01
        self.ax = max(-1.5, min(1.5, self.ax))
        self._last = (e.x, e.y)
        self._draw_3d()

    def _pan_drag(self, e):
        if not self._last:
            return
        self.panx += e.x - self._last[0]
        self.pany += e.y - self._last[1]
        self._last = (e.x, e.y)
        self._draw_3d()

    def _zoom(self, f):
        self.zoom = max(20.0, min(900.0, self.zoom * f))
        self._draw_3d()

    def _view_iso(self):
        self.ax, self.ay = 0.44, -0.62; self._draw_3d()

    def _view_front(self):
        self.ax, self.ay = 0.0, 0.0; self._draw_3d()

    def _view_side(self):
        self.ax, self.ay = 0.0, math.pi / 2; self._draw_3d()

    def _view_top(self):
        self.ax, self.ay = math.pi / 2 - 0.01, 0.0; self._draw_3d()

    def _view_reset(self):
        self.panx = self.pany = 0.0
        self.zoom = 150.0
        self._view_iso()

    # ======================================================================
    #  REPORT / RESET
    # ======================================================================
    def generate_report(self):
        self.recompute()
        if not self.R:
            return
        self.report_text = build_report(self.I, self.R)
        self.report_box.delete("1.0", "end")
        self.report_box.insert("1.0", self.report_text)
        self._show_page("Report")

    def save_report(self):
        if not self.report_text:
            self.generate_report()
        if not self.report_text:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile="%s_%s.txt" % (self.vars["proj"].get().replace(" ", "_"),
                                       self.vars["beam_id"].get()))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.report_text)
            messagebox.showinfo("Saved", "Report saved:\n%s" % path)
        except OSError as e:
            messagebox.showerror("Save Error", str(e))

    def reset_defaults(self):
        for k, v in self.defaults.items():
            self.vars[k].set(v)
        self.self_weight.set(True)
        self.crit_shear.set(True)
        if hasattr(self, "notes_txt"):
            self.notes_txt.delete("1.0", "end")
        self.recompute()


def main():
    root = tk.Tk()
    BeamStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()