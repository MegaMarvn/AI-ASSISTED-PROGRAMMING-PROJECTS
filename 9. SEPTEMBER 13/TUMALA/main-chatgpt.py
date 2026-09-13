"""
BEAM REINFORCEMENT DESIGN GUI
--------------------------------
Purpose:
    Preliminary flexural reinforcement calculation for a singly reinforced
    rectangular reinforced-concrete beam.

Units:
    Geometry: mm
    Concrete/rebar strength: MPa
    Loads/moments: kN, kN-m
    Reinforcement area: mm^2

IMPORTANT:
    This is an educational/preliminary design tool. It is NOT a complete
    NSCP 2015/ACI 318 beam-design program. Final design should also check
    shear, development length, bar spacing, deflection, crack control,
    seismic/detailing requirements, torsion, load combinations, and all
    applicable code provisions.

Core flexural model:
    Mn = As * fy * (d - a/2)
    a  = As * fy / (0.85 * f'c * b)

For a singly reinforced rectangular section:
    phi*Mn >= Mu

The GUI also calculates:
    - effective depth d
    - required nominal moment Mn
    - required tensile steel As
    - minimum beam reinforcement
    - maximum practical steel based on a simplified strain criterion
    - selected bar size and number
    - provided steel area
    - reinforcement ratio
    - approximate capacity phi*Mn
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox


# ---------------------------------------------------------------------------
# BAR DATABASE
# Areas are approximate nominal areas in mm^2.
# Add/change bars here if your project uses another standard.
# ---------------------------------------------------------------------------
BAR_AREA = {
    "10 mm": 78.5,
    "12 mm": 113.1,
    "16 mm": 201.1,
    "20 mm": 314.2,
    "25 mm": 490.9,
    "28 mm": 615.8,
    "32 mm": 804.2,
    "36 mm": 1017.9,
}


def solve_quadratic(a, b, c):
    """Return the positive root of a*x^2 + b*x + c = 0."""
    disc = b * b - 4 * a * c
    if disc < 0:
        raise ValueError("No real solution for the required steel area.")
    roots = [
        (-b + math.sqrt(disc)) / (2 * a),
        (-b - math.sqrt(disc)) / (2 * a),
    ]
    positive = [x for x in roots if x > 0]
    if not positive:
        raise ValueError("No positive solution for the required steel area.")
    return min(positive)


def calculate_beam(b, h, fc, fy, Mu, cover, stirrup_dia, bar_dia,
                   phi=0.90):
    """
    Perform a simplified flexural design.

    Parameters:
        b, h          = beam width and overall depth, mm
        fc            = concrete compressive strength, MPa
        fy            = reinforcing steel yield strength, MPa
        Mu            = factored bending moment, kN-m
        cover         = clear concrete cover, mm
        stirrup_dia   = stirrup diameter, mm
        bar_dia       = trial longitudinal bar diameter, mm
        phi           = flexural strength reduction factor

    Returns:
        Dictionary containing calculated design values.
    """

    # Effective depth measured approximately from compression face
    # to centroid of tensile reinforcement.
    d = h - cover - stirrup_dia - bar_dia / 2

    if d <= 0:
        raise ValueError("Effective depth d must be positive.")

    # Convert Mu from kN-m to N-mm.
    Mu_Nmm = Mu * 1_000_000

    # Required nominal moment.
    Mn_req = Mu_Nmm / phi

    # -----------------------------------------------------------------------
    # Solve:
    #
    # Mn = As*fy*(d - a/2)
    # a  = As*fy/(0.85*fc*b)
    #
    # This becomes:
    # Mn = As*fy*d - As^2*fy^2/(2*0.85*fc*b)
    #
    # Rearranged as:
    # A*As^2 + B*As + C = 0
    # -----------------------------------------------------------------------
    A = fy**2 / (2 * 0.85 * fc * b)
    B = -fy * d
    C = Mn_req

    As_req = solve_quadratic(A, B, C)

    # -----------------------------------------------------------------------
    # Simplified minimum reinforcement check.
    #
    # For SI units, the commonly used ACI-style expression is:
    # As,min = max(0.25*sqrt(fc')/fy * b*d,
    #              1.4/fy * b*d)
    #
    # This should be checked against the exact governing code edition and
    # member conditions before final use.
    # -----------------------------------------------------------------------
    As_min_1 = 0.25 * math.sqrt(fc) / fy * b * d
    As_min_2 = 1.40 / fy * b * d
    As_min = max(As_min_1, As_min_2)

    As_design = max(As_req, As_min)

    # -----------------------------------------------------------------------
    # Simplified maximum reinforcement based on a tension-controlled strain
    # limit using beta1 and epsilon_t = 0.005.
    #
    # This is included as an informational check, not as a substitute for
    # the complete code strain classification provisions.
    # -----------------------------------------------------------------------
    beta1 = max(0.65, min(0.85, 0.85 - 0.05 * max(fc - 28, 0) / 7))
    beta1 = max(0.65, beta1)

    epsilon_cu = 0.003
    epsilon_t_limit = 0.005

    # c = epsilon_cu/(epsilon_cu+epsilon_t) * d
    c_limit = epsilon_cu / (epsilon_cu + epsilon_t_limit) * d
    a_limit = beta1 * c_limit

    As_max_simplified = 0.85 * fc * b * a_limit / fy

    # Check that selected steel will be enough.
    # Number of bars is rounded UP.
    n_bars = math.ceil(As_design / BAR_AREA[f"{bar_dia:g} mm"])
    As_provided = n_bars * BAR_AREA[f"{bar_dia:g} mm"]

    # Actual compression block and nominal moment using provided steel.
    a_provided = As_provided * fy / (0.85 * fc * b)
    Mn_provided = As_provided * fy * (d - a_provided / 2)
    phi_Mn = phi * Mn_provided / 1_000_000  # kN-m

    rho = As_provided / (b * d)

    return {
        "d": d,
        "Mn_req": Mn_req / 1_000_000,
        "As_req": As_req,
        "As_min": As_min,
        "As_design": As_design,
        "As_max_simplified": As_max_simplified,
        "beta1": beta1,
        "n_bars": n_bars,
        "As_provided": As_provided,
        "a_provided": a_provided,
        "phi_Mn": phi_Mn,
        "rho": rho,
        "adequate": phi_Mn >= Mu,
    }


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class BeamDesignGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RC Beam Reinforcement Calculator")
        self.root.geometry("820x720")
        self.root.minsize(760, 650)

        # Main frame
        main = ttk.Frame(root, padding=15)
        main.pack(fill="both", expand=True)

        title = ttk.Label(
            main,
            text="RC BEAM FLEXURAL REINFORCEMENT CALCULATOR",
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=(0, 5))

        subtitle = ttk.Label(
            main,
            text="Simplified singly reinforced rectangular beam design",
            font=("Segoe UI", 10)
        )
        subtitle.pack(pady=(0, 15))

        # -------------------- INPUT SECTION -------------------------------
        input_frame = ttk.LabelFrame(main, text="Design Inputs", padding=12)
        input_frame.pack(fill="x")

        self.entries = {}

        inputs = [
            ("Beam width, b (mm)", "300"),
            ("Overall depth, h (mm)", "500"),
            ("Concrete strength, f'c (MPa)", "21"),
            ("Steel yield strength, fy (MPa)", "415"),
            ("Factored moment, Mu (kN-m)", "150"),
            ("Clear cover (mm)", "40"),
            ("Stirrup diameter (mm)", "10"),
            ("Trial main bar diameter (mm)", "20"),
        ]

        for row, (label, default) in enumerate(inputs):
            ttk.Label(input_frame, text=label).grid(
                row=row, column=0, sticky="w", padx=5, pady=4
            )

            entry = ttk.Entry(input_frame, width=18)
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=4)

            self.entries[label] = entry

        # -------------------- BUTTONS ------------------------------------
        button_frame = ttk.Frame(main)
        button_frame.pack(fill="x", pady=12)

        ttk.Button(
            button_frame,
            text="CALCULATE",
            command=self.calculate
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_frame,
            text="CLEAR",
            command=self.clear
        ).pack(side="left", padx=8)

        ttk.Button(
            button_frame,
            text="LOAD EXAMPLE",
            command=self.load_example
        ).pack(side="left", padx=8)

        # -------------------- OUTPUT SECTION ------------------------------
        output_frame = ttk.LabelFrame(main, text="Calculation Results", padding=12)
        output_frame.pack(fill="both", expand=True)

        self.output = tk.Text(
            output_frame,
            height=22,
            width=90,
            wrap="word",
            font=("Consolas", 10)
        )
        self.output.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=scrollbar.set)

        self.show_welcome()

    def show_welcome(self):
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Enter the beam data, then click CALCULATE.\n\n")
        self.output.insert(
            tk.END,
            "The program calculates required flexural steel and proposes "
            "a number of identical longitudinal bars based on the selected "
            "trial bar diameter.\n\n"
        )
        self.output.insert(
            tk.END,
            "NOTE: This is a preliminary calculation tool. Verify all "
            "requirements using the governing NSCP/ACI provisions."
        )

    def get_float(self, label):
        try:
            value = float(self.entries[label].get())
        except ValueError:
            raise ValueError(f"Invalid number: {label}")
        if value <= 0:
            raise ValueError(f"{label} must be greater than zero.")
        return value

    def calculate(self):
        try:
            b = self.get_float("Beam width, b (mm)")
            h = self.get_float("Overall depth, h (mm)")
            fc = self.get_float("Concrete strength, f'c (MPa)")
            fy = self.get_float("Steel yield strength, fy (MPa)")
            Mu = self.get_float("Factored moment, Mu (kN-m)")
            cover = self.get_float("Clear cover (mm)")
            stirrup = self.get_float("Stirrup diameter (mm)")
            bar = self.get_float("Trial main bar diameter (mm)")

            # Make sure the trial bar exists in our database.
            bar_key = f"{bar:g} mm"
            if bar_key not in BAR_AREA:
                raise ValueError(
                    "Trial bar diameter must be one of: "
                    + ", ".join(BAR_AREA.keys())
                )

            result = calculate_beam(
                b, h, fc, fy, Mu, cover, stirrup, bar
            )

            self.display_result(b, h, fc, fy, Mu, cover, stirrup, bar, result)

        except Exception as exc:
            messagebox.showerror("Input / Calculation Error", str(exc))

    def display_result(self, b, h, fc, fy, Mu, cover, stirrup, bar, r):
        self.output.delete("1.0", tk.END)

        status = "ADEQUATE" if r["adequate"] else "NOT ADEQUATE"

        text = f"""
