import json
import math
import os
import traceback
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

APP_TITLE = "RC Footing Design — NSCP 2015"
MM_PER_M = 1000.0
BAR_DIAMETERS_MM = {10: 10.0, 12: 12.0, 16: 16.0, 20: 20.0, 25: 25.0, 28: 28.0, 32: 32.0, 36: 36.0}
BAR_SPACINGS_MM = [100, 125, 150, 175, 200, 225, 250, 300]
PHI_FLEXURE = 0.90
PHI_SHEAR = 0.75

DISCLAIMER = (
    "FOR ENGINEERING DESIGN ASSISTANCE ONLY.\n\n"
    "This software implements selected NSCP 2015 / ACI-based reinforced-concrete "
    "and foundation design checks. Final foundation design must be verified by a "
    "qualified structural/geotechnical engineer using the official NSCP 2015, "
    "project-specific geotechnical investigation, actual structural analysis, "
    "and applicable local requirements.\n\n"
    "The software does not replace engineering judgment, site investigation, "
    "geotechnical interpretation, or detailed structural analysis."
)


@dataclass
class ProjectData:
    project_name: str = ""
    location: str = ""
    structure: str = ""
    footing_mark: str = "F1"
    column_mark: str = "C1"
    designer: str = ""
    checked_by: str = ""
    design_date: str = field(default_factory=lambda: str(date.today()))
    notes: str = ""


@dataclass
class MaterialProperties:
    fc: float = 21.0
    gamma_c: float = 24.0
    fy: float = 415.0
    es: float = 200000.0


@dataclass
class SoilProperties:
    qa: float = 150.0
    gamma_soil: float = 18.0
    phi_deg: float = 0.0
    cohesion: float = 0.0
    groundwater: float = 99.0
    embedment: float = 1.0
    soil_cover: float = 0.15
    fos: float = 3.0
    settlement_limit: float = 25.0
    pressure_type: str = "Gross allowable"
    bearing_method: str = "User-Provided qa"


@dataclass
class LoadData:
    input_mode: str = "Service Loads"
    self_weight_mode: str = "Auto include footing self-weight"
    manual_self_weight: float = 0.0
    D: float = 600.0
    L: float = 180.0
    other: float = 0.0
    roof: float = 0.0
    equipment: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    Hx: float = 0.0
    Hy: float = 0.0
    direct_Pu: float = 0.0
    direct_Mux: float = 0.0
    direct_Muy: float = 0.0
    direct_Vux: float = 0.0
    direct_Vuy: float = 0.0
    combo: str = "1.2D + 1.6L"


@dataclass
class FootingGeometry:
    footing_type: str = "Isolated Rectangular"
    B: float = 2.4
    L: float = 2.1
    h: float = 0.45
    cx: float = 0.40
    cy: float = 0.40
    cover: float = 75.0
    col_offset_x: float = 0.0
    col_offset_y: float = 0.0
    pedestal_B: float = 0.0
    pedestal_L: float = 0.0
    pedestal_h: float = 0.0
    auto_size: bool = True
    square: bool = False
    rounding_mm: float = 50.0
    h_max: float = 1.0
    B1: float = 1.5
    B2: float = 2.2
    col_spacing: float = 3.0
    strap_width: float = 0.35
    strap_depth: float = 0.50
    wall_t: float = 0.20
    wall_line_load: float = 100.0


@dataclass
class RebarSpec:
    x_dia: int = 16
    x_spacing: int = 150
    y_dia: int = 16
    y_spacing: int = 150
    dowel_dia: int = 16
    dowel_n: int = 4
    top_dia: int = 12
    top_spacing: int = 200


@dataclass
class DesignResults:
    ok: bool = False
    status: str = "NOT CALCULATED"
    warnings: list = field(default_factory=list)
    calculations: list = field(default_factory=list)
    footing: dict = field(default_factory=dict)
    bearing: dict = field(default_factory=dict)
    flexure: dict = field(default_factory=dict)
    shear: dict = field(default_factory=dict)
    punching: dict = field(default_factory=dict)
    development: dict = field(default_factory=dict)
    detailing: dict = field(default_factory=dict)
    reinforcement: dict = field(default_factory=dict)
    combined: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    code_refs: list = field(default_factory=list)


def rnd_up(value, increment):
    if increment <= 0:
        return value
    return math.ceil(value / increment - 1e-12) * increment


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def bar_area_mm2(d):
    return math.pi * d * d / 4.0


def bar_area_per_m(d, spacing_mm):
    if spacing_mm <= 0:
        return 0.0
    return bar_area_mm2(d) * 1000.0 / spacing_mm


def parse_float(value, name, allow_zero=True):
    try:
        x = float(value)
    except Exception:
        raise ValueError(f"{name} must be numeric.")
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite.")
    if allow_zero:
        if x < 0:
            raise ValueError(f"{name} cannot be negative.")
    else:
        if x <= 0:
            raise ValueError(f"{name} must be greater than zero.")
    return x


def load_combinations(load: LoadData):
    if load.input_mode == "Factored / Ultimate Loads":
        return [("Direct ultimate", load.direct_Pu, load.direct_Mux, load.direct_Muy,
                 math.hypot(load.direct_Vux, load.direct_Vuy), "User-supplied ultimate")]

    D = load.D + load.other
    L = load.L
    # Only commonly used gravity combinations explicitly requested in the source specification.
    combos = [
        ("1.4D", 1.4 * D, 1.4 * load.Mx, 1.4 * load.My, 1.4 * math.hypot(load.Hx, load.Hy), "NSCP 2015 / ACI-based gravity combination — VERIFY AGAINST OFFICIAL NSCP 2015"),
        ("1.2D + 1.6L", 1.2 * D + 1.6 * L, 1.2 * load.Mx + 1.6 * load.Mx, 1.2 * load.My + 1.6 * load.My, math.hypot(1.2 * load.Hx, 1.2 * load.Hy), "NSCP 2015 / ACI-based gravity combination — VERIFY AGAINST OFFICIAL NSCP 2015"),
        ("1.2D + 1.0L", 1.2 * D + 1.0 * L, 1.2 * load.Mx + load.Mx, 1.2 * load.My + load.My, math.hypot(1.2 * load.Hx, 1.2 * load.Hy), "NSCP 2015 / ACI-based gravity combination — VERIFY AGAINST OFFICIAL NSCP 2015"),
    ]
    return combos


def get_governing_combo(load):
    combos = load_combinations(load)
    return max(combos, key=lambda x: abs(x[1]))


def calculate_bearing_capacity(soil: SoilProperties):
    if soil.bearing_method == "User-Provided qa":
        return {"method": "User-Provided qa", "qa": soil.qa, "implemented": False,
                "warning": "Allowable bearing capacity is user-provided; use project geotechnical report."}

    phi = math.radians(soil.phi_deg)
    if soil.phi_deg <= 0 and soil.cohesion <= 0:
        return {"method": soil.bearing_method, "qa": soil.qa, "implemented": False,
                "warning": "Insufficient soil parameters for bearing-capacity calculation."}

    # Transparent simplified Terzaghi/Meyerhof-style equation. Exact code/project corrections
    # are intentionally flagged for independent verification.
    tanp = math.tan(phi)
    if abs(math.tan(phi)) < 1e-9:
        Nq = 1.0
    else:
        Nq = math.exp(math.pi * tanp) * math.tan(math.pi / 4 + phi / 2) ** 2
    Nc = (Nq - 1.0) / tanp if abs(tanp) > 1e-9 else 5.14
    Ngamma = 2.0 * (Nq + 1.0) * tanp
    Df = soil.embedment
    q = soil.gamma_soil * Df
    B = 1.0
    if soil.bearing_method == "Terzaghi":
        qult = soil.cohesion * Nc + q * Nq + 0.5 * soil.gamma_soil * B * Ngamma
    else:
        # General equation nominal form; shape/depth/inclination factors omitted -> explicit warning.
        qult = soil.cohesion * Nc + q * Nq + 0.5 * soil.gamma_soil * B * Ngamma
    qa = qult / max(soil.fos, 1e-9)
    return {
        "method": soil.bearing_method,
        "Nc": Nc, "Nq": Nq, "Ngamma": Ngamma, "q_overburden": q,
        "qult": qult, "qa": qa, "implemented": True,
        "warning": "Simplified bearing-capacity implementation. Shape/depth/inclination, water-table and effective-stress corrections require project-specific verification. [VERIFY AGAINST OFFICIAL NSCP 2015]"
    }


def soil_pressures(B, L, P, Mx, My):
    if P <= 0:
        raise ValueError("Resultant vertical load must be greater than zero for bearing-pressure analysis.")
    ex = Mx / P
    ey = My / P
    q0 = P / (B * L)
    qx = 6.0 * Mx / (B * L * L)
    qy = 6.0 * My / (L * B * B)
    # Common biaxial full-contact linear approximation.
    qmax = q0 + abs(qx) + abs(qy)
    qmin = q0 - abs(qx) - abs(qy)
    return ex, ey, q0, qmax, qmin


def required_area(service_P, qa):
    if qa <= 0:
        raise ValueError("Allowable bearing capacity must be greater than zero.")
    return service_P / qa


def choose_dims(area_req, square, rounding_mm, max_ratio=2.5):
    inc_m = max(0.05, rounding_mm / 1000.0)
    if square:
        b = rnd_up(math.sqrt(area_req), inc_m)
        return b, b
    # Favor roughly rectangular dimensions with bounded aspect ratio.
    b = math.sqrt(area_req / 1.05)
    l = area_req / b
    if l / b > max_ratio:
        b = math.sqrt(area_req / max_ratio)
        l = area_req / b
    b = rnd_up(b, inc_m)
    l = rnd_up(max(l, area_req / b), inc_m)
    return b, l


def phi_flexural_capacity(fc, fy, b_mm, d_mm, As_mm2):
    if b_mm <= 0 or d_mm <= 0 or As_mm2 <= 0:
        return 0.0, 0.0, 0.0
    a = As_mm2 * fy / (0.85 * fc * b_mm)
    Mn = As_mm2 * fy * (d_mm - a / 2.0) / 1e6
    return PHI_FLEXURE * Mn, Mn, a


