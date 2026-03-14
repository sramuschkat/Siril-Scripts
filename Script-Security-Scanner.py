"""
Siril Script Security Scanner
Script Version: 1.1.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script scans all Python scripts in the configured Siril script folders and
reports potentially dangerous patterns: destructive file operations, data theft,
network exfiltration, code execution escalation, persistence mechanisms,
obfuscation techniques, denial-of-service patterns, social engineering tricks,
and supply-chain poisoning.

Run from Siril via Processing → Scripts (or your configured Scripts menu). Siril uses
the script's parent folder name as the menu section; to show under "Utility", place
Script-Security-Scanner.py inside a folder named Utility in one of Siril's Script Storage
Directories (Preferences → Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.1.0 - UI labels each directory with its discovery source
1.0.0 - Initial release
      - AST + regex based scanning for 8 threat categories
      - Dark-themed PyQt6 UI matching Multiple Histogram Viewer style
      - Per-category filtering, severity colouring, exportable plain-text report
"""
from __future__ import annotations

import re
import sys
import traceback
import textwrap
from pathlib import Path
from dataclasses import dataclass, field

import sirilpy as s

s.ensure_installed("PyQt6")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QDialog, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QSizePolicy, QScrollArea, QAbstractItemView, QHeaderView,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

VERSION = "1.1.0"

# Layout constants – match MultipleHistogramViewer
LEFT_PANEL_WIDTH = 320

# ------------------------------------------------------------------------------
# STYLING  (identical palette to MultipleHistogramViewer)
# ------------------------------------------------------------------------------

DARK_STYLESHEET = """
QWidget{background-color:#2b2b2b;color:#e0e0e0;font-size:10pt}

QToolTip{background-color:#333333;color:#ffffff;border:1px solid #88aaff}

QGroupBox{border:1px solid #444444;margin-top:5px;font-weight:bold;border-radius:4px;padding-top:12px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 3px;color:#88aaff}

QLabel{color:#cccccc}

QCheckBox{color:#cccccc;spacing:5px}
QCheckBox::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:3px}
QCheckBox::indicator:checked{background:#285299;border:1px solid #88aaff;image:none}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#ScanButton{background-color:#285299;border:1px solid #3a6fcc}
QPushButton#ScanButton:hover{background-color:#3a6fcc}
QPushButton#ScanButton:disabled{background-color:#333333;color:#666666;border:1px solid #444444}

QTreeWidget{background-color:#1e1e1e;color:#e0e0e0;border:1px solid #444444;
            alternate-background-color:#252525}
QTreeWidget::item:selected{background-color:#285299}
QTreeWidget::item:hover{background-color:#333333}
QHeaderView::section{background-color:#333333;color:#cccccc;border:1px solid #444444;padding:4px}

QScrollBar:vertical{background:#2b2b2b;width:12px}
QScrollBar::handle:vertical{background:#555555;border-radius:5px;min-height:20px}
QScrollBar::handle:vertical:hover{background:#777777}
QScrollBar:horizontal{background:#2b2b2b;height:12px}
QScrollBar::handle:horizontal{background:#555555;border-radius:5px;min-width:20px}
QScrollBar::handle:horizontal:hover{background:#777777}
"""


def _nofocus(w: QWidget | None) -> None:
    """Disable keyboard focus on a widget."""
    if w is not None:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ------------------------------------------------------------------------------
# THREAT CATEGORIES AND PATTERNS
# ------------------------------------------------------------------------------