============================================================
RC BEAM FLEXURAL DESIGN RESULTS
============================================================

INPUTS
------------------------------------------------------------
Beam width, b                 = {b:.1f} mm
Overall depth, h              = {h:.1f} mm
Concrete strength, f'c        = {fc:.2f} MPa
Steel yield strength, fy      = {fy:.2f} MPa
Factored moment, Mu           = {Mu:.2f} kN-m
Clear cover                   = {cover:.1f} mm
Stirrup diameter              = {stirrup:.1f} mm
Trial main bar                = {bar:.0f} mm

CALCULATED SECTION
------------------------------------------------------------
Effective depth, d            = {r["d"]:.2f} mm
Required nominal moment, Mn   = {r["Mn_req"]:.2f} kN-m

REINFORCEMENT
------------------------------------------------------------
Required As from flexure      = {r["As_req"]:.2f} mm^2
Minimum As                    = {r["As_min"]:.2f} mm^2
Design As                     = {r["As_design"]:.2f} mm^2

SELECTED REINFORCEMENT
------------------------------------------------------------
{r["n_bars"]} - {bar:.0f} mm bars
Provided As                   = {r["As_provided"]:.2f} mm^2
Provided steel ratio, rho     = {r["rho"]:.5f}
Provided phi*Mn               = {r["phi_Mn"]:.2f} kN-m