def flexural_As(fc, fy, b_mm, d_mm, Mu_kNm, min_ratio=0.0018):
    if d_mm <= 0 or b_mm <= 0:
        return 0.0, 0.0, 0.0
    # Solve phi * As fy (d-a/2) >= Mu, iteratively.
    As = max(Mu_kNm * 1e6 / (PHI_FLEXURE * fy * max(0.9 * d_mm, 1.0)), b_mm * min_ratio * 1.0)
    for _ in range(50):
        a = As * fy / (0.85 * fc * b_mm)
        Mn = As * fy * max(d_mm - a / 2.0, 0.0) / 1e6
        f = PHI_FLEXURE * Mn - Mu_kNm
        if f >= 0:
            break
        As *= 1.05
    Asmin = b_mm * min_ratio
    return As, Asmin, PHI_FLEXURE


def vc_oneway(fc, b_mm, d_mm):
    # ACI-style nominal concrete shear strength approximation, SI.
    return 0.17 * math.sqrt(max(fc, 0.0)) * b_mm * d_mm / 1000.0


def vc_punching(fc, bo_mm, d_mm, vc_factor=4.0):
    # Conservative simplified upper-level expression used only for screening.
    return 0.33 * math.sqrt(max(fc, 0.0)) * bo_mm * d_mm / 1000.0


def development_length_tension(db_mm, fy, fc, cover_mm=75.0):
    # Transparent simplified tension development screen; detailed bar/top-bar/epoxy modifiers not modeled.
    ld = max(12.0 * db_mm, (3.0 / 40.0) * fy * db_mm / max(math.sqrt(fc), 1e-9))
    return ld


def select_spacing(As_req_per_m, dia, candidates=None):
    if candidates is None:
        candidates = BAR_SPACINGS_MM
    for s in candidates:
        Asprov = bar_area_per_m(dia, s)
        if Asprov + 1e-9 >= As_req_per_m:
            return s, Asprov
    return candidates[-1], bar_area_per_m(dia, candidates[-1])


def fit_rebar(width_mm, dia_mm, cover_mm, spacing_mm):
    usable = width_mm - 2 * cover_mm - dia_mm
    if usable <= 0:
        return False, 0, "No usable bar placement width after cover/bar diameter."
    n = math.floor(usable / spacing_mm) + 1
    if n < 2:
        return False, n, "Too few bars fit within the footing width."
    min_clear = max(25.0, dia_mm)
    actual_clear = (usable - (n - 1) * spacing_mm) / max(n - 1, 1)
    if actual_clear < min_clear - 1e-6:
        return False, n, f"Computed clear spacing is {actual_clear:.1f} mm < minimum screening value {min_clear:.1f} mm."
    return True, n, ""


def design_isolated(data_project, mat, soil, load, geom, rebar):
    r = DesignResults()
    r.assumptions = [
        "Geotechnical bearing check uses service-level load for allowable soil pressure.",
        "Structural flexure/shear checks use governing user-selected or generated ultimate combination.",
        "Footing self-weight treatment is controlled by the user interface; this build auto-includes a screening allowance when selected.",
        "Soil pressure distribution is a linear rectangular-footing approximation.",
        "Punching shear eccentricity/unbalanced-moment transfer is not fully modeled; verify against official NSCP 2015.",
        "Settlement is not calculated unless a future geotechnical module is added.",
    ]
    r.code_refs = [
        "NSCP 2015 — Reinforced Concrete provisions; exact clause/table references should be verified against the official edition.",
        "ACI-based flexural and shear strength methodology — [VERIFY AGAINST OFFICIAL NSCP 2015].",
    ]

    bearing_info = calculate_bearing_capacity(soil)
    qa = bearing_info.get("qa", soil.qa)
    if bearing_info.get("warning"):
        r.warnings.append(bearing_info["warning"])

    combos = load_combinations(load)
    gov = get_governing_combo(load)
    combo_name, Pu, Mux, Muy, Vh, combo_note = gov
    if load.input_mode == "Service Loads":
        service_P = load.D + load.L + load.other + load.roof + load.equipment
        if load.self_weight_mode == "Auto include footing self-weight":
            service_P += mat.gamma_c * geom.B * geom.L * geom.h
        elif load.self_weight_mode == "Manual footing self-weight":
            service_P += load.manual_self_weight
        if load.input_mode == "Service Loads" and service_P <= 0:
            raise ValueError("Service vertical load must be greater than zero.")
        service_Mx = load.Mx
        service_My = load.My
    else:
        service_P = load.direct_Pu
        service_Mx = load.direct_Mux
        service_My = load.direct_Muy

    if geom.B < geom.cx or geom.L < geom.cy:
        raise ValueError("Footing dimensions must be greater than or equal to column dimensions.")

    if geom.auto_size:
        # Iterate area sizing when automatic footing self-weight is enabled because self-weight depends on B × L × h.
        B, L = geom.B, geom.L
        for _ in range(20):
            service_P_eff = load.D + load.L + load.other + load.roof + load.equipment
            if load.self_weight_mode == "Auto include footing self-weight":
                service_P_eff += mat.gamma_c * B * L * geom.h
            elif load.self_weight_mode == "Manual footing self-weight":
                service_P_eff += load.manual_self_weight
            area_req = required_area(service_P_eff, qa)
            nb, nl = choose_dims(area_req, geom.square, geom.rounding_mm)
            if abs(nb-B) < 1e-9 and abs(nl-L) < 1e-9:
                break
            B, L = nb, nl
        geom.B, geom.L = B, L
        service_P = load.D + load.L + load.other + load.roof + load.equipment
        if load.self_weight_mode == "Auto include footing self-weight":
            service_P += mat.gamma_c * B * L * geom.h
        elif load.self_weight_mode == "Manual footing self-weight":
            service_P += load.manual_self_weight
    else:
        B, L = geom.B, geom.L

    if geom.square:
        L = B
        geom.L = L

    # Apply column offsets to service moments for bearing.
    Mx_b = service_Mx + service_P * geom.col_offset_y
    My_b = service_My + service_P * geom.col_offset_x
    ex, ey, q0, qmax, qmin = soil_pressures(B, L, service_P, Mx_b, My_b)
    kern_x = B / 6.0
    kern_y = L / 6.0
    if qmin < 0:
        r.warnings.append("qmin < 0: linear full-contact theory predicts soil tension. A partial-contact analysis is not fully implemented; verify/redo bearing analysis.")
    if abs(ex) > kern_x or abs(ey) > kern_y:
        r.warnings.append("Resultant is outside the kern in at least one direction; partial-contact behavior must be checked.")

    bearing_util = qmax / max(qa, 1e-9)
    bearing_pass = qmax <= qa + 1e-9 and qmin >= -qa
    r.bearing = {
        "qa": qa, "service_P": service_P, "q0": q0, "qmax": qmax, "qmin": qmin,
        "ex": ex, "ey": ey, "kern_x": kern_x, "kern_y": kern_y,
        "utilization": bearing_util, "pass": bearing_pass, "method": bearing_info.get("method")
    }
    if not bearing_pass:
        r.warnings.append("Bearing pressure exceeds the stated allowable pressure or indicates unsupported tensile contact.")

    # Structural design uses factored soil reaction over full footing. For partial-contact cases, mark warning.
    h_mm = geom.h * 1000.0
    max_bar = max(rebar.x_dia, rebar.y_dia)
    d_mm = h_mm - geom.cover - max_bar / 2.0
    if d_mm <= 0:
        raise ValueError("Effective depth is non-positive. Increase footing thickness or revise cover/bar diameter.")

    # Soil pressure envelope for factored action.
    _, _, uq0, uqmax, uqmin = soil_pressures(B, L, max(Pu, 1e-9), Mux, Muy)
    q_design = max(uqmax, 0.0)

    # Projection distances beyond column faces.
    lx = max((B - geom.cx) / 2.0, 0.0)
    ly = max((L - geom.cy) / 2.0, 0.0)

    # Cantilever strip approximation in each direction, using q_design.
    Mu_x = q_design * L * lx * lx / 2.0
    Mu_y = q_design * B * ly * ly / 2.0
    Asx_req, Asx_min, _ = flexural_As(mat.fc, mat.fy, L * 1000.0, d_mm, Mu_x)
    Asy_req, Asy_min, _ = flexural_As(mat.fc, mat.fy, B * 1000.0, d_mm, Mu_y)
    Asx_req = max(Asx_req, Asx_min)
    Asy_req = max(Asy_req, Asy_min)

    s_x, Asx_prov = select_spacing(Asx_req, rebar.x_dia)
    s_y, Asy_prov = select_spacing(Asy_req, rebar.y_dia)
    fitx, nx, fitmsgx = fit_rebar(L * 1000.0, rebar.x_dia, geom.cover, s_x)
    fity, ny, fitmsgy = fit_rebar(B * 1000.0, rebar.y_dia, geom.cover, s_y)

    phiMn_x, Mn_x, a_x = phi_flexural_capacity(mat.fc, mat.fy, L * 1000.0, d_mm, Asx_prov)
    phiMn_y, Mn_y, a_y = phi_flexural_capacity(mat.fc, mat.fy, B * 1000.0, d_mm, Asy_prov)
    flex_x_pass = phiMn_x >= Mu_x and fitx
    flex_y_pass = phiMn_y >= Mu_y and fity
    if not fitx:
        r.warnings.append("X-direction reinforcement cannot be physically fitted with the current geometry/spacing.")
    if not fity:
        r.warnings.append("Y-direction reinforcement cannot be physically fitted with the current geometry/spacing.")

    r.flexure = {
        "x": {"Mu": Mu_x, "d": d_mm, "As_req": Asx_req, "As_min": Asx_min, "As_prov": Asx_prov, "dia": rebar.x_dia, "spacing": s_x, "phiMn": phiMn_x, "a": a_x, "pass": flex_x_pass},
        "y": {"Mu": Mu_y, "d": d_mm, "As_req": Asy_req, "As_min": Asy_min, "As_prov": Asy_prov, "dia": rebar.y_dia, "spacing": s_y, "phiMn": phiMn_y, "a": a_y, "pass": flex_y_pass},
    }

    # One-way shear at a distance d from column face.
    # Use conservative rectangle-strip estimates based on q_design.
    xu = max(lx - d_mm / 1000.0, 0.0)
    yu = max(ly - d_mm / 1000.0, 0.0)
    Vu_x = q_design * L * xu
    Vu_y = q_design * B * yu
    Vc_x = vc_oneway(mat.fc, L * 1000.0, d_mm)
    Vc_y = vc_oneway(mat.fc, B * 1000.0, d_mm)
    phiVc_x = PHI_SHEAR * Vc_x
    phiVc_y = PHI_SHEAR * Vc_y
    shear_x_pass = Vu_x <= phiVc_x
    shear_y_pass = Vu_y <= phiVc_y
    if not shear_x_pass or not shear_y_pass:
        r.warnings.append("One-way shear failure: increase footing thickness and/or footing dimensions rather than relying on additional flexural steel.")

    # Punching: perimeter at d/2 from column face, simplified rectangular perimeter.
    c1 = geom.cx * 1000.0
    c2 = geom.cy * 1000.0
    b0 = 2.0 * ((c1 + d_mm) + (c2 + d_mm))
    inside_area = (c1 + d_mm) * (c2 + d_mm) / 1e6
    Vu_p = max(Pu - q_design * inside_area, 0.0)
    Vc_p = vc_punching(mat.fc, b0, d_mm)
    phiVc_p = PHI_SHEAR * Vc_p
    punching_pass = Vu_p <= phiVc_p
    if not punching_pass:
        r.warnings.append("Punching shear failure: increasing footing thickness is the primary screening action.")

    r.shear = {
        "x": {"critical_distance": d_mm / 1000.0, "Vu": Vu_x, "Vc": Vc_x, "phiVc": phiVc_x, "utilization": Vu_x / max(phiVc_x, 1e-9), "pass": shear_x_pass},
        "y": {"critical_distance": d_mm / 1000.0, "Vu": Vu_y, "Vc": Vc_y, "phiVc": phiVc_y, "utilization": Vu_y / max(phiVc_y, 1e-9), "pass": shear_y_pass},
    }
    r.punching = {"bo": b0, "inside_area": inside_area, "Vu": Vu_p, "Vc": Vc_p, "phiVc": phiVc_p, "utilization": Vu_p / max(phiVc_p, 1e-9), "pass": punching_pass,
                  "note": "Simplified punching check; eccentricity/unbalanced moment transfer is not fully modeled. [VERIFY AGAINST OFFICIAL NSCP 2015]"}
    r.warnings.append("Punching shear eccentricity/unbalanced moment transfer is not fully modeled in this build. [VERIFY AGAINST OFFICIAL NSCP 2015]") if abs(Mux) + abs(Muy) > 1e-9 else None

    # Anchorage screen.
    ld = development_length_tension(max_bar, mat.fy, mat.fc, geom.cover)
    available = h_mm - geom.cover
    dev_pass = available >= ld
    r.development = {"Ld": ld, "available": available, "pass": dev_pass, "note": "Simplified tension development screen; detailed modifiers/hooks/lap splice rules require code verification."}
    if not dev_pass:
        r.warnings.append("Development length exceeds the available anchorage depth in this simplified check.")

    spacing_pass = all(s in BAR_SPACINGS_MM for s in [s_x, s_y])
    cover_pass = geom.cover >= 75.0
    if geom.cover < 50:
        cover_pass = False
        r.warnings.append("Specified footing cover is below this application's cast-against-earth screening default; verify exact code requirement.")
    r.detailing = {"cover": geom.cover, "cover_pass": cover_pass, "spacing_pass": spacing_pass, "fit_x": fitx, "fit_y": fity,
                   "n_x": nx, "n_y": ny, "fitmsg_x": fitmsgx, "fitmsg_y": fitmsgy}

    r.reinforcement = {
        "bottom_x": f"{rebar.x_dia} mm Ø @ {s_x} mm",
        "bottom_y": f"{rebar.y_dia} mm Ø @ {s_y} mm",
        "dowels": f"{rebar.dowel_n}–{rebar.dowel_dia} mm Ø (screening)",
        "top": f"{rebar.top_dia} mm Ø @ {rebar.top_spacing} mm (where required by analysis/detailing)",
        "As_x_per_m": Asx_prov, "As_y_per_m": Asy_prov,
    }

    r.footing = {"type": geom.footing_type, "B": B, "L": L, "h": geom.h, "d": d_mm / 1000.0,
                 "cx": geom.cx, "cy": geom.cy, "volume": B * L * geom.h}
    r.combined = {"governing_combo": combo_name, "Pu": Pu, "Mux": Mux, "Muy": Muy, "service_P": service_P,
                  "required_area": required_area(service_P, qa), "provided_area": B * L, "combo_note": combo_note}

    r.calculations = [
        f"Required footing area: Areq = Pservice / qa = {service_P:.1f} / {qa:.1f} = {required_area(service_P, qa):.3f} m²",
        f"Adopted footing area: Aprov = B × L = {B:.3f} × {L:.3f} = {B*L:.3f} m²",
        f"Eccentricity: ex = Mx/P = {Mx_b:.2f}/{service_P:.2f} = {ex:.4f} m; ey = My/P = {My_b:.2f}/{service_P:.2f} = {ey:.4f} m",
        f"Bearing: qmax = {qmax:.2f} kPa; qmin = {qmin:.2f} kPa",
        f"Flexure X: Mu = {Mu_x:.2f} kN·m; As,req = {Asx_req:.0f} mm²/m; As,prov = {Asx_prov:.0f} mm²/m",
        f"Flexure Y: Mu = {Mu_y:.2f} kN·m; As,req = {Asy_req:.0f} mm²/m; As,prov = {Asy_prov:.0f} mm²/m",
        f"One-way shear X: Vu = {Vu_x:.2f} kN; φVc = {phiVc_x:.2f} kN",
        f"One-way shear Y: Vu = {Vu_y:.2f} kN; φVc = {phiVc_y:.2f} kN",
        f"Punching: Vu = {Vu_p:.2f} kN; φVc = {phiVc_p:.2f} kN",
        f"Development: Ld ≈ {ld:.0f} mm; available ≈ {available:.0f} mm",
    ]
    r.trace = ["qa → Required area → Footing dimensions → Soil pressure → Critical section → Mu → As → Bar selection → Spacing check"]
    r.recommendations = []
    if not all([bearing_pass, flex_x_pass, flex_y_pass, shear_x_pass, shear_y_pass, punching_pass, dev_pass, cover_pass]):
        r.recommendations.extend(["Review the controlling failed or warning check.", "For shear deficiencies, increase footing thickness and/or dimensions.", "For bearing deficiency, increase footing plan area or revisit geotechnical criteria."])
    else:
        r.recommendations.append("All implemented screening checks pass; independently verify code clauses, geotechnical settlement, and project-specific conditions.")

    checks = [bearing_pass, flex_x_pass, flex_y_pass, shear_x_pass, shear_y_pass, punching_pass, dev_pass, cover_pass]
    r.ok = all(checks)
    r.status = "PASS" if r.ok else ("FAIL" if any(not x for x in checks) else "WARNING")
    return r


