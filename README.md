# Svenesis Siril Scripts

A collection of Python scripts for [Siril](https://www.siril.org/) (astronomical image processing).

## Author and links

- **Author:** Sven Ramuschkat — [www.svenesis.org](https://www.svenesis.org)
- **Repository:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)

## License

GPL-3.0-or-later

## Scripts

| Script | Description |
|--------|-------------|
| [Multiple Histogram Viewer](#multiple-histogram-viewer) | View linear and stretched images with RGB histograms, 3D surface plots, and detailed statistics. |
| [Script Security Scanner](#script-security-scanner) | Scan Siril Python scripts for malicious patterns across 10 threat categories. |

---

## Multiple Histogram Viewer

**File:** `MultipleHistogramViewer.py` (v1.0.1)

Reads the current linear image from Siril (or a linear FITS file), applies a 2%–98% percentile autostretch for preview, and displays **Linear** and **Auto-Stretched** views side by side with combined RGB histograms or 3D surface plots. You can also load up to **2 additional stretched FITS** files for comparison. Compressed FITS (e.g. `.fz`, `.gz`) are supported.

### Screenshots

![Multiple Histogram Viewer — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-1.jpg)

*Main window: Linear and Auto-Stretched columns with histogram view, controls, and statistics.*

![Multiple Histogram Viewer — 3D and stats](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-2.jpg)

*3D surface plot option and statistical data (Size, Min/Max, Mean, Median, Std, IQR, MAD, P2/P98, Range, Near-black/Near-white).*

### Features

- **Image sources:** Current image from Siril, or load a linear FITS directly (including compressed `.fz`/`.gz`); up to 2 stretched FITS for comparison.
- **Views:** Histogram (2D) or 3D surface plot (X/Y = pixel position, Z = channel value).
- **Histogram:** Combined RGB and per-channel (R, G, B, L) with Normal or Logarithmic Y-axis; X-axis in ADU.
- **Statistics:** Size, Pixels, Min/Max, Mean, Median, Std, IQR, MAD, P2/P98 (2nd/98th percentile), Range (P2–P98), Near-black/Near-white %. Tooltip explains each metric; “(subsampled)” when stats are from a subset of pixels.
- **Enlarge Diagram:** Button under each histogram/3D plot opens a larger modal with the same diagram and a channel legend.
- **Help:** Modal help with author info, usage, and control descriptions.
- **Image zoom:** −, Fit, 1:1, + per column; after loading, all images are fitted to their windows.
- **Click on image:** Shows pixel R, G, B, I (ADU) in the stats area and a vertical line in the histogram.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, Pillow, astropy (installed automatically via `s.ensure_installed`)
- matplotlib (for 3D surface plot only)

### Usage

1. Load an image in Siril (or use **Load linear FITS...** in the script).
2. Run **Multiple Histogram Viewer** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Use the left panel for view type (Histogram / 3D), Data-Mode (Normal / Log), channels, and image/source options. Use **Enlarge Diagram** for a larger histogram or 3D view.

---

## Script Security Scanner

**File:** `Script-Security-Scanner.py` (v2.0.0)

Scans all Python scripts in your configured Siril script folders for potentially dangerous patterns across **10 threat categories**. Siril scripts run with full user-level OS permissions, so a malicious script can do virtually anything on your machine. This tool gives you a first-pass analysis before you run any script you did not write yourself.

### Screenshots

![Script Security Scanner — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Security-Scanner-1.jpg)

*Main window: script directories, category selection, scan results grouped by file with severity indicators.*

### Features

- **10 threat categories:** File System — Destructive, File System — Data Theft, Network — Exfiltration, Network — Inbound/Backdoor, Code Execution — Escalation, Persistence, Obfuscation, Denial of Service, Social Engineering, Supply Chain.
- **Severity levels:** HIGH (red) — likely dangerous; MEDIUM (orange) — suspicious; LOW (blue) — informational.
- **Script directory discovery:** Automatically reads configured Siril script paths from the OS-specific Siril config file; falls back to well-known default locations.
- **Anti-evasion measures:** Multi-line continuation joins, triple-quoted string awareness, import alias expansion, comment-line filtering.
- **Detailed findings:** Click any finding for a full explanation; double-click to open the file in your default text editor.
- **Export:** Save a full plain-text report of all findings with explanations.
- **Startup warning:** Explains the limitations of static analysis and reminds you to also use AI-assisted review.
- **AI-assisted analysis tip:** Includes a ready-to-use prompt for ChatGPT or Claude to perform a semantic review that can catch threats pattern-based tools miss.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- PyQt6 (installed automatically when the script runs)

### Usage

1. Run **Script Security Scanner** from Siril: **Processing → Scripts** (or your Scripts menu).
2. The scanner auto-discovers your Siril script directories. Use **Add Directory…** or **Paste Paths** to add more.
3. Select the threat categories you want to scan, then press **Scan Now**.
4. Review findings grouped by file. Click a finding for details; double-click to open the file.
5. Use **Export Report…** to save the results as a plain-text file.

> **Note:** This tool performs static pattern matching and is a first-pass aid — not a guarantee of safety. For an additional layer of review, paste the script code into ChatGPT or Claude using the prompt shown in the startup dialog and the Help screen.

---

### ⚠️ A word of caution before you scan

Siril Python scripts are powerful — and that power cuts both ways. A script can do **virtually anything your user account can do** on this machine: delete files and folders, download and execute additional programs, exfiltrate data, modify system settings … everything you can imagine a bad actor might want to do.

We are a friendly and welcoming astronomy community — but *you never truly know* where a script came from or who really wrote it. **Be careful about where you load scripts from.**

This tool gives you an impression of what a script is doing under the hood — potentially dangerous calls, obfuscated code, network access, file deletions, and more. It is a genuine help for spotting suspicious behaviour.

**However:** this is a cat-and-mouse game (as we say in German: *„Hase und Igel"* — hare and hedgehog). A determined bad actor who knows this scanner exists will adapt their script to avoid triggering the rules. **No automated tool can give you a 100 % guarantee.** Use your own judgement, only run scripts from sources you trust, and keep backups of your data.

Stay safe — and clear skies. 🌠

---

### ⚠️ Important — Why you should always do an AI check

This scanner performs **static analysis based on pattern matching** — it looks for known dangerous signatures in the source code. A clever attacker can evade these patterns. **ChatGPT and Claude understand code semantically**, like a human expert would, and can catch threats that pattern-based tools miss entirely. Paste the script into either AI with the prompt below — it takes 30 seconds and could save you from serious harm:

> *"You are an expert Python developer and cybersecurity specialist. Analyze the following Python script designed for the astrophotography program Siril. The script can access Siril data via its API but runs with full user-level OS permissions. Review the code for any malicious, harmful, or risky behavior — including but not limited to: file system access, network calls, data exfiltration, privilege escalation, obfuscated code, or destructive operations. Provide a security risk assessment and a clear recommendation on whether the script is safe to run."*
