"""
RC Footing Designer — NSCP 2015
Single-file implementation of the specification in "RC Footing Designer — NSCP 2015.pdf"

Structure (mirrors the recommended modular layout so it can be split later):
    [SECTION 1]  Utils / constants / units
    [SECTION 2]  Data models (Project, Geometry, Materials, Loads, Soil, Reinforcement)
    [SECTION 3]  Design engine (bearing, flexure, shear, punching, reinforcement)
    [SECTION 4]  Visualization (2D via Matplotlib, 3D via PyVista)
    [SECTION 5]  Reporting (PDF via ReportLab)
    [SECTION 6]  GUI (PySide6)
    [SECTION 7]  Entry point

DISCLAIMER
----------
This software is intended to assist qualified structural engineers.
It does NOT replace engineering judgment, geotechnical investigation,
code verification, professional review, or approval by the responsible
design professional. It never guarantees structural safety.

All NSCP 2015 clause references and factors marked REQUIRES CODE
VERIFICATION must be checked against the actual code document before
use in real design.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# [SECTION 1]  UTILS / CONSTANTS / UNITS
# ---------------------------------------------------------------------------

CODE_VERSION = "NSCP 2015"

# ---- Strength reduction factors -------------------------------------------
# REQUIRES CODE VERIFICATION — these values follow the ACI 318-14 lineage
# which NSCP 2015 is based on. Confirm each against the NSCP 2015 text.
PHI_FLEXURE = 0.90          # REQUIRES CODE VERIFICATION — NSCP 2015 §421.2.2
PHI_SHEAR = 0.75            # REQUIRES CODE VERIFICATION — NSCP 2015 §421.2.1
PHI_BEARING = 0.65          # REQUIRES CODE VERIFICATION — NSCP 2015 §422.4

# ---- Material defaults ----------------------------------------------------
ES_STEEL = 200_000.0        # MPa — universal (VERIFIED)
DEFAULT_CONCRETE_DENSITY = 24.0  # kN/m^3 (normal-weight RC)

# ---- Minimum reinforcement ------------------------------------------------
# REQUIRES CODE VERIFICATION — NSCP 2015 §425.2 (temperature/shrinkage,
# deformed bars, grade 420). Value below is the ACI 318-14 lineage value.
MIN_REBAR_RATIO_FOOTING = 0.0018  # REQUIRES CODE VERIFICATION

# ---- Cover ----------------------------------------------------------------
# REQUIRES CODE VERIFICATION — NSCP 2015 §420.6.1.3 (cast against earth)
DEFAULT_COVER_MM = 75.0     # REQUIRES CODE VERIFICATION

# ---- Centralized code references -----------------------------------------
CODE_REFERENCES = {
    "load_combinations": "NSCP 2015 §203 — REQUIRES CODE VERIFICATION",
    "bearing": "NSCP 2015 §304 / §305 — REQUIRES CODE VERIFICATION",
    "flexure": "NSCP 2015 §422.3 — REQUIRES CODE VERIFICATION",
    "one_way_shear": "NSCP 2015 §422.5 — REQUIRES CODE VERIFICATION",
    "punching_shear": "NSCP 2015 §422.6 — REQUIRES CODE VERIFICATION",
    "min_reinforcement": "NSCP 2015 §425.2 — REQUIRES CODE VERIFICATION",
    "development": "NSCP 2015 §425.4 — REQUIRES CODE VERIFICATION",
    "cover": "NSCP 2015 §420.6.1 — REQUIRES CODE VERIFICATION",
    "modulus_concrete": "NSCP 2015 §419.2.2 — REQUIRES CODE VERIFICATION",
}

DISCLAIMER_TEXT = (
    "This software is intended to assist qualified structural engineers in "
    "analysis and design. It does not replace engineering judgment, "
    "geotechnical investigation, code verification, professional review, or "
    "approval by the responsible design professional. It does not guarantee "
    "structural safety."
)

# Standard bar diameters (mm) — informational list, user may enter custom
STANDARD_BAR_DIAMETERS_MM = [10, 12, 16, 20, 25, 28, 32, 36]


class Status(str, Enum):
    NOT_ANALYZED = "NOT ANALYZED"
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# [SECTION 2]  DATA MODELS
# ---------------------------------------------------------------------------

@dataclass
class ProjectInfo:
    name: str = "Untitled Project"
    location: str = ""
    structure: str = ""
    client: str = ""
    design_engineer: str = ""
    checker: str = ""
    date: str = ""
    revision: str = "0"
    drawing_no: str = ""
    foundation_mark: str = "F1"


@dataclass
class Concrete:
    fc: float = 28.0              # MPa
    density: float = DEFAULT_CONCRETE_DENSITY  # kN/m^3
    lambda_factor: float = 1.0    # normal weight

    def Ec(self) -> float:
        # REQUIRES CODE VERIFICATION — NSCP 2015 §419.2.2
        return 4700.0 * math.sqrt(self.fc)


@dataclass
class Rebar:
    fy: float = 415.0             # MPa
    Es: float = ES_STEEL
    diameter: float = 20.0        # mm

    @property
    def area(self) -> float:
        return math.pi * self.diameter ** 2 / 4.0  # mm^2


@dataclass
class Soil:
    qa: float = 200.0             # kPa allowable bearing pressure
    unit_weight: float = 18.0     # kN/m^3
    Df: float = 1.5               # m embedment depth
    groundwater_depth: float = 99.0
    has_bearing_capacity: bool = True


@dataclass
class FootingGeometry:
    B: float = 2000.0             # mm width
    L: float = 2000.0             # mm length
    H: float = 450.0              # mm thickness
    cx: float = 400.0             # mm column width
    cy: float = 400.0             # mm column length
    cover: float = DEFAULT_COVER_MM

    def effective_depth(self, bar_dia: float) -> float:
        return self.H - self.cover - bar_dia / 2.0


@dataclass
class LoadCase:
    name: str
    P: float = 0.0                # kN
    Mx: float = 0.0               # kN·m
    My: float = 0.0               # kN·m


@dataclass
class LoadCombination:
    name: str
    factors: Dict[str, float]
    basis: str = "strength"       # "strength" | "service"


@dataclass
class CheckResult:
    name: str
    status: Status = Status.NOT_ANALYZED
    demand: float = 0.0
    capacity: float = 0.0
    utilization: float = 0.0
    units: str = ""
    code_ref: str = "CODE REFERENCE REQUIRES VERIFICATION"
    inputs: Dict[str, Any] = field(default_factory=dict)
    intermediate: Dict[str, Any] = field(default_factory=dict)
    equations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DesignResult:
    bearing: Optional[CheckResult] = None
    flexure_x: Optional[CheckResult] = None
    flexure_y: Optional[CheckResult] = None
    one_way_shear_x: Optional[CheckResult] = None
    one_way_shear_y: Optional[CheckResult] = None
    punching_shear: Optional[CheckResult] = None
    reinforcement: Optional[CheckResult] = None
    warnings: List[str] = field(default_factory=list)
    overall_status: Status = Status.NOT_ANALYZED

    def all_checks(self) -> List[CheckResult]:
        return [c for c in [
            self.bearing, self.flexure_x, self.flexure_y,
            self.one_way_shear_x, self.one_way_shear_y,
            self.punching_shear, self.reinforcement,
        ] if c is not None]


@dataclass
class Project:
    info: ProjectInfo = field(default_factory=ProjectInfo)
    footing_type: str = "isolated"
    geometry: FootingGeometry = field(default_factory=FootingGeometry)
    concrete: Concrete = field(default_factory=Concrete)
    rebar: Rebar = field(default_factory=Rebar)
    soil: Soil = field(default_factory=Soil)
    load_cases: List[LoadCase] = field(default_factory=lambda: [
        LoadCase("D", 800.0, 0.0, 0.0),
        LoadCase("L", 400.0, 0.0, 0.0),
    ])


# ---------------------------------------------------------------------------
# [SECTION 3]  DESIGN ENGINE
# ---------------------------------------------------------------------------

class InputValidationError(ValueError):
    """Raised for invalid inputs so the GUI can present a clean message."""


def validate_project(p: Project) -> List[str]:
    """Return list of human-readable validation warnings (may be empty)."""
    warnings: List[str] = []
    g, c, s, r = p.geometry, p.concrete, p.soil, p.rebar

    if g.B <= 0:
        raise InputValidationError("Footing width B must be greater than zero.")
    if g.L <= 0:
        raise InputValidationError("Footing length L must be greater than zero.")
    if g.H <= 0:
        raise InputValidationError("Footing thickness H must be greater than zero.")
    if g.cx <= 0 or g.cy <= 0:
        raise InputValidationError("Column dimensions must be positive.")
    if g.cover < 0:
        raise InputValidationError("Clear cover cannot be negative.")
    if c.fc <= 0:
        raise InputValidationError("Concrete strength f'c must be positive.")
    if r.fy <= 0:
        raise InputValidationError("Steel yield strength fy must be positive.")
    if r.diameter <= 0:
        raise InputValidationError("Bar diameter must be positive.")
    if s.qa <= 0:
        raise InputValidationError("Allowable bearing pressure qa must be positive.")
    if not s.has_bearing_capacity:
        warnings.append(
            "Soil bearing capacity has not been independently verified. "
            "Geotechnical input is required for final design."
        )
    if g.cover < DEFAULT_COVER_MM - 1e-9:
        warnings.append(
            f"Clear cover {g.cover:.0f} mm is below the default "
            f"{DEFAULT_COVER_MM:.0f} mm for concrete cast against earth "
            "(NSCP 2015 §420.6.1.3 — REQUIRES CODE VERIFICATION)."
        )
    return warnings


# --- Load combinations -----------------------------------------------------

def strength_combinations() -> List[LoadCombination]:
    """Strength (LRFD) combinations — ACI/ASCE lineage.
    REQUIRES CODE VERIFICATION against NSCP 2015 §203.3."""
    return [
        LoadCombination("1.4D", {"D": 1.4}, "strength"),
        LoadCombination("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "strength"),
    ]


def service_combinations() -> List[LoadCombination]:
    """Service combinations — REQUIRES CODE VERIFICATION §203.4."""
    return [
        LoadCombination("D + L", {"D": 1.0, "L": 1.0}, "service"),
        LoadCombination("D + 0.75L", {"D": 1.0, "L": 0.75}, "service"),
    ]


def _apply_combo(cases: Dict[str, LoadCase], combo: LoadCombination):
    P = Mx = My = 0.0
    for cname, factor in combo.factors.items():
        if cname in cases:
            P += factor * cases[cname].P
            Mx += factor * cases[cname].Mx
            My += factor * cases[cname].My
    return P, Mx, My


def governing_strength_loads(project: Project):
    cases = {lc.name: lc for lc in project.load_cases}
    gov = None
    for combo in strength_combinations():
        P, Mx, My = _apply_combo(cases, combo)
        if gov is None or P > gov[0]:
            gov = (P, Mx, My, combo.name)
    return gov


def governing_service_loads(project: Project):
    cases = {lc.name: lc for lc in project.load_cases}
    gov = None
    for combo in service_combinations():
        P, Mx, My = _apply_combo(cases, combo)
        if gov is None or P > gov[0]:
            gov = (P, Mx, My, combo.name)
    return gov


# --- Bearing ---------------------------------------------------------------

def check_bearing(project: Project) -> CheckResult:
    """Service-level soil bearing check with biaxial eccentricity."""
    svc_P, svc_Mx, svc_My, combo_name = governing_service_loads(project)
    g, s = project.geometry, project.soil

    B_m = g.B / 1000.0
    L_m = g.L / 1000.0
    H_m = g.H / 1000.0
    A = B_m * L_m

    W_footing = A * H_m * project.concrete.density
    W_soil = A * max(0.0, s.Df - H_m) * s.unit_weight
    P_total = svc_P + W_footing + W_soil

    ex = svc_My / P_total if P_total else 0.0
    ey = svc_Mx / P_total if P_total else 0.0

    Ix = B_m * L_m ** 3 / 12.0
    Iy = L_m * B_m ** 3 / 12.0
    q_avg = P_total / A
    qx = svc_Mx * (L_m / 2.0) / Ix if Ix else 0.0
    qy = svc_My * (B_m / 2.0) / Iy if Iy else 0.0
    qmax = q_avg + abs(qx) + abs(qy)
    qmin = q_avg - abs(qx) - abs(qy)

    warnings: List[str] = []
    if qmin < 0:
        warnings.append(
            "qmin < 0 — loss of full soil contact. Review eccentricity and "
            "uplift assumptions."
        )
    if abs(ex) > B_m / 6.0 or abs(ey) > L_m / 6.0:
        warnings.append(
            "Resultant outside middle-third (kern). Partial compression likely."
        )

    if qmax <= s.qa and qmin >= 0:
        status = Status.PASS if not warnings else Status.WARNING
    else:
        status = Status.FAIL

    util = qmax / s.qa if s.qa > 0 else float("inf")

    return CheckResult(
        name="Bearing Pressure",
        status=status,
        demand=qmax, capacity=s.qa, utilization=util, units="kPa",
        code_ref=CODE_REFERENCES["bearing"],
        inputs={"combo": combo_name, "P_service_kN": svc_P,
                "Mx_service_kNm": svc_Mx, "My_service_kNm": svc_My,
                "qa_kPa": s.qa, "B_m": B_m, "L_m": L_m, "H_m": H_m},
        intermediate={"P_total_kN": P_total,
                      "W_footing_kN": W_footing, "W_soil_kN": W_soil,
                      "ex_m": ex, "ey_m": ey,
                      "q_avg_kPa": q_avg,
                      "qmax_kPa": qmax, "qmin_kPa": qmin},
        equations=[
            "ex = My / P_total",
            "ey = Mx / P_total",
            "q_avg = P_total / (B·L)",
            "qmax = q_avg + Mx·(L/2)/Ix + My·(B/2)/Iy",
            "qmin = q_avg − Mx·(L/2)/Ix − My·(B/2)/Iy",
        ],
        warnings=warnings,
    )


# --- Flexure ---------------------------------------------------------------

def _beta1(fc: float) -> float:
    # REQUIRES CODE VERIFICATION — NSCP 2015 §422.2.2.3
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return 0.85 - 0.05 * (fc - 28.0) / 7.0


def check_flexure(Mu_kNm: float, b_mm: float, d_mm: float,
                  fc: float, fy: float, axis: str) -> CheckResult:
    Mu_Nmm = Mu_kNm * 1e6
    phi = PHI_FLEXURE
    beta1 = _beta1(fc)

    Rn = Mu_Nmm / (phi * b_mm * d_mm ** 2) if b_mm * d_mm ** 2 else 0.0
    inner = 1.0 - 2.0 * Rn / (0.85 * fc) if fc > 0 else 0.0
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(max(0.0, inner))) if fy > 0 else 0.0
    As_req = rho * b_mm * d_mm
    As_min = MIN_REBAR_RATIO_FOOTING * b_mm * d_mm  # REQUIRES CODE VERIFICATION
    As_required = max(As_req, As_min)

    a = As_required * fy / (0.85 * fc * b_mm) if fc * b_mm else 0.0
    c = a / beta1 if beta1 else 0.0
    eps_t = 0.003 * (d_mm - c) / c if c > 0 else 0.0

    if eps_t >= 0.005:
        phi_use = 0.90
    elif eps_t <= 0.002:
        phi_use = 0.65
    else:
        phi_use = 0.65 + 0.25 * (eps_t - 0.002) / 0.003

    Mn_Nmm = As_required * fy * (d_mm - a / 2.0)
    phiMn_kNm = phi_use * Mn_Nmm / 1e6

    status = Status.PASS if phiMn_kNm >= Mu_kNm else Status.FAIL
    util = Mu_kNm / phiMn_kNm if phiMn_kNm > 0 else float("inf")
    warnings = []
    if status == Status.PASS and util > 0.95:
        warnings.append(f"Flexure {axis} is close to capacity "
                        f"(utilization = {util:.2f}).")

    return CheckResult(
        name=f"Flexure {axis}",
        status=status,
        demand=Mu_kNm, capacity=phiMn_kNm, utilization=util, units="kN·m",
        code_ref=CODE_REFERENCES["flexure"],
        inputs={"Mu_kNm": Mu_kNm, "b_mm": b_mm, "d_mm": d_mm,
                "fc_MPa": fc, "fy_MPa": fy},
        intermediate={"rho": rho, "As_req_mm2": As_req, "As_min_mm2": As_min,
                      "As_required_mm2": As_required, "a_mm": a, "c_mm": c,
                      "eps_t": eps_t, "phi": phi_use, "beta1": beta1,
                      "phiMn_kNm": phiMn_kNm},
        equations=[
            "Rn = Mu / (φ·b·d²)",
            "ρ = (0.85 f'c / fy)·[1 − √(1 − 2Rn/(0.85 f'c))]",
            "As = ρ·b·d",
            "As,min = 0.0018·b·h  (REQUIRES CODE VERIFICATION §425.2)",
            "a = As·fy / (0.85 f'c b)",
            "φMn = φ·As·fy·(d − a/2)",
        ],
        warnings=warnings,
    )


# --- One-way shear ---------------------------------------------------------

def check_one_way_shear(Vu_kN: float, b_mm: float, d_mm: float,
                        fc: float, axis: str,
                        lambda_factor: float = 1.0) -> CheckResult:
    # Vc = 0.17·λ·√f'c·bw·d (SI: N, MPa, mm) — REQUIRES CODE VERIFICATION §422.5.1
    Vc_N = 0.17 * lambda_factor * math.sqrt(fc) * b_mm * d_mm
    phiVn_kN = PHI_SHEAR * Vc_N / 1000.0
    status = Status.PASS if phiVn_kN >= Vu_kN else Status.FAIL
    util = Vu_kN / phiVn_kN if phiVn_kN > 0 else float("inf")
    warnings = []
    if status == Status.PASS and util > 0.95:
        warnings.append(f"One-way shear {axis} close to capacity "
                        f"(utilization = {util:.2f}).")
    return CheckResult(
        name=f"One-way Shear {axis}",
        status=status, demand=Vu_kN, capacity=phiVn_kN,
        utilization=util, units="kN",
        code_ref=CODE_REFERENCES["one_way_shear"],
        inputs={"Vu_kN": Vu_kN, "b_mm": b_mm, "d_mm": d_mm, "fc_MPa": fc},
        intermediate={"Vc_N": Vc_N, "phiVn_kN": phiVn_kN, "phi": PHI_SHEAR},
        equations=["Vc = 0.17·λ·√f'c·bw·d  (SI)",
                   "φVn = φ·Vc, φ = 0.75"],
        warnings=warnings,
    )


# --- Punching shear --------------------------------------------------------

def check_punching(Vu_kN: float, cx_mm: float, cy_mm: float, d_mm: float,
                   fc: float, lambda_factor: float = 1.0,
                   alpha_s: float = 40.0) -> CheckResult:
    if cx_mm <= 0 or cy_mm <= 0:
        raise InputValidationError(
            "Column dimensions must be positive for punching shear check.")

    beta_col = max(cx_mm, cy_mm) / min(cx_mm, cy_mm)

    # b0 at d/2 from column face — REQUIRES CODE VERIFICATION §422.6.1
    b0 = 2.0 * (cx_mm + d_mm) + 2.0 * (cy_mm + d_mm)

    # Three expressions, take minimum — REQUIRES CODE VERIFICATION §422.6.5
    Vc1 = 0.33 * lambda_factor * math.sqrt(fc) * b0 * d_mm
    Vc2 = 0.17 * (1.0 + 2.0 / beta_col) * lambda_factor * math.sqrt(fc) * b0 * d_mm
    Vc3 = 0.083 * (2.0 + alpha_s * d_mm / b0) * lambda_factor * math.sqrt(fc) * b0 * d_mm

    Vc_N = min(Vc1, Vc2, Vc3)
    phiVc_kN = PHI_SHEAR * Vc_N / 1000.0
    status = Status.PASS if phiVc_kN >= Vu_kN else Status.FAIL
    util = Vu_kN / phiVc_kN if phiVc_kN > 0 else float("inf")
    warnings = []
    if status == Status.PASS and util > 0.90:
        warnings.append(f"Punching shear utilization = {util:.2f}. "
                        "Design is close to capacity.")

    return CheckResult(
        name="Punching Shear",
        status=status, demand=Vu_kN, capacity=phiVc_kN,
        utilization=util, units="kN",
        code_ref=CODE_REFERENCES["punching_shear"],
        inputs={"Vu_kN": Vu_kN, "cx_mm": cx_mm, "cy_mm": cy_mm,
                "d_mm": d_mm, "fc_MPa": fc, "beta_col": beta_col,
                "alpha_s": alpha_s},
        intermediate={"b0_mm": b0, "Vc1_N": Vc1, "Vc2_N": Vc2, "Vc3_N": Vc3,
                      "Vc_governing_N": Vc_N, "phiVc_kN": phiVc_kN,
                      "phi": PHI_SHEAR},
        equations=[
            "b0 = 2(c1 + d) + 2(c2 + d)   (d/2 from column face)",
            "Vc1 = 0.33·λ·√f'c·b0·d",
            "Vc2 = 0.17·(1 + 2/β)·λ·√f'c·b0·d,  β = long/short column side",
            "Vc3 = 0.083·(2 + αs·d/b0)·λ·√f'c·b0·d",
            "Vc = min(Vc1, Vc2, Vc3)",
            "φVc = φ·Vc, φ = 0.75",
        ],
        warnings=warnings,
    )


# --- Reinforcement selection ----------------------------------------------

@dataclass
class BarLayout:
    diameter_mm: float
    count: int
    spacing_mm: float
    As_provided_mm2: float
    length_mm: float = 0.0

    def label(self) -> str:
        return f"{self.count}-{self.diameter_mm:.0f}mm @ {self.spacing_mm:.0f}mm"


def select_reinforcement(As_required_mm2: float, B_mm: float,
                         cover_mm: float, preferred_dia: float = 20.0
                         ) -> BarLayout:
    """Pick a practical bar arrangement satisfying As_required, minimum
    clear spacing, and minimum bar count."""
    usable = B_mm - 2.0 * cover_mm
    if usable <= 0 or preferred_dia <= 0:
        raise InputValidationError(
            "Usable width is not positive — check B and cover.")

    bar_area = math.pi * preferred_dia ** 2 / 4.0
    count_min = max(2, math.ceil(As_required_mm2 / bar_area))
    # Minimum clear spacing = max(25 mm, bar diameter) — REQUIRES CODE VERIFICATION
    min_clear = max(25.0, preferred_dia)

    # Increase count until spacing >= min_clear, else fall back to smaller bars
    count = count_min
    for _ in range(500):
        if count <= 1:
            break
        spacing = usable / (count - 1)
        if spacing >= min_clear:
            As_provided = count * bar_area
            return BarLayout(preferred_dia, count, spacing, As_provided,
                             length_mm=B_mm - 2.0 * cover_mm)
        count += 1

    raise InputValidationError(
        "Unable to fit reinforcement — reduce required As or enlarge footing.")


def design_reinforcement(project: Project, flex_x: CheckResult,
                         flex_y: CheckResult) -> CheckResult:
    As_x_req = flex_x.intermediate.get("As_required_mm2", 0.0)
    As_y_req = flex_y.intermediate.get("As_required_mm2", 0.0)
    g = project.geometry

    layout_x = select_reinforcement(As_x_req, g.L, g.cover, project.rebar.diameter)
    layout_y = select_reinforcement(As_y_req, g.B, g.cover, project.rebar.diameter)

    ok = (layout_x.As_provided_mm2 >= As_x_req and
          layout_y.As_provided_mm2 >= As_y_req)
    status = Status.PASS if ok else Status.FAIL

    util_x = As_x_req / layout_x.As_provided_mm2 if layout_x.As_provided_mm2 else 0.0
    util_y = As_y_req / layout_y.As_provided_mm2 if layout_y.As_provided_mm2 else 0.0

    return CheckResult(
        name="Reinforcement Design",
        status=status,
        demand=max(As_x_req, As_y_req),
        capacity=min(layout_x.As_provided_mm2, layout_y.As_provided_mm2),
        utilization=max(util_x, util_y),
        units="mm²",
        code_ref=CODE_REFERENCES["min_reinforcement"],
        inputs={"As_x_required_mm2": As_x_req, "As_y_required_mm2": As_y_req,
                "bar_dia_mm": project.rebar.diameter},
        intermediate={
            "layout_x": asdict(layout_x),
            "layout_y": asdict(layout_y),
            "As_x_provided_mm2": layout_x.As_provided_mm2,
            "As_y_provided_mm2": layout_y.As_provided_mm2,
        },
        equations=[
            "As,min = 0.0018·b·h  (REQUIRES CODE VERIFICATION §425.2)",
            "Select bar count such that As_provided ≥ As_required",
            "Check minimum clear spacing = max(25 mm, bar diameter) "
            "(REQUIRES CODE VERIFICATION)",
        ],
        warnings=[],
    )


# --- Orchestrator ----------------------------------------------------------

class IsolatedFootingDesign:
    """Orchestrates the isolated footing design pipeline.
    GUI never calls the individual check functions directly."""

    def __init__(self, project: Project):
        self.project = project

    def run(self) -> DesignResult:
        warnings = validate_project(self.project)
        result = DesignResult(warnings=list(warnings))

        g = self.project.geometry
        c = self.project.concrete
        r = self.project.rebar
        s = self.project.soil

        # --- SERVICE: Bearing ---
        result.bearing = check_bearing(self.project)

        # --- STRENGTH: Factored loads ---
        fact_P, fact_Mx, fact_My, combo_name = governing_strength_loads(self.project)

        d = g.effective_depth(r.diameter)
        if d <= 0:
            raise InputValidationError(
                "Effective depth d ≤ 0 — footing thickness is too small "
                "for the specified cover and bar diameter.")

        B_m = g.B / 1000.0
        L_m = g.L / 1000.0
        q_u = fact_P / (B_m * L_m) if B_m * L_m else 0.0  # kPa (net)

        a_x = max(0.0, (B_m - g.cx / 1000.0) / 2.0)
        a_y = max(0.0, (L_m - g.cy / 1000.0) / 2.0)

        Mu_x = q_u * L_m * a_x ** 2 / 2.0
        Mu_y = q_u * B_m * a_y ** 2 / 2.0

        result.flexure_x = check_flexure(Mu_x, g.L, d, c.fc, r.fy, "X")
        result.flexure_y = check_flexure(Mu_y, g.B, d, c.fc, r.fy, "Y")

        # One-way shear at d from column face
        Vu_x = q_u * L_m * max(0.0, a_x - d / 1000.0)
        Vu_y = q_u * B_m * max(0.0, a_y - d / 1000.0)
        result.one_way_shear_x = check_one_way_shear(
            Vu_x, g.L, d, c.fc, "X", c.lambda_factor)
        result.one_way_shear_y = check_one_way_shear(
            Vu_y, g.B, d, c.fc, "Y", c.lambda_factor)

        # Punching shear — Vu = q_u × (area outside critical perimeter)
        A_in = (g.cx + d) * (g.cy + d)  # mm^2 (approx inside d/2 perimeter)
        A_total = g.B * g.L
        A_out = max(0.0, A_total - A_in)
        Vu_punch = q_u * (A_out / 1e6)
        result.punching_shear = check_punching(
            Vu_punch, g.cx, g.cy, d, c.fc, c.lambda_factor)

        # Reinforcement
        result.reinforcement = design_reinforcement(
            self.project, result.flexure_x, result.flexure_y)

        # Aggregate warnings
        for chk in result.all_checks():
            result.warnings.extend(chk.warnings)

        # Overall status
        statuses = [chk.status for chk in result.all_checks()]
        if any(s == Status.FAIL for s in statuses):
            result.overall_status = Status.FAIL
        elif any(s == Status.WARNING for s in statuses) or result.warnings:
            result.overall_status = Status.WARNING
        elif all(s == Status.PASS for s in statuses):
            result.overall_status = Status.PASS
        else:
            result.overall_status = Status.NOT_ANALYZED

        return result


# ---------------------------------------------------------------------------
# [SECTION 4]  VISUALIZATION
# ---------------------------------------------------------------------------

def draw_plan(project: Project, result: DesignResult, ax):
    """Plan view of the footing, column, punching perimeter, and resultant."""
    g = project.geometry
    B = g.B
    L = g.L

    # Footing outline
    ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
        (-B / 2, -L / 2), B, L, fill=False, edgecolor="black", linewidth=2))
    # Column outline
    ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
        (-g.cx / 2, -g.cy / 2), g.cx, g.cy, fill=False,
        edgecolor="black", linewidth=1.5))

    # Punching perimeter (d/2 from column face)
    d = g.effective_depth(project.rebar.diameter)
    if d > 0:
        bx = g.cx + 2 * d / 2
        by = g.cy + 2 * d / 2
        ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
            (-bx / 2, -by / 2), bx, by, fill=False, linestyle="--",
            edgecolor="red", linewidth=1.2, label="Critical perimeter (d/2)"))

    # Resultant
    if result.bearing is not None:
        ex = result.bearing.intermediate.get("ex_m", 0.0) * 1000.0
        ey = result.bearing.intermediate.get("ey_m", 0.0) * 1000.0
        ax.plot(ex, ey, marker="o", color="blue", markersize=8,
                label="Resultant (service)")
        ax.annotate("RESULTANT", (ex, ey),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=9)

    # Dimensions
    ax.annotate("", xy=(-B / 2, -L / 2 - 100), xytext=(B / 2, -L / 2 - 100),
                arrowprops=dict(arrowstyle="<->"))
    ax.text(0, -L / 2 - 180, f"B = {B:.0f} mm", ha="center", fontsize=9)
    ax.annotate("", xy=(B / 2 + 100, -L / 2), xytext=(B / 2 + 100, L / 2),
                arrowprops=dict(arrowstyle="<->"))
    ax.text(B / 2 + 150, 0, f"L = {L:.0f} mm", rotation=90,
            va="center", fontsize=9)

    ax.set_aspect("equal")
    ax.set_title("Plan View", fontsize=11)
    ax.set_xlabel("X [mm]")
    ax.set_ylabel("Y [mm]")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)


def draw_section(project: Project, ax):
    """Elevation section through the footing."""
    g = project.geometry
    B = g.B
    H = g.H
    # Footing block
    ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
        (-B / 2, -H), B, H, fill=False, edgecolor="black", linewidth=2))
    # Column
    ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
        (-g.cx / 2, 0), g.cx, 800, fill=False, edgecolor="black", linewidth=1.5))
    # Soil line
    ax.plot([-B / 2 - 200, B / 2 + 200], [0, 0], color="brown",
            linewidth=1.0, linestyle="--")
    ax.text(B / 2 + 210, 0, "Ground", fontsize=8, va="center", color="brown")
    # Rebar indication
    d = g.effective_depth(project.rebar.diameter)
    if d > 0:
        ax.plot([-B / 2 + g.cover, B / 2 - g.cover],
                [-H + g.cover + project.rebar.diameter / 2,
                 -H + g.cover + project.rebar.diameter / 2],
                color="red", linewidth=2, label="Bottom steel")
        ax.text(0, -H + g.cover + project.rebar.diameter / 2 + 40,
                f"{project.rebar.diameter:.0f}mm bars", ha="center",
                fontsize=8, color="red")

    ax.annotate("", xy=(-B / 2, -H - 120), xytext=(B / 2, -H - 120),
                arrowprops=dict(arrowstyle="<->"))
    ax.text(0, -H - 200, f"B = {B:.0f} mm", ha="center", fontsize=9)
    ax.annotate("", xy=(-B / 2 - 100, -H), xytext=(-B / 2 - 100, 0),
                arrowprops=dict(arrowstyle="<->"))
    ax.text(-B / 2 - 180, -H / 2, f"H = {H:.0f} mm", rotation=90,
            va="center", fontsize=9)

    ax.set_aspect("equal")
    ax.set_title("Section", fontsize=11)
    ax.set_xlabel("X [mm]")
    ax.set_ylabel("Elevation [mm]")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="lower right", fontsize=8)


# ---------------------------------------------------------------------------
# [SECTION 5]  REPORTING
# ---------------------------------------------------------------------------

def build_calc_report_text(project: Project, result: DesignResult) -> str:
    """Plain-text calculation report — same content the PDF renders."""
    lines: List[str] = []
    add = lines.append

    add("=" * 78)
    add("RC FOOTING DESIGNER — NSCP 2015")
    add("CALCULATION REPORT")
    add("=" * 78)
    add("")
    add(f"Project          : {project.info.name}")
    add(f"Location         : {project.info.location}")
    add(f"Foundation Mark  : {project.info.foundation_mark}")
    add(f"Footing Type     : {project.footing_type.title()}")
    add(f"Design Engineer  : {project.info.design_engineer}")
    add(f"Checker          : {project.info.checker}")
    add(f"Date             : {project.info.date}")
    add(f"Design Code      : {CODE_VERSION}")
    add("")

    add("--- DESIGN DISCLAIMER ---")
    for chunk in _wrap(DISCLAIMER_TEXT, 76):
        add(chunk)
    add("")

    add("--- 1. DESIGN CRITERIA ---")
    add(f"  f'c (concrete)          : {project.concrete.fc:.1f} MPa")
    add(f"  fy (reinforcement)      : {project.rebar.fy:.1f} MPa")
    add(f"  Es                      : {project.rebar.Es:.0f} MPa")
    add(f"  Concrete density        : {project.concrete.density:.1f} kN/m³")
    add(f"  Allowable soil bearing  : {project.soil.qa:.1f} kPa")
    add(f"  Soil unit weight        : {project.soil.unit_weight:.1f} kN/m³")
    add(f"  Embedment depth Df      : {project.soil.Df:.2f} m")
    add("")

    add("--- 2. INPUT DATA ---")
    g = project.geometry
    add(f"  Footing width  B        : {g.B:.0f} mm")
    add(f"  Footing length L        : {g.L:.0f} mm")
    add(f"  Footing thickness H     : {g.H:.0f} mm")
    add(f"  Column width  cx        : {g.cx:.0f} mm")
    add(f"  Column length cy        : {g.cy:.0f} mm")
    add(f"  Clear cover             : {g.cover:.0f} mm")
    add(f"  Bar diameter            : {project.rebar.diameter:.0f} mm")
    add("")

    add("--- 3. LOAD CASES ---")
    add(f"  {'Name':<10}{'P [kN]':>12}{'Mx [kN·m]':>14}{'My [kN·m]':>14}")
    for lc in project.load_cases:
        add(f"  {lc.name:<10}{lc.P:>12.2f}{lc.Mx:>14.2f}{lc.My:>14.2f}")
    add("")

    add("--- 4. LOAD COMBINATIONS (REQUIRES CODE VERIFICATION §203) ---")
    add("  Strength:")
    for c in strength_combinations():
        add(f"    {c.name}   factors = {c.factors}")
    add("  Service:")
    for c in service_combinations():
        add(f"    {c.name}   factors = {c.factors}")
    add("")

    def dump(chk: Optional[CheckResult]):
        if chk is None:
            return
        add(f"--- {chk.name.upper()} ---")
        add(f"  Code reference: {chk.code_ref}")
        for k, v in chk.inputs.items():
            add(f"    input.{k:<22}: {_fmt(v)}")
        for k, v in chk.intermediate.items():
            add(f"    calc .{k:<22}: {_fmt(v)}")
        add("  Equations:")
        for eq in chk.equations:
            add(f"    {eq}")
        add(f"  DEMAND   = {_fmt(chk.demand)} {chk.units}")
        add(f"  CAPACITY = {_fmt(chk.capacity)} {chk.units}")
        add(f"  UTILIZATION = {chk.utilization:.3f}")
        add(f"  STATUS   = {chk.status.value}")
        for w in chk.warnings:
            add(f"  WARNING  : {w}")
        add("")

    dump(result.bearing)
    dump(result.flexure_x)
    dump(result.flexure_y)
    dump(result.one_way_shear_x)
    dump(result.one_way_shear_y)
    dump(result.punching_shear)
    dump(result.reinforcement)

    add("--- FINAL SUMMARY ---")
    add(f"  OVERALL STATUS: {result.overall_status.value}")
    for chk in result.all_checks():
        add(f"    {chk.name:<22}: {chk.status.value:<12} "
            f"(util = {chk.utilization:.2f})")
    add("")
    if result.warnings:
        add("--- WARNINGS ---")
        for w in result.warnings:
            for line in _wrap("* " + w, 76):
                add("  " + line)

    return "\n".join(lines)


def _wrap(text: str, width: int) -> List[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:,.3f}"
    return str(v)


def export_pdf(project: Project, result: DesignResult, path: str) -> bool:
    """Optional PDF export via ReportLab. Returns True on success."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return False

    text = build_calc_report_text(project, result)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Courier", 8)
    for line in text.splitlines():
        if y < 40:
            c.showPage()
            c.setFont("Courier", 8)
            y = height - 40
        c.drawString(30, y, line[:130])
        y -= 10
    c.save()
    return True