SIMPLIFIED STRAIN-BASED CHECK
------------------------------------------------------------
beta1                         = {r["beta1"]:.3f}
Approx. maximum As            = {r["As_max_simplified"]:.2f} mm^2

FLEXURAL CAPACITY STATUS
------------------------------------------------------------
Required Mu                   = {Mu:.2f} kN-m
Provided phi*Mn               = {r["phi_Mn"]:.2f} kN-m

STATUS: {status}

============================================================
DESIGN NOTES
============================================================
1. The calculation is for a singly reinforced rectangular beam.
2. The selected bars are rounded UP to the nearest whole bar.
3. Bar spacing and number of layers are NOT checked here.
4. Shear reinforcement and shear capacity are NOT checked.
5. Development/anchorage length is NOT checked.
6. Deflection and crack-control checks are NOT included.
7. Torsion and seismic special detailing are NOT included.
8. Verify minimum/maximum reinforcement using the exact governing
   NSCP 2015 / ACI 318 provisions applicable to your project.
9. Verify load combinations and Mu from the structural analysis model.
10. Final construction drawings require professional engineering review.

EQUATIONS USED
------------------------------------------------------------
a  = As*fy / (0.85*f'c*b)
Mn = As*fy*(d - a/2)
phi*Mn >= Mu
As,min = max[(0.25*sqrt(f'c)/fy)*b*d, (1.4/fy)*b*d]

All calculations use SI-consistent units.
============================================================
"""
        self.output.insert(tk.END, text)

    def clear(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.show_welcome()

    def load_example(self):
        example = {
            "Beam width, b (mm)": "300",
            "Overall depth, h (mm)": "500",
            "Concrete strength, f'c (MPa)": "21",
            "Steel yield strength, fy (MPa)": "415",
            "Factored moment, Mu (kN-m)": "150",
            "Clear cover (mm)": "40",
            "Stirrup diameter (mm)": "10",
            "Trial main bar diameter (mm)": "20",
        }

        for label, value in example.items():
            self.entries[label].delete(0, tk.END)
            self.entries[label].insert(0, value)


# ---------------------------------------------------------------------------
# PROGRAM START
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()

    # Use a modern ttk theme where available.
    try:
        root.tk.call("tk", "scaling", 1.15)
    except tk.TclError:
        pass

    app = BeamDesignGUI(root)
    root.mainloop()
