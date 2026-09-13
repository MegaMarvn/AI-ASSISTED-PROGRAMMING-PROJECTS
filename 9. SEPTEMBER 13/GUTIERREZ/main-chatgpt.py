import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
from datetime import date

# ============================================================
# NSCP 2015 RC BEAM DESIGNER - SINGLE FILE / STANDARD LIBRARY
# ============================================================
# Educational engineering calculation aid.
# Verify all provisions, load combinations, analysis, detailing,
# seismic requirements, development/anchorage and project-specific
# NSCP 2015 requirements before professional use.
#
# Basis: NSCP 2015 reinforced-concrete strength-design concepts,
# using ACI 318-style equations adopted/referenced by NSCP 2015.
# Always confirm the exact edition, amendments and project criteria.
# ============================================================

BARS = {
    "10M": (11.3, 100.0), "15M": (16.0, 200.0), "20M": (19.5, 300.0),
    "25M": (25.2, 500.0), "30M": (29.9, 700.0), "35M": (35.7, 1000.0)
}

def beta1(fc):
    return max(0.65, min(0.85, 0.85 - 0.05 * max(fc - 28.0, 0) / 7.0))

def calc_design(x):
    b,h,L,cover,fc,fy,D,Lv,addD,P,aP,support,loadtype,lam = x

    # Normal-weight concrete density = 24 kN/m³.
    self_w = b/1000 * h/1000 * 24.0
    wu = 1.2*(D + addD + self_w) + 1.6*Lv

    # Idealized gravity actions. Continuous/fixed values are preliminary
    # coefficients only; actual frame analysis governs final design.
    if support == "Cantilever":
        M = wu*L**2/2 + P*L if loadtype in ("Point load", "Combination") else wu*L**2/2
        V = wu*L + P if loadtype in ("Point load", "Combination") else wu*L
        coeff = "Cantilever: wL²/2"
    elif support == "Fixed":
        M = wu*L**2/12 + P*L/4 if loadtype in ("Point load", "Combination") else wu*L**2/12
        V = wu*L/2 + P/2 if loadtype in ("Point load", "Combination") else wu*L/2
        coeff = "Fixed approximation: wL²/12"
    elif support == "Continuous":
        M = wu*L**2/10 + P*L/4 if loadtype in ("Point load", "Combination") else wu*L**2/10
        V = wu*L/2 + P/2 if loadtype in ("Point load", "Combination") else wu*L/2
        coeff = "Continuous preliminary: wL²/10"
    else:
        M = wu*L**2/8 + P*L/4 if loadtype in ("Point load", "Combination") else wu*L**2/8
        V = wu*L/2 + P/2 if loadtype in ("Point load", "Combination") else wu*L/2
        coeff = "Simply supported: wL²/8"

    # Flexure: rectangular singly reinforced section.
    phi0 = 0.90
    d_guess = h-cover-BARS["20M"][0]/2
    Rn = M*1e6/(phi0*b*d_guess**2)
    disc = 1-2*Rn/(0.85*fc)
    if d_guess <= 0 or disc <= 0:
        raise ValueError("Beam geometry is insufficient for the simplified flexural model.")

    aa = (1-math.sqrt(disc))*d_guess
    As_req = M*1e6/(phi0*fy*(d_guess-aa/2))
    As_min = max(0.25*math.sqrt(fc)/fy*b*d_guess, 1.4/fy*b*d_guess)

    # Tension-controlled upper limit using epsilon_t = 0.005.
    c_lim = d_guess*0.003/(0.003+0.005)
    As_max = 0.85*fc*b*beta1(fc)*c_lim/fy

    candidates = []
    for bar,(db,area) in BARS.items():
        for n in range(2,17):
            As = n*area
            if As < max(As_req,As_min) or As > As_max:
                continue
            d = h-cover-db/2
            a = As*fy/(0.85*fc*b)
            c = a/beta1(fc)
            et = 0.003*(d-c)/c if c > 0 else 0
            phi = 0.90 if et >= 0.005 else max(0.65, 0.65+(et-0.002)/0.003*0.25)
            Mn = As*fy*(d-a/2)/1e6
            if phi*Mn >= M:
                candidates.append((As,n,bar,d,a,c,et,phi,Mn,phi*Mn))

    if not candidates:
        raise ValueError("No practical tension-steel arrangement found. Increase beam size or review loading.")

    flex = min(candidates, key=lambda q:(q[0],q[1]))
    As,n,bar,d,a,c,et,phi,Mn,phiMn = flex

    # Top reinforcement: preliminary minimum longitudinal steel.
    top_bar = "15M"
    top_n = max(2, math.ceil(As_min/BARS[top_bar][1]))
    top_As = top_n*BARS[top_bar][1]

    # Shear. NSCP/ACI-style SI equation for normal-weight concrete.
    Vc = 0.17*lam*math.sqrt(fc)*b*d/1000
    phiV = 0.75
    Vs_req = max(0, V/phiV-Vc)

    stirrup_options = ["10M","15M","20M"]
    stirrup = "10M"
    best_s = 25
    for st in stirrup_options:
        av = 2*BARS[st][1]
        if Vs_req <= 0:
            req_s = 99999
        else:
            req_s = av*fy*d/(Vs_req*1000)
        smax = min(d/2,600)
        allowed = [25,50,75,100,125,150,175,200,225,250,275,300,350,400,450,500,550,600]
        s = max([q for q in allowed if q <= min(req_s,smax)], default=25)
        phiVn = phiV*(Vc+av*fy*d/(s*1000))
        if phiVn >= V:
            stirrup,best_s = st,s
            break

    av = 2*BARS[stirrup][1]
    phiVn = phiV*(Vc+av*fy*d/(best_s*1000))
    shear_limit = phiV*(0.66*math.sqrt(fc)*b*d/1000)

    # Simplified preliminary development length.
    db=BARS[bar][0]
    ld=max(300,(fy/(1.1*math.sqrt(fc)))*db)

    # Approximate congestion check: bottom bars in one layer.
    available = b-2*(cover+BARS["10M"][0])
    spacing = (available-As/BARS[bar][1]*BARS[bar][0]) if False else 0
    bar_clear = (available-n*db)/(n-1) if n>1 else available
    congestion = bar_clear < max(25,db)

    return dict(
        b=b,h=h,L=L,cover=cover,fc=fc,fy=fy,D=D,Lv=Lv,addD=addD,P=P,aP=aP,
        self_w=self_w,wu=wu,M=M,V=V,coeff=coeff,d=d,As_req=As_req,As_min=As_min,
        As_max=As_max,As=As,n=n,bar=bar,a=a,c=c,et=et,phi=phi,Mn=Mn,phiMn=phiMn,
        top_bar=top_bar,top_n=top_n,top_As=top_As,Vc=Vc,Vs_req=Vs_req,stirrup=stirrup,
        s=best_s,phiVn=phiVn,shear_limit=shear_limit,ld=ld,congestion=congestion,
        loadtype=loadtype,support=support,lam=lam
    )