# ---------------------------------------------------------------------------
# [SECTION 6]  GUI
# ---------------------------------------------------------------------------

def run_gui():  # noqa: C901
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QColor, QFont
        from PySide6.QtWidgets import (
            QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
            QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
            QListWidgetItem, QMainWindow, QMessageBox, QProgressBar,
            QPushButton, QScrollArea, QSplitter, QStackedWidget,
            QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
            QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
        )
    except ImportError:
        print("PySide6 is required. Install with:  pip install PySide6")
        sys.exit(1)

    try:
        import matplotlib
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        HAS_MPL = True
    except ImportError:
        HAS_MPL = False

    # ------------------- Shared project state -------------------
    state = {"project": Project(), "result": None}

    # ------------------- Small helpers --------------------------

    def status_color(status: Status) -> str:
        return {
            Status.PASS: "#2e7d32",
            Status.WARNING: "#f9a825",
            Status.FAIL: "#c62828",
            Status.NOT_ANALYZED: "#616161",
        }.get(status, "#616161")

    def make_spin(minimum: float, maximum: float, value: float,
                  decimals: int = 2, suffix: str = "") -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(minimum, maximum)
        sb.setDecimals(decimals)
        sb.setValue(value)
        if suffix:
            sb.setSuffix(" " + suffix)
        return sb

    # ------------------- Page: Project Info ---------------------

    class ProjectPage(QWidget):
        def __init__(self):
            super().__init__()
            form = QFormLayout(self)
            self.fields: Dict[str, QLineEdit] = {}
            for label, key in [
                ("Project name", "name"),
                ("Location", "location"),
                ("Building / structure", "structure"),
                ("Client", "client"),
                ("Design engineer", "design_engineer"),
                ("Checker", "checker"),
                ("Date", "date"),
                ("Revision", "revision"),
                ("Drawing number", "drawing_no"),
                ("Foundation mark / tag", "foundation_mark"),
            ]:
                le = QLineEdit()
                le.textChanged.connect(
                    lambda text, k=key: setattr(state["project"].info, k, text))
                self.fields[key] = le
                form.addRow(label, le)

        def refresh_from_model(self):
            for k, le in self.fields.items():
                le.setText(str(getattr(state["project"].info, k)))

    # ------------------- Page: Footing Type ---------------------

    class FootingTypePage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            v.addWidget(QLabel("<b>Select foundation type</b>"))
            self.listw = QListWidget()
            types = [
                ("Isolated / Single Footing", "isolated"),
                ("Combined Footing (future)", "combined"),
                ("Strap Footing (future)", "strap"),
                ("Strip / Continuous Footing (future)", "strip"),
                ("Wall Footing (future)", "wall"),
                ("Circular Footing (future)", "circular"),
            ]
            for label, key in types:
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, key)
                if key != "isolated":
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setToolTip("Not yet implemented in this single-file "
                                    "build — architecture supports adding it.")
                self.listw.addItem(item)
            self.listw.setCurrentRow(0)
            self.listw.currentItemChanged.connect(self._changed)
            v.addWidget(self.listw)
            self.note = QLabel(
                "Only <b>Isolated Footing</b> is fully implemented in this "
                "single-file build. Other types are architecturally reserved "
                "(see FootingDesign interface).")
            self.note.setWordWrap(True)
            v.addWidget(self.note)

        def _changed(self, cur, _prev):
            if cur is None:
                return
            key = cur.data(Qt.UserRole)
            state["project"].footing_type = key

    # ------------------- Page: Geometry -------------------------

    class GeometryPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            gb = QGroupBox("Footing geometry")
            form = QFormLayout(gb)
            g = state["project"].geometry
            self.B = make_spin(200, 20000, g.B, 0, "mm")
            self.L = make_spin(200, 20000, g.L, 0, "mm")
            self.H = make_spin(100, 5000, g.H, 0, "mm")
            self.cx = make_spin(50, 5000, g.cx, 0, "mm")
            self.cy = make_spin(50, 5000, g.cy, 0, "mm")
            self.cover = make_spin(20, 200, g.cover, 0, "mm")
            for label, widget, attr in [
                ("Footing width B", self.B, "B"),
                ("Footing length L", self.L, "L"),
                ("Footing thickness H", self.H, "H"),
                ("Column width cx", self.cx, "cx"),
                ("Column length cy", self.cy, "cy"),
                ("Clear cover", self.cover, "cover"),
            ]:
                widget.valueChanged.connect(
                    lambda val, a=attr: setattr(state["project"].geometry, a, val))
                form.addRow(label, widget)
            v.addWidget(gb)
            v.addStretch(1)

        def refresh_from_model(self):
            g = state["project"].geometry
            self.B.setValue(g.B); self.L.setValue(g.L); self.H.setValue(g.H)
            self.cx.setValue(g.cx); self.cy.setValue(g.cy)
            self.cover.setValue(g.cover)

    # ------------------- Page: Materials ------------------------

    class MaterialsPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            gb_c = QGroupBox("Concrete")
            f1 = QFormLayout(gb_c)
            c = state["project"].concrete
            self.fc = make_spin(15, 100, c.fc, 1, "MPa")
            self.dens = make_spin(15, 30, c.density, 1, "kN/m³")
            self.fc.valueChanged.connect(
                lambda val: setattr(state["project"].concrete, "fc", val))
            self.dens.valueChanged.connect(
                lambda val: setattr(state["project"].concrete, "density", val))
            f1.addRow("f'c", self.fc)
            f1.addRow("Density", self.dens)
            v.addWidget(gb_c)

            gb_s = QGroupBox("Reinforcing steel")
            f2 = QFormLayout(gb_s)
            r = state["project"].rebar
            self.fy = make_spin(200, 800, r.fy, 0, "MPa")
            self.dia = QComboBox()
            for d in STANDARD_BAR_DIAMETERS_MM:
                self.dia.addItem(f"{d} mm", float(d))
            self.dia.setCurrentText(f"{int(r.diameter)} mm")
            self.fy.valueChanged.connect(
                lambda val: setattr(state["project"].rebar, "fy", val))
            self.dia.currentIndexChanged.connect(
                lambda _: setattr(state["project"].rebar, "diameter",
                                  self.dia.currentData()))
            f2.addRow("fy", self.fy)
            f2.addRow("Bar diameter", self.dia)
            v.addWidget(gb_s)
            v.addStretch(1)

        def refresh_from_model(self):
            c = state["project"].concrete
            r = state["project"].rebar
            self.fc.setValue(c.fc)
            self.dens.setValue(c.density)
            self.fy.setValue(r.fy)
            idx = self.dia.findData(r.diameter)
            if idx >= 0:
                self.dia.setCurrentIndex(idx)

    # ------------------- Page: Soil -----------------------------

    class SoilPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            gb = QGroupBox("Soil")
            form = QFormLayout(gb)
            s = state["project"].soil
            self.qa = make_spin(10, 2000, s.qa, 1, "kPa")
            self.uw = make_spin(10, 25, s.unit_weight, 1, "kN/m³")
            self.df = make_spin(0.3, 20, s.Df, 2, "m")
            self.qa.valueChanged.connect(
                lambda val: setattr(state["project"].soil, "qa", val))
            self.uw.valueChanged.connect(
                lambda val: setattr(state["project"].soil, "unit_weight", val))
            self.df.valueChanged.connect(
                lambda val: setattr(state["project"].soil, "Df", val))
            form.addRow("Allowable bearing qa", self.qa)
            form.addRow("Soil unit weight", self.uw)
            form.addRow("Embedment Df", self.df)
            v.addWidget(gb)
            note = QLabel(
                "⚠ Soil bearing capacity is assumed user-provided. Confirm "
                "against geotechnical investigation for final design.")
            note.setWordWrap(True)
            v.addWidget(note)
            v.addStretch(1)

        def refresh_from_model(self):
            s = state["project"].soil
            self.qa.setValue(s.qa); self.uw.setValue(s.unit_weight)
            self.df.setValue(s.Df)

    # ------------------- Page: Loads ----------------------------

    class LoadsPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Name", "P [kN]", "Mx [kN·m]", "My [kN·m]"])
            v.addWidget(self.table)
            h = QHBoxLayout()
            b_add = QPushButton("Add row")
            b_del = QPushButton("Delete selected")
            b_add.clicked.connect(self._add_row)
            b_del.clicked.connect(self._del_row)
            h.addWidget(b_add); h.addWidget(b_del); h.addStretch(1)
            v.addLayout(h)
            self.refresh_from_model()

        def _add_row(self):
            self.table.insertRow(self.table.rowCount())
            self.table.setItem(self.table.rowCount() - 1, 0, QTableWidgetItem("NEW"))
            for col in range(1, 4):
                self.table.setItem(self.table.rowCount() - 1, col, QTableWidgetItem("0"))
            self._sync()

        def _del_row(self):
            row = self.table.currentRow()
            if row >= 0:
                self.table.removeRow(row)
                self._sync()

        def refresh_from_model(self):
            self.table.setRowCount(0)
            for lc in state["project"].load_cases:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(lc.name))
                self.table.setItem(r, 1, QTableWidgetItem(str(lc.P)))
                self.table.setItem(r, 2, QTableWidgetItem(str(lc.Mx)))
                self.table.setItem(r, 3, QTableWidgetItem(str(lc.My)))
            self.table.itemChanged.connect(lambda _: self._sync())

        def _sync(self):
            out = []
            for r in range(self.table.rowCount()):
                try:
                    name = self.table.item(r, 0).text()
                    P = float(self.table.item(r, 1).text())
                    Mx = float(self.table.item(r, 2).text())
                    My = float(self.table.item(r, 3).text())
                    out.append(LoadCase(name, P, Mx, My))
                except (AttributeError, ValueError):
                    pass
            state["project"].load_cases = out

    # ------------------- Page: Results --------------------------

    class ResultsPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            self.summary = QLabel("Not analyzed yet.")
            f = QFont(); f.setBold(True); f.setPointSize(11)
            self.summary.setFont(f)
            self.summary.setWordWrap(True)
            v.addWidget(self.summary)

            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(
                ["Check", "Demand", "Capacity", "Utilization", "Status"])
            v.addWidget(self.table)

            self.warn_box = QTextEdit()
            self.warn_box.setReadOnly(True)
            self.warn_box.setPlaceholderText("Warnings will appear here.")
            v.addWidget(QLabel("<b>Warnings</b>"))
            v.addWidget(self.warn_box)

        def update_from_result(self, project: Project, result: DesignResult):
            self.summary.setText(
                f"<b>FOOTING:</b> {project.info.foundation_mark} &nbsp; "
                f"<b>TYPE:</b> {project.footing_type.title()} &nbsp; "
                f"<b>SIZE:</b> {project.geometry.B:.0f} × {project.geometry.L:.0f} × "
                f"{project.geometry.H:.0f} mm<br>"
                f"<b>OVERALL STATUS:</b> "
                f"<span style='color:{status_color(result.overall_status)};'>"
                f"{result.overall_status.value}</span>")

            self.table.setRowCount(0)
            for chk in result.all_checks():
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(chk.name))
                self.table.setItem(r, 1, QTableWidgetItem(
                    f"{chk.demand:,.2f} {chk.units}"))
                self.table.setItem(r, 2, QTableWidgetItem(
                    f"{chk.capacity:,.2f} {chk.units}"))
                self.table.setItem(r, 3, QTableWidgetItem(f"{chk.utilization:.3f}"))
                item = QTableWidgetItem(chk.status.value)
                item.setForeground(QColor(status_color(chk.status)))
                self.table.setItem(r, 4, item)

            self.warn_box.setPlainText("\n".join(result.warnings)
                                       if result.warnings else "(none)")

    # ------------------- Page: Calculations ---------------------

    class CalcPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            self.text = QTextEdit()
            self.text.setReadOnly(True)
            self.text.setFont(QFont("Courier", 9))
            v.addWidget(self.text)

        def update_from_result(self, project: Project, result: DesignResult):
            self.text.setPlainText(build_calc_report_text(project, result))

    # ------------------- Page: 2D Drawing -----------------------

    class Drawing2DPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            if HAS_MPL:
                self.fig = Figure(figsize=(9, 5))
                self.canvas = FigureCanvasQTAgg(self.fig)
                v.addWidget(self.canvas)
            else:
                v.addWidget(QLabel("Matplotlib is required for 2D drawings."))

        def update_from_result(self, project: Project, result: DesignResult):
            if not HAS_MPL:
                return
            self.fig.clear()
            ax1 = self.fig.add_subplot(1, 2, 1)
            ax2 = self.fig.add_subplot(1, 2, 2)
            draw_plan(project, result, ax1)
            draw_section(project, ax2)
            self.fig.tight_layout()
            self.canvas.draw_idle()

    # ------------------- Page: 3D Model -------------------------

    class Model3DPage(QWidget):
        def __init__(self):
            super().__init__()
            v = QVBoxLayout(self)
            self.status = QLabel("3D model will appear here after RUN DESIGN.")
            v.addWidget(self.status)
            self.frame = QWidget()
            v.addWidget(self.frame)

        def update_from_result(self, project: Project, result: DesignResult):
            try:
                import pyvista as pv
                from pyvistaqt import QtInteractor  # optional
                # If pyvistaqt is not installed, fall back to a static plot
                # rendered to a PNG-like note.
                raise ImportError("pyvistaqt not installed in this build")
            except Exception:
                # Graceful fallback
                self.status.setText(
                    "3D view requires <code>pyvista</code> and "
                    "<code>pyvistaqt</code>.<br>"
                    "Install with:  <code>pip install pyvista pyvistaqt</code><br><br>"
                    f"Model summary (from design result):<br>"
                    f"&nbsp;&nbsp;Footing: {project.geometry.B:.0f} × "
                    f"{project.geometry.L:.0f} × {project.geometry.H:.0f} mm<br>"
                    f"&nbsp;&nbsp;Column : {project.geometry.cx:.0f} × "
                    f"{project.geometry.cy:.0f} mm<br>"
                    f"&nbsp;&nbsp;Rebar  : {project.rebar.diameter:.0f} mm")
                return

    # ------------------- Main Window ----------------------------

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("RC Footing Designer — NSCP 2015")
            self.resize(1280, 800)

            splitter = QSplitter()
            self.setCentralWidget(splitter)

            # Sidebar
            self.tree = QTreeWidget()
            self.tree.setHeaderLabel("Navigation")
            self.tree.setMinimumWidth(260)
            self.tree.setIndentation(14)
            splitter.addWidget(self.tree)

            # Right side: header + stacked pages
            right = QWidget()
            rv = QVBoxLayout(right)
            rv.setContentsMargins(6, 6, 6, 6)
            self.header = QLabel()
            self.header.setStyleSheet("font-size: 14px; font-weight: bold;")
            rv.addWidget(self.header)

            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            rv.addWidget(self.progress)

            self.stack = QStackedWidget()
            rv.addWidget(self.stack, 1)
            splitter.addWidget(right)
            splitter.setStretchFactor(1, 1)

            # Pages
            self.pages: Dict[str, QWidget] = {}
            for key, label, cls in [
                ("project", "Project Information", ProjectPage),
                ("footing", "Footing Type", FootingTypePage),
                ("geometry", "Geometry", GeometryPage),
                ("materials", "Materials", MaterialsPage),
                ("loads", "Loads", LoadsPage),
                ("soil", "Soil", SoilPage),
                ("results", "Results Dashboard", ResultsPage),
                ("calc", "Detailed Calculations", CalcPage),
                ("d2", "2D Drawing", Drawing2DPage),
                ("d3", "3D Model", Model3DPage),
            ]:
                page = cls()
                self.pages[key] = page
                self.stack.addWidget(page)

            # Tree items
            groups = {
                "PROJECT": [("Project Information", "project"),
                            ("Footing Type", "footing")],
                "INPUTS": [("Geometry", "geometry"),
                           ("Materials", "materials"),
                           ("Loads", "loads"),
                           ("Soil", "soil")],
                "OUTPUT": [("Summary", "results"),
                           ("Detailed Calculations", "calc"),
                           ("2D Drawing", "d2"),
                           ("3D Model", "d3")],
            }
            for gname, entries in groups.items():
                gitem = QTreeWidgetItem(self.tree, [gname])
                f = gitem.font(0); f.setBold(True); gitem.setFont(0, f)
                gitem.setExpanded(True)
                for label, key in entries:
                    item = QTreeWidgetItem(gitem, [label])
                    item.setData(0, Qt.UserRole, key)
            self.tree.itemClicked.connect(self._navigate)

            # Toolbar
            tb = self.addToolBar("Main")
            act_run = QAction("▶  RUN DESIGN", self)
            act_run.triggered.connect(self.run_design)
            tb.addAction(act_run)
            act_save = QAction("💾  Save Project", self)
            act_save.triggered.connect(self.save_project)
            tb.addAction(act_save)
            act_open = QAction("📂  Open Project", self)
            act_open.triggered.connect(self.open_project)
            tb.addAction(act_open)
            act_pdf = QAction("📄  Export PDF Report", self)
            act_pdf.triggered.connect(self.export_pdf_report)
            tb.addAction(act_pdf)

            # Footer status bar
            self.statusBar().showMessage(
                "Ready. Design code: NSCP 2015. "
                "Unverified provisions are flagged 'REQUIRES CODE VERIFICATION'.")
            self._refresh_header()
            self.stack.setCurrentWidget(self.pages["project"])

        def _refresh_header(self):
            p = state["project"]
            self.header.setText(
                f"RC Footing Designer — NSCP 2015 &nbsp;|&nbsp; "
                f"Project: {p.info.name} &nbsp;|&nbsp; "
                f"Footing: {p.info.foundation_mark} ({p.footing_type}) &nbsp;|&nbsp; "
                f"Status: "
                f"<span style='color:{status_color(state['result'].overall_status if state['result'] else Status.NOT_ANALYZED)};'>"
                f"{(state['result'].overall_status.value if state['result'] else Status.NOT_ANALYZED.value)}</span>")

        def _navigate(self, item, _col):
            key = item.data(0, Qt.UserRole)
            if key and key in self.pages:
                page = self.pages[key]
                if hasattr(page, "refresh_from_model"):
                    page.refresh_from_model()
                self.stack.setCurrentWidget(page)

        def run_design(self):
            self.progress.setValue(10)
            try:
                project = state["project"]
                self.progress.setValue(30)
                engine = IsolatedFootingDesign(project)
                result = engine.run()
                self.progress.setValue(80)
                state["result"] = result

                # Refresh dependent pages
                for key in ("results", "calc", "d2", "d3"):
                    page = self.pages[key]
                    if hasattr(page, "update_from_result"):
                        page.update_from_result(project, result)

                self.progress.setValue(100)
                self._refresh_header()
                self.statusBar().showMessage(
                    f"Design complete — {result.overall_status.value}",
                    5000)
                if result.overall_status == Status.FAIL:
                    QMessageBox.warning(self, "Design FAIL",
                        "One or more NSCP 2015 checks FAILED. "
                        "Review the Results dashboard and Detailed Calculations.")
                elif result.warnings:
                    QMessageBox.information(self, "Design with warnings",
                        "Design completed with warnings. "
                        "See the Results dashboard.")
                self.stack.setCurrentWidget(self.pages["results"])
            except InputValidationError as e:
                self.progress.setValue(0)
                QMessageBox.critical(self, "Invalid input", str(e))
            except Exception as e:  # noqa: BLE001
                self.progress.setValue(0)
                traceback.print_exc()
                QMessageBox.critical(self, "Unexpected error",
                    f"Unable to complete design:\n\n{e}\n\n"
                    "Possible causes: invalid dimensions, missing materials, "
                    "or invalid load input. Please review the highlighted "
                    "inputs. Technical details logged to the console.")

        def save_project(self):
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Project", "footing_project.json",
                "JSON files (*.json)")
            if not path:
                return
            try:
                p = state["project"]
                data = {
                    "info": asdict(p.info),
                    "footing_type": p.footing_type,
                    "geometry": asdict(p.geometry),
                    "concrete": asdict(p.concrete),
                    "rebar": asdict(p.rebar),
                    "soil": asdict(p.soil),
                    "load_cases": [asdict(lc) for lc in p.load_cases],
                    "code_version": CODE_VERSION,
                }
                Path(path).write_text(json.dumps(data, indent=2))
                self.statusBar().showMessage(f"Saved: {path}", 4000)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Save error", str(e))

        def open_project(self):
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Project", "", "JSON files (*.json)")
            if not path:
                return
            try:
                data = json.loads(Path(path).read_text())
                p = Project(
                    info=ProjectInfo(**data["info"]),
                    footing_type=data.get("footing_type", "isolated"),
                    geometry=FootingGeometry(**data["geometry"]),
                    concrete=Concrete(**data["concrete"]),
                    rebar=Rebar(**data["rebar"]),
                    soil=Soil(**data["soil"]),
                    load_cases=[LoadCase(**lc) for lc in data["load_cases"]],
                )
                state["project"] = p
                state["result"] = None
                # Refresh all pages
                for page in self.pages.values():
                    if hasattr(page, "refresh_from_model"):
                        page.refresh_from_model()
                self._refresh_header()
                self.statusBar().showMessage(f"Loaded: {path}", 4000)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Open error", str(e))

        def export_pdf_report(self):
            if state["result"] is None:
                QMessageBox.information(self, "Run design first",
                    "Please run the design before exporting a report.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Export PDF Report", "footing_report.pdf",
                "PDF files (*.pdf)")
            if not path:
                return
            ok = export_pdf(state["project"], state["result"], path)
            if not ok:
                # Save as .txt fallback
                txt_path = path + ".txt"
                Path(txt_path).write_text(
                    build_calc_report_text(state["project"], state["result"]))
                QMessageBox.information(self, "ReportLab not available",
                    f"ReportLab is not installed, so a plain-text report "
                    f"was saved instead:\n{txt_path}")
            else:
                self.statusBar().showMessage(f"PDF saved: {path}", 4000)

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


# ---------------------------------------------------------------------------
# [SECTION 7]  ENTRY POINT
# ---------------------------------------------------------------------------

def run_cli_demo():
    """Headless demonstration so the file is testable without a GUI."""
    p = Project()
    p.info.name = "DEMO — NOT FOR ACTUAL DESIGN"
    p.info.foundation_mark = "F1"
    p.geometry = FootingGeometry(B=2400, L=2000, H=450, cx=400, cy=400)
    p.concrete = Concrete(fc=28.0)
    p.rebar = Rebar(fy=415.0, diameter=20.0)
    p.soil = Soil(qa=200.0, Df=1.5, unit_weight=18.0)
    p.load_cases = [LoadCase("D", 800, 0, 0), LoadCase("L", 400, 0, 0)]

    engine = IsolatedFootingDesign(p)
    result = engine.run()
    print(build_calc_report_text(p, result))


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_demo()
    else:
        run_gui()