# Each rule: (category_key, severity, description, regex_pattern)
# severity: "HIGH" | "MEDIUM" | "LOW"
_RULES: list[tuple[str, str, str, str]] = [
    # ── File System — Destructive ──────────────────────────────────────────
    ("fs_destructive", "HIGH",
     "os.remove / os.unlink – deletes user files",
     r"\bos\.(remove|unlink)\s*\("),
    ("fs_destructive", "HIGH",
     "pathlib Path.unlink() – deletes user files",
     r"\.unlink\s*\("),
    ("fs_destructive", "HIGH",
     "shutil.rmtree – wipes entire directory trees",
     r"\bshutil\.rmtree\s*\("),
    ("fs_destructive", "HIGH",
     "os.removedirs – removes directory tree",
     r"\bos\.removedirs\s*\("),
    ("fs_destructive", "MEDIUM",
     "open(..., 'w'/'wb'/'a') – overwrites or truncates files",
     r"\bopen\s*\([^)]*,\s*['\"](?:w|wb|a|ab)['\"]"),

    # ── File System — Data Theft ───────────────────────────────────────────
    ("fs_theft", "HIGH",
     "Access to ~/.ssh keys",
     r"['\"].*\.ssh[/\\](?:id_rsa|id_ed25519|id_ecdsa|authorized_keys|known_hosts)['\"]"),
    ("fs_theft", "HIGH",
     "Access to credential files (.env, .netrc, .git-credentials)",
     r"['\"].*(?:\.env|\.netrc|\.git-credentials|credentials\.json|client_secret)['\"]"),
    ("fs_theft", "HIGH",
     "AWS / GCP / Azure cloud credentials",
     r"['\"].*(?:\.aws[/\\]credentials|\.config[/\\]gcloud|\.azure)['\"]"),
    ("fs_theft", "HIGH",
     "Browser cookie or password store",
     r"['\"].*(?:Cookies|Login\s+Data|cookies\.sqlite|key4\.db|logins\.json)['\"]"),
    ("fs_theft", "MEDIUM",
     "Reading other Siril scripts (potential algorithm theft)",
     r"\bopen\s*\([^)]*\.py[^)]*\)"),
    ("fs_theft", "MEDIUM",
     "Filesystem walk / scandir – scanning for interesting files",
     r"\bos\.walk\s*\(|\bos\.scandir\s*\(|\bPath\s*\([^)]*\)\s*\.rglob\s*\("),

    # ── Network — Exfiltration ─────────────────────────────────────────────
    ("net_exfil", "HIGH",
     "urllib / http.client outbound request",
     r"\burllib\.request\.|urllib\.urlopen\s*\(|http\.client\.(HTTP|HTTPS)Connection"),
    ("net_exfil", "HIGH",
     "requests library outbound call",
     r"\brequests\.(get|post|put|patch|delete|head|request)\s*\("),
    ("net_exfil", "HIGH",
     "ftplib – FTP upload",
     r"\bftplib\b|\bFTP\s*\("),
    ("net_exfil", "HIGH",
     "smtplib – email exfiltration",
     r"\bsmtplib\b|\bSMTP\s*\("),
    ("net_exfil", "HIGH",
     "Raw socket connection",
     r"\bsocket\.socket\s*\(|\bsocket\.connect\s*\("),
    ("net_exfil", "MEDIUM",
     "DNS query – potential DNS tunnelling",
     r"\bsocket\.getaddrinfo\s*\(|\bsocket\.gethostbyname\s*\(|\bdnspython\b|\bdns\.resolver\b"),

    # ── Network — Inbound / Backdoor ──────────────────────────────────────
    ("net_inbound", "HIGH",
     "socket.bind / socket.listen – opens local server or reverse shell",
     r"\bsocket\.bind\s*\(|\b\.listen\s*\(|\bsocket\.accept\s*\("),
    ("net_inbound", "HIGH",
     "http.server / BaseHTTPServer – exposes local HTTP server",
     r"\bhttp\.server\b|\bBaseHTTPServer\b|\bSimpleHTTPRequestHandler\b"),
    ("net_inbound", "HIGH",
     "Download and execute payload (urllib + exec/eval chain)",
     r"urllib.*exec\s*\(|urllib.*eval\s*\(|requests.*exec\s*\(|requests.*eval\s*\("),

    # ── Code Execution — Escalation ───────────────────────────────────────
    ("code_exec", "HIGH",
     "os.system – arbitrary shell command",
     r"\bos\.system\s*\("),
    ("code_exec", "HIGH",
     "subprocess.run / Popen / call – arbitrary process execution",
     r"\bsubprocess\.(run|Popen|call|check_call|check_output|getoutput)\s*\("),
    ("code_exec", "HIGH",
     "eval() – executes dynamic code",
     r"\beval\s*\("),
    ("code_exec", "HIGH",
     "exec() – executes dynamic code",
     r"\bexec\s*\("),
    ("code_exec", "HIGH",
     "compile() – compiles dynamic code object",
     r"\bcompile\s*\("),
    ("code_exec", "HIGH",
     "__import__() – dynamic module import",
     r"\b__import__\s*\("),
    ("code_exec", "MEDIUM",
     "ctypes / cffi – calls C-level system functions",
     r"\bctypes\b|\bcffi\b"),
    ("code_exec", "MEDIUM",
     "sys.path manipulation – hijacks Python imports",
     r"\bsys\.path\.(insert|append)\s*\("),
    ("code_exec", "MEDIUM",
     "Monkey-patching sirilpy – alters library behaviour",
     r"\bsirilpy\.[A-Za-z_]+\s*="),

    # ── Persistence ───────────────────────────────────────────────────────
    ("persistence", "HIGH",
     "crontab write – installs scheduled task (Linux)",
     r"\bcrontab\b|/etc/cron\b|\bcron\.d\b"),
    ("persistence", "HIGH",
     "systemd unit write – installs service (Linux)",
     r"/etc/systemd/|\.service\s*\[Unit\]"),
    ("persistence", "HIGH",
     "Autostart entry (~/.config/autostart)",
     r"autostart[/\\][^'\"]*\.desktop"),
    ("persistence", "HIGH",
     "Shell startup file modification (.bashrc / .zshrc / .profile)",
     r"['\"].*\.(bashrc|zshrc|bash_profile|profile|zprofile)['\"]"),
    ("persistence", "MEDIUM",
     "pip install at runtime – installs packages (possible backdoor)",
     r"\bpip\s+install\b|subprocess.*pip.*install"),
    ("persistence", "MEDIUM",
     "s.ensure_installed() – auto-installs packages",
     r"\bs\.ensure_installed\s*\("),

    # ── Obfuscation ───────────────────────────────────────────────────────
    ("obfuscation", "HIGH",
     "base64.b64decode – decodes hidden payload at runtime",
     r"\bbase64\.b64decode\s*\("),
    ("obfuscation", "HIGH",
     "zlib.decompress – decompresses hidden code",
     r"\bzlib\.decompress\s*\("),
    ("obfuscation", "HIGH",
     "importlib.import_module with computed name – dynamic import",
     r"\bimportlib\.import_module\s*\("),
    ("obfuscation", "MEDIUM",
     "chr() concatenation – builds strings character by character",
     r"\bchr\s*\(\s*\d+\s*\)\s*\+"),
    ("obfuscation", "MEDIUM",
     "Hex / unicode escape sequence in string literal",
     r"['\"](?:[^'\"]*(?:\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})){3,}[^'\"]*['\"]"),
    ("obfuscation", "LOW",
     "codecs.decode / ROT-13 – hides module names",
     r"\bcodecs\.decode\s*\(|rot.?13"),

    # ── Denial of Service ─────────────────────────────────────────────────
    ("dos", "HIGH",
     "Huge numpy allocation – exhausts RAM",
     r"numpy\.zeros\s*\(\s*\(\s*\d{5,}|\bnp\.zeros\s*\(\s*\(\s*\d{5,}"),
    ("dos", "HIGH",
     "os.fork() – fork bomb risk",
     r"\bos\.fork\s*\("),
    ("dos", "MEDIUM",
     "while True: without obvious sleep – potential CPU spin",
     r"\bwhile\s+True\s*:"),

    # ── Social Engineering ────────────────────────────────────────────────
    ("social_eng", "MEDIUM",
     "Fake update / download dialog – tricks user into running malware",
     r"(?i)update\s+available|new\s+version\s+available.*download"),
    ("social_eng", "MEDIUM",
     "Covert image modification (noise / colour shift)",
     r"(?i)add.*noise|random.*noise|color.*shift|colour.*shift|watermark"),

    # ── Supply Chain ──────────────────────────────────────────────────────
    ("supply_chain", "HIGH",
     "Pinning a known-vulnerable package version",
     r"(?i)pip\s+install.*==\s*\d"),
    ("supply_chain", "MEDIUM",
     "Installing package from non-PyPI index (--index-url / -i flag)",
     r"(?i)pip.*--index-url|pip.*-i\s+http"),
]