def report(r, project, beam, designer, notes):
    return f"""NSCP 2015 RC BEAM DESIGN REPORT
========================================
PROJECT: {project}
BEAM ID: {beam}
DESIGNER: {designer}
DATE: {date.today().isoformat()}

IMPORTANT:
This software is an engineering calculation aid. Professional verification
is required. Confirm the applicable NSCP 2015 provisions, amendments,
structural analysis, load combinations, seismic provisions, development,
anchorage and detailing requirements.

INPUTS
------
b x h = {r['b']:.0f} x {r['h']:.0f} mm
Span = {r['L']:.2f} m
Clear cover = {r['cover']:.0f} mm
f'c = {r['fc']:.1f} MPa
fy = {r['fy']:.1f} MPa
D = {r['D']:.2f} kN/m
L = {r['Lv']:.2f} kN/m
Additional D = {r['addD']:.2f} kN/m
Point load = {r['P']:.2f} kN
Point-load location = {r['aP']:.2f} m
Support = {r['support']}
Loading = {r['loadtype']}
lambda = {r['lam']:.2f}

LOADS
-----
Self-weight = {r['self_w']:.2f} kN/m
wu = 1.2(D + additional D + self-weight) + 1.6L
wu = {r['wu']:.2f} kN/m
Moment model = {r['coeff']}
Mu = {r['M']:.2f} kN-m
Vu = {r['V']:.2f} kN

FLEXURE
-------
d = {r['d']:.1f} mm
As,req = {r['As_req']:.0f} mm2
As,min = {r['As_min']:.0f} mm2
As,max (preliminary tension-controlled limit) = {r['As_max']:.0f} mm2
Bottom steel = {r['n']}-{r['bar']} = {r['As']:.0f} mm2
Top steel = {r['top_n']}-{r['top_bar']} = {r['top_As']:.0f} mm2
a = {r['a']:.1f} mm
c = {r['c']:.1f} mm
epsilon_t = {r['et']:.5f}
phi = {r['phi']:.3f}
phiMn = {r['phiMn']:.2f} kN-m
FLEXURE = {'PASS' if r['phiMn'] >= r['M'] and r['As'] <= r['As_max'] else 'FAIL'}

SHEAR
-----
Vc = {r['Vc']:.2f} kN
Required Vs = {r['Vs_req']:.2f} kN
Stirrups = 2-{r['stirrup']} @ {r['s']:.0f} mm
phiVn = {r['phiVn']:.2f} kN
Shear upper-limit check = {'PASS' if r['V'] <= r['shear_limit'] else 'FAIL'}
SHEAR = {'PASS' if r['phiVn'] >= r['V'] and r['V'] <= r['shear_limit'] else 'FAIL'}

DETAILING
---------
Preliminary tension development length = {r['ld']:.0f} mm
Bottom bar clear spacing estimate = {'WARNING: congestion possible' if r['congestion'] else 'PASS'}
Development/anchorage/detailing require final project-specific verification.

NOTES
-----
{notes}

BASIS / LIMITATIONS
-------------------
NSCP 2015 reinforced-concrete strength-design concepts, with ACI 318-style
equations where applicable. The load-analysis coefficients for continuous
and fixed beams are preliminary approximations only. Actual structural
analysis should govern. Torsion, seismic detailing, moment redistribution,
openings, compression reinforcement, exact development modifiers, hooks,
laps, anchorage, bar layering and frame interaction are not fully modeled.
"""

