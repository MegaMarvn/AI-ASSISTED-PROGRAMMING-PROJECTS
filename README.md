# AI-Assisted Programming Projects
### A shared learning archive for civil & structural engineers who code

Welcome! 👋 This repository collects **every script, tool, and model built by participants of the AI-Assisted Programming training for Civil Engineering** — organized by the date of the training session they came from.

If you attended a session, your work is in here. If you didn't, you're still welcome to read, run, and learn from everything.

> [!WARNING]
> **This repository is PUBLIC. Anyone on the internet can read it, clone it, and keep a copy forever.**
> Never upload client drawings, signed/sealed plans, real project data, contracts, or anyone's personal information.
> Use made-up sample numbers instead. Please read [Data & Confidentiality](#-data--confidentiality) before you contribute.

---

## 📚 Table of Contents

- [What is this repository?](#-what-is-this-repository)
- [Who is this for?](#-who-is-this-for)
- [How the repository is organized](#️-how-the-repository-is-organized)
- [Training sessions index](#-training-sessions-index)
- [What the file types mean](#-what-the-file-types-mean)
- [How to run the projects](#️-how-to-run-the-projects)
- [Setting up your computer](#-setting-up-your-computer)
- [How to add your own work](#-how-to-add-your-own-work)
- [Data & Confidentiality](#-data--confidentiality)
- [Engineering disclaimer](#️-engineering-disclaimer)
- [License](#-license)
- [Credits](#-credits)

---

## 🎯 What is this repository?

This is a **teaching archive**, not a software product.

Over 8 training sessions in 2026, **76 contributors** learned to use AI assistants to write real engineering software — many with little or no prior programming background. The results are all here: working calculators, analysis tools, 3D visualizers, and automation scripts.

Everything here is kept for **academic and educational purposes**. The goal is simple:

> *See what other engineers built, understand how they built it, and build your own.*

**What you'll find inside:**

| You'll find | Examples from real sessions |
|---|---|
| 🧮 **Design calculators** | RC beam design (NSCP 2015), column buckling, concrete mix design, retaining walls |
| 🏗️ **3D structural modelers** | Parametric truss modelers, frame generators, beam deflection visualizers |
| 🔌 **STAAD.Pro automation** | OpenSTAAD scripts that build entire models — nodes, members, supports, loads — from Python |
| 🖥️ **Desktop applications** | Tkinter and PyQt5 tools with graphs, 3D views, and PDF report export |
| 🌐 **Browser-based tools** | Single-file HTML calculators that run with a double-click — no install needed |

**Design codes referenced across projects:** NSCP 2015 (Philippines) · AISC 360-16 LRFD · NBCC 2020 / CSA A23.3-19 (Canada)

---

## 👷 Who is this for?

| If you are... | Start here |
|---|---|
| **A past participant** | Find your session below, then your surname folder. Your work is preserved as you submitted it. |
| **A new participant** | Browse the recent sessions (July 12 and July 26) to see where the training is now. |
| **Brand new to coding** | Start with the `.html` tools — open one in your browser and it just works. No installation required. |
| **An engineer who wants ideas** | Search the session index for a tool close to what you need, then adapt it. |
| **A teacher or student** | Everything is MIT-licensed. Use it in class freely. |

---

## 🗂️ How the repository is organized

Work is filed **by training session date**, then **by participant surname**:

```
AI-ASSISTED-PROGRAMMING-PROJECTS/
│
├── 1. FEBRUARY 14 - 15/        ← Session number + dates
│   ├── ABERIN/                 ← One folder per participant (surname)
│   │   ├── AbeMain.py
│   │   ├── ABERIN.HTML
│   │   └── Std Model/
│   │       └── abe_model.std   ← STAAD.Pro model
│   ├── GUTIERREZ/
│   ├── QUIOBE/
│   └── ...
│
├── 2. FEBRUARY 23 - 24/
├── 3. MARCH 14-15/
├── ...
└── 8. JULY 26/
```

**The two rules:**

1. **Sessions are numbered and dated** — `1.` is the earliest, `8.` the most recent. Chronological order is preserved.
2. **Each participant owns one folder**, named after their surname. Your folder is yours; nobody edits anyone else's.

<details>
<summary><b>📌 Known quirks (honest notes about the archive)</b></summary>

<br>

This is a real training archive that grew organically, so a few things are uneven. They are documented rather than silently "fixed", because participants may have forks and open pull requests pointing at these paths:

- **Some early sessions have loose files at the session root** instead of participant folders — for example `MARTINEZ.HTML` and `Pagaduan.HTML` in Session 1, and `AUMAN.HTML` in Session 2. These are still that participant's submission; they just predate the folder convention.
- **Filename casing is inconsistent** (`MAIN.PY`, `Main.py`, `main.py`). This is harmless on Windows but matters on Linux and macOS — if a script cannot find an import, check the exact capitalization.
- **Session 7 is stored as `7. July 12`**, not `7. JULY 12` like the other uppercase months. Git records that exact spelling, so links and paths must use `July`. Windows hides the difference; GitHub and Linux do not.
- **Session 8 has nested participant folders** under `GUTIERREZ/` (FIDEL, MJTO, MONDRANO, PRIOLO, VELUZ) — these were submitted together during a group exercise.
- **One typo survives in the wild:** `6. MAY 13 - 14/PELARCA/index.htlml`. It still opens fine if you rename it locally.

New submissions should follow the clean `SESSION / SURNAME / files` convention.

</details>

---

## 📅 Training sessions index

Eight sessions, February → July 2026. Each row links to the folder.

| # | Session & dates | People | Python | HTML | STAAD | Focus of the session |
|---|---|---|---|---|---|---|
| 1 | [February 14 – 15](./1.%20FEBRUARY%2014%20-%2015) | 8+ | 17 | 9 | 10 | **First contact.** Connecting Python to STAAD.Pro; first 3D structure viewers in the browser. |
| 2 | [February 23 – 24](./2.%20FEBRUARY%2023%20-%2024) | 9+ | 5 | 20 | – | **Parametric truss modelers.** Heavy on browser-based 3D — change a number, the truss rebuilds. |
| 3 | [March 14 – 15](./3.%20MARCH%2014-15) | 7 | 12 | 7 | 1 | **Analysis & design calculators.** Beam deflection, column buckling, NSCP 2015 RC beam design. |
| 4 | [April 20 – 21](./4.%20APRIL%2020%20-%2021) | 19 | 24 | 18 | – | **Largest cohort.** Paired `INDEX.HTML` + `MAIN.PY` deliverables; PDF reports with ReportLab. |
| 5 | [May 2 – 3](./5.%20MAY%202%20-%203) | 2 | 4 | 2 | – | **Small workshop.** Plotting with Matplotlib and CSV data handling. |
| 6 | [May 13 – 14](./6.%20MAY%2013%20-%2014) | 4 | 9 | 5 | – | **Structured code.** Splitting a tool into modules (`design_engine.py` + `gui.py`). |
| 7 | [July 12](./7.%20July%2012) | 5 | 32 | 7 | 3 | **Full applications.** Multi-module PyQt5 + PyVista 3D apps, Streamlit dashboards, packaged tools. |
| 8 | [July 26](./8.%20JULY%2026) | 6 | 17 | 7 | – | **Connections & bridges.** Shear connection design, bridge models, CustomTkinter interfaces. |

> *"People" counts participant folders; early sessions also have loose single-file submissions at the session root.*

<br>

### Session 1 — February 14 – 15

**Participants:** ABERIN · GUTIERREZ · ITABLE · LANTICSE · MOTOL · QUIOBE · RBJACK · SADANGUEL · GALANG · MARTINEZ · PANGANIBAN · Pagaduan

The starting point. Participants connected Python to STAAD.Pro for the first time using `openstaadpy`, and built their first browser-based 3D structure views. Highlights include a **cryorack structure for a petrochemical facility**, a **steel pipe rack connection design (AISC 360-16 LRFD)**, and a **doubly-reinforced beam shear & moment tool**. This session holds the most `.std` STAAD models (10) of any session.

### Session 2 — February 23 – 24

**Participants:** COMIA · GUTIERREZ · LIM · LUMA · PANGAN · PELOSTRATOS · TAKABE · TAMIAT · VALENCIA · AUMAN · BALTAZAR · MALAHITO · ROBLES

The **truss session**. Almost everyone built a parametric 3D truss modeler that runs entirely in the browser — adjust span, height, and panel count, and the structure regenerates live. Also includes an **OpenSTAAD multistory building generator** and a **cold-formed metal purlin designer (NSCP)**.

### Session 3 — March 14 – 15

**Participants:** BOLLA · ESCABUSA · Fruto · GUTIERREZ · LUCERO · Nsultan · RAMILBILAN

Focus shifted to **analysis and code-based design**. Includes a 3D beam deflection visualizer, a column buckling calculator, an SPF wood joist stress calculator, and a rectangular RC beam designer with 3D visualization. Look at `Nsultan/nscp_design.py` — it generates a **full 10-panel structural drawing sheet** as a single high-resolution image.

### Session 4 — April 20 – 21

**Participants:** ABOY · ALAR BENJAMIN · Abria · BIGNOTIA · DANAN · EARL · EBRO · ESPERIDA · ESTABILLO_RITZ JASON · FORCADAS · GUTIERREZ - LOWRENCE SCOTT · Intelegando · MENDOZA · MUEGA · NONAN · Pol · ROSADA RONALD · SADUMIANO · VASQUEZ - JEFFREY

The **biggest session** — 19 participants. The standard deliverable was a matched pair: `INDEX.HTML` (the interface) and `MAIN.PY` (the engine). This session introduced **PDF report generation** with ReportLab. Notable work includes an RC column PMM optimizer, a retaining wall visualizer, a concrete mix design tool, and a pad footing designer to Canadian codes (NBCC 2020 / CSA A23.3-19). `EBRO/` is worth studying — it is cleanly split into `model.py`, `loads.py`, `properties.py`, and `export.py`.

### Session 5 — May 2 – 3

**Participants:** GUTIERREZ · LOSEO

A small, focused workshop on Matplotlib plotting and reading and writing CSV data.

### Session 6 — May 13 – 14

**Participants:** ALMAZAN · GUTIERREZ · JONGOY · PELARCA

The **"stop writing one giant file"** session. Participants learned to separate calculation logic from the interface — see `GUTIERREZ/design_engine.py` paired with `GUTIERREZ/gui.py`. `PELARCA/` includes `test_truss.py`, the archive's first steps toward automated testing.

### Session 7 — July 12

**Participants:** DALAGUAN · GUTIERREZ · Lacaran · SANCHEZ · TURLA

The most **software-engineering-heavy** session, and the largest by file count. Projects became real multi-module applications:

- **PyQt5 + PyVista** desktop apps with interactive 3D (`DALAGUAN/`, `GUTIERREZ/`)
- **Streamlit** web app for H-shape base plate design (`DALAGUAN/H Shape BP/`)
- **BuildScope Consultation Portal** — a full client-intake app with roles, file uploads, map pins, and PDF/CSV export (`Lacaran/Project_JKL/`)
- **Floor framing automation** that reads a STAAD model and emits an SVG plan, a beam schedule CSV, and a summary report (`SANCHEZ/`)
- A **Civil Formula Garden** reference tool, an isolated footing design sheet, and — because training should be fun — a cat-themed Pomodoro timer with sound 🐱

### Session 8 — July 26

**Participants:** ELICRUZ · GAYANA · GUTIERREZ · HONDA · TEMPLONUEVO · TORRES
*(plus group work under `GUTIERREZ/`: FIDEL · MJTO · MONDRANO · PRIOLO · VELUZ)*

The most recent session. Focus on **steel connections and bridge structures**, with a return to OpenSTAAD automation. Introduced **CustomTkinter** for modern-looking interfaces and `win32print` for sending output straight to a printer.

---

## 📁 What the file types mean

New to this? Here is what you are looking at.

| Extension | What it is | How to open it |
|---|---|---|
| `.html` | A complete tool in one file — interface, styling, and math together. Many use 3D graphics. | **Double-click it.** Opens in your browser. Nothing to install. |
| `.py` | A Python script — the calculation engine, a desktop app, or a STAAD automation script. | Run with Python (see below). |
| `.std` | A **STAAD.Pro model** — the actual structure with nodes, members, supports, and loads. | Open in STAAD.Pro. It is a text file, so you can also read it in Notepad. |
| `.md` / `.txt` | Notes and documentation written by the participant. | Any text editor. |
| `requirements.txt` | The list of Python packages that project needs. | `pip install -r requirements.txt` |
| `.json`, `.csv`, `.svg` | Data files and vector drawings produced by the scripts. | Text editor, Excel, or browser. |

> **Not stored here:** compiled files (`.pyc`), packaged executables (`.exe`), and STAAD's auto-generated companion files (`.cod`, `.cut`, `.slg`, `.sbk`, `.uid`, `.App.log`). These are regenerated automatically from the source, so keeping them would only bloat the repository. The `.std` models — the real work — **are** kept.

---

## ▶️ How to run the projects

### The easy way — browser tools (no installation)

1. Download or clone the repository
2. Find any `.html` file
3. **Double-click it**

That is it. These tools are fully self-contained.

### Python scripts

```bash
# 1. Go to the project folder (quote the path — it contains spaces!)
cd "4. APRIL 20 - 21/EBRO"

# 2. Install dependencies, if the project lists them
pip install -r requirements.txt

# 3. Run it
python main.py
```

> 💡 **Nothing listed?** Most scripts only need `matplotlib`, `numpy`, and `tkinter`.
> A good catch-all: `pip install matplotlib numpy reportlab`
> (`tkinter` ships with Python on Windows. On Linux: `sudo apt install python3-tk`)

### STAAD.Pro automation scripts

These scripts **drive STAAD.Pro from Python**. They need a bit more setup.

**Requirements:** Windows · STAAD.Pro installed and licensed · `pip install openstaadpy pywin32`

**Steps:**

1. **Open STAAD.Pro first** and create a **new empty model** — the script connects to what is already running
2. Run the script: `python openstaad.py`
3. Watch the model build itself — nodes, members, properties, supports, and loads appear automatically

```python
# The pattern used across the archive:
from openstaadpy import os_analytical

staad = os_analytical.connect()     # attach to the open STAAD.Pro session
geo   = staad.Geometry
staad.SetInputUnits(1, 0)           # feet, kips

geo.CreateNode(1, 0.0, 0.0, 0.0)    # node ID, x, y, z
geo.CreateBeam(1, 1, 2)             # member ID, start node, end node
```

> ⚠️ Always start from an **empty** model. These scripts add geometry and will pile on top of an existing structure.

---

## 💻 Setting up your computer

Only needed for the Python projects — the `.html` tools need nothing.

**1. Install Python** — [python.org/downloads](https://www.python.org/downloads/)

> ✅ On Windows, **tick "Add Python to PATH"** on the first installer screen. It saves a lot of pain later.

**2. Check it worked** — open a terminal:

```bash
python --version
```

**3. Get the repository:**

```bash
git clone https://github.com/SC0L0W/AI-ASSISTED-PROGRAMMING-PROJECTS.git
```

> No Git? Click the green **Code** button on GitHub, then **Download ZIP**.

**4. Install the common packages:**

```bash
pip install matplotlib numpy reportlab
```

<details>
<summary><b>Optional: packages used by specific projects</b></summary>

<br>

```bash
pip install PyQt5 pyvista pyvistaqt   # 3D desktop apps (Session 7)
pip install streamlit plotly          # web dashboards (Session 7)
pip install customtkinter             # modern interfaces (Session 8)
pip install openstaadpy pywin32       # STAAD.Pro automation (Windows only)
pip install pandas                    # data handling
```

</details>

---

## 🤝 How to add your own work

Participants contribute through **fork → pull request**. Here is the whole flow.

**1. Fork** this repository (button on the top-right of GitHub)

**2. Add your folder** in the correct session, named with your surname:

```
8. JULY 26/YOURSURNAME/
├── README.md      ← what your tool does and how to run it
├── main.py        ← your code
└── index.html     ← your interface, if you built one
```

**3. Commit and push:**

```bash
git add "8. JULY 26/YOURSURNAME"
git commit -m "Add YOURSURNAME session project"
git push
```

**4. Open a Pull Request** back to this repository.

### ✅ Checklist before you submit

- [ ] My files are inside **my own folder**, in the **correct session**
- [ ] I did **not** modify anyone else's folder
- [ ] **No confidential or client data** — see the section below 👇
- [ ] No real names, emails, phone numbers, or addresses in my code or comments
- [ ] No passwords, API keys, or license keys
- [ ] I removed generated clutter (`__pycache__/`, `.exe`, STAAD `.cod`/`.slg`/`.uid` files) — `.gitignore` handles most of this for you
- [ ] I added a short `README.md` explaining what my tool does

### House rules

- **Your folder is yours.** Nobody edits it but you.
- **Your work stays as you submitted it.** This archive preserves learning history — including the rough early attempts. That is the point.
- **Imperfect code is welcome.** This is a training archive, not production software. A tool that only half-works still teaches something.

---

## 🔒 Data & Confidentiality

> [!CAUTION]
> **This repository is public and permanent.** Anything committed here can be read, cloned, mirrored, indexed by search engines, and archived by third parties **within minutes**. Deleting a file later does **not** remove it from Git history, and it does not remove copies other people already made.

### ❌ Never upload

| Category | Examples |
|---|---|
| **Client & project data** | Real project names, addresses, lot numbers, site coordinates, client drawings, signed or sealed plans, soil reports, surveys |
| **Commercial information** | Contracts, bids, tender documents, cost estimates, BOQs, rate schedules, invoices |
| **Personal information** | Names, emails, phone numbers, home addresses, ID numbers, signatures, photos of people, CVs |
| **Credentials** | Passwords, API keys, tokens, license keys, database connection strings, `.env` files |
| **Proprietary material** | Licensed software installers, copyrighted code, internal company standards or templates |
| **Regulated documents** | Anything under an NDA, or any document marked *confidential*, *internal*, or *restricted* |

### ✅ Always do this instead

- **Invent your sample data.** A beam is a beam — `Span = 6.0 m, fc' = 28 MPa` teaches exactly as well as real project numbers.
- **Use generic names** — "Project A", "Warehouse Sample", "Structure1".
- **Strip metadata** from any file you export before committing.
- **Share the method, not the client's data.** The calculation logic is the valuable part; the client's numbers are not yours to publish.

### 🚨 If you uploaded something by mistake

Act fast, and **do not just delete the file and commit** — that leaves it fully visible in the Git history.

1. **Tell the repository maintainer immediately** — send a private message, not a public issue describing the sensitive content
2. **If it was a credential, revoke and rotate it right away.** Assume it is already compromised
3. The maintainer will purge it from history (`git filter-repo` or BFG) and, if needed, contact GitHub Support to clear cached views
4. **Notify your client or employer** if their data was involved — most professional and contractual obligations require this

> **Your responsibility:** You are accountable for everything you commit. If you are unsure whether something is safe to publish, **ask before you push** — and when still in doubt, leave it out.

### Legal note

Contributors are responsible for ensuring they have the right to publish what they upload. Content that violates confidentiality obligations, NDAs, data protection law, or third-party copyright will be removed on discovery. Contributing to this repository does **not** transfer any rights you do not hold.

---

## ⚠️ Engineering disclaimer

> [!IMPORTANT]
> **Nothing in this repository is approved for use in real construction, design, or engineering decisions.**

Please understand clearly what this code is and is not:

- These are **training exercises** written by engineers *while learning to program*, often with AI assistance.
- The code is **not validated, not peer-reviewed, and not quality-assured.** It may contain errors in formulas, unit conversions, code provisions, assumptions, or logic.
- Design code implementations (NSCP, AISC, CSA, NBCC and others) may be **incomplete, simplified, or outdated.** Always verify against the current official code text.
- Results have **not** been checked against commercial software or hand calculations unless a participant specifically says so.

**If you use any of this for actual work:**

1. **A licensed professional engineer must independently verify every calculation** and takes full responsibility for the result.
2. Check all assumptions, units, load combinations, and code provisions yourself.
3. Validate against known solutions, hand calculations, or established software.
4. Comply with your local building code and regulatory requirements.

The authors, contributors, and maintainers accept **no liability whatsoever** for any use of this material. See [LICENSE](./LICENSE) — the software is provided *"as is", without warranty of any kind*.

---

## 📄 License

Released under the **MIT License** — see [LICENSE](./LICENSE).

You are free to use, copy, modify, and distribute this material, including commercially, provided the copyright notice and license text are retained. It comes with **no warranty of any kind**.

Individual participants retain authorship of their own contributions.

---

## 🙏 Credits

Built by **76 contributors** across 8 training sessions in 2026 — engineers who had never written a line of code sitting beside engineers automating STAAD.Pro, all learning together.

Thank you to every participant who shared their work publicly so that others could learn from it. That generosity is what makes this archive worth having.

**Training programme:** AI-Assisted Programming for Civil Engineering
**Maintained by:** [@SC0L0W](https://github.com/SC0L0W)

---

<div align="center">

### 🎓 For academic and educational use

*Learn from it · Build on it · Verify everything before you use it*

**Never upload confidential or client data.**

</div>