CATEGORY_LABELS: dict[str, str] = {
    "fs_destructive": "File System — Destructive",
    "fs_theft":       "File System — Data Theft",
    "net_exfil":      "Network — Exfiltration",
    "net_inbound":    "Network — Inbound / Backdoor",
    "code_exec":      "Code Execution — Escalation",
    "persistence":    "Persistence",
    "obfuscation":    "Obfuscation",
    "dos":            "Denial of Service",
    "social_eng":     "Social Engineering",
    "supply_chain":   "Supply Chain",
}

SEVERITY_COLOR: dict[str, str] = {
    "HIGH":   "#ff5555",
    "MEDIUM": "#ffaa33",
    "LOW":    "#88aaff",
}

# Pre-compile all regex patterns once
_COMPILED_RULES: list[tuple[str, str, str, re.Pattern]] = [
    (cat, sev, desc, re.compile(pat))
    for cat, sev, desc, pat in _RULES
]


# ------------------------------------------------------------------------------
# SCANNING LOGIC
# ------------------------------------------------------------------------------

@dataclass
class Finding:
    file_path: Path
    line_no: int
    line_text: str
    category: str
    severity: str
    description: str


def _get_siril_script_dirs() -> list[tuple[Path, str]]:
    """
    Return ``(directory_path, source_label)`` tuples for all existing Siril
    script directories, probing the sirilpy interface first, then falling back
    to well-known default locations.
    """
    home = Path.home()
    found: list[tuple[Path, str]] = []

    # ── 1. sirilpy interface (if Siril exposes paths programmatically) ────────
    try:
        iface = s.SirilInterface()
        for attr in ("script_paths", "get_script_paths", "scriptPaths"):
            fn = getattr(iface, attr, None)
            if callable(fn):
                result = fn()
                if isinstance(result, list):
                    found.extend((Path(p), "sirilpy interface") for p in result)
                break
    except Exception:
        pass

    # ── 2. Well-known fallback locations ─────────────────────────────────────
    fallbacks: list[tuple[Path, str]] = [
        (home / ".siril" / "scripts",                           "fallback"),
        (home / "siril" / "scripts",                            "fallback"),
        (home / "Documents" / "siril" / "scripts",              "fallback"),
        (Path("/usr/share/siril/scripts"),                       "fallback"),
        (Path("/usr/local/share/siril/scripts"),                 "fallback"),
        (home / "AppData" / "Roaming" / "siril" / "scripts",    "fallback"),
        (home / "AppData" / "Local"   / "siril" / "scripts",    "fallback"),
        (home / "Library" / "Application Support" / "siril" / "scripts", "fallback"),
    ]
    found.extend(fallbacks)

    # ── Deduplicate, keep only directories that actually exist ────────────────
    seen: set[Path] = set()
    result: list[tuple[Path, str]] = []
    for p, label in found:
        if p not in seen:
            seen.add(p)
            if p.is_dir():
                result.append((p, label))
    return result