class App:
    def __init__(self, root):
        self.root=root
        root.title("NSCP 2015 | RC Beam Designer")
        root.geometry("1280x820")
        root.minsize(1000,700)
        self.last=None
        self.dark=True
        self.vars={}

        style=ttk.Style()
        try: style.theme_use("clam")
        except: pass
        style.configure("TButton", padding=8, font=("Segoe UI",10))
        style.configure("TLabel", font=("Segoe UI",10))
        style.configure("TLabelframe", padding=8)

        header=tk.Frame(root,bg="#101820",height=64)
        header.pack(fill="x")
        tk.Label(header,text="▰  STRUCTURE LAB",fg="#F5B700",bg="#101820",
                 font=("Segoe UI",12,"bold")).pack(side="left",padx=18,pady=16)
        tk.Label(header,text="NSCP 2015  |  RC BEAM DESIGNER",fg="white",bg="#101820",
                 font=("Segoe UI",17,"bold")).pack(side="left")
        self.status=tk.Label(header,text="● READY",fg="#7CFC00",bg="#101820",
                             font=("Segoe UI",11,"bold"))
        self.status.pack(side="right",padx=20)

        body=tk.Frame(root,bg="#18232C")
        body.pack(fill="both",expand=True)

        nav=tk.Frame(body,bg="#111A20",width=190)
        nav.pack(side="left",fill="y")
        tk.Label(nav,text="DESIGN WORKFLOW",fg="#F5B700",bg="#111A20",
                 font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18,pady=(20,10))
        for t in ["PROJECT","GEOMETRY","MATERIALS","LOADS","FLEXURE","SHEAR","DETAILING","3D VIEW","CALCULATIONS","REPORT"]:
            tk.Button(nav,text=t,anchor="w",bd=0,fg="#DDE6ED",bg="#111A20",
                      activebackground="#263641",activeforeground="#F5B700",
                      font=("Segoe UI",9,"bold"),command=lambda q=t:self.jump(q)).pack(fill="x",padx=8,pady=1,ipady=7)

        main=tk.Frame(body,bg="#18232C")
        main.pack(side="left",fill="both",expand=True,padx=12,pady=12)

        self.nb=ttk.Notebook(main)
        self.nb.pack(fill="both",expand=True)

        self.tabs={}
        for name in ["PROJECT","DESIGN","3D VIEW","CALCULATIONS","REPORT"]:
            f=tk.Frame(self.nb,bg="#E9EEF2")
            self.nb.add(f,text=name)
            self.tabs[name]=f

        self.build_project()
        self.build_design()
        self.build_3d()
        self.build_calc()
        self.build_report()

    def entry(self,parent,label,key,default):
        row=tk.Frame(parent,bg="#E9EEF2")
        row.pack(fill="x",pady=3)
        tk.Label(row,text=label,bg="#E9EEF2",fg="#26323A",width=25,anchor="w").pack(side="left")
        v=tk.StringVar(value=str(default)); self.vars[key]=v
        e=tk.Entry(row,textvariable=v,width=15,relief="solid",bd=1)
        e.pack(side="right")
        return e

    def build_project(self):
        f=self.tabs["PROJECT"]
        card=tk.LabelFrame(f,text=" PROJECT INFORMATION ",bg="#F7F9FA",fg="#26323A",
                           font=("Segoe UI",11,"bold"),padx=15,pady=15)
        card.pack(fill="x",padx=20,pady=20)
        self.entry(card,"Project name","project","RC Beam Project")
        self.entry(card,"Beam ID","beam","B1")
        self.entry(card,"Designer","designer","")
        self.entry(card,"Notes","notes","")
        tk.Label(f,text="Offline single-file engineering tool • NSCP 2015 basis",
                 bg="#E9EEF2",fg="#64727C",font=("Segoe UI",10)).pack(anchor="w",padx=24)

    def build_design(self):
        f=self.tabs["DESIGN"]
        top=tk.Frame(f,bg="#E9EEF2"); top.pack(fill="x",padx=18,pady=15)
        cards=[("GEOMETRY",[("b","Beam width b (mm)",300),("h","Overall depth h (mm)",500),("L","Span (m)",6),("cover","Clear cover (mm)",40)]),
               ("MATERIALS",[("fc","Concrete f'c (MPa)",25),("fy","Steel fy (MPa)",415),("lam","Lambda",1.0)]),
               ("LOADS",[("D","Dead load D (kN/m)",10),("Lv","Live load L (kN/m)",5),("addD","Additional D (kN/m)",0),("P","Point load P (kN)",0),("aP","Point load location (m)",3)])]
        for title,fields in cards:
            c=tk.LabelFrame(top,text=" "+title+" ",bg="#F7F9FA",fg="#26323A",font=("Segoe UI",10,"bold"),padx=10,pady=8)
            c.pack(side="left",fill="both",expand=True,padx=5)
            for k,lbl,d in fields:self.entry(c,lbl,k,d)

        bottom=tk.Frame(f,bg="#E9EEF2"); bottom.pack(fill="x",padx=18)
        self.combo(bottom,"Support","support",["Simply supported","Continuous","Fixed","Cantilever"],"Simply supported")
        self.combo(bottom,"Loading","loadtype",["Uniform load","Point load","Combination"],"Uniform load")

        btn=tk.Button(f,text="⚡  RUN DESIGN",command=self.calculate,bg="#F5B700",
                      fg="#111820",font=("Segoe UI",12,"bold"),bd=0,padx=20,pady=12)
        btn.pack(anchor="w",padx=24,pady=15)

        self.summary=tk.Frame(f,bg="#111A20")
        self.summary.pack(fill="both",expand=True,padx=18,pady=(0,15))
        self.summary_text=tk.Text(self.summary,bg="#111A20",fg="#EAF1F5",bd=0,
                                  font=("Consolas",11),wrap="word")
        self.summary_text.pack(fill="both",expand=True,padx=15,pady=15)
        self.summary_text.insert("1.0","RUN DESIGN to generate the engineering dashboard.")

    def combo(self,parent,label,key,values,default):
        tk.Label(parent,text=label,bg="#E9EEF2").pack(side="left",padx=(8,4))
        v=tk.StringVar(value=default); self.vars[key]=v
        ttk.Combobox(parent,textvariable=v,values=values,state="readonly",width=18).pack(side="left")

    def build_3d(self):
        f=self.tabs["3D VIEW"]
        self.canvas=tk.Canvas(f,bg="#101820",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw3d())
        self.canvas.bind("<MouseWheel>",self.wheel)
        self.canvas.bind("<ButtonPress-1>",self.drag_start)
        self.canvas.bind("<B1-Motion>",self.drag)
        self.zoom=1.0; self.rot=0.0; self.panx=0; self.pany=0; self.dragxy=(0,0)

    def build_calc(self):
        f=self.tabs["CALCULATIONS"]
        self.calc=tk.Text(f,bg="#111A20",fg="#EAF1F5",font=("Consolas",10),wrap="word")
        self.calc.pack(fill="both",expand=True,padx=15,pady=15)

    def build_report(self):
        f=self.tabs["REPORT"]
        tk.Button(f,text="SAVE .TXT REPORT",command=self.save_report,bg="#F5B700",
                  font=("Segoe UI",11,"bold"),bd=0,padx=18,pady=10).pack(anchor="w",padx=20,pady=20)
        self.report_box=tk.Text(f,font=("Consolas",10),wrap="word")
        self.report_box.pack(fill="both",expand=True,padx=20,pady=(0,20))

    def values(self):
        def num(k): return float(self.vars[k].get())
        vals=[num(k) for k in ["b","h","L","cover","fc","fy","D","Lv","addD","P","aP"]]
        if any(v<=0 for v in vals[:8]) or vals[8]<0 or vals[9]<0 or vals[10]<0:
            raise ValueError("Check dimensions, material values and loads.")
        return (*vals,self.vars["support"].get(),self.vars["loadtype"].get(),num("lam"))

    def calculate(self):
        try:
            r=calc_design(self.values()); self.last=r
            self.status.config(text="● DESIGN COMPLETE",fg="#7CFC00")
            flex="PASS" if r["phiMn"]>=r["M"] and r["As"]<=r["As_max"] else "FAIL"
            shear="PASS" if r["phiVn"]>=r["V"] and r["V"]<=r["shear_limit"] else "FAIL"
            detail="WARNING" if r["congestion"] else "PASS"
            self.summary_text.delete("1.0","end")
            self.summary_text.insert("end",
                f"DESIGN STATUS\n{'='*48}\n"
                f"  FLEXURE       {flex}\n  SHEAR         {shear}\n  DETAILING     {detail}\n\n"
                f"DESIGN REINFORCEMENT\n{'='*48}\n"
                f"  BOTTOM   {r['n']}-{r['bar']}\n"
                f"  TOP      {r['top_n']}-{r['top_bar']}\n"
                f"  STIRRUPS 2-{r['stirrup']} @ {r['s']:.0f} mm\n\n"
                f"ACTIONS\n{'='*48}\n"
                f"  Mu       {r['M']:.2f} kN-m\n  phiMn    {r['phiMn']:.2f} kN-m\n"
                f"  Vu       {r['V']:.2f} kN\n  phiVn    {r['phiVn']:.2f} kN\n\n"
                f"SECTION\n{'='*48}\n  d        {r['d']:.1f} mm\n"
                f"  As req   {r['As_req']:.0f} mm²\n  As prov  {r['As']:.0f} mm²\n"
                f"  epsilon_t {r['et']:.5f}\n  phi      {r['phi']:.3f}\n\n"
                "⚠ Professional verification is required.")
            self.update_calc(r)
            self.update_report(r)
            self.draw3d()
        except Exception as e:
            self.status.config(text="● INPUT / DESIGN ERROR",fg="#FF6B6B")
            messagebox.showerror("Design Error",str(e))

    def update_calc(self,r):
        self.calc.delete("1.0","end")
        self.calc.insert("end",
f"""NSCP 2015 CALCULATION WORKSHEET
============================================

1. FACTORED LOAD
Self-weight = b/1000 × h/1000 × 24
             = {r['self_w']:.2f} kN/m

wu = 1.2(D + Additional D + Self-weight) + 1.6L
   = 1.2({r['D']:.2f} + {r['addD']:.2f} + {r['self_w']:.2f}) + 1.6({r['Lv']:.2f})
   = {r['wu']:.2f} kN/m

2. ACTIONS
Model: {r['coeff']}
Mu = {r['M']:.2f} kN-m
Vu = {r['V']:.2f} kN

3. FLEXURE
beta1 = {beta1(r['fc']):.3f}
Effective depth d = {r['d']:.1f} mm
As,req = {r['As_req']:.0f} mm²
As,min = {r['As_min']:.0f} mm²
As,max = {r['As_max']:.0f} mm²

Provide {r['n']}-{r['bar']} bottom
As,prov = {r['As']:.0f} mm²

a = As fy / (0.85 f'c b)
  = {r['a']:.1f} mm

c = a / beta1
  = {r['c']:.1f} mm

epsilon_t = {r['et']:.5f}
phi = {r['phi']:.3f}
phiMn = {r['phiMn']:.2f} kN-m

4. SHEAR
Vc = 0.17 lambda sqrt(f'c) b d
   = {r['Vc']:.2f} kN

Required Vs = {r['Vs_req']:.2f} kN
Provide 2-{r['stirrup']} @ {r['s']:.0f} mm
phiVn = {r['phiVn']:.2f} kN

5. DETAILING
Preliminary development length = {r['ld']:.0f} mm
Congestion check = {'WARNING' if r['congestion'] else 'PASS'}

BASIS
NSCP 2015 reinforced-concrete strength-design concepts and
ACI 318-style equations adopted/referenced by NSCP 2015.

LIMITATION
This worksheet does not replace full structural analysis or
professional verification of NSCP 2015, seismic, anchorage,
development, detailing and project-specific requirements.
""")

    def update_report(self,r):
        txt=report(r,self.vars["project"].get(),self.vars["beam"].get(),
                   self.vars["designer"].get(),self.vars["notes"].get())
        self.report_box.delete("1.0","end"); self.report_box.insert("1.0",txt)

    def save_report(self):
        if not self.last:
            messagebox.showinfo("Report","Run the design first."); return
        p=filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Text files","*.txt")],initialfile=self.vars["beam"].get()+"_NSCP2015_Report.txt")
        if p:
            with open(p,"w",encoding="utf-8") as f:f.write(self.report_box.get("1.0","end"))
            messagebox.showinfo("Saved","Report saved successfully.")

    def jump(self,name):
        mapping={"PROJECT":"PROJECT","GEOMETRY":"DESIGN","MATERIALS":"DESIGN","LOADS":"DESIGN",
                 "FLEXURE":"DESIGN","SHEAR":"DESIGN","DETAILING":"DESIGN","3D VIEW":"3D VIEW",
                 "CALCULATIONS":"CALCULATIONS","REPORT":"REPORT"}
        self.nb.select(self.tabs[mapping[name]])

    def draw3d(self):
        c=self.canvas; c.delete("all")
        w=max(c.winfo_width(),700); h=max(c.winfo_height(),500)
        r=self.last
        if not r:
            c.create_text(w/2,h/2,text="3D BEAM VISUALIZATION\nRun design to display reinforcement",
                          fill="#F5B700",font=("Segoe UI",16,"bold"),justify="center"); return
        # Isometric pseudo-3D. Single-file Tkinter, no external 3D engine.
        L=r["L"]; bw=r["b"]; bh=r["h"]
        scale=min((w-180)/(L*1000),(h-180)/max(bh,bw))/1.3*self.zoom
        ox=w/2+self.panx; oy=h/2+self.pany
        ang=self.rot
        ca,sa=math.cos(ang),math.sin(ang)

        def iso(x,y,z):
            X=(x*scale)
            Y=(y*scale)
            Z=(z*scale)
            return (ox + X*ca-Y*sa, oy + Z*0.55-X*0.20*sa-Y*0.20*ca)

        length=L*1000
        pts=[]
        for X,Y,Z in [(0,0,0),(length,0,0),(length,bw,0),(0,bw,0),
                      (0,0,bh),(length,0,bh),(length,bw,bh),(0,bw,bh)]:
            pts.append(iso(X,Y,Z))
        # concrete faces
        faces=[([pts[i] for i in [0,1,2,3]],"#314A58"),
               ([pts[i] for i in [4,5,6,7]],"#476574"),
               ([pts[i] for i in [0,1,5,4]],"#3A5663")]
        for p,col in faces:c.create_polygon(p,fill=col,outline="#8AA6B3")
        # ends
        c.create_polygon([pts[i] for i in [0,3,7,4]],fill="#29404C",outline="#8AA6B3")

        # reinforcement: longitudinal lines
        if True:
            n=r["n"]; db=r["bar"]
            inset=r["cover"]+db/2
            for j in range(n):
                y=inset+(bw-2*inset)*(j/(max(n-1,1)))
                z=inset
                p1=iso(0,y,z); p2=iso(length,y,z)
                c.create_line(*p1,*p2,fill="#F5B700",width=3)
            for j in range(r["top_n"]):
                y=inset+(bw-2*inset)*(j/(max(r["top_n"]-1,1)))
                z=bh-inset
                p1=iso(0,y,z); p2=iso(length,y,z)
                c.create_line(*p1,*p2,fill="#FF7F50",width=3)

            # representative stirrups at spacing.
            for xx in range(0,int(length)+1,max(int(r["s"]),1)):
                q=[iso(xx,inset,inset),iso(xx,bw-inset,inset),
                   iso(xx,bw-inset,bh-inset),iso(xx,inset,bh-inset)]
                c.create_line(*sum(([a,b] for a,b in zip(q,q[1:]+q[:1])),[]),
                              fill="#EAF1F5",width=2)

        c.create_text(25,25,text="ISOMETRIC BEAM MODEL",anchor="nw",
                      fill="#F5B700",font=("Segoe UI",13,"bold"))
        c.create_text(25,50,text=f"{r['b']:.0f} × {r['h']:.0f} mm  |  L = {r['L']:.2f} m",
                      anchor="nw",fill="white",font=("Segoe UI",10))
        c.create_text(w-25,25,text="BOTTOM: "+f"{r['n']}-{r['bar']}",
                      anchor="ne",fill="#F5B700",font=("Segoe UI",10,"bold"))
        c.create_text(w-25,48,text="TOP: "+f"{r['top_n']}-{r['top_bar']}",
                      anchor="ne",fill="#FF7F50",font=("Segoe UI",10,"bold"))
        c.create_text(w-25,71,text="STIRRUPS: "+f"2-{r['stirrup']} @ {r['s']:.0f}",
                      anchor="ne",fill="#EAF1F5",font=("Segoe UI",10,"bold"))

    def wheel(self,e):
        self.zoom=max(.5,min(2.5,self.zoom*(1.1 if e.delta>0 else .9))); self.draw3d()

    def drag_start(self,e): self.dragxy=(e.x,e.y)
    def drag(self,e):
        dx=e.x-self.dragxy[0]; self.dragxy=(e.x,e.y)
        self.rot+=dx*0.01; self.panx+=dx; self.pany+=e.y-self.dragxy[1]
        self.draw3d()

if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