def design_strip(data_project, mat, soil, load, geom, rebar):
    # Convert a wall load to a 1 m strip and reuse isolated-style equations with wall width.
    g = FootingGeometry(**asdict(geom))
    g.footing_type = "Strip / Wall"
    g.cx = max(geom.wall_t, 0.1)
    g.cy = 1.0
    g.B = geom.B
    g.L = 1.0
    g.auto_size = False
    p = LoadData(**asdict(load))
    if p.input_mode == "Service Loads":
        p.D = max(load.D, 0.0)
        p.self_weight_mode = "Manual footing self-weight"
        p.manual_self_weight = max(geom.wall_line_load, 0.0)
    else:
        p.direct_Pu = max(load.direct_Pu, 0.0) + load.wall_line_load * 1.5
    return design_isolated(data_project, mat, soil, p, g, rebar)


def design_combined_like(data_project, mat, soil, load, geom, rebar, trapezoid=False, strap=False):
    # Transparent preliminary mechanics for two-column foundations. Advanced frame analysis is flagged.
    P1 = max(load.D * 0.55 + load.L * 0.55, 0.01)
    P2 = max(load.D * 0.45 + load.L * 0.45, 0.01)
    if load.input_mode == "Factored / Ultimate Loads":
        P1 = max(load.direct_Pu * 0.55, 0.01)
        P2 = max(load.direct_Pu * 0.45, 0.01)
    totalP = P1 + P2
    spacing = max(geom.col_spacing, 0.1)
    if trapezoid:
        B1, B2 = max(geom.B1, geom.cx), max(geom.B2, geom.cx)
        L = max(geom.L, spacing + max(geom.cx, geom.cy) + 0.6)
        area = 0.5 * (B1 + B2) * L
    else:
        L = max(geom.L, spacing + max(geom.cx, geom.cy) + 0.6)
        area = max(geom.B * L, 0.01)
        B1 = B2 = area / L
    bearing_info = calculate_bearing_capacity(soil)
    qa = bearing_info.get("qa", soil.qa)
    q = totalP / area
    # Moment about centroid from column spacing and unequal loads.
    resultant_from_left = P2 * spacing / totalP
    center_target = L / 2.0
    ecc = resultant_from_left - center_target
    qmax = q * (1 + 6 * abs(ecc) / L)
    qmin = q * (1 - 6 * abs(ecc) / L)
    status = "PASS" if qmax <= qa and qmin >= 0 else "WARNING"
    warnings = [
        "Combined/strap footing analysis is a preliminary equilibrium model; full beam-on-soil or frame analysis is not implemented.",
        "Column moments, column offsets, compatibility, differential soil contact, and detailed reinforcement interaction require project-specific verification.",
        "[VERIFY AGAINST OFFICIAL NSCP 2015]",
    ]
    if qmin < 0:
        warnings.append("Combined footing simplified model predicts negative soil pressure; partial contact requires dedicated analysis.")
    # Reuse isolated footing as a conservative local-pad screen only, but clearly do not relabel it complete.
    local = FootingGeometry(**asdict(geom))
    local.B = max(B1 if not trapezoid else min(B1, B2), geom.cx + 0.5)
    local.L = max(1.0, L / 2.5)
    local.auto_size = False
    local.footing_type = "Combined / Strap preliminary"
    local.h = geom.h
    ld = design_isolated(data_project, mat, soil, load, local, rebar)
    ld.warnings = warnings + ld.warnings
    ld.combined.update({"P1": P1, "P2": P2, "totalP": totalP, "column_spacing": spacing, "resultant_from_left": resultant_from_left,
                        "centroid": center_target, "eccentricity_along_length": ecc, "qavg": q, "qmax": qmax, "qmin": qmin,
                        "B1": B1, "B2": B2, "L": L, "area": area,
                        "model": "Preliminary statics model — not a substitute for detailed combined/strap footing analysis"})
    ld.status = "WARNING" if status == "WARNING" or ld.status != "PASS" else "PASS"
    ld.ok = False if status != "PASS" else ld.ok
    return ld