def _collect_python_scripts(dirs: list[tuple[Path, str]]) -> list[Path]:
    """Collect all .py files recursively from the given (directory, label) pairs."""
    scripts: list[Path] = []
    seen: set[Path] = set()
    for d, _label in dirs:
        for p in sorted(d.rglob("*.py")):
            if p not in seen:
                seen.add(p)
                scripts.append(p)
    return scripts


def _scan_file(path: Path, active_categories: set[str]) -> list[Finding]:
    """Scan a single file and return all findings."""
    findings: list[Finding] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    lines = source.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for cat, sev, desc, pattern in _COMPILED_RULES:
            if cat not in active_categories:
                continue
            if pattern.search(line):
                findings.append(Finding(
                    file_path=path,
                    line_no=lineno,
                    line_text=line.strip(),
                    category=cat,
                    severity=sev,
                    description=desc,
                ))
    return findings


class ScanWorker(QThread):
    """Background thread that scans script files and emits progress."""
    progress = pyqtSignal(int, int, str)   # scanned, total, filename
    finished = pyqtSignal(list, list)       # findings, scanned_paths

    def __init__(self, script_dirs: list[tuple[Path, str]], active_categories: set[str]):
        super().__init__()
        self._dirs = script_dirs
        self._categories = active_categories

    def run(self) -> None:
        scripts = _collect_python_scripts(self._dirs)
        total = len(scripts)
        all_findings: list[Finding] = []
        for idx, script in enumerate(scripts):
            self.progress.emit(idx + 1, total, script.name)
            all_findings.extend(_scan_file(script, self._categories))
        self.finished.emit(all_findings, scripts)


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class SecurityScannerWindow(QMainWindow):
    """Main application window for the Siril Script Security Scanner."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Siril Script Security Scanner {VERSION}")
        self.setMinimumSize(1100, 700)
        self._worker: ScanWorker | None = None
        self._findings: list[Finding] = []
        self._scanned_paths: list[Path] = []
        self._scan_dirs: list[tuple[Path, str]] = []
        self._init_ui()
        QTimer.singleShot(100, self._refresh_dirs)

    # ── UI construction ────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), stretch=1)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Title
        title = QLabel(f"Script Security Scanner {VERSION}")
        title.setStyleSheet(
            "font-size:16pt;font-weight:bold;color:#88aaff;margin-top:5px;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)

        layout.addWidget(self._build_dirs_group())
        layout.addWidget(self._build_categories_group())

        # Scan button
        self.btn_scan = QPushButton("Scan Now")
        self.btn_scan.setObjectName("ScanButton")
        _nofocus(self.btn_scan)
        self.btn_scan.clicked.connect(self._start_scan)
        layout.addWidget(self.btn_scan)

        # Export button
        btn_export = QPushButton("Export Report…")
        _nofocus(btn_export)
        btn_export.clicked.connect(self._export_report)
        layout.addWidget(btn_export)

        layout.addStretch()

        btn_help = QPushButton("Help")
        _nofocus(btn_help)
        btn_help.clicked.connect(self._show_help_dialog)
        layout.addWidget(btn_help)

        btn_close = QPushButton("Close")
        btn_close.setObjectName("CloseButton")
        _nofocus(btn_close)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return left

    def _build_dirs_group(self) -> QGroupBox:
        g = QGroupBox("Script Directories")
        layout = QVBoxLayout(g)

        self.lbl_dirs = QLabel("Searching…")
        self.lbl_dirs.setWordWrap(True)
        self.lbl_dirs.setStyleSheet("font-size:8pt;color:#aaaaaa;")
        layout.addWidget(self.lbl_dirs)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Directory…")
        _nofocus(btn_add)
        btn_add.clicked.connect(self._add_directory)
        btn_row.addWidget(btn_add)

        btn_paste = QPushButton("Paste Paths")
        _nofocus(btn_paste)
        btn_paste.setToolTip(
            "Paste one or more script directory paths from the clipboard.\n"
            "Separate multiple paths with newlines, commas, semicolons, or colons."
        )
        btn_paste.clicked.connect(self._paste_paths)
        btn_row.addWidget(btn_paste)

        layout.addLayout(btn_row)

        return g

    def _build_categories_group(self) -> QGroupBox:
        g = QGroupBox("Scan Categories")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(2)

        self._category_checks: dict[str, QCheckBox] = {}
        for key, label in CATEGORY_LABELS.items():
            chk = QCheckBox(label)
            chk.setChecked(True)
            _nofocus(chk)
            self._category_checks[key] = chk
            inner_layout.addWidget(chk)

        scroll.setWidget(inner)
        layout = QVBoxLayout(g)
        layout.addWidget(scroll)

        # Select / deselect all
        row = QHBoxLayout()
        btn_all = QPushButton("All")
        _nofocus(btn_all)
        btn_all.clicked.connect(lambda: self._set_all_categories(True))
        btn_none = QPushButton("None")
        _nofocus(btn_none)
        btn_none.clicked.connect(lambda: self._set_all_categories(False))
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        layout.addLayout(row)

        return g

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Status bar
        self.lbl_status = QLabel("Ready. Configure directories and press Scan Now.")
        self.lbl_status.setStyleSheet("color:#88aaff;font-weight:bold;")
        layout.addWidget(self.lbl_status)

        # Summary row
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color:#cccccc;font-size:9pt;")
        layout.addWidget(self.lbl_summary)

        # Results tree
        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Script / Line", "Risk", "Issue"])
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 240)
        layout.addWidget(self.tree, stretch=1)

        # Detail panel
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(120)
        self.detail.setStyleSheet(
            "background:#1e1e1e;color:#e0e0e0;font-family:Courier New,Courier,monospace;font-size:9pt;"
        )
        self.detail.setPlaceholderText("Click a finding to see details…")
        layout.addWidget(self.detail)

        self.tree.currentItemChanged.connect(self._on_item_changed)

        return right

    # ── Directory management ───────────────────────────────────────────────

    def _refresh_dirs(self) -> None:
        self._scan_dirs = _get_siril_script_dirs()
        self._update_dirs_label()

    def _update_dirs_label(self) -> None:
        if self._scan_dirs:
            lines: list[str] = []
            for p, label in self._scan_dirs:
                src = "" if label == "fallback" else f"  [{label}]"
                lines.append(f"{p}{src}")
            text = "\n".join(lines)
        else:
            text = "No Siril script directories found.\nUse 'Add Directory…' to add one."
        self.lbl_dirs.setText(text)

    def _add_directory(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Script Directory")
        if chosen:
            p = Path(chosen)
            existing_paths = {d for d, _ in self._scan_dirs}
            if p not in existing_paths:
                self._scan_dirs.append((p, "user-added"))
                self._update_dirs_label()

    @staticmethod
    def _split_pasted_text(text: str) -> list[str]:
        """
        Split clipboard text into individual path strings.
        Handles newlines, commas, semicolons, and Unix-style colon separators.
        Colons that are part of a Windows drive letter (e.g. ``C:``) are preserved.
        """
        result: list[str] = []
        for part in re.split(r"[\n,;]+", text):
            part = part.strip().strip('"').strip("'")
            if not part:
                continue
            # Split on colons that are NOT a Windows drive letter (``C:``).
            # A drive-letter colon is always at index 1 preceded by a single letter.
            buf = ""
            for i, ch in enumerate(part):
                if ch == ":" and not (i == 1 and part[0].isalpha()):
                    if buf:
                        result.append(buf.strip().strip('"').strip("'"))
                    buf = ""
                else:
                    buf += ch
            if buf.strip():
                result.append(buf.strip().strip('"').strip("'"))
        return result

    def _paste_paths(self) -> None:
        """Add directories from clipboard text (newline-, comma-, semicolon-, or colon-separated)."""
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            QMessageBox.information(self, "Clipboard Empty", "No text found in clipboard.")
            return
        existing_paths = {d for d, _ in self._scan_dirs}
        added: list[str] = []
        skipped: list[str] = []
        for raw in self._split_pasted_text(text):
            if not raw:
                continue
            p = Path(raw).expanduser()
            if p in existing_paths:
                continue
            if p.is_dir():
                self._scan_dirs.append((p, "pasted"))
                existing_paths.add(p)
                added.append(str(p))
            else:
                skipped.append(str(p))
        self._update_dirs_label()
        msg_parts: list[str] = []
        if added:
            msg_parts.append(f"Added {len(added)} director{'y' if len(added) == 1 else 'ies'}:\n" + "\n".join(added))
        if skipped:
            msg_parts.append(f"Skipped {len(skipped)} (not found / not a directory):\n" + "\n".join(skipped))
        if not msg_parts:
            QMessageBox.information(self, "No New Paths", "All pasted paths were already in the list.")
        else:
            QMessageBox.information(self, "Paste Paths Result", "\n\n".join(msg_parts))

    # ── Category helpers ───────────────────────────────────────────────────

    def _active_categories(self) -> set[str]:
        return {k for k, chk in self._category_checks.items() if chk.isChecked()}

    def _set_all_categories(self, state: bool) -> None:
        for chk in self._category_checks.values():
            chk.setChecked(state)

    # ── Scanning ──────────────────────────────────────────────────────────

    def _start_scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        active = self._active_categories()
        if not active:
            QMessageBox.warning(self, "No Categories", "Please select at least one scan category.")
            return
        if not self._scan_dirs:
            QMessageBox.warning(
                self, "No Directories",
                "No script directories configured.\nUse 'Add Directory…' to add at least one folder."
            )
            return

        self.tree.clear()
        self.detail.clear()
        self.lbl_summary.setText("")
        self.lbl_status.setText("Scanning…")
        self.btn_scan.setEnabled(False)

        self._worker = ScanWorker(self._scan_dirs, active)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def _on_scan_progress(self, done: int, total: int, filename: str) -> None:
        self.lbl_status.setText(f"Scanning ({done}/{total}): {filename}")

    def _on_scan_finished(self, findings: list[Finding], scripts: list[Path]) -> None:
        self._findings = findings
        self._scanned_paths = scripts
        self.btn_scan.setEnabled(True)
        self._populate_tree(findings)

        n_files = len(scripts)
        n_findings = len(findings)
        n_high = sum(1 for f in findings if f.severity == "HIGH")
        n_med  = sum(1 for f in findings if f.severity == "MEDIUM")
        n_low  = sum(1 for f in findings if f.severity == "LOW")

        # Identify directories that were searched but contained no Python files
        empty_dirs = [
            str(p) for p, _ in self._scan_dirs
            if not any(sp.is_relative_to(p) for sp in scripts)
        ]
        empty_note = (
            f"   |   No .py files in: {', '.join(empty_dirs)}" if empty_dirs else ""
        )

        if n_findings == 0:
            self.lbl_status.setText(f"Scan complete — {n_files} script(s) checked, no issues found.")
            self.lbl_summary.setText(empty_note.lstrip("   |   ") if empty_note else "")
        else:
            self.lbl_status.setText(
                f"Scan complete — {n_files} script(s) checked, {n_findings} issue(s) found."
            )
            parts = []
            if n_high:   parts.append(f"🔴 {n_high} HIGH")
            if n_med:    parts.append(f"🟠 {n_med} MEDIUM")
            if n_low:    parts.append(f"🔵 {n_low} LOW")
            summary = "   ".join(parts)
            if empty_note:
                summary += empty_note
            self.lbl_summary.setText(summary)

    def _populate_tree(self, findings: list[Finding]) -> None:
        self.tree.clear()
        if not findings:
            placeholder = QTreeWidgetItem(self.tree, ["No issues detected.", "", ""])
            placeholder.setForeground(0, QColor("#88aa88"))
            return

        # Group by file path
        by_file: dict[Path, list[Finding]] = {}
        for f in findings:
            by_file.setdefault(f.file_path, []).append(f)

        for path, file_findings in sorted(by_file.items()):
            # File-level row: filename bold, directory in col 2
            file_item = QTreeWidgetItem(self.tree)
            file_item.setText(0, path.name)
            file_item.setToolTip(0, str(path))
            count = len(file_findings)
            worst = "HIGH" if any(x.severity == "HIGH" for x in file_findings) else \
                    "MEDIUM" if any(x.severity == "MEDIUM" for x in file_findings) else "LOW"
            file_item.setText(1, f"{count} issue(s)")
            file_item.setText(2, str(path.parent))
            file_item.setForeground(0, QColor("#88aaff"))
            file_item.setForeground(1, QColor(SEVERITY_COLOR[worst]))
            file_item.setForeground(2, QColor("#777777"))
            font = file_item.font(0)
            font.setBold(True)
            file_item.setFont(0, font)
            file_item.setExpanded(True)

            for finding in sorted(file_findings, key=lambda x: x.line_no):
                child = QTreeWidgetItem(file_item)
                child.setText(0, f"  Line {finding.line_no}")
                child.setText(1, finding.severity)
                # Issue column: category label + short description
                issue = f"{CATEGORY_LABELS.get(finding.category, finding.category)}  —  {finding.description}"
                child.setText(2, issue)
                color = QColor(SEVERITY_COLOR.get(finding.severity, "#cccccc"))
                child.setForeground(0, color)
                child.setForeground(1, color)
                child.setForeground(2, QColor("#cccccc"))
                child.setData(0, Qt.ItemDataRole.UserRole, finding)

    def _on_item_changed(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self.detail.clear()
            return
        finding: Finding | None = current.data(0, Qt.ItemDataRole.UserRole)
        if finding is None:
            self.detail.clear()
            return
        sev_color = SEVERITY_COLOR.get(finding.severity, "#cccccc")
        self.detail.setHtml(
            f"<b style='color:{sev_color};'>{finding.severity}</b>"
            f"&nbsp;&nbsp;<span style='color:#88aaff;'>{CATEGORY_LABELS.get(finding.category, finding.category)}</span>"
            f"&nbsp;&nbsp;<span style='color:#aaaaaa;font-size:8pt;'>{finding.file_path.name} · Line {finding.line_no}</span><br>"
            f"<span style='color:#e0e0e0;font-size:9pt;'>{finding.description}</span><br>"
            f"<span style='color:#888888;font-size:8pt;'>{finding.file_path.parent}</span><br>"
            f"<span style='font-family:Courier New,Courier,monospace;color:#ffcc88;font-size:9pt;'>{finding.line_text}</span>"
        )

    # ── Export ────────────────────────────────────────────────────────────

    def _export_report(self) -> None:
        if not self._findings and not self._scanned_paths:
            QMessageBox.information(self, "Nothing to Export", "Run a scan first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "siril_security_report.txt",
            "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        lines: list[str] = [
            "Siril Script Security Scanner — Report",
            f"Version: {VERSION}",
            "=" * 72,
            f"Scripts scanned: {len(self._scanned_paths)}",
            f"Total findings:  {len(self._findings)}",
            f"HIGH:   {sum(1 for f in self._findings if f.severity == 'HIGH')}",
            f"MEDIUM: {sum(1 for f in self._findings if f.severity == 'MEDIUM')}",
            f"LOW:    {sum(1 for f in self._findings if f.severity == 'LOW')}",
            "",
        ]
        by_file: dict[Path, list[Finding]] = {}
        for f in self._findings:
            by_file.setdefault(f.file_path, []).append(f)
        for p, flist in sorted(by_file.items()):
            lines.append(f"\nFILE: {p}")
            lines.append("-" * 72)
            for finding in sorted(flist, key=lambda x: x.line_no):
                lines.append(
                    f"  [{finding.severity:<6}] Line {finding.line_no:<5} "
                    f"{CATEGORY_LABELS.get(finding.category, finding.category)}"
                )
                lines.append(f"           Rule: {finding.description}")
                lines.append(f"           Code: {finding.line_text[:100]}")
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except OSError as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    # ── Help dialog ───────────────────────────────────────────────────────

    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Script Security Scanner — Help")
        dlg.setMinimumSize(620, 560)
        layout = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(
            "Script Security Scanner — Help\n"
            "==============================\n\n"
            "This script was developed by Sven Ramuschkat.\n"
            "Web: www.svenesis.org\n"
            "GitHub: https://github.com/sramuschkat/Siril-Scripts\n\n"
            "1. PURPOSE\n"
            "----------\n"
            "Scans all Python scripts in your configured Siril script folders for\n"
            "potentially dangerous patterns across 10 threat categories:\n\n"
            "  • File System — Destructive  (deletes/overwrites files)\n"
            "  • File System — Data Theft   (reads credentials, SSH keys, etc.)\n"
            "  • Network — Exfiltration     (sends data to remote servers)\n"
            "  • Network — Inbound/Backdoor (opens listening sockets, reverse shells)\n"
            "  • Code Execution — Escalation (os.system, eval, exec, subprocess…)\n"
            "  • Persistence                (crontab, systemd, startup files)\n"
            "  • Obfuscation                (base64, chr(), hex escapes, zlib)\n"
            "  • Denial of Service          (huge allocations, fork bombs, spin loops)\n"
            "  • Social Engineering         (fake dialogs, covert image tampering)\n"
            "  • Supply Chain               (installing packages at runtime)\n\n"
            "2. HOW TO USE\n"
            "-------------\n"
            "The scanner probes the sirilpy interface for script directories and\n"
            "falls back to well-known default locations automatically.\n"
            "Each discovered directory shows its source in brackets.\n"
            "Use 'Add Directory…' to add extras.\n"
            "Select the categories you want to scan, then press 'Scan Now'.\n"
            "Results appear grouped by file. Click any finding for details.\n\n"
            "3. SEVERITY LEVELS\n"
            "------------------\n"
            "  RED    HIGH   — Likely dangerous; review immediately.\n"
            "  ORANGE MEDIUM — Suspicious; may be legitimate but warrants review.\n"
            "  BLUE   LOW    — Informational; unlikely to be harmful on its own.\n\n"
            "4. IMPORTANT CAVEATS\n"
            "--------------------\n"
            "The scanner uses regex pattern matching, not full code-flow analysis.\n"
            "False positives are possible — a flagged pattern does not automatically\n"
            "mean the script is malicious. Always review flagged code in context.\n"
            "False negatives are also possible — obfuscated malware may evade\n"
            "pattern matching entirely. This tool is a first-pass aid, not a\n"
            "guarantee of safety.\n\n"
            "5. EXPORT\n"
            "---------\n"
            "Click 'Export Report…' to save the findings as a plain-text file.\n\n"
            "6. REQUIREMENTS\n"
            "---------------\n"
            "Siril 1.4+ with Python script support, sirilpy (bundled with Siril),\n"
            "and PyQt6 (installed automatically when the script runs).\n\n"
            "For more details and menu setup, see the repository README at\n"
            "https://github.com/sramuschkat/Siril-Scripts"
        )
        te.setStyleSheet("font-size:10pt;color:#e0e0e0;background:#2b2b2b;")
        layout.addWidget(te)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    try:
        win = SecurityScannerWindow()
        win.showMaximized()
        try:
            iface = s.SirilInterface()
            iface.log(f"Script Security Scanner v{VERSION} loaded.")
        except Exception:
            pass
        return app.exec()
    except Exception as e:
        QMessageBox.critical(
            None,
            "Script Security Scanner Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