def design_footing(project, mat, soil, load, geom, rebar):
    t = geom.footing_type
    if t in ("Isolated Square", "Isolated Rectangular", "Pedestal-Supported"):
        return design_isolated(project, mat, soil, load, geom, rebar)
    if t == "Strip / Wall":
        return design_strip(project, mat, soil, load, geom, rebar)
    if t == "Combined Rectangular":
        return design_combined_like(project, mat, soil, load, geom, rebar, trapezoid=False)
    if t == "Combined Trapezoidal":
        return design_combined_like(project, mat, soil, load, geom, rebar, trapezoid=True)
    if t == "Strap Footing":
        return design_combined_like(project, mat, soil, load, geom, rebar, strap=True)
    return design_isolated(project, mat, soil, load, geom, rebar)


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        ttk.Label(self.tip, text=self.text, relief="solid", borderwidth=1, padding=6).pack()
    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class FootingDesignApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x920")
        self.minsize(1150, 760)
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self._configure_style()
        self.project = ProjectData()
        self.material = MaterialProperties()
        self.soil = SoilProperties()
        self.load = LoadData()
        self.geom = FootingGeometry()
        self.rebar = RebarSpec()
        self.results = DesignResults()
        self.vars = {}
        self.pages = {}
        self.nav_items = []
        self.page_names = ["Project", "Foundation", "Materials", "Soil", "Loads", "Geometry", "Design", "Rebar", "Drawings", "Results", "Calculations", "Report"]
        self.page_index = 0
        self._build_shell()
        self._build_pages()
        self.show_page(0)

    def _configure_style(self):
        self.configure(bg="#f3f5f8")
        self.style.configure("TFrame", background="#f3f5f8")
        self.style.configure("Card.TFrame", background="white", relief="solid", borderwidth=1)
        self.style.configure("Sidebar.TFrame", background="#17212b")
        self.style.configure("Sidebar.TButton", background="#17212b", foreground="white", anchor="w", padding=(14, 10), borderwidth=0)
        self.style.map("Sidebar.TButton", background=[("active", "#263645")])
        self.style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background="#ffffff", foreground="#15202b")
        self.style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), background="#ffffff", foreground="#1e2a36")
        self.style.configure("TLabel", font=("Segoe UI", 9), background="#f3f5f8", foreground="#23313d")
        self.style.configure("Card.TLabel", background="#ffffff")
        self.style.configure("Small.TLabel", font=("Segoe UI", 8), background="#ffffff", foreground="#637381")
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8))
        self.style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8))
        self.style.configure("TNotebook", background="#f3f5f8", borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=(12, 7))

    def _build_shell(self):
        self.sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=215)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ttk.Label(self.sidebar, text="RC FOOTING\nDESIGN", font=("Segoe UI", 16, "bold"), foreground="white", background="#17212b", justify="left", padding=(18, 22)).pack(fill="x")
        ttk.Label(self.sidebar, text="NSCP 2015 / ACI-based\nengineering workflow", font=("Segoe UI", 8), foreground="#b7c4cf", background="#17212b", justify="left", padding=(18, 0, 18, 16)).pack(fill="x")
        self.nav_frame = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        self.nav_frame.pack(fill="both", expand=True)
        for i, name in enumerate(self.page_names):
            b = ttk.Button(self.nav_frame, text=f"{i+1:02d}  {name}", style="Sidebar.TButton", command=lambda idx=i: self.show_page(idx))
            b.pack(fill="x", pady=1)
            self.nav_items.append(b)
        ttk.Label(self.sidebar, text="Engineering design assistance only.\nVerify against official code and\ngeotechnical report.", font=("Segoe UI", 8), foreground="#9fadb8", background="#17212b", justify="left", padding=18).pack(side="bottom", fill="x")

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(right, style="Card.TFrame")
        top.pack(fill="x")
        self.page_title = ttk.Label(top, text="", style="Header.TLabel", padding=(20, 14))
        self.page_title.pack(side="left")
        self.status_lbl = ttk.Label(top, text="NOT CALCULATED", padding=(20, 14), background="#ffffff", foreground="#7a8792", font=("Segoe UI", 9, "bold"))
        self.status_lbl.pack(side="right")
        self.main = ttk.Frame(right)
        self.main.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.content = ttk.Frame(self.main)
        self.content.pack(fill="both", expand=True)

        bottom = ttk.Frame(right, style="Card.TFrame")
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Reset", command=self.reset_project).pack(side="left", padx=8, pady=8)
        ttk.Button(bottom, text="Save Project", command=self.save_project).pack(side="left", padx=4, pady=8)
        ttk.Button(bottom, text="Load Project", command=self.load_project).pack(side="left", padx=4, pady=8)
        ttk.Label(bottom, text="", style="Card.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Previous", command=self.prev_page).pack(side="left", padx=4, pady=8)
        ttk.Button(bottom, text="Calculate", style="Primary.TButton", command=self.calculate).pack(side="left", padx=4, pady=8)
        ttk.Button(bottom, text="Next", command=self.next_page).pack(side="left", padx=4, pady=8)
        ttk.Button(bottom, text="Generate Report", command=self.generate_report).pack(side="left", padx=8, pady=8)

    def _new_page(self, name):
        frame = ttk.Frame(self.content)
        frame.pack(fill="both", expand=True)
        self.pages[name] = frame
        return frame

    def _build_pages(self):
        for name in self.page_names:
            self._new_page(name)
        self._build_project_page(self.pages["Project"])
        self._build_foundation_page(self.pages["Foundation"])
        self._build_materials_page(self.pages["Materials"])
        self._build_soil_page(self.pages["Soil"])
        self._build_loads_page(self.pages["Loads"])
        self._build_geometry_page(self.pages["Geometry"])
        self._build_design_page(self.pages["Design"])
        self._build_rebar_page(self.pages["Rebar"])
        self._build_drawings_page(self.pages["Drawings"])
        self._build_results_page(self.pages["Results"])
        self._build_calculations_page(self.pages["Calculations"])
        self._build_report_page(self.pages["Report"])

    def _scroll_frame(self, parent):
        outer = ttk.Frame(parent, style="Card.TFrame")
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg="#f3f5f8", highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return inner

    def _card(self, parent, title):
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", padx=2, pady=6)
        ttk.Label(card, text=title, style="Section.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 9))
        return card

    def _entry(self, parent, row, label, key, default="", unit="", width=17, tooltip=""):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 6))
        v = tk.StringVar(value=str(default))
        self.vars[key] = v
        e = ttk.Entry(parent, textvariable=v, width=width)
        e.grid(row=row, column=1, sticky="w", pady=4)
        if unit:
            ttk.Label(parent, text=unit, style="Small.TLabel").grid(row=row, column=2, sticky="w", padx=6)
        if tooltip:
            ToolTip(e, tooltip)
        return e

    def _combo(self, parent, row, label, key, values, default=None, width=24, tooltip=""):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 6))
        v = tk.StringVar(value=default if default is not None else values[0])
        self.vars[key] = v
        c = ttk.Combobox(parent, textvariable=v, values=values, width=width, state="readonly")
        c.grid(row=row, column=1, sticky="w", pady=4)
        if tooltip:
            ToolTip(c, tooltip)
        return c

    def _check(self, parent, row, label, key, default=False):
        v = tk.BooleanVar(value=default)
        self.vars[key] = v
        ttk.Checkbutton(parent, text=label, variable=v).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
        return v

    def _text(self, parent, row, label, key, default="", height=4, width=70):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 6))
        t = tk.Text(parent, width=width, height=height, wrap="word", relief="solid", borderwidth=1)
        t.insert("1.0", default)
        t.grid(row=row, column=1, columnspan=5, sticky="ew", pady=4)
        self.vars[key] = t
        return t

    def _build_project_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Project Information")
        fields = [
            ("Project Name", "project_name", ""), ("Project Location", "location", ""), ("Building / Structure", "structure", ""),
            ("Foundation Mark", "footing_mark", "F1"), ("Column Mark", "column_mark", "C1"), ("Designer", "designer", ""),
            ("Checked By", "checked_by", ""), ("Date", "design_date", str(date.today()))]
        for i,(lab,key,d) in enumerate(fields): self._entry(c, i, lab, key, d)
        self._text(c, len(fields), "Design Notes", "notes", "", height=5)
        d = self._card(inner, "Design Assumptions — Always Accessible")
        self.assump_text = tk.Text(d, height=12, width=100, wrap="word", relief="flat", bg="white")
        self.assump_text.insert("1.0", DISCLAIMER)
        self.assump_text.configure(state="disabled")
        self.assump_text.pack(fill="x", pady=4)
        ttk.Label(inner, text="The application keeps project inputs while navigating. JSON save/load is user-generated project data.", style="Small.TLabel").pack(anchor="w", padx=4, pady=4)

    def _build_foundation_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Foundation Type")
        types = ["Isolated Square", "Isolated Rectangular", "Combined Rectangular", "Combined Trapezoidal", "Strap Footing", "Strip / Wall", "Pedestal-Supported"]
        self._combo(c, 1, "Footing configuration", "footing_type", types, geom_default := "Isolated Rectangular", width=32)
        self.vars["footing_type"].trace_add("write", lambda *_: self.update_dynamic_fields())
        ttk.Label(c, text="Choose the configuration before entering geometry. Combined and strap modes are transparent preliminary models in this build.", style="Small.TLabel").grid(row=2, column=0, columnspan=4, sticky="w", pady=6)
        self.foundation_note = ttk.Label(c, text="", style="Small.TLabel", wraplength=800)
        self.foundation_note.grid(row=3, column=0, columnspan=4, sticky="w", pady=4)
        d = self._card(inner, "Workflow")
        ttk.Label(d, text="INPUTS → ASSUMPTIONS → GEOTECHNICAL CHECKS → STRUCTURAL DESIGN → DETAILING → FINAL RECOMMENDATION", style="Card.TLabel", font=("Segoe UI",10,"bold"), wraplength=1100).grid(row=1,column=0,sticky="w")
        self.update_dynamic_fields()

    def _build_materials_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Concrete")
        self._entry(c, 1, "f'c", "fc", self.material.fc, "MPa")
        self._entry(c, 2, "Unit weight", "gamma_c", self.material.gamma_c, "kN/m³")
        d = self._card(inner, "Reinforcing Steel")
        self._entry(d, 1, "fy", "fy", self.material.fy, "MPa")
        self._entry(d, 2, "Es", "es", self.material.es, "MPa")
        ttk.Label(inner, text="Common steel grades are user-selectable through fy. Code-dependent values are not silently hard-coded.", style="Small.TLabel").pack(anchor="w", padx=4)

    def _build_soil_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Geotechnical Inputs")
        self._entry(c, 1, "Allowable bearing capacity qa", "qa", self.soil.qa, "kPa", tooltip="Prefer project-specific geotechnical report value where available.")
        self._entry(c, 2, "Soil unit weight", "gamma_soil", self.soil.gamma_soil, "kN/m³")
        self._entry(c, 3, "Internal friction angle φ", "phi_deg", self.soil.phi_deg, "deg")
        self._entry(c, 4, "Cohesion c", "cohesion", self.soil.cohesion, "kPa")
        self._entry(c, 5, "Groundwater depth", "groundwater", self.soil.groundwater, "m")
        self._entry(c, 6, "Minimum embedment", "embedment", self.soil.embedment, "m")
        self._entry(c, 7, "Soil cover above footing", "soil_cover", self.soil.soil_cover, "m")
        self._entry(c, 8, "Required factor of safety", "fos", self.soil.fos, "-")
        self._entry(c, 9, "Settlement limit", "settlement_limit", self.soil.settlement_limit, "mm")
        d = self._card(inner, "Bearing Pressure Type / Capacity Method")
        self._combo(d, 1, "Pressure type", "pressure_type", ["Gross allowable", "Net allowable"], self.soil.pressure_type)
        self._combo(d, 2, "Bearing-capacity method", "bearing_method", ["User-Provided qa", "Terzaghi", "Meyerhof", "General Equation"], self.soil.bearing_method, width=25)
        ttk.Label(d, text="Method-based capacity is a screening calculation; water-table/effective-stress, shape, depth and inclination factors require independent verification.", style="Small.TLabel", wraplength=900).grid(row=3,column=0,columnspan=4,sticky="w",pady=6)

    def _build_loads_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Load Input Mode")
        self._combo(c, 1, "Input mode", "input_mode", ["Service Loads", "Factored / Ultimate Loads"], self.load.input_mode)
        self._combo(c, 2, "Footing self-weight", "self_weight_mode", ["Auto include footing self-weight", "Exclude (already included)", "Manual footing self-weight"], self.load.self_weight_mode)
        self._entry(c, 3, "Manual footing self-weight", "manual_self_weight", self.load.manual_self_weight, "kN")
        ttk.Label(c, text="Select explicitly whether the loads are service-level or already factored/ultimate.", style="Small.TLabel").grid(row=2,column=0,columnspan=4,sticky="w")
        s = self._card(inner, "Service Loads")
        self._entry(s, 1, "Dead load D", "D", self.load.D, "kN")
        self._entry(s, 2, "Live load L", "L", self.load.L, "kN")
        self._entry(s, 3, "Other permanent", "other", self.load.other, "kN")
        self._entry(s, 4, "Roof load", "roof", self.load.roof, "kN")
        self._entry(s, 5, "Equipment load", "equipment", self.load.equipment, "kN")
        self._entry(s, 6, "Mx", "Mx", self.load.Mx, "kN·m")
        self._entry(s, 7, "My", "My", self.load.My, "kN·m")
        self._entry(s, 8, "Hx", "Hx", self.load.Hx, "kN")
        self._entry(s, 9, "Hy", "Hy", self.load.Hy, "kN")
        u = self._card(inner, "Factored / Ultimate Loads — used only when selected")
        self._entry(u, 1, "Pu", "direct_Pu", self.load.direct_Pu, "kN")
        self._entry(u, 2, "Mux", "direct_Mux", self.load.direct_Mux, "kN·m")
        self._entry(u, 3, "Muy", "direct_Muy", self.load.direct_Muy, "kN·m")
        self._entry(u, 4, "Vux", "direct_Vux", self.load.direct_Vux, "kN")
        self._entry(u, 5, "Vuy", "direct_Vuy", self.load.direct_Vuy, "kN")
        cmb = self._card(inner, "Supported Gravity Combinations")
        txt = "1.4D\n1.2D + 1.6L\n1.2D + 1.0L\n\nAdditional wind/earthquake/fluid/soil/rain combinations are not fabricated in this build. Exact NSCP 2015 applicability should be verified against the official code and project load model."
        ttk.Label(cmb,text=txt,style="Card.TLabel",justify="left",wraplength=900).grid(row=1,column=0,columnspan=6,sticky="w")

    def _build_geometry_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Footing Geometry")
        self._check(c, 1, "Automatically size footing from service bearing criterion", "auto_size", True)
        self._check(c, 2, "Square footing (B = L)", "square", False)
        self._entry(c, 3, "Footing width B", "B", self.geom.B, "m")
        self._entry(c, 4, "Footing length L", "L", self.geom.L, "m")
        self._entry(c, 5, "Footing thickness h", "h", self.geom.h, "m")
        self._entry(c, 6, "Column width cx", "cx", self.geom.cx, "m")
        self._entry(c, 7, "Column depth cy", "cy", self.geom.cy, "m")
        self._entry(c, 8, "Clear cover", "cover", self.geom.cover, "mm")
        self._entry(c, 9, "Column offset X", "col_offset_x", self.geom.col_offset_x, "m")
        self._entry(c, 10, "Column offset Y", "col_offset_y", self.geom.col_offset_y, "m")
        self._entry(c, 11, "Dimension rounding increment", "rounding_mm", self.geom.rounding_mm, "mm")
        self._entry(c, 12, "Maximum thickness limit", "h_max", self.geom.h_max, "m")
        p = self._card(inner, "Pedestal / Multi-Column / Wall Parameters")
        self._entry(p, 1, "Pedestal width", "pedestal_B", self.geom.pedestal_B, "m")
        self._entry(p, 2, "Pedestal length", "pedestal_L", self.geom.pedestal_L, "m")
        self._entry(p, 3, "Pedestal height", "pedestal_h", self.geom.pedestal_h, "m")
        self._entry(p, 4, "Column spacing", "col_spacing", self.geom.col_spacing, "m")
        self._entry(p, 5, "Trapezoid width B1", "B1", self.geom.B1, "m")
        self._entry(p, 6, "Trapezoid width B2", "B2", self.geom.B2, "m")
        self._entry(p, 7, "Strap width", "strap_width", self.geom.strap_width, "m")
        self._entry(p, 8, "Strap depth", "strap_depth", self.geom.strap_depth, "m")
        self._entry(p, 9, "Wall thickness", "wall_t", self.geom.wall_t, "m")
        self._entry(p, 10, "Wall line load", "wall_line_load", self.geom.wall_line_load, "kN/m")

    def _build_design_page(self, frame):
        inner = self._scroll_frame(frame)
        c = self._card(inner, "Design Method")
        ttk.Label(c,text="Bearing and flexural demand use service/ultimate load levels explicitly; the interface prevents silent mixing.",style="Card.TLabel",wraplength=1000).grid(row=1,column=0,columnspan=6,sticky="w")
        ttk.Label(c,text="Thickness iteration is available through the Calculate routine for isolated/pedestal modes; the combined/strap models remain preliminary.",style="Small.TLabel",wraplength=1000).grid(row=2,column=0,columnspan=6,sticky="w",pady=6)
        d=self._card(inner,"Implemented Checks")
        checks=["Required footing area / dimensions","Eccentricity and kern screening","qmax / qmin bearing pressure","Flexural reinforcement X and Y","One-way shear X and Y","Punching shear screening","Development-length screening","Cover and rebar fit","Utilization ratios","Calculation trace"]
        for i,t in enumerate(checks,1): ttk.Label(d,text="✓  "+t,style="Card.TLabel").grid(row=i,column=0,sticky="w",pady=2)
        w=self._card(inner,"Known Limitations")
        ttk.Label(w,text="Settlement: NOT IMPLEMENTED.\nUnbalanced moment transfer in punching: simplified / flagged.\nCombined and strap footing: preliminary statics model only.\nDetailed seismic/soil-structure interaction: NOT IMPLEMENTED.\nExact code clause/table references: VERIFY AGAINST OFFICIAL NSCP 2015.",style="Card.TLabel",wraplength=1000,justify="left").grid(row=1,column=0,columnspan=6,sticky="w")

    def _build_rebar_page(self, frame):
        inner=self._scroll_frame(frame)
        c=self._card(inner,"Bottom Reinforcement")
        self._combo(c,1,"X bar diameter","x_dia",list(map(str,BAR_DIAMETERS_MM.keys())),str(self.rebar.x_dia),width=12)
        self._combo(c,2,"Y bar diameter","y_dia",list(map(str,BAR_DIAMETERS_MM.keys())),str(self.rebar.y_dia),width=12)
        self._entry(c,3,"X spacing","x_spacing",self.rebar.x_spacing,"mm")
        self._entry(c,4,"Y spacing","y_spacing",self.rebar.y_spacing,"mm")
        d=self._card(inner,"Column Dowels / Top Reinforcement")
        self._combo(d,1,"Dowel diameter","dowel_dia",list(map(str,BAR_DIAMETERS_MM.keys())),str(self.rebar.dowel_dia),width=12)
        self._entry(d,2,"Number of dowels","dowel_n",self.rebar.dowel_n,"bars")
        self._combo(d,3,"Top bar diameter","top_dia",list(map(str,BAR_DIAMETERS_MM.keys())),str(self.rebar.top_dia),width=12)
        self._entry(d,4,"Top spacing","top_spacing",self.rebar.top_spacing,"mm")
        ttk.Label(inner,text="The calculator may select a practical spacing automatically for the implemented isolated-footing checks. User-entered spacing is retained as a preference/input cue.",style="Small.TLabel").pack(anchor="w",padx=4)

    def _build_drawings_page(self, frame):
        toolbar=ttk.Frame(frame,style="Card.TFrame")
        toolbar.pack(fill="x",pady=(0,8))
        ttk.Button(toolbar,text="Plan",command=lambda:self.plot_plan()).pack(side="left",padx=4,pady=5)
        ttk.Button(toolbar,text="Section",command=lambda:self.plot_section()).pack(side="left",padx=4,pady=5)
        ttk.Button(toolbar,text="3D Model",command=lambda:self.plot_3d()).pack(side="left",padx=4,pady=5)
        ttk.Button(toolbar,text="Export Current PNG",command=self.export_current_plot).pack(side="right",padx=4,pady=5)
        self.plot_frame=ttk.Frame(frame,style="Card.TFrame")
        self.plot_frame.pack(fill="both",expand=True)
        self.plot_figure=None
        self.plot_canvas=None
        self.current_plot_kind="plan"
        self.plot_plan()

    def _build_results_page(self, frame):
        inner=self._scroll_frame(frame)
        self.result_text=tk.Text(inner,height=35,width=120,wrap="word",bg="white",relief="solid",borderwidth=1)
        self.result_text.pack(fill="both",expand=True,padx=4,pady=4)
        self.result_text.insert("1.0","Calculate the design to populate the dashboard.")
        self.result_text.configure(state="disabled")

    def _build_calculations_page(self, frame):
        inner=self._scroll_frame(frame)
        self.calc_text=tk.Text(inner,height=40,width=120,wrap="word",bg="white",relief="solid",borderwidth=1)
        self.calc_text.pack(fill="both",expand=True,padx=4,pady=4)
        self.calc_text.insert("1.0","Detailed calculation sheet will appear here after Calculate.")
        self.calc_text.configure(state="disabled")

    def _build_report_page(self, frame):
        inner=self._scroll_frame(frame)
        self.report_text=tk.Text(inner,height=40,width=120,wrap="word",bg="white",relief="solid",borderwidth=1)
        self.report_text.pack(fill="both",expand=True,padx=4,pady=4)
        self.report_text.insert("1.0",DISCLAIMER)
        self.report_text.configure(state="disabled")

    def update_dynamic_fields(self):
        t=self.vars.get("footing_type").get() if "footing_type" in self.vars else ""
        notes={
            "Isolated Square":"Single-column square footing. Automatic sizing may enforce B = L.",
            "Isolated Rectangular":"Single-column rectangular footing with biaxial eccentricity screening.",
            "Combined Rectangular":"Two-column preliminary equilibrium model. Full beam/soil interaction analysis is NOT implemented.",
            "Combined Trapezoidal":"Two-column trapezoidal preliminary model using B1/B2/L geometry.",
            "Strap Footing":"Two-pad + strap preliminary equilibrium model. Strap beam design is not a substitute for detailed frame analysis.",
            "Strip / Wall":"Continuous wall footing checked using a 1 m design strip representation.",
            "Pedestal-Supported":"Isolated footing with pedestal geometry inputs for visualization; pedestal structural design is not fully implemented.",
        }
        if hasattr(self,"foundation_note"):
            self.foundation_note.config(text=notes.get(t,""))

    def show_page(self,index):
        self.page_index=index
        for f in self.pages.values(): f.pack_forget()
        self.pages[self.page_names[index]].pack(fill="both",expand=True)
        self.page_title.config(text=self.page_names[index])
        for i,b in enumerate(self.nav_items):
            b.state(["!pressed"])
        try: self.nav_items[index].state(["pressed"])
        except Exception: pass
        if self.page_names[index]=="Drawings":
            self.plot_plan()
        if self.page_names[index]=="Results": self.update_results_dashboard()
        if self.page_names[index]=="Calculations": self.update_calculations()
        if self.page_names[index]=="Report": self.update_report_text()

    def next_page(self):
        if self.page_index < len(self.page_names)-1: self.show_page(self.page_index+1)
    def prev_page(self):
        if self.page_index > 0: self.show_page(self.page_index-1)

    def read_inputs(self):
        self.project=ProjectData(
            project_name=self.vars["project_name"].get(),location=self.vars["location"].get(),structure=self.vars["structure"].get(),
            footing_mark=self.vars["footing_mark"].get(),column_mark=self.vars["column_mark"].get(),designer=self.vars["designer"].get(),
            checked_by=self.vars["checked_by"].get(),design_date=self.vars["design_date"].get(),notes=self.vars["notes"].get("1.0","end-1c")
        )
        self.material=MaterialProperties(fc=parse_float(self.vars["fc"].get(),"f'c",False),gamma_c=parse_float(self.vars["gamma_c"].get(),"Concrete unit weight",False),fy=parse_float(self.vars["fy"].get(),"fy",False),es=parse_float(self.vars["es"].get(),"Es",False))
        self.soil=SoilProperties(qa=parse_float(self.vars["qa"].get(),"qa",False),gamma_soil=parse_float(self.vars["gamma_soil"].get(),"Soil unit weight",False),phi_deg=parse_float(self.vars["phi_deg"].get(),"φ"),cohesion=parse_float(self.vars["cohesion"].get(),"cohesion"),groundwater=parse_float(self.vars["groundwater"].get(),"Groundwater depth"),embedment=parse_float(self.vars["embedment"].get(),"Embedment",False),soil_cover=parse_float(self.vars["soil_cover"].get(),"Soil cover"),fos=parse_float(self.vars["fos"].get(),"Factor of safety",False),settlement_limit=parse_float(self.vars["settlement_limit"].get(),"Settlement limit"),pressure_type=self.vars["pressure_type"].get(),bearing_method=self.vars["bearing_method"].get())
        self.load=LoadData(input_mode=self.vars["input_mode"].get(),self_weight_mode=self.vars["self_weight_mode"].get(),manual_self_weight=parse_float(self.vars["manual_self_weight"].get(),"Manual footing self-weight"),D=parse_float(self.vars["D"].get(),"D"),L=parse_float(self.vars["L"].get(),"L"),other=parse_float(self.vars["other"].get(),"Other permanent"),roof=parse_float(self.vars["roof"].get(),"Roof load"),equipment=parse_float(self.vars["equipment"].get(),"Equipment load"),Mx=float(self.vars["Mx"].get()),My=float(self.vars["My"].get()),Hx=float(self.vars["Hx"].get()),Hy=float(self.vars["Hy"].get()),direct_Pu=parse_float(self.vars["direct_Pu"].get(),"Pu"),direct_Mux=float(self.vars["direct_Mux"].get()),direct_Muy=float(self.vars["direct_Muy"].get()),direct_Vux=float(self.vars["direct_Vux"].get()),direct_Vuy=float(self.vars["direct_Vuy"].get()))
        self.geom=FootingGeometry(footing_type=self.vars["footing_type"].get(),B=parse_float(self.vars["B"].get(),"B",False),L=parse_float(self.vars["L"].get(),"L",False),h=parse_float(self.vars["h"].get(),"h",False),cx=parse_float(self.vars["cx"].get(),"cx",False),cy=parse_float(self.vars["cy"].get(),"cy",False),cover=parse_float(self.vars["cover"].get(),"Cover",False),col_offset_x=float(self.vars["col_offset_x"].get()),col_offset_y=float(self.vars["col_offset_y"].get()),pedestal_B=parse_float(self.vars["pedestal_B"].get(),"Pedestal B"),pedestal_L=parse_float(self.vars["pedestal_L"].get(),"Pedestal L"),pedestal_h=parse_float(self.vars["pedestal_h"].get(),"Pedestal h"),auto_size=bool(self.vars["auto_size"].get()),square=bool(self.vars["square"].get()),rounding_mm=parse_float(self.vars["rounding_mm"].get(),"Rounding increment",False),h_max=parse_float(self.vars["h_max"].get(),"Maximum h",False),B1=parse_float(self.vars["B1"].get(),"B1",False),B2=parse_float(self.vars["B2"].get(),"B2",False),col_spacing=parse_float(self.vars["col_spacing"].get(),"Column spacing",False),strap_width=parse_float(self.vars["strap_width"].get(),"Strap width",False),strap_depth=parse_float(self.vars["strap_depth"].get(),"Strap depth",False),wall_t=parse_float(self.vars["wall_t"].get(),"Wall thickness",False),wall_line_load=parse_float(self.vars["wall_line_load"].get(),"Wall line load"))
        self.rebar=RebarSpec(x_dia=int(self.vars["x_dia"].get()),x_spacing=int(float(self.vars["x_spacing"].get())),y_dia=int(self.vars["y_dia"].get()),y_spacing=int(float(self.vars["y_spacing"].get())),dowel_dia=int(self.vars["dowel_dia"].get()),dowel_n=int(float(self.vars["dowel_n"].get())),top_dia=int(self.vars["top_dia"].get()),top_spacing=int(float(self.vars["top_spacing"].get())))
        if self.geom.square: self.geom.L=self.geom.B
        if self.geom.h > self.geom.h_max: raise ValueError("Footing thickness exceeds the specified maximum thickness limit.")
        if self.geom.B < self.geom.cx or self.geom.L < self.geom.cy: raise ValueError("Footing must be larger than the column in both plan dimensions.")
        return True

    def calculate(self):
        try:
            self.read_inputs()
            # Thickness iteration for isolated-like modes.
            h0=self.geom.h
            candidate=self.geom.h
            best=None
            max_iter=max(0,int(round((self.geom.h_max-h0)/0.025))+1)
            if self.geom.auto_size and self.geom.footing_type in ("Isolated Square","Isolated Rectangular","Pedestal-Supported"):
                for _ in range(max_iter+1):
                    self.geom.h=candidate
                    rr=design_footing(self.project,self.material,self.soil,self.load,self.geom,self.rebar)
                    best=rr
                    if rr.ok or candidate >= self.geom.h_max-1e-9: break
                    # If shear/punching/development controls, increase thickness; otherwise retain geometry result.
                    if (not rr.punching.get("pass",True)) or any(not x.get("pass",True) for x in rr.shear.values()) or not rr.development.get("pass",True):
                        candidate=round(candidate+0.025, 6)
                    else: break
                self.geom.h=candidate if best and best.footing else h0
                self.results=best
            else:
                self.results=design_footing(self.project,self.material,self.soil,self.load,self.geom,self.rebar)
            self.status_lbl.config(text=self.results.status, foreground={"PASS":"#1f7a3a","FAIL":"#b42318","WARNING":"#9a6700"}.get(self.results.status,"#7a8792"))
            self.update_results_dashboard(); self.update_calculations(); self.update_report_text(); self.plot_plan()
            messagebox.showinfo("Calculation complete", f"Design status: {self.results.status}\nSee Results, Calculations, Drawings, and Report pages.")
        except Exception as e:
            self.status_lbl.config(text="ERROR", foreground="#b42318")
            messagebox.showerror("Input / calculation error", str(e))

    def update_results_dashboard(self):
        r=self.results
        lines=["RC FOOTING DESIGN — RESULTS DASHBOARD","="*68]
        if not r.footing:
            lines.append("No completed calculation yet.")
        else:
            f=r.footing;b=r.bearing;fx=r.flexure;sh=r.shear;p=r.punching;d=r.detailing
            lines += [
                f"Type: {f.get('type')}",f"Size: {f.get('B',0):.3f} m × {f.get('L',0):.3f} m × {f.get('h',0)*1000:.0f} mm",f"Effective depth: {f.get('d',0)*1000:.0f} mm",
                "",f"qa = {b.get('qa',0):.2f} kPa",f"qmax = {b.get('qmax',0):.2f} kPa",f"qmin = {b.get('qmin',0):.2f} kPa",f"Bearing utilization = {b.get('utilization',0):.3f}",f"BEARING: {'PASS' if b.get('pass') else 'FAIL / WARNING'}",
                "",f"X: Mu={fx.get('x',{}).get('Mu',0):.2f} kN·m; As,req={fx.get('x',{}).get('As_req',0):.0f}; As,prov={fx.get('x',{}).get('As_prov',0):.0f}; {fx.get('x',{}).get('dia','')} mm Ø @ {fx.get('x',{}).get('spacing','')} mm",f"Y: Mu={fx.get('y',{}).get('Mu',0):.2f} kN·m; As,req={fx.get('y',{}).get('As_req',0):.0f}; As,prov={fx.get('y',{}).get('As_prov',0):.0f}; {fx.get('y',{}).get('dia','')} mm Ø @ {fx.get('y',{}).get('spacing','')} mm",f"FLEXURE: {'PASS' if fx.get('x',{}).get('pass') and fx.get('y',{}).get('pass') else 'FAIL'}",
                "",f"One-way shear X: {'PASS' if sh.get('x',{}).get('pass') else 'FAIL'}; utilization={sh.get('x',{}).get('utilization',0):.3f}",f"One-way shear Y: {'PASS' if sh.get('y',{}).get('pass') else 'FAIL'}; utilization={sh.get('y',{}).get('utilization',0):.3f}",f"Punching: {'PASS' if p.get('pass') else 'FAIL'}; utilization={p.get('utilization',0):.3f}",f"Detailing / fit: {'PASS' if d.get('cover_pass') and d.get('fit_x') and d.get('fit_y') else 'WARNING / FAIL'}",
                "",f"BOTTOM X: {r.reinforcement.get('bottom_x','-')}",f"BOTTOM Y: {r.reinforcement.get('bottom_y','-')}",f"DOWELS: {r.reinforcement.get('dowels','-')}","",f"OVERALL DESIGN STATUS: {r.status}","",
                "WARNINGS:"]+(["• "+w for w in r.warnings] if r.warnings else ["• None"])
        self.result_text.configure(state="normal");self.result_text.delete("1.0","end");self.result_text.insert("1.0","\n".join(lines));self.result_text.configure(state="disabled")

    def update_calculations(self):
        r=self.results
        text=["DETAILED CALCULATION SHEET","="*80]
        if not r.calculations:
            text.append("Calculate the design first.")
        else:
            text += r.calculations
            text += ["","CALCULATION TRACE:"]+[" → ".join(r.trace)]
            text += ["","ASSUMPTIONS:"]+(["• "+x for x in r.assumptions] if r.assumptions else [])
            text += ["","CODE REFERENCES / VERIFICATION NOTES:"]+(["• "+x for x in r.code_refs] if r.code_refs else [])
            text += ["","ENGINEERING LIMITATIONS:","• Settlement analysis not implemented.","• Combined/trapezoidal/strap footing models are preliminary where applicable.","• Exact NSCP 2015 clause numbers are intentionally not fabricated."]
        self.calc_text.configure(state="normal");self.calc_text.delete("1.0","end");self.calc_text.insert("1.0","\n".join(text));self.calc_text.configure(state="disabled")

    def update_report_text(self):
        self.report_text.configure(state="normal");self.report_text.delete("1.0","end");self.report_text.insert("1.0",self.make_report_text());self.report_text.configure(state="disabled")

    def make_report_text(self):
        r=self.results;p=self.project;m=self.material;s=self.soil;l=self.load;g=self.geom
        lines=["="*72,"REINFORCED CONCRETE FOOTING DESIGN","NSCP 2015 / ACI-BASED SCREENING","="*72,"PROJECT INFORMATION","-"*72,f"Project: {p.project_name}",f"Location: {p.location}",f"Structure: {p.structure}",f"Foundation: {p.footing_mark}",f"Column: {p.column_mark}",f"Designer: {p.designer}",f"Checked By: {p.checked_by}",f"Date: {p.design_date}","", "DESIGN INPUTS","-"*72,f"f'c = {m.fc:.2f} MPa",f"fy = {m.fy:.2f} MPa",f"qa = {s.qa:.2f} kPa",f"Bearing method = {s.bearing_method}",f"Input mode = {l.input_mode}","", "FOOTING GEOMETRY","-"*72,f"Type = {g.footing_type}",f"B = {g.B:.3f} m; L = {g.L:.3f} m; h = {g.h:.3f} m",f"Column = {g.cx:.3f} × {g.cy:.3f} m",f"Cover = {g.cover:.0f} mm"]
        if r.footing:
            lines += ["", "BEARING PRESSURE","-"*72,f"qmax = {r.bearing.get('qmax',0):.2f} kPa",f"qmin = {r.bearing.get('qmin',0):.2f} kPa",f"ex = {r.bearing.get('ex',0):.4f} m; ey = {r.bearing.get('ey',0):.4f} m",f"Bearing status = {'PASS' if r.bearing.get('pass') else 'FAIL / WARNING'}", "", "FLEXURAL DESIGN", "-"*72]
            for k,label in (("x","X-DIRECTION"),("y","Y-DIRECTION")):
                f=r.flexure.get(k,{})
                lines += [label,f"Mu = {f.get('Mu',0):.2f} kN·m",f"d = {f.get('d',0):.1f} mm",f"As,req = {f.get('As_req',0):.0f} mm²/m",f"As,min = {f.get('As_min',0):.0f} mm²/m",f"As,prov = {f.get('As_prov',0):.0f} mm²/m",f"Reinforcement = {f.get('dia','')} mm Ø @ {f.get('spacing','')} mm",f"Status = {'PASS' if f.get('pass') else 'FAIL'}",""]
            lines += ["ONE-WAY SHEAR","-"*72]
            for k in ("x","y"):
                q=r.shear.get(k,{})
                lines += [f"{k.upper()}: Vu={q.get('Vu',0):.2f} kN; φVc={q.get('phiVc',0):.2f} kN; status={'PASS' if q.get('pass') else 'FAIL'}"]
            lines += ["", "PUNCHING SHEAR", "-"*72,f"bo = {r.punching.get('bo',0):.1f} mm",f"Vu = {r.punching.get('Vu',0):.2f} kN",f"φVc = {r.punching.get('phiVc',0):.2f} kN",f"Status = {'PASS' if r.punching.get('pass') else 'FAIL'}", "", "DEVELOPMENT / DETAILING", "-"*72,f"Ld screen = {r.development.get('Ld',0):.0f} mm",f"Available = {r.development.get('available',0):.0f} mm",f"Development = {'PASS' if r.development.get('pass') else 'FAIL'}", "", "FINAL RECOMMENDATION", "-"*72,f"Overall status = {r.status}"]
            lines += ["", "WARNINGS"] + (["- "+w for w in r.warnings] if r.warnings else ["- None"])
            lines += ["", "ASSUMPTIONS"] + (["- "+x for x in r.assumptions] if r.assumptions else ["- None recorded"])
            lines += ["", "CODE REFERENCES"] + (["- "+x for x in r.code_refs] if r.code_refs else ["- Verify against official NSCP 2015"])
            lines += ["", "DISCLAIMER",DISCLAIMER]
        else:
            lines += ["",DISCLAIMER]
        return "\n".join(lines)

    def reset_project(self):
        if not messagebox.askyesno("Reset", "Reset all project inputs and results?"): return
        self.destroy(); FootingDesignApp().mainloop()

    def save_project(self):
        try:
            self.read_inputs()
            payload={"project":asdict(self.project),"material":asdict(self.material),"soil":asdict(self.soil),"load":asdict(self.load),"geom":asdict(self.geom),"rebar":asdict(self.rebar)}
            p=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON project","*.json")],title="Save Project")
            if not p:return
            with open(p,"w",encoding="utf-8") as f: json.dump(payload,f,indent=2)
            messagebox.showinfo("Saved",f"Project saved to:\n{p}")
        except Exception as e: messagebox.showerror("Save error",str(e))

    def load_project(self):
        p=filedialog.askopenfilename(filetypes=[("JSON project","*.json")],title="Load Project")
        if not p:return
        try:
            with open(p,"r",encoding="utf-8") as f: payload=json.load(f)
            for section, cls in [("project",ProjectData),("material",MaterialProperties),("soil",SoilProperties),("load",LoadData),("geom",FootingGeometry),("rebar",RebarSpec)]:
                if section in payload:
                    obj=cls(**payload[section])
                    setattr(self, {"project":"project","material":"material","soil":"soil","load":"load","geom":"geom","rebar":"rebar"}[section], obj)
            self._push_objects_to_vars(); messagebox.showinfo("Loaded",f"Project loaded from:\n{p}")
        except Exception as e: messagebox.showerror("Load error",str(e))

    def _push_objects_to_vars(self):
        d=self.project.__dict__
        for k,v in d.items():
            if k in self.vars:
                if isinstance(self.vars[k],tk.Text): self.vars[k].delete("1.0","end");self.vars[k].insert("1.0",v)
                else:self.vars[k].set(v)
        for obj in (self.material,self.soil,self.load,self.geom,self.rebar):
            for k,v in asdict(obj).items():
                if k in self.vars:self.vars[k].set(v)
        self.update_dynamic_fields()
        self.update_results_dashboard();self.update_calculations();self.update_report_text()

    def generate_report(self):
        try:
            if not self.results.footing: self.calculate()
            p=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text report","*.txt")],title="Save Calculation Report")
            if not p:return
            with open(p,"w",encoding="utf-8") as f:f.write(self.make_report_text())
            messagebox.showinfo("Report generated",f"Calculation report saved to:\n{p}\n\nPNG exports are available from Drawings.")
        except Exception as e: messagebox.showerror("Report error",str(e))

    def clear_plot(self):
        for w in self.plot_frame.winfo_children(): w.destroy()
        self.plot_figure=None;self.plot_canvas=None

    def _new_fig(self, projection=None):
        self.clear_plot();fig=plt.Figure(figsize=(10,6),dpi=100);ax=fig.add_subplot(111,projection=projection) if projection else fig.add_subplot(111);self.plot_figure=fig;self.plot_canvas=FigureCanvasTkAgg(fig,master=self.plot_frame);self.plot_canvas.draw();self.plot_canvas.get_tk_widget().pack(fill="both",expand=True);return ax

    def plot_plan(self):
        self.current_plot_kind="plan"
        ax=self._new_fig();g=self.geom;r=self.results
        B=r.footing.get("B",g.B) if r.footing else g.B;L=r.footing.get("L",g.L) if r.footing else g.L
        ax.set_aspect("equal",adjustable="box")
        if g.footing_type=="Combined Trapezoidal":
            B1,B2=g.B1,g.B2; x=np.array([0,L,L,0,0]); y=np.array([-B1/2,B2/2,B2/2,-B1/2,-B1/2]); ax.plot(x,y,linewidth=2,label="Footing")
        else:
            ax.add_patch(plt.Rectangle((-L/2,-B/2),L,B,fill=False,linewidth=2))
        cx,cy=g.cx,g.cy
        ox,oy=g.col_offset_x,g.col_offset_y
        ax.add_patch(plt.Rectangle((ox-cx/2,oy-cy/2),cx,cy,fill=False,linewidth=2))
        ax.axhline(0,color="gray",linewidth=0.8);ax.axvline(0,color="gray",linewidth=0.8)
        ax.plot(0,0,'o',markersize=4,label="Footing center")
        if r.bearing:
            ex,ey=r.bearing.get("ex",0),r.bearing.get("ey",0);ax.plot(ey,ex,'x',markersize=9,label="Resultant")
            ax.annotate(f"e = ({ey:.3f}, {ex:.3f}) m",(ey,ex),textcoords="offset points",xytext=(8,8))
        if g.footing_type in ("Combined Rectangular","Strap Footing"):
            s=g.col_spacing
            for xx in (-s/2,s/2): ax.add_patch(plt.Rectangle((xx-cx/2,-cy/2),cx,cy,fill=False,linewidth=1.7))
        # Conceptual rebars
        if r.flexure:
            sx=r.flexure.get("x",{}).get("spacing",150)/1000; sy=r.flexure.get("y",{}).get("spacing",150)/1000
            for y in np.arange(-B/2+g.cover/1000,B/2+1e-6,sy): ax.plot(np.linspace(-L/2+g.cover/1000,L/2-g.cover/1000,2),[y,y],alpha=0.45)
            for x in np.arange(-L/2+g.cover/1000,L/2+1e-6,sx): ax.plot([x,x],[-B/2+g.cover/1000,B/2-g.cover/1000],alpha=0.45)
        ax.set_xlabel("Length / X (m)");ax.set_ylabel("Width / Y (m)");ax.set_title("PLAN VIEW — SCHEMATIC");ax.legend(loc="upper right",fontsize=8);ax.grid(alpha=0.2)
        ax.text(0.01,0.01,"SCHEMATIC — NOT FOR FABRICATION",transform=ax.transAxes,fontsize=8)
        self.plot_canvas.draw()

    def plot_section(self):
        self.current_plot_kind="section"
        ax=self._new_fig();g=self.geom;r=self.results
        B=r.footing.get("B",g.B) if r.footing else g.B; h=r.footing.get("h",g.h) if r.footing else g.h
        c=max(g.cx,g.cy);ph=g.pedestal_h if g.pedestal_h>0 else 0
        ax.set_aspect("equal",adjustable="box")
        ax.add_patch(plt.Rectangle((-B/2,-h),B,h,fill=False,linewidth=2))
        colw=c/2
        ax.add_patch(plt.Rectangle((-colw,0),c,max(1.5,h+ph),fill=False,linewidth=2))
        if g.pedestal_B>0 and g.pedestal_h>0:
            ax.add_patch(plt.Rectangle((-g.pedestal_B/2,0),g.pedestal_B,g.pedestal_h,fill=False,linewidth=1.5))
        ax.axhline(0,color="gray",linewidth=1);ax.text(B*0.52,0,"Ground / reference",va="bottom")
        ybar=-h+g.cover/1000
        dia=(r.flexure.get("x",{}).get("dia",16))/1000
        xs=np.linspace(-B/2+g.cover/1000,B/2-g.cover/1000,max(4,int(B/0.25)))
        ax.plot(xs,[ybar]*len(xs),'o',markersize=3)
        ax.annotate(f"h = {h*1000:.0f} mm",(B/2,-h/2),xytext=(B*0.58,-h/2),arrowprops=dict(arrowstyle="<->"))
        ax.annotate(f"cover = {g.cover:.0f} mm",(-B/2,-h+g.cover/1000),xytext=(-B*0.9,-h*0.75),arrowprops=dict(arrowstyle="->"))
        ax.set_xlim(-B*0.75,B*0.75);ax.set_ylim(-h*1.35,max(1.7,h+ph));ax.set_xlabel("Section width (m)");ax.set_ylabel("Elevation (m)");ax.set_title("SECTION VIEW — SCHEMATIC");ax.grid(alpha=0.15)
        ax.text(0.01,0.01,"SCHEMATIC — NOT FOR FABRICATION",transform=ax.transAxes,fontsize=8)
        self.plot_canvas.draw()

    def _cuboid(self, ax, x0,x1,y0,y1,z0,z1,alpha=0.7):
        verts=[[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)],[(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],[(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],[(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)],[(x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1)],[(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)]]
        ax.add_collection3d(Poly3DCollection(verts,alpha=alpha,linewidths=0.7))

    def plot_3d(self):
        self.current_plot_kind="3d"
        ax=self._new_fig(projection="3d");g=self.geom;r=self.results
        B=r.footing.get("B",g.B) if r.footing else g.B;L=r.footing.get("L",g.L) if r.footing else g.L;h=r.footing.get("h",g.h) if r.footing else g.h
        self._cuboid(ax,-L/2,L/2,-B/2,B/2,-h,0,0.45)
        cx,cy=g.cx,g.cy; self._cuboid(ax,-cx/2,cx/2,-cy/2,cy/2,0,1.5,0.6)
        if g.pedestal_B>0 and g.pedestal_L>0 and g.pedestal_h>0:self._cuboid(ax,-g.pedestal_L/2,g.pedestal_L/2,-g.pedestal_B/2,g.pedestal_B/2,0,g.pedestal_h,0.65)
        # conceptual reinforcement
        if r.flexure:
            for xx in np.linspace(-L/2+g.cover/1000,L/2-g.cover/1000,6): ax.plot([xx,xx],[-B/2+g.cover/1000,B/2-g.cover/1000],[-h+g.cover/1000]*2,linewidth=1)
            for yy in np.linspace(-B/2+g.cover/1000,B/2-g.cover/1000,6): ax.plot([-L/2+g.cover/1000,L/2-g.cover/1000],[yy,yy],[-h+g.cover/1000]*2,linewidth=1)
        ax.set_xlabel("X (m)");ax.set_ylabel("Y (m)");ax.set_zlabel("Z (m)");ax.set_title("3D MODEL — SCHEMATIC");
        ax.text2D(0.02,0.02,"SCHEMATIC — NOT FOR FABRICATION",transform=ax.transAxes,fontsize=8)
        self.plot_canvas.draw()

    def export_current_plot(self):
        if self.plot_figure is None:return
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG image","*.png")],title="Export Drawing")
        if not p:return
        self.plot_figure.savefig(p,bbox_inches="tight",dpi=200)
        messagebox.showinfo("Exported",f"Drawing exported to:\n{p}")


def main():
    app=FootingDesignApp()
    app.mainloop()


if __name__ == "__main__":
    main()
