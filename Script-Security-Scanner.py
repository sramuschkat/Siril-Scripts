"""
Siril Script Security Scanner
Script Version: 2.0.0
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
2.0.0 - Architecture overhaul: Severity enum, rule_id keys, suppressor pipeline
      - 7 new detection rules (pickle, yaml, environ, webbrowser, shutil copy, getattr, tempfile+subprocess)
      - Evasion resistance: multi-line continuation, docstring awareness, import alias expansion, self-exclude
      - False positive reduction: re.compile, commented lines, print(), config writes, SOCK_DGRAM, macOS open
      - Performance: file read caching, pre-compiled regexes
      - UX: severity filter counts, category combo filter, export with explanations, don't-show-again, double-click open
      - Security: HTML escaping, ReDoS protection, path traversal guard
1.1.0 - UI labels each directory with its discovery source
1.0.0 - Initial release
      - AST + regex based scanning for 8 threat categories
      - Dark-themed PyQt6 UI matching Multiple Histogram Viewer style
      - Per-category filtering, severity colouring, exportable plain-text report
"""
from __future__ import annotations

import base64
import functools
import html
import json
import re
import subprocess as _subprocess_mod
import sys
import traceback
import textwrap
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

import sirilpy as s

s.ensure_installed("PyQt6")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QDialog, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QSizePolicy, QScrollArea, QAbstractItemView, QHeaderView,
    QFileDialog, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QFont, QDesktopServices

VERSION = "2.0.0"

# Layout / sizing constants
LEFT_PANEL_WIDTH = 320
DETAIL_MIN_HEIGHT = 220
DETAIL_HEIGHT_NORMAL = 350
DETAIL_HEIGHT_IMAGE = 500
MAX_LINE_LENGTH = 5000  # ReDoS protection: skip lines longer than this

# Preference file for "don't show again" etc.
_PREFS_PATH = Path.home() / ".config" / "siril-scanner" / "prefs.json"


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

QComboBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #555555;border-radius:3px;padding:3px 6px}
QComboBox::drop-down{border:none}
QComboBox QAbstractItemView{background:#2b2b2b;color:#e0e0e0;selection-background-color:#285299}

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
# THREAT CATEGORIES AND PATTERNS  (E5: each rule has a unique rule_id)
# ------------------------------------------------------------------------------

# Each rule: (category_key, severity, description, regex_pattern, rule_id)
_RULES: list[tuple[str, str, str, str, str]] = [
    # ── File System — Destructive ──────────────────────────────────────────
    ("fs_destructive", "HIGH",
     "os.remove / os.unlink – deletes user files",
     r"\bos\.(remove|unlink)\s*\(", "fs_remove"),
    ("fs_destructive", "HIGH",
     "pathlib Path.unlink() – deletes user files",
     r"\b\w+\.unlink\s*\(", "fs_unlink"),  # A1: require preceding identifier
    ("fs_destructive", "HIGH",
     "shutil.rmtree – wipes entire directory trees",
     r"\bshutil\.rmtree\s*\(", "fs_rmtree"),
    ("fs_destructive", "HIGH",
     "os.removedirs – removes directory tree",
     r"\bos\.removedirs\s*\(", "fs_removedirs"),
    ("fs_destructive", "MEDIUM",
     "open(..., 'w'/'wb'/'a') – overwrites or truncates files",
     r"\bopen\s*\([^)]*(?:,\s*|mode\s*=\s*)['\"](?:w|wb|a|ab)['\"]", "fs_open_write"),

    ("fs_destructive", "HIGH",
     "os.symlink – creates symbolic link (can redirect file access)",
     r"\bos\.symlink\s*\(", "fs_symlink"),

    # ── File System — Data Theft ───────────────────────────────────────────
    ("fs_theft", "HIGH",
     "Access to ~/.ssh keys",
     r"['\"].*\.ssh[/\\](?:id_rsa|id_ed25519|id_ecdsa|authorized_keys|known_hosts)['\"]", "fs_ssh"),
    ("fs_theft", "HIGH",
     "Access to credential files (.env, .netrc, .git-credentials)",
     r"['\"].*(?:\.env|\.netrc|\.git-credentials|credentials\.json|client_secret)['\"]", "fs_creds"),
    ("fs_theft", "HIGH",
     "AWS / GCP / Azure cloud credentials",
     r"['\"].*(?:\.aws[/\\]credentials|\.config[/\\]gcloud|\.azure)['\"]", "fs_cloud"),
    ("fs_theft", "HIGH",
     "Browser cookie or password store",
     r"['\"].*(?:Cookies|Login\s+Data|cookies\.sqlite|key4\.db|logins\.json)['\"]", "fs_browser"),
    ("fs_theft", "MEDIUM",
     "Reading other Siril scripts (potential algorithm theft)",
     r"\bopen\s*\([^)]*\.py[^)]*\)", "fs_read_py"),
    ("fs_theft", "MEDIUM",
     "Filesystem walk / scandir – scanning for interesting files",
     r"\bos\.walk\s*\(|\bos\.scandir\s*\(|\bPath\s*\([^)]*\)\s*\.rglob\s*\(", "fs_walk"),
    ("fs_theft", "MEDIUM",
     "os.environ access – reads/modifies environment variables",
     r"\bos\.environ\b|\bos\.getenv\s*\(", "fs_environ"),  # B2
    ("fs_theft", "MEDIUM",
     "shutil.copy/move – copies or moves files",
     r"\bshutil\.(copy2?|copytree|move)\s*\(", "fs_copy"),  # B4
    ("fs_theft", "HIGH",
     "/proc/self/ access – reads process memory, maps, environment (Linux)",
     r"/proc/self/|/proc/\d+/", "fs_proc_self"),

    # ── Network — Exfiltration ─────────────────────────────────────────────
    ("net_exfil", "HIGH",
     "urllib / http.client outbound request",
     r"\burllib\.request\.|urllib\.urlopen\s*\(|http\.client\.(HTTP|HTTPS)Connection", "net_urllib"),
    ("net_exfil", "HIGH",
     "requests library outbound call",
     r"\brequests\.(get|post|put|patch|delete|head|request)\s*\(", "net_requests"),
    ("net_exfil", "HIGH",
     "ftplib – FTP upload",
     r"\bftplib\b|\bFTP\s*\(", "net_ftp"),
    ("net_exfil", "HIGH",
     "smtplib – email exfiltration",
     r"\bsmtplib\b|\bSMTP\s*\(", "net_smtp"),
    ("net_exfil", "HIGH",
     "Raw socket connection",
     r"\bsocket\.socket\s*\(|\bsocket\.connect\s*\(", "net_socket"),
    ("net_exfil", "MEDIUM",
     "DNS query – potential DNS tunnelling",
     r"\bsocket\.getaddrinfo\s*\(|\bsocket\.gethostbyname\s*\(|\bdnspython\b|\bdns\.resolver\b", "net_dns"),

    # ── Network — Inbound / Backdoor ──────────────────────────────────────
    ("net_inbound", "HIGH",
     "socket.bind / socket.listen – opens local server or reverse shell",
     r"\bsocket\.bind\s*\(|\b\.listen\s*\(|\bsocket\.accept\s*\(", "net_bind"),
    ("net_inbound", "HIGH",
     "http.server / BaseHTTPServer – exposes local HTTP server",
     r"\bhttp\.server\b|\bBaseHTTPServer\b|\bSimpleHTTPRequestHandler\b", "net_httpserver"),
    ("net_inbound", "HIGH",
     "Download and execute payload (urllib + exec/eval chain)",
     r"urllib.*exec\s*\(|urllib.*eval\s*\(|requests.*exec\s*\(|requests.*eval\s*\(", "net_dl_exec"),

    # ── Code Execution — Escalation ───────────────────────────────────────
    ("code_exec", "HIGH",
     "os.system – arbitrary shell command",
     r"\bos\.system\s*\(", "code_system"),
    ("code_exec", "HIGH",
     "subprocess.run / Popen / call – arbitrary process execution",
     r"\bsubprocess\.(run|Popen|call|check_call|check_output|getoutput)\s*\(", "code_subprocess"),
    ("code_exec", "HIGH",
     "eval() – executes dynamic code",
     r"(?<!\.)\beval\s*\(", "code_eval"),
    ("code_exec", "HIGH",
     "exec() – executes dynamic code",
     r"(?<!\.)\bexec\s*\(", "code_exec_fn"),
    ("code_exec", "HIGH",
     "compile() – compiles dynamic code object",
     r"(?<!re\.)(?<!regex\.)\bcompile\s*\(", "code_compile"),
    ("code_exec", "HIGH",
     "__import__() – dynamic module import",
     r"\b__import__\s*\(", "code_dyn_import"),
    ("code_exec", "HIGH",
     "pickle/torch/joblib.load – arbitrary code execution via deserialization",
     r"\bpickle\.loads?\s*\(|\btorch\.load\s*\(|\bjoblib\.load\s*\(", "code_pickle"),  # B1
    ("code_exec", "HIGH",
     "yaml.load() without SafeLoader – arbitrary code execution",
     r"\byaml\.load\s*\((?!.*SafeLoader)(?!.*safe_load)(?!.*BaseLoader)(?!.*FullLoader)(?!.*yaml\.Loader)(?!.*yaml\.UnsafeLoader)", "code_yaml"),  # B7
    ("code_exec", "MEDIUM",
     "yaml.load() with unsafe Loader – yaml.Loader allows arbitrary execution",
     r"\byaml\.load\s*\(.*Loader\s*=\s*yaml\.(?:Loader|UnsafeLoader|FullLoader)\b", "code_yaml_unsafe"),
    ("code_exec", "MEDIUM",
     "ctypes / cffi – calls C-level system functions",
     r"\bctypes\.(CDLL|WinDLL|windll|cdll|cast|pointer|POINTER|CFUNCTYPE)\b|\bcffi\b", "code_ctypes"),  # A2
    ("code_exec", "MEDIUM",
     "sys.path manipulation – hijacks Python imports",
     r"\bsys\.path\.(insert|append)\s*\(|\bsys\.path\s*=", "code_syspath"),
    ("code_exec", "MEDIUM",
     "Monkey-patching sirilpy – alters library behaviour",
     r"\bsirilpy\.[A-Za-z_]+\s*=", "code_monkeypatch"),
    ("code_exec", "MEDIUM",
     "getattr()/setattr() – reflective attribute access",
     r"\b(?:get|set|del)attr\s*\([^)]*,\s*['\"]", "code_reflect"),  # B6
    ("code_exec", "LOW",
     "webbrowser.open() – opens URL in user's browser",
     r"\bwebbrowser\.open\s*\(", "code_webbrowser"),  # B3
    ("code_exec", "HIGH",
     "__builtins__ access – bypasses name-based detection of eval/exec/compile",
     r"\b__builtins__\s*[\[.]|__builtins__\s*\.\s*__dict__", "code_builtins"),
    ("code_exec", "HIGH",
     "vars()/__dict__ attribute access – indirect function call bypass",
     r"\bvars\s*\([^)]+\)\s*\[|\b\w+\.__dict__\s*\[", "code_vars_dict"),
    ("code_exec", "HIGH",
     "getattr()/setattr() with variable argument – reflective access evading literal detection",
     r"\b(?:get|set|del)attr\s*\([^,]+,\s*[a-zA-Z_]\w*\s*\)", "code_reflect_var"),
    ("code_exec", "HIGH",
     "pty.spawn – spawns interactive shell (reverse shell risk)",
     r"\bpty\.spawn\s*\(", "code_pty"),
    ("code_exec", "HIGH",
     "multiprocessing.Process – executes code in child process",
     r"\bmultiprocessing\.Process\s*\(", "code_multiproc"),
    ("code_exec", "HIGH",
     "importlib.util – loads arbitrary Python module from file path",
     r"\bimportlib\.util\.(?:spec_from_file_location|module_from_spec|find_spec)\s*\(", "code_importlib_util"),
    ("code_exec", "MEDIUM",
     "os.kill / signal – sends signal to a process (can terminate processes)",
     r"\bos\.kill\s*\(|\bsignal\.(?:SIGKILL|SIGTERM|SIGSTOP)\b|\bsignal\.signal\s*\(", "code_kill"),
    ("code_exec", "MEDIUM",
     "mmap – direct memory-mapped file access",
     r"\bmmap\.mmap\s*\(", "code_mmap"),
    ("code_exec", "MEDIUM",
     "__getattr__ / __reduce__ / descriptor / metaclass hook – enables dynamic dispatch or silent code execution",
     r"\bdef\s+__(?:getattr|getattribute|reduce|reduce_ex|set_name|init_subclass|enter|exit|code)__\s*\(", "code_magic_methods"),
    ("code_exec", "MEDIUM",
     "String concatenation in __import__ or getattr – hides function/module names",
     r"""(?:__import__|getattr)\s*\([^)]*['"][^'"]*['"]\s*\+""", "code_str_concat"),
    ("code_exec", "HIGH",
     "atexit.register – executes code at interpreter shutdown (silent persistence)",
     r"\batexit\.register\s*\(", "code_atexit"),
    ("code_exec", "MEDIUM",
     "weakref callback – executes code when object is garbage-collected",
     r"\bweakref\.(?:ref|proxy)\s*\([^,]+,\s*", "code_weakref"),
    ("code_exec", "HIGH",
     "sys.settrace / sys.setprofile – instruments all function calls (keylogger/debugger risk)",
     r"\bsys\.(?:settrace|setprofile)\s*\(", "code_settrace"),
    ("code_exec", "HIGH",
     "sys._getframe / frame.f_builtins – stack frame introspection (sandbox escape)",
     r"\bsys\._getframe\s*\(|\bf_builtins\b|\bf_locals\b|\bf_globals\b", "code_getframe"),
    ("code_exec", "HIGH",
     "asyncio.create_subprocess – executes shell commands asynchronously",
     r"\basyncio\.create_subprocess_(?:exec|shell)\s*\(", "code_asyncio_proc"),
    ("code_exec", "MEDIUM",
     "threading.Thread – runs code in a background thread (can hide activity)",
     r"\bthreading\.Thread\s*\(", "code_threading"),
    ("code_exec", "HIGH",
     "marshal.loads / types.CodeType / types.FunctionType – low-level code object creation",
     r"\bmarshal\.loads?\s*\(|\btypes\.CodeType\s*\(|\btypes\.FunctionType\s*\(", "code_marshal"),
    ("code_exec", "HIGH",
     "type() with 3 args – dynamic class creation (can inject __init__, descriptors, metaclass hooks)",
     r"\btype\s*\(\s*['\"][^'\"]+['\"]\s*,\s*\(", "code_type_create"),
    ("code_exec", "HIGH",
     "sys.meta_path manipulation – hijacks the import system",
     r"\bsys\.meta_path\b", "code_meta_path"),
    ("code_exec", "MEDIUM",
     "site.getsitepackages / site.getusersitepackages – locates package directories for injection",
     r"\bsite\.(?:getsitepackages|getusersitepackages)\s*\(", "code_site_packages"),
    ("code_exec", "LOW",
     "Custom logging.Formatter subclass – can execute code on every log message",
     r"\bclass\s+\w+\s*\(\s*logging\.Formatter\s*\)", "code_log_formatter"),

    # ── Persistence ───────────────────────────────────────────────────────
    ("persistence", "HIGH",
     "crontab write – installs scheduled task (Linux)",
     r"\bcrontab\b|/etc/cron\b|\bcron\.d\b", "persist_cron"),
    ("persistence", "HIGH",
     "systemd unit write – installs service (Linux)",
     r"/etc/systemd/|\.service\s*\[Unit\]", "persist_systemd"),
    ("persistence", "HIGH",
     "Autostart entry (~/.config/autostart)",
     r"autostart[/\\][^'\"]*\.desktop", "persist_autostart"),
    ("persistence", "HIGH",
     "Shell startup file modification (.bashrc / .zshrc / .profile)",
     r"['\"].*\.(bashrc|zshrc|bash_profile|profile|zprofile)['\"]", "persist_shell"),
    ("persistence", "HIGH",
     "macOS LaunchAgent – installs persistent agent that runs at login",
     r"LaunchAgents|launchctl\s+load|\.plist", "persist_launchagent"),
    ("persistence", "MEDIUM",
     "pip install at runtime – installs packages (possible backdoor)",
     r"\bpip\s+install\b|subprocess.*pip.*install", "persist_pip"),
    ("persistence", "MEDIUM",
     "s.ensure_installed() – auto-installs packages",
     r"\bs\.ensure_installed\s*\(", "persist_ensure"),

    # ── Obfuscation ───────────────────────────────────────────────────────
    ("obfuscation", "HIGH",
     "base64.b64decode – decodes hidden payload at runtime",
     r"\bbase64\.b64decode\s*\(", "obf_b64"),
    ("obfuscation", "HIGH",
     "zlib.decompress – decompresses hidden code",
     r"\bzlib\.decompress\s*\(", "obf_zlib"),
    ("obfuscation", "HIGH",
     "importlib.import_module with computed name – dynamic import",
     r"\bimportlib\.import_module\s*\(", "obf_importlib"),
    ("obfuscation", "MEDIUM",
     "chr() concatenation – builds strings character by character",
     r"\bchr\s*\(\s*\d+\s*\)\s*\+", "obf_chr"),
    ("obfuscation", "MEDIUM",
     "Hex / unicode escape sequence in string literal",
     r"['\"](?:[^'\"]*(?:\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})){3,}[^'\"]*['\"]", "obf_hex"),
    ("obfuscation", "LOW",
     "codecs.decode / ROT-13 – hides module names",
     r"\bcodecs\.decode\s*\(|rot.?13", "obf_rot13"),
    ("obfuscation", "MEDIUM",
     "from X import * – star import hides which names are used",
     r"^\s*from\s+\w+(?:\.\w+)*\s+import\s+\*", "obf_star_import"),
    ("obfuscation", "MEDIUM",
     "chr()/join() string building – assembles strings to evade detection",
     r"""['"]\.join\s*\(\s*\[\s*chr\s*\(|''\s*\.join\s*\(\s*\[.*chr""", "obf_chr_join"),
    ("obfuscation", "HIGH",
     "Unicode homoglyph in identifier – non-ASCII character that looks like ASCII (visual spoofing)",
     r"[A-Za-z_]\w*[^\x00-\x7F]+\w*\s*[=(]|[^\x00-\x7F]+\w+\s*[=(]",
     "obf_homoglyph"),

    # ── Denial of Service ─────────────────────────────────────────────────
    ("dos", "HIGH",
     "Huge numpy allocation – exhausts RAM",
     r"numpy\.zeros\s*\(\s*\(\s*\d{5,}|\bnp\.zeros\s*\(\s*\(\s*\d{5,}", "dos_numpy"),
    ("dos", "HIGH",
     "os.fork() – fork bomb risk",
     r"\bos\.fork\s*\(", "dos_fork"),

    # ── Social Engineering ────────────────────────────────────────────────
    ("social_eng", "MEDIUM",
     "Fake update / download dialog – tricks user into running malware",
     r"""(?i)['"][^'"]*(?:update\s+available|new\s+version\s+available.*download)[^'"]*['"]""",
     "social_update"),  # A6: anchored to string literals

    # ── Supply Chain ──────────────────────────────────────────────────────
    ("supply_chain", "LOW",
     "Pinned package version (check if intentional)",
     r"(?i)pip\s+install.*==\s*\d", "supply_pin"),  # A7: downgraded to LOW
    ("supply_chain", "MEDIUM",
     "Installing package from non-PyPI index (--index-url / -i flag)",
     r"(?i)pip.*--index-url|pip.*-i\s+http", "supply_index"),
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
_COMPILED_RULES: list[tuple[str, str, str, re.Pattern, str]] = [
    (cat, sev, desc, re.compile(pat), rid)
    for cat, sev, desc, pat, rid in _RULES
]

# Libraries considered safe for Siril scripting — suppress package-install warnings for these
_SAFE_LIBS: frozenset[str] = frozenset({
    "PyQt6", "numpy", "astropy", "opencv-python", "scipy",
    "matplotlib", "tiffile", "Pillow",
})
_SAFE_LIBS_RULE_IDS: frozenset[str] = frozenset({
    "persist_pip", "persist_ensure", "supply_pin", "supply_index",
})
_RE_SAFE_LIBS = re.compile(
    r"(?i)(?<![a-zA-Z0-9_-])(" +
    "|".join(re.escape(lib) for lib in _SAFE_LIBS) +
    r")(?![a-zA-Z0-9_-])"
)

# Suppress social-engineering findings when the match is inside a UI widget string
_RE_SOCIAL_ENG_UI = re.compile(
    r"(?i)(\.setWindowTitle\s*\(|\.setText\s*\(|\.setTitle\s*\(|"
    r"\.setLabelText\s*\(|QLabel\s*\(|QMessageBox)"
)

# Unified magic-byte registry: (prefix, label, mime_or_None)
# - label: human-readable file type for _describe_bytes
# - mime: MIME type for image display, or None if not displayable as <img>
_MAGIC_SIGNATURES: tuple[tuple[bytes, str, str | None], ...] = (
    (b'\xff\xd8\xff',       "JPEG image",           "image/jpeg"),
    (b'\x89PNG\r\n\x1a\n',  "PNG image",            "image/png"),
    (b'GIF8',               "GIF image",            "image/gif"),
    (b'BM',                 "BMP image",            "image/bmp"),
    (b'II*\x00',            "TIFF image",           None),
    (b'MM\x00*',            "TIFF image",           None),
    (b'SIMPLE  =',          "FITS image",           None),
    (b'\x00\x00\x01\x00',   "ICO icon",            None),
    (b'RIFF',               "RIFF container (WAV/AVI)", None),
    (b'%PDF',               "PDF document",         None),
    (b'PK\x03\x04',         "ZIP / JAR archive",    None),
    (b'\x1f\x8b',           "gzip-compressed data", None),
    (b'BZh',                "bzip2-compressed data", None),
    (b'\xfd7zXZ\x00',       "xz-compressed data",   None),
    (b'\x7fELF',            "ELF executable",       None),
    (b'MZ',                 "Windows PE executable", None),
    (b'\xca\xfe\xba\xbe',   "Java class file",      None),
    (b'\xce\xfa\xed\xfe',   "Mach-O binary (32-bit)", None),
    (b'\xcf\xfa\xed\xfe',   "Mach-O binary (64-bit)", None),
)

# File-deletion self-cleanup detection
_FS_REMOVE_IDS: frozenset[str] = frozenset({"fs_remove", "fs_unlink"})
_RE_FS_REMOVE_ARG = re.compile(r"\bos\.(?:remove|unlink)\s*\(\s*([A-Za-z_]\w*)")

# Config-file path indicators for open('w') downgrade (A3)
_RE_CONFIG_PATH = re.compile(
    r"(?i)(config|settings|\.ini|\.json|preferences|preset|\.cfg|\.conf)"
)

# System directories to reject in path traversal guard (G1)
_SYSTEM_DIRS = tuple(Path(p) for p in ("/etc", "/usr", "/System", "/bin", "/sbin", "/var"))


# ------------------------------------------------------------------------------
# SUPPRESSOR / DOWNGRADER PIPELINE  (E2)
#
# Contract:
#   Suppressors return True to DROP a finding entirely (it never appears).
#   Downgraders return (new_sev, new_desc) to MODIFY a finding, or None to skip.
#
#   Suppressors run first. If no suppressor fires, downgraders run.
#   _suppress_safe_libs: drops findings for WHITELISTED libs (they're fine).
#   _downgrade_safe_libs: downgrades findings for NON-whitelisted libs to LOW.
# ------------------------------------------------------------------------------

def _suppress_commented(cat: str, sev: str, desc: str, rid: str,
                        line: str, lines: list[str]) -> bool:
    """Suppress findings on commented-out lines."""
    return line.lstrip().startswith("#")


def _suppress_print_pip(cat: str, sev: str, desc: str, rid: str,
                        line: str, lines: list[str]) -> bool:
    """Suppress pip-install findings inside print()."""
    return rid == "persist_pip" and bool(re.search(r"\bprint\s*\(", line))


def _suppress_safe_libs(cat: str, sev: str, desc: str, rid: str,
                        line: str, lines: list[str]) -> bool:
    """Suppress package-install findings when only whitelisted libs are mentioned."""
    return rid in _SAFE_LIBS_RULE_IDS and bool(_RE_SAFE_LIBS.search(line))


def _suppress_social_print(cat: str, sev: str, desc: str, rid: str,
                           line: str, lines: list[str]) -> bool:
    """Suppress social-engineering findings on print() statements."""
    return cat == "social_eng" and bool(re.search(r"\bprint\s*\(", line))


def _suppress_social_ui(cat: str, sev: str, desc: str, rid: str,
                        line: str, lines: list[str]) -> bool:
    """Suppress social-engineering findings when text is a UI widget string."""
    return cat == "social_eng" and bool(_RE_SOCIAL_ENG_UI.search(line))


_self_cleanup_cache: dict[str, re.Pattern] = {}


def _suppress_self_cleanup(cat: str, sev: str, desc: str, rid: str,
                           line: str, lines: list[str]) -> bool:
    """Suppress file-deletion findings when the script deletes its own files."""
    if rid not in _FS_REMOVE_IDS:
        return False
    m = _RE_FS_REMOVE_ARG.search(line)
    if not m:
        return False
    varname = m.group(1)
    pat = _self_cleanup_cache.get(varname)
    if pat is None:
        pat = re.compile(rf"\b{re.escape(varname)}\s*=")
        _self_cleanup_cache[varname] = pat
    return any(pat.search(l) for l in lines)


_SUPPRESSORS: list[Callable] = [
    _suppress_commented,
    _suppress_print_pip,
    _suppress_safe_libs,
    _suppress_social_print,
    _suppress_social_ui,
    _suppress_self_cleanup,
]


def _downgrade_safe_libs(cat: str, sev: str, desc: str, rid: str,
                         line: str, lines: list[str]) -> tuple[str, str] | None:
    """Downgrade non-whitelisted lib installs to MEDIUM (unknown package — possible typosquatting)."""
    if rid in _SAFE_LIBS_RULE_IDS and not _RE_SAFE_LIBS.search(line):
        return ("MEDIUM", desc + " (unknown package — verify name)")
    return None


def _downgrade_b64_image(cat: str, sev: str, desc: str, rid: str,
                         line: str, lines: list[str],
                         path: Path, lineno: int) -> tuple[str, str] | None:
    """Downgrade base64 findings to LOW when the payload is an image."""
    if rid != "obf_b64":
        return None
    decoded = _try_decode_base64(line.strip(), path, lineno)
    if decoded is None:
        return None
    _, raw_bytes = decoded
    for magic, label, _mime in _MAGIC_SIGNATURES:
        if raw_bytes[:len(magic)] == magic and "image" in label.lower():
            return ("LOW", "base64.b64decode – embedded image asset (icon/resource, not executable)")
    return None


def _downgrade_config_write(cat: str, sev: str, desc: str, rid: str,
                            line: str, lines: list[str]) -> tuple[str, str] | None:
    """Downgrade open('w') to LOW when writing a config/settings file (A3)."""
    if rid == "fs_open_write" and _RE_CONFIG_PATH.search(line):
        return ("LOW", "open(..., 'w') – writes config/settings file (likely benign)")
    return None


def _downgrade_udp_socket(cat: str, sev: str, desc: str, rid: str,
                          line: str, lines: list[str]) -> tuple[str, str] | None:
    """Downgrade SOCK_DGRAM (UDP) socket to MEDIUM — common for local IP detection but also DNS tunnelling (A4)."""
    if rid == "net_socket" and "SOCK_DGRAM" in line:
        return ("MEDIUM", "UDP socket (often local IP detection, but also usable for DNS tunnelling)")
    return None


def _downgrade_macos_open(cat: str, sev: str, desc: str, rid: str,
                          line: str, lines: list[str]) -> tuple[str, str] | None:
    """Downgrade subprocess that just calls macOS 'open' command (A5)."""
    if rid == "code_subprocess" and re.search(r'''["']\s*open\s*["']|["']open["']\s*,''', line):
        return ("MEDIUM", "macOS open command (opens URL/file in default app, not arbitrary execution)")
    return None


# Simple downgraders (no path/lineno needed)
_SIMPLE_DOWNGRADERS: list[Callable] = [
    _downgrade_safe_libs,
    _downgrade_config_write,
    _downgrade_udp_socket,
    _downgrade_macos_open,
]


# ------------------------------------------------------------------------------
# RULE EXPLANATIONS  (E5: keyed by rule_id, not duplicated description)
# ------------------------------------------------------------------------------

_RULE_EXPLANATIONS: dict[str, str] = {
    # ── Code Execution ────────────────────────────────────────────────────
    "code_subprocess": (
        "<b>What this means:</b> The script launches an external program on your computer. "
        "Python's <code>subprocess</code> can run <em>any</em> command — open a browser, run another script, "
        "call system tools, or execute a downloaded binary. "
        "Legitimate scripts use this to call external AI engines (e.g. GraXpert, CosmicClarity). "
        "A malicious script could use it to run anything at all without asking you. "
        "<b>Check the code above:</b> what command or program is being executed?"
    ),
    "code_compile": (
        "<b>What this means:</b> Python's built-in <code>compile()</code> turns a string of text "
        "into executable Python code. If that string comes from the internet or a file, a bad actor "
        "could inject any instructions they like. "
        "Note: <code>re.compile()</code> (regular expressions) is harmless and is excluded from this rule."
    ),
    "code_eval": (
        "<b>What this means:</b> <code>eval()</code> takes a piece of text and runs it as Python code. "
        "Example: <code>eval('import os; os.remove(\"/your/file\")')</code> would silently delete a file. "
        "If the argument comes from the internet, user input, or a downloaded file, "
        "this is one of the most dangerous constructs in Python."
    ),
    "code_exec_fn": (
        "<b>What this means:</b> <code>exec()</code> runs an entire block of Python code stored in a string. "
        "Same danger as <code>eval()</code> — if that string is fetched from an untrusted source, "
        "the script can execute anything on your machine: delete files, steal data, install software."
    ),
    "code_ctypes": (
        "<b>What this means:</b> <code>ctypes</code> lets Python code call functions directly from "
        "system libraries (Windows DLLs, macOS dylibs, Linux .so files), bypassing Python's normal "
        "safety layer. Legitimate uses include accessing GPU drivers or OS-level APIs. "
        "Malicious uses could hide activity, escalate privileges, or bypass security controls."
    ),
    "code_syspath": (
        "<b>What this means:</b> <code>sys.path</code> controls where Python looks for modules. "
        "By inserting a custom folder at the front, a script can make Python load a fake/modified "
        "version of a library instead of the real one — a technique called a 'path hijack'. "
        "Legitimate scripts use this to load a local AI engine or plugin folder. "
        "<b>Check what directory is being added.</b>"
    ),
    "code_dyn_import": (
        "<b>What this means:</b> <code>__import__()</code> loads a Python module by name at runtime, "
        "where the name can be computed from a string. This makes it possible to import modules "
        "whose names are hidden or obfuscated, bypassing static analysis tools."
    ),
    "code_system": (
        "<b>What this means:</b> <code>os.system()</code> runs a shell command. Any string passed to it "
        "is executed by the operating system's command shell. This is the simplest and most dangerous "
        "way for a script to execute arbitrary commands."
    ),
    "code_pickle": (
        "<b>What this means:</b> <code>pickle.load()</code>, <code>torch.load()</code>, and "
        "<code>joblib.load()</code> deserialize binary data back into Python objects. "
        "A maliciously crafted pickle file can execute arbitrary code when loaded. "
        "This is a well-known attack vector in machine learning / AI scripts."
    ),
    "code_yaml": (
        "<b>What this means:</b> <code>yaml.load()</code> without <code>SafeLoader</code> can "
        "execute arbitrary Python code embedded in a YAML file. Always use "
        "<code>yaml.safe_load()</code> or pass <code>Loader=SafeLoader</code>."
    ),
    "code_monkeypatch": (
        "<b>What this means:</b> The script modifies the sirilpy library at runtime by overwriting "
        "one of its attributes. This can alter how Siril itself behaves — potentially disabling "
        "safety checks or redirecting function calls."
    ),
    "code_reflect": (
        "<b>What this means:</b> <code>getattr()</code> and <code>setattr()</code> with string arguments "
        "allow accessing or modifying any attribute of any object dynamically. This can be used to "
        "bypass name-based detection and call dangerous functions indirectly."
    ),
    "code_webbrowser": (
        "<b>What this means:</b> <code>webbrowser.open()</code> opens a URL in your default web browser. "
        "This is low risk on its own, but could be used to direct you to a phishing site or trigger "
        "a download. Check the URL being opened."
    ),
    # ── Network ────────────────────────────────────────────────────────────
    "net_requests": (
        "<b>What this means:</b> The script makes an outgoing network request — essentially "
        "visiting a URL on the internet. Legitimate scripts use this to download AI models, "
        "check for updates, or query star catalogues (e.g. Simbad, Gaia). "
        "A malicious script could send your personal data to a remote server, or download "
        "and execute additional code. <b>Check which URL is being contacted.</b>"
    ),
    "net_urllib": (
        "<b>What this means:</b> The script contacts a server on the internet using Python's "
        "built-in <code>urllib</code> library. Same risk profile as <code>requests</code>: "
        "could be legitimate (downloading models, star catalogues, checksums) or malicious "
        "(data theft, downloading further payloads). <b>Check the URL in the code above.</b>"
    ),
    "net_socket": (
        "<b>What this means:</b> The script opens a raw network socket — a low-level connection "
        "that bypasses higher-level libraries. A common harmless use is detecting the local IP "
        "address (standard Python trick using UDP). However it can also be used to communicate "
        "covertly with a remote server without leaving obvious traces in network logs."
    ),
    "net_dns": (
        "<b>What this means:</b> The script resolves a hostname to an IP address. On its own this "
        "is low risk, but it can be the first step of a network connection or used to detect "
        "whether a specific server is reachable (a 'phone-home' check)."
    ),
    "net_ftp": (
        "<b>What this means:</b> The script uses FTP (File Transfer Protocol), which can upload "
        "or download files to/from a remote server. FTP transmits data unencrypted."
    ),
    "net_smtp": (
        "<b>What this means:</b> The script sends email via SMTP. A malicious script could "
        "email your files, credentials, or other data to an attacker's address."
    ),
    "net_bind": (
        "<b>What this means:</b> The script opens a listening port on your computer, accepting "
        "incoming connections. This could be a reverse shell (backdoor) or a hidden local server."
    ),
    "net_httpserver": (
        "<b>What this means:</b> The script starts a local HTTP server, making files accessible "
        "over the network. Anyone on your local network could potentially connect."
    ),
    "net_dl_exec": (
        "<b>What this means:</b> The script downloads something from the internet and immediately "
        "executes it. This is the most dangerous network pattern — the equivalent of running "
        "unknown code from the internet without inspection."
    ),
    # ── File System — Destructive ──────────────────────────────────────────
    "fs_rmtree": (
        "<b>What this means:</b> <code>shutil.rmtree()</code> deletes an entire folder and "
        "<em>everything inside it</em> — all subfolders and files — in one call. "
        "There is no Recycle Bin / Trash: the data is gone permanently and immediately. "
        "Legitimate scripts use this to clean up temporary processing folders they created. "
        "A malicious script could wipe your entire image library or project data."
    ),
    "fs_remove": (
        "<b>What this means:</b> <code>os.remove()</code> permanently deletes a single file from disk. "
        "No Recycle Bin, no undo. Legitimate scripts delete temporary files they created themselves. "
        "<b>Check whether the file is a temp file the script made, or a file from your project.</b>"
    ),
    "fs_unlink": (
        "<b>What this means:</b> <code>Path.unlink()</code> is the modern Python way to delete a file — "
        "same effect as <code>os.remove()</code>. The file is permanently gone. "
        "Legitimate scripts use this to clean up temp files after processing."
    ),
    "fs_open_write": (
        "<b>What this means:</b> The script opens a file for writing. Mode <code>'w'</code> "
        "overwrites the file completely (previous contents are lost immediately on open). "
        "<code>'wb'</code> does the same in binary mode. <code>'a'</code> appends without "
        "destroying existing content. Most scripts legitimately write config files, log files, "
        "or export results. <b>Check what file path is being written.</b>"
    ),
    "fs_removedirs": (
        "<b>What this means:</b> <code>os.removedirs()</code> removes a chain of empty directories. "
        "Less dangerous than rmtree (only works on empty dirs), but still destructive."
    ),
    "fs_environ": (
        "<b>What this means:</b> The script accesses environment variables via <code>os.environ</code> "
        "or <code>os.getenv()</code>. Environment variables often contain API keys, tokens, paths, "
        "and other sensitive configuration. Reading them may be harmless (checking system locale) "
        "or malicious (harvesting credentials)."
    ),
    "fs_copy": (
        "<b>What this means:</b> The script copies or moves files using <code>shutil.copy()</code>, "
        "<code>shutil.copytree()</code>, or <code>shutil.move()</code>. Legitimate scripts copy "
        "files for processing. A malicious script could exfiltrate your files to a hidden location."
    ),
    # ── File System — Data Theft ───────────────────────────────────────────
    "fs_ssh": (
        "<b>What this means:</b> The script accesses your SSH private keys. These keys provide "
        "authentication to remote servers — stealing them gives an attacker access to your servers."
    ),
    "fs_creds": (
        "<b>What this means:</b> The script accesses credential files (.env, .netrc, .git-credentials). "
        "These files contain passwords, API keys, and authentication tokens."
    ),
    "fs_cloud": (
        "<b>What this means:</b> The script accesses cloud provider credential files "
        "(AWS, GCP, Azure). These could give an attacker control of your cloud infrastructure."
    ),
    "fs_browser": (
        "<b>What this means:</b> The script accesses browser cookie or password databases. "
        "This could allow stealing your saved passwords or hijacking logged-in sessions."
    ),
    "fs_read_py": (
        "<b>What this means:</b> The script reads other Python files. This could be legitimate "
        "(loading a plugin) or malicious (stealing proprietary algorithms from other scripts)."
    ),
    "fs_walk": (
        "<b>What this means:</b> The script scans directories recursively, listing all files. "
        "Legitimate scripts do this to find FITS files for processing. Malicious scripts scan "
        "for interesting files to steal."
    ),
    # ── Persistence ────────────────────────────────────────────────────────
    "persist_pip": (
        "<b>What this means:</b> The script installs a Python package via pip at runtime — "
        "downloading and installing software from the internet automatically when you run it. "
        "Legitimate scripts do this to ensure their dependencies are present. "
        "A malicious script could install a package containing harmful code. "
        "<b>Check the package name:</b> is it a well-known, reputable library?"
    ),
    "persist_ensure": (
        "<b>What this means:</b> Siril's <code>ensure_installed()</code> function automatically "
        "downloads and installs a Python package if it is not already present. "
        "This is a very common and legitimate pattern in Siril scripts. "
        "The risk depends entirely on the package name — well-known libraries "
        "(numpy, astropy, PyQt6, scipy) are safe; obscure or misspelled names are worth investigating."
    ),
    "persist_cron": (
        "<b>What this means:</b> The script modifies crontab or a cron directory, scheduling "
        "a command to run automatically at regular intervals — even when you are not using the "
        "script. This is a classic persistence mechanism used by malware to survive reboots."
    ),
    "persist_systemd": (
        "<b>What this means:</b> The script creates a systemd service unit, which can run "
        "a program automatically on boot and restart it if it crashes."
    ),
    "persist_autostart": (
        "<b>What this means:</b> The script creates a desktop autostart entry, causing a program "
        "to launch every time you log in."
    ),
    "persist_shell": (
        "<b>What this means:</b> The script touches a shell startup file. These files run "
        "every time you open a terminal. A malicious script could add itself here to run "
        "automatically every time you use your computer."
    ),
    # ── Obfuscation ────────────────────────────────────────────────────────
    "obf_b64": (
        "<b>What this means:</b> The script decodes a Base64-encoded blob of data at runtime. "
        "Base64 is an encoding scheme that turns binary data into text. It is commonly used to "
        "embed images or icons in a script — but it is also used to hide malicious code so it "
        "is not immediately readable. "
        "This scanner will try to decode the payload and show you what is inside."
    ),
    "obf_zlib": (
        "<b>What this means:</b> The script decompresses data using zlib at runtime. "
        "Like Base64, this can be used to embed compressed resources legitimately, "
        "but is also used to hide code that would look suspicious if written in plain text."
    ),
    "obf_importlib": (
        "<b>What this means:</b> The script imports a module whose name is computed at runtime "
        "rather than written literally. This can hide which modules are being loaded, making "
        "it harder to spot suspicious imports."
    ),
    "obf_chr": (
        "<b>What this means:</b> The script builds a string one character at a time using "
        "ASCII codes (<code>chr(104)+chr(101)+chr(108)...</code> = 'hel...'). This technique "
        "is almost exclusively used to hide strings from static analysis — e.g. hiding a URL, "
        "a command, or a module name so it does not appear in the source code."
    ),
    "obf_hex": (
        "<b>What this means:</b> The script contains strings with many hex or unicode escape "
        "sequences (\\x41, \\u0041). This can hide readable text so it doesn't appear in searches. "
        "Legitimate uses exist (binary protocols), but 3+ escapes in one string is suspicious."
    ),
    "obf_rot13": (
        "<b>What this means:</b> The script uses codecs.decode or ROT-13 to decode strings "
        "at runtime. ROT-13 is a simple letter substitution cipher. While it has legitimate "
        "uses, applying it to module names or commands is a classic obfuscation trick."
    ),
    # ── Social Engineering ──────────────────────────────────────────────────
    "social_update": (
        "<b>What this means:</b> The script may show a dialog or message claiming an update "
        "is available and prompting you to download or install something. "
        "Many legitimate scripts do check for updates — but this pattern is also used by "
        "malware to trick users into installing malicious software. "
        "<b>Look at the context:</b> does it download and execute something automatically, "
        "or does it just inform you and let you decide?"
    ),
    # ── DoS ────────────────────────────────────────────────────────────────
    "dos_numpy": (
        "<b>What this means:</b> The script allocates a very large numpy array (hundreds of "
        "thousands or millions of elements). If this is larger than available RAM, it can "
        "freeze or crash your computer. Legitimate scripts sometimes work with large image data; "
        "check whether the size is proportional to a real image."
    ),
    "dos_fork": (
        "<b>What this means:</b> <code>os.fork()</code> creates a copy of the running process. "
        "If called in a loop without limits, this creates a 'fork bomb' — an exponentially "
        "growing number of processes that can freeze your entire system."
    ),
    # ── Supply Chain ───────────────────────────────────────────────────────
    "supply_pin": (
        "<b>What this means:</b> The script installs a specific version of a package. "
        "This can be legitimate (compatibility reasons) or deliberate (exploiting a known "
        "vulnerability in that version). Check if the version is reasonable."
    ),
    "supply_index": (
        "<b>What this means:</b> The script installs a package from a custom repository "
        "instead of the official Python Package Index (PyPI). This bypasses PyPI's security "
        "scanning and could serve a malicious or counterfeit package."
    ),
    # ── Evasion / Introspection ──────────────────────────────────────────
    "code_builtins": (
        "<b>What this means:</b> The script accesses <code>__builtins__</code> directly. "
        "This is a common evasion technique: instead of writing <code>eval('code')</code> "
        "(which a scanner catches), an attacker writes <code>__builtins__['eval']('code')</code> "
        "to call the same function indirectly. There is almost never a legitimate reason "
        "to access <code>__builtins__</code> in a Siril script."
    ),
    "code_vars_dict": (
        "<b>What this means:</b> The script accesses an object's internal <code>__dict__</code> "
        "or uses <code>vars()</code> to look up functions by name. This is another bypass technique: "
        "<code>vars(os)['remove']('/file')</code> has the same effect as <code>os.remove('/file')</code> "
        "but evades simple name-based detection."
    ),
    "code_reflect_var": (
        "<b>What this means:</b> The script uses <code>getattr()</code> or <code>setattr()</code> "
        "with a <em>variable</em> as the attribute name (not a string literal). "
        "This means the function being called is determined at runtime and cannot be statically "
        "identified — a key evasion technique. Example: <code>fn = 'rem'+'ove'; getattr(os, fn)(path)</code>."
    ),
    "code_pty": (
        "<b>What this means:</b> <code>pty.spawn()</code> opens a pseudo-terminal and launches "
        "an interactive shell. This is the most common way to create a reverse shell in Python — "
        "giving a remote attacker an interactive command prompt on your machine. "
        "There is no legitimate use for this in a Siril astronomy script."
    ),
    "code_multiproc": (
        "<b>What this means:</b> <code>multiprocessing.Process()</code> creates a child process "
        "that runs the given function. This can be used to execute malicious code in a separate "
        "process that survives even if the parent script is killed, or to fork bomb the system."
    ),
    "code_importlib_util": (
        "<b>What this means:</b> <code>importlib.util.spec_from_file_location()</code> loads "
        "a Python module from an arbitrary file path. An attacker can use this to load "
        "malicious code from a downloaded or temporary file, bypassing normal import mechanisms."
    ),
    "code_kill": (
        "<b>What this means:</b> <code>os.kill()</code> sends a signal to a running process. "
        "Combined with <code>signal.SIGKILL</code> or <code>signal.SIGTERM</code>, this can "
        "forcibly terminate any process owned by your user — including Siril itself, "
        "your desktop environment, or other important applications."
    ),
    "code_mmap": (
        "<b>What this means:</b> <code>mmap.mmap()</code> maps a file directly into memory, "
        "bypassing normal file I/O. This can be used for direct memory manipulation, "
        "modifying files without triggering normal write detection, or even injecting code."
    ),
    "code_magic_methods": (
        "<b>What this means:</b> The script defines a dunder method that enables silent code execution. "
        "<code>__getattr__</code> intercepts attribute access; <code>__reduce__</code> runs code during "
        "pickle deserialization; <code>__set_name__</code> fires when a class is created (no instantiation "
        "needed); <code>__init_subclass__</code> fires when the class is subclassed; <code>__enter__</code>/"
        "<code>__exit__</code> run inside <code>with</code> blocks; <code>__code__</code> can replace "
        "a function's bytecode. All of these can execute attacker-controlled code silently."
    ),
    "code_str_concat": (
        "<b>What this means:</b> The script uses string concatenation inside "
        "<code>__import__()</code> or <code>getattr()</code>. This hides the real module or "
        "function name from scanners: <code>__import__('sub'+'process')</code> imports subprocess "
        "without the word 'subprocess' appearing as a single token. "
        "Legitimate code has no reason to split module names this way."
    ),
    "code_yaml_unsafe": (
        "<b>What this means:</b> <code>yaml.load()</code> is called with an unsafe Loader. "
        "<code>yaml.Loader</code>, <code>yaml.UnsafeLoader</code>, and <code>yaml.FullLoader</code> "
        "can all execute arbitrary Python code embedded in a YAML file. "
        "Always use <code>yaml.safe_load()</code> or <code>Loader=yaml.SafeLoader</code>."
    ),
    "fs_symlink": (
        "<b>What this means:</b> <code>os.symlink()</code> creates a symbolic link that "
        "points to another file. An attacker can use this for 'symlink attacks': create a link "
        "from an innocent-looking path to a sensitive file like <code>/etc/passwd</code>, "
        "then read or overwrite it via the link."
    ),
    # ── Obfuscation (new) ─────────────────────────────────────────────────
    "obf_star_import": (
        "<b>What this means:</b> <code>from X import *</code> imports all names from a module "
        "without listing them explicitly. This makes it impossible to tell which functions "
        "are being used — an attacker can call <code>remove('/file')</code> directly instead "
        "of <code>os.remove('/file')</code>, evading module-based detection rules."
    ),
    "obf_chr_join": (
        "<b>What this means:</b> The script builds a string using <code>''.join([chr(n), ...])</code> "
        "— assembling text character by character from ASCII codes. This is almost exclusively "
        "an obfuscation technique to hide module names, URLs, or commands from scanners."
    ),
    # ── New adversarial-round-2 rules ────────────────────────────────────
    "code_atexit": (
        "<b>What this means:</b> <code>atexit.register()</code> schedules a function to run when "
        "the Python interpreter exits. An attacker can use this to exfiltrate data or clean up "
        "evidence after the main script finishes — the user never sees the cleanup happening."
    ),
    "code_weakref": (
        "<b>What this means:</b> <code>weakref.ref()</code> or <code>weakref.proxy()</code> with "
        "a callback function. The callback fires when the referenced object is garbage-collected, "
        "which is non-deterministic and invisible. An attacker can use this for delayed code execution."
    ),
    "code_settrace": (
        "<b>What this means:</b> <code>sys.settrace()</code> or <code>sys.setprofile()</code> installs "
        "a hook that is called on every function call, return, or line execution. An attacker can use "
        "this to monitor all code execution (keylogger-style), modify return values, or inject code."
    ),
    "code_getframe": (
        "<b>What this means:</b> <code>sys._getframe()</code> accesses the call stack frames directly. "
        "Combined with <code>f_builtins</code>, <code>f_locals</code>, or <code>f_globals</code>, "
        "this allows reading/modifying variables in calling functions — a sandbox escape technique."
    ),
    "code_asyncio_proc": (
        "<b>What this means:</b> <code>asyncio.create_subprocess_exec/shell()</code> runs external "
        "commands asynchronously. This is functionally equivalent to <code>subprocess.Popen()</code> "
        "but harder to detect because it doesn't import <code>subprocess</code> directly."
    ),
    "code_threading": (
        "<b>What this means:</b> <code>threading.Thread()</code> runs code in a background thread. "
        "An attacker can use this to perform malicious activity (exfiltration, file deletion) "
        "concurrently while the main thread shows innocent-looking behavior to the user."
    ),
    "code_marshal": (
        "<b>What this means:</b> <code>marshal.loads()</code> deserializes Python bytecode objects, "
        "and <code>types.CodeType()</code> / <code>types.FunctionType()</code> create executable "
        "code objects from raw bytecode. This bypasses all source-level detection — the malicious "
        "code exists only as binary data until it is loaded and executed."
    ),
    "code_type_create": (
        "<b>What this means:</b> <code>type('Name', (bases,), dict)</code> with 3 arguments creates "
        "a class dynamically. The class dict can contain <code>__init__</code>, descriptors, or "
        "metaclass hooks that execute immediately on class creation, without explicit instantiation."
    ),
    "code_meta_path": (
        "<b>What this means:</b> <code>sys.meta_path</code> is the list of import finders. "
        "An attacker who appends a custom finder can intercept <code>import</code> statements, "
        "returning malicious modules when the script tries to import legitimate ones."
    ),
    "code_site_packages": (
        "<b>What this means:</b> <code>site.getsitepackages()</code> reveals the paths where "
        "Python packages are installed. An attacker can use this to locate and modify installed "
        "packages, injecting backdoors that persist across all Python scripts on the system."
    ),
    "code_log_formatter": (
        "<b>What this means:</b> A custom <code>logging.Formatter</code> subclass can override "
        "<code>format()</code> to execute arbitrary code every time a log message is emitted. "
        "Since logging happens frequently and implicitly, this is a stealthy execution vector."
    ),
    "persist_launchagent": (
        "<b>What this means:</b> References to <code>LaunchAgents</code>, <code>launchctl</code>, "
        "or <code>.plist</code> files suggest the script may install a macOS LaunchAgent — a "
        "persistent daemon that automatically runs at user login, surviving reboots."
    ),
    "fs_proc_self": (
        "<b>What this means:</b> <code>/proc/self/</code> (or <code>/proc/PID/</code>) on Linux "
        "exposes process internals: memory maps, environment variables, file descriptors. "
        "An attacker can read <code>/proc/self/environ</code> to steal API keys and secrets."
    ),
    "obf_homoglyph": (
        "<b>What this means:</b> A non-ASCII character appears in what looks like a Python identifier. "
        "Unicode homoglyphs (e.g., Cyrillic 'а' instead of Latin 'a') can make two identifiers look "
        "identical but refer to different variables — used to hide backdoors in plain sight."
    ),
    # ── Special downgraded / file-level descriptions ─────────────────────
    "obf_b64_image": (
        "<b>What this means:</b> The script contains a Base64-encoded image (icon or logo) "
        "embedded directly in the source code. This is a very common and entirely harmless "
        "technique for bundling a window icon without needing a separate image file. "
        "The scanner has decoded the data and confirmed it is an image, not code."
    ),
    "code_tempfile_subprocess": (
        "<b>What this means:</b> This file uses both <code>tempfile</code> (to create temporary files) "
        "and <code>subprocess</code> (to execute programs). A common attack pattern is to write "
        "malicious code to a temp file, then execute it. This is a <em>file-level</em> heuristic — "
        "check whether the temp files are being executed or just used for data processing."
    ),
}


# ------------------------------------------------------------------------------
# DATA MODEL  (E5: Finding includes rule_id)
# ------------------------------------------------------------------------------

@dataclass
class Finding:
    file_path: Path
    line_no: int
    line_text: str
    category: str
    severity: str
    description: str
    rule_id: str


# ------------------------------------------------------------------------------
# SCANNING LOGIC
# ------------------------------------------------------------------------------

_NET_CATEGORIES = {"net_exfil", "net_inbound"}

# Patterns for extracting network targets from a code line
_RE_URL      = re.compile(r'(?:https?|ftp|ftps|sftp|ws|wss)://[^\s\'">\])\}]+')
_RE_IP_PORT  = re.compile(r'\b(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?\b')
_RE_HOSTNAME = re.compile(
    r'''[\'"]([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'''
    r'''(?:\.[a-zA-Z]{2,})+(?::\d+)?)[\'"]'''
)


# ── File read cache (D1) ──────────────────────────────────────────────────

@functools.lru_cache(maxsize=64)
def _read_file_cached(path: Path) -> str:
    """Read and cache file contents. Cache is per-session (cleared on next scan)."""
    return path.read_text(encoding="utf-8", errors="replace")


def _clear_file_cache() -> None:
    """Clear the file read cache (call at start of each scan)."""
    _read_file_cached.cache_clear()


def _extract_network_targets(line: str) -> list[str]:
    """Return a deduplicated list of URLs, IPs, and hostnames found in *line*."""
    targets: list[str] = []
    seen: set[str] = set()

    def _add(t: str) -> None:
        if t not in seen:
            seen.add(t)
            targets.append(t)

    for m in _RE_URL.finditer(line):
        _add(m.group(0).rstrip(".,;)\"'"))
    for m in _RE_IP_PORT.finditer(line):
        _add(f"{m.group(1)}:{m.group(2)}" if m.group(2) else m.group(1))
    for m in _RE_HOSTNAME.finditer(line):
        _add(m.group(1))
    return targets


# Identifiers that are never meaningful URL variable names
_VAR_SKIP = frozenset({
    "self", "cls", "None", "True", "False", "return", "import", "from",
    "as", "in", "is", "not", "and", "or", "if", "else", "for", "while",
    "with", "try", "except", "raise", "pass", "break", "continue", "def",
    "class", "lambda", "yield", "del", "global", "nonlocal", "assert",
    "open", "print", "len", "str", "int", "float", "list", "dict", "set",
    "tuple", "bytes", "type", "range", "enumerate", "zip", "map", "filter",
    "path", "file", "mode", "data", "result", "response", "output", "args",
    "kwargs", "key", "value", "name", "text", "line", "lines", "buf",
})


def _resolve_url_vars(line_text: str, file_path: Path) -> list[tuple[str, str]]:
    """
    When no literal URL/IP appears on the flagged line, try to locate network
    targets by scanning the source file.
    """
    identifiers = [
        m.group(0) for m in re.finditer(r'\b([a-z_][a-z0-9_]{2,})\b', line_text)
        if m.group(0) not in _VAR_SKIP
    ]

    try:
        source = _read_file_cached(file_path)
    except OSError:
        return []

    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _collect(label: str, text: str) -> None:
        for m in _RE_URL.finditer(text):
            key = (label, m.group(0).rstrip(".,;)\"'"))
            if key not in seen:
                seen.add(key)
                results.append(key)
        for m in _RE_IP_PORT.finditer(text):
            val = f"{m.group(1)}:{m.group(2)}" if m.group(2) else m.group(1)
            key = (label, val)
            if key not in seen:
                seen.add(key)
                results.append(key)

    for var in identifiers:
        # Use re.finditer with inline pattern — Python caches recently used patterns
        for m in re.finditer(rf'^\s*{re.escape(var)}\s*=\s*(.+)$', source, re.MULTILINE):
            _collect(var, m.group(1))

    if results:
        return results

    _collect("(file)", source)
    return results


def _describe_bytes(data: bytes) -> str:
    """Return a human-readable type + size description for decoded bytes."""
    n = len(data)
    if not data:
        return "empty payload"
    for magic, label, _mime in _MAGIC_SIGNATURES:
        if data[:len(magic)] == magic:
            return f"{label}  ({n:,} bytes)"
    try:
        text = data.decode("utf-8")
        preview = text[:120].replace("\n", "↵").replace("\r", "")
        return f"Text / script  ({n:,} bytes)  »  {preview}"
    except UnicodeDecodeError:
        pass
    return f"Binary data  ({n:,} bytes)  first 16 bytes: {data[:16].hex(' ')}"


_RE_ENSURE_INSTALLED = re.compile(r"""['"]([\w][\w\-\.\[\]<>=!,~ ]*)['"]""")
_RE_PIP_PKG = re.compile(r"pip\s+install\s+([\w\-\.\[\]<>=!,~ ]+)")


def _extract_packages(line: str) -> list[str]:
    """Extract package names from s.ensure_installed(...) or pip install ... lines."""
    pkgs: list[str] = []
    if "ensure_installed" in line:
        for m in _RE_ENSURE_INSTALLED.finditer(line):
            name = m.group(1).strip()
            if name and not name.startswith("-"):
                pkgs.append(name)
    else:
        m = _RE_PIP_PKG.search(line)
        if m:
            for part in re.split(r"[\s,]+", m.group(1)):
                part = part.strip().strip('"\'[]')
                if part:
                    pkgs.append(part)
    return pkgs


def _try_decode_base64(line_text: str, file_path: Path, line_no: int) -> tuple[str, bytes] | None:
    """
    Extract and decode a base64 payload referenced on *line_no* of *file_path*.
    Handles both inline (single-line) and multi-line triple-quoted strings.
    Returns (human-readable description, raw bytes) or None if decoding fails.
    """
    def _decode(raw: str) -> tuple[str, bytes] | None:
        clean = re.sub(r'\s+', '', raw)
        if len(clean) < 8:
            return None
        try:
            data = base64.b64decode(clean, validate=False)
            return (_describe_bytes(data), data)
        except Exception:
            return None

    # ── Try inline single-line extraction first ──────────────────────────────
    m = re.search(r'b64decode\s*\(\s*[bBrR]*["\']([A-Za-z0-9+/=]+)["\']', line_text)
    if m:
        result = _decode(m.group(1))
        if result:
            return result

    # ── Multi-line: read file and grab the full call ──────────────────────────
    try:
        source = _read_file_cached(file_path)
    except OSError:
        return None

    lines = source.splitlines()
    start = max(0, line_no - 3)
    window = "\n".join(lines[start:min(len(lines), line_no + 300)])

    for quote in ('"""', "'''"):
        pat = re.compile(
            r'b64decode\s*\(\s*[bBrR]*' + re.escape(quote) +
            r'(.*?)' + re.escape(quote) + r'\s*\)',
            re.DOTALL,
        )
        m = pat.search(window)
        if m:
            result = _decode(m.group(1))
            if result:
                return result

    return None


# ── Evasion resistance helpers (C1, C2, C3) ────────────────────────────────

_RE_IMPORT_AS = re.compile(r"^\s*import\s+(\w+(?:\.\w+)*)\s+as\s+(\w+)", re.MULTILINE)
_RE_FROM_IMPORT = re.compile(r"^\s*from\s+(\w+(?:\.\w+)*)\s+import\s+(.+)", re.MULTILINE)


# Common names that should not be treated as import aliases when they appear
# in bare `from X import Y` (without `as`), because they collide with local
# variable names and cause false alias expansions.
_ALIAS_SKIP = frozenset({
    "path", "name", "error", "warning", "info", "debug", "log",
    "sleep", "time", "date", "copy", "move", "open", "close",
    "read", "write", "run", "call", "check", "get", "set",
    "loads", "dumps", "load", "dump", "join", "split",
})


def _build_alias_map(source: str) -> dict[str, str]:
    """Build a mapping of import aliases to their full module names (C3)."""
    aliases: dict[str, str] = {}
    for m in _RE_IMPORT_AS.finditer(source):
        # Explicit `import X as Y` — always safe to track
        aliases[m.group(2)] = m.group(1)
    for m in _RE_FROM_IMPORT.finditer(source):
        module = m.group(1)
        for part in m.group(2).split(","):
            part = part.strip()
            if " as " in part:
                # Explicit alias — always safe
                orig, alias = part.split(" as ", 1)
                aliases[alias.strip()] = f"{module}.{orig.strip()}"
            else:
                # Bare import — skip common names that collide with variables
                name = part.strip()
                if name and name != "*" and name not in _ALIAS_SKIP:
                    aliases[name] = f"{module}.{name}"
    return aliases


def _compile_alias_patterns(alias_map: dict[str, str]) -> list[tuple[re.Pattern, str]]:
    """Pre-compile regex patterns for alias expansion."""
    return [
        (re.compile(rf'\b{re.escape(alias)}\.'), f'{full}.')
        for alias, full in alias_map.items()
    ]


def _expand_aliases(line: str, compiled_aliases: list[tuple[re.Pattern, str]]) -> str:
    """Expand known import aliases in a line so rules can match full module paths (C3)."""
    if not compiled_aliases:
        return line
    expanded = line
    for pat, replacement in compiled_aliases:
        expanded = pat.sub(replacement, expanded)
    return expanded


def _preprocess_lines(raw_lines: list[str]) -> tuple[list[str], list[int], list[bool]]:
    """
    Preprocess source lines for evasion resistance.

    Returns:
        logical_lines: Lines with continuations merged
        line_numbers: Original line number for each logical line
        in_docstring: Whether each logical line is inside a triple-quoted string
    """
    # C1: Join continuation lines
    logical_lines: list[str] = []
    line_numbers: list[int] = []
    buf = ""
    buf_lineno = 0

    for i, raw in enumerate(raw_lines):
        if not buf:
            buf_lineno = i + 1
        if raw.rstrip().endswith("\\"):
            buf += raw.rstrip()[:-1] + " "
            continue
        buf += raw
        logical_lines.append(buf)
        line_numbers.append(buf_lineno)
        buf = ""

    if buf:  # unterminated continuation at EOF
        logical_lines.append(buf)
        line_numbers.append(buf_lineno)

    # C2: Track triple-quoted string regions using character-level state machine.
    # Handles triple-quotes inside single-quoted strings correctly.
    in_docstring: list[bool] = []
    tq_open = ""  # which triple-quote is currently open ("" = none)

    for line in logical_lines:
        if tq_open:
            # We're inside a triple-quoted string — check if it closes on this line
            close_pos = line.find(tq_open)
            if close_pos >= 0:
                tq_open = ""
            in_docstring.append(True if tq_open else False)
            continue

        # Not inside a triple-quoted string — scan for one opening
        # but skip triple-quotes that appear inside single/double-quoted strings
        i = 0
        opened = False
        while i < len(line):
            ch = line[i]
            # Skip escape sequences
            if ch == '\\':
                i += 2
                continue
            # Single or double quote — skip the whole string
            if ch in ('"', "'"):
                triple = line[i:i+3]
                if triple in ('"""', "'''"):
                    # This is a real triple-quote opening
                    # Check if it also closes on the same line
                    end = line.find(triple, i + 3)
                    if end >= 0:
                        # Opens and closes on same line — not a docstring region
                        i = end + 3
                        continue
                    else:
                        # Opens but doesn't close — entering docstring
                        tq_open = triple
                        opened = True
                        break
                else:
                    # Regular single/double quote — skip to closing quote
                    close = line.find(ch, i + 1)
                    while close > 0 and line[close - 1] == '\\':
                        close = line.find(ch, close + 1)
                    i = (close + 1) if close > 0 else len(line)
                    continue
            # Comment — rest of line is not code
            if ch == '#':
                break
            i += 1
        in_docstring.append(opened)

    return logical_lines, line_numbers, in_docstring


def _get_siril_script_dirs() -> list[tuple[Path, str]]:
    """
    Return ``(directory_path, source_label)`` tuples for all existing Siril
    script directories.
    """
    home = Path.home()
    found: list[tuple[Path, str]] = []

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

    seen: set[Path] = set()
    result: list[tuple[Path, str]] = []
    for p, label in found:
        if p not in seen:
            seen.add(p)
            if p.is_dir():
                result.append((p, label))
    return result


def _collect_python_scripts(dirs: list[tuple[Path, str]] | list[Path]) -> list[Path]:
    """Collect all .py files recursively from the given directories."""
    scripts: list[Path] = []
    seen: set[Path] = set()
    # C6: self-exclude
    try:
        self_path = Path(__file__).resolve()
    except Exception:
        self_path = None

    for entry in dirs:
        d = entry[0] if isinstance(entry, tuple) else entry
        for p in sorted(d.rglob("*.py")):
            resolved = p.resolve()
            if resolved in seen:
                continue
            if self_path and resolved == self_path:
                continue  # C6: skip ourselves
            seen.add(resolved)
            scripts.append(p)
    return scripts


def _scan_file(path: Path, active_categories: set[str]) -> list[Finding]:
    """Scan a single file and return all findings."""
    findings: list[Finding] = []
    try:
        source = _read_file_cached(path)
    except OSError:
        return findings

    raw_lines = source.splitlines()

    # C1+C2: preprocess for continuation lines and docstrings
    logical_lines, line_numbers, in_docstring = _preprocess_lines(raw_lines)

    # C3: build import alias map and pre-compile patterns
    alias_map = _build_alias_map(source)
    compiled_aliases = _compile_alias_patterns(alias_map)

    for idx, line in enumerate(logical_lines):
        lineno = line_numbers[idx]

        # C2: skip lines inside triple-quoted strings (docstrings)
        if in_docstring[idx]:
            continue

        # G2: ReDoS protection — skip extremely long lines
        if len(line) > MAX_LINE_LENGTH:
            continue

        # C3: expand aliases for matching
        expanded = _expand_aliases(line, compiled_aliases)

        for cat, sev, desc, pattern, rid in _COMPILED_RULES:
            if cat not in active_categories:
                continue
            if not pattern.search(expanded):
                continue

            # Run suppressor pipeline (E2)
            if any(s(cat, sev, desc, rid, line, raw_lines) for s in _SUPPRESSORS):
                continue

            # Run downgrader pipeline (E1/E2)
            final_sev = sev
            final_desc = desc

            for dg in _SIMPLE_DOWNGRADERS:
                result = dg(cat, sev, desc, rid, line, raw_lines)
                if result is not None:
                    final_sev, final_desc = result
                    break

            # Special downgrader that needs path/lineno
            b64_result = _downgrade_b64_image(cat, sev, desc, rid, line, raw_lines, path, lineno)
            if b64_result is not None:
                final_sev, final_desc = b64_result

            findings.append(Finding(
                file_path=path,
                line_no=lineno,
                line_text=line.strip(),
                category=cat,
                severity=final_sev,
                description=final_desc,
                rule_id=rid,
            ))

    # B5: file-level heuristic — tempfile + code execution in same file
    if "code_exec" in active_categories:
        has_tempfile = bool(re.search(r"^\s*(?:import|from)\s+tempfile\b", source, re.MULTILINE))
        has_exec = bool(re.search(
            r"^\s*(?:import|from)\s+subprocess\b|\bos\.system\s*\(|\bos\.popen\s*\(",
            source, re.MULTILINE
        ))
        if has_tempfile and has_exec:
            findings.append(Finding(
                file_path=path,
                line_no=0,
                line_text="(file-level pattern: tempfile + code execution used together)",
                category="code_exec",
                severity="MEDIUM",
                description="tempfile + code execution pattern – may write and execute a payload",
                rule_id="code_tempfile_subprocess",
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
        _clear_file_cache()  # D1: fresh cache per scan
        scripts = _collect_python_scripts(self._dirs)
        total = len(scripts)
        all_findings: list[Finding] = []
        for idx, script in enumerate(scripts):
            self.progress.emit(idx + 1, total, script.name)
            all_findings.extend(_scan_file(script, self._categories))
        self.finished.emit(all_findings, scripts)


# ------------------------------------------------------------------------------
# PREFERENCES (F5)
# ------------------------------------------------------------------------------

def _load_prefs() -> dict:
    try:
        return json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except OSError:
        pass


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
        QTimer.singleShot(200, self._show_startup_warning)

    # ── UI construction ────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), stretch=1)

    def _show_startup_warning(self) -> None:
        # F5: check "don't show again" preference
        prefs = _load_prefs()
        if prefs.get("skip_startup_warning"):
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("⚠️  Before You Scan — Please Read")
        dlg.setModal(True)
        dlg.setMinimumWidth(600)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet(
            "background:#1e1e1e;color:#e0e0e0;"
            "font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:13pt;"
            "border:none;"
        )
        text.setHtml("""
<p style='color:#ffaa44;font-size:13pt;font-weight:bold;margin-bottom:6px;'>
    ⚠️&nbsp; A word of caution before you scan
</p>

<p>
Siril Python scripts are powerful — and that power cuts both ways.
A script can do <b>virtually anything your user account can do</b> on this machine:
delete files and folders, download and execute additional programs,
exfiltrate data, modify system settings … everything you can imagine
a bad actor might want to do.
</p>

<p>
We are a friendly and welcoming astronomy community — but <em>you never truly
know</em> where a script came from or who really wrote it.
<b>Be careful about where you load scripts from.</b>
</p>

<p>
This tool gives you an impression of what a script is doing under the hood —
potentially dangerous calls, obfuscated code, network access, file deletions,
and more. It is a genuine help for spotting suspicious behaviour.
</p>

<p style='color:#ff8888;'>
<b>However:</b> this is a cat-and-mouse game (as we say in German:
<em>„Hase und Igel"</em> — hare and hedgehog).
A determined bad actor who knows this scanner exists will adapt their script
to avoid triggering the rules. <b>No automated tool can give you a 100 %
guarantee.</b> Use your own judgement, only run scripts from sources you trust,
and keep backups of your data.
</p>

<p style='color:#aaaaaa;font-size:9.5pt;'>
Stay safe — and clear skies. 🌠
</p>

<p style='color:#ffdd88;'>
<b>⚠️ Important — Why you should always do an AI check:</b> This scanner performs
<b>static analysis based on pattern matching</b> — it looks for known dangerous
signatures in the source code. A clever attacker can evade these patterns.
<b>ChatGPT and Claude understand code semantically</b>, like a human expert would,
and can catch threats that pattern-based tools miss entirely. Paste the script
into either AI with the prompt below — it takes 30 seconds and could save you
from serious harm:
</p>

<p style='background:#2a2a2a;padding:10px;border-left:3px solid #4488cc;
font-size:9.5pt;color:#cccccc;font-family:monospace;'>
"You are an expert Python developer and cybersecurity specialist. Analyze the
following Python script designed for the astrophotography program Siril. The
script can access Siril data via its API but runs with full user-level OS
permissions. Review the code for any malicious, harmful, or risky behavior —
including but not limited to: file system access, network calls, data
exfiltration, privilege escalation, obfuscated code, or destructive operations.
Provide a security risk assessment and a clear recommendation on whether the
script is safe to run."
</p>
""")
        text.setMinimumHeight(320)
        layout.addWidget(text)

        # F5: "Don't show again" checkbox
        chk_dont_show = QCheckBox("Don't show this warning again")
        chk_dont_show.setStyleSheet("color:#999999;font-size:9pt;")
        layout.addWidget(chk_dont_show)

        btn_ok = QPushButton("I understand — let's scan")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(dlg.accept)
        btn_ok.setStyleSheet(
            "QPushButton{background:#285299;color:#ffffff;padding:7px 22px;"
            "border-radius:4px;font-size:10pt;}"
            "QPushButton:hover{background:#3363bb;}"
        )
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        dlg.exec()

        # F5: save preference
        if chk_dont_show.isChecked():
            prefs["skip_startup_warning"] = True
            _save_prefs(prefs)

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
        layout.addSpacing(10)

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
        layout.addSpacing(10)

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

        btn_clear = QPushButton("Clear Paths")
        _nofocus(btn_clear)
        btn_clear.setToolTip("Remove all script directories from the list.")
        btn_clear.clicked.connect(self._clear_paths)
        btn_row.addWidget(btn_clear)

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

        # Filter row: severity checkboxes + category combo (F1, F3)
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 2, 0, 2)
        filter_row.setSpacing(12)
        lbl_filter = QLabel("Filter:")
        lbl_filter.setStyleSheet("color:#aaaaaa;font-size:9pt;")
        filter_row.addWidget(lbl_filter)
        self._chk_high = QCheckBox("HIGH")
        self._chk_med  = QCheckBox("MEDIUM")
        self._chk_low  = QCheckBox("LOW")
        for chk, color in (
            (self._chk_high, "#ff6b6b"),
            (self._chk_med,  "#ffaa44"),
            (self._chk_low,  "#88ccff"),
        ):
            chk.setChecked(True)
            chk.setStyleSheet(
                f"QCheckBox{{color:{color};font-size:9pt;}}"
                f"QCheckBox::indicator{{width:13px;height:13px;}}"
            )
            chk.stateChanged.connect(self._apply_filter)
            filter_row.addWidget(chk)

        # F3: category combo filter
        self._cat_combo = QComboBox()
        self._cat_combo.addItem("All Categories", "")
        for key, label in CATEGORY_LABELS.items():
            self._cat_combo.addItem(label, key)
        self._cat_combo.setStyleSheet("font-size:9pt;min-width:160px;")
        self._cat_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._cat_combo)

        filter_row.addStretch()
        layout.addLayout(filter_row)

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

        # Detail panel (F2: increased height)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(DETAIL_MIN_HEIGHT)
        self.detail.setMaximumHeight(DETAIL_HEIGHT_NORMAL)
        self.detail.setStyleSheet(
            "background:#1e1e1e;color:#e0e0e0;font-family:Courier New,Courier,monospace;font-size:13pt;"
        )
        self.detail.setPlaceholderText("Click a finding to see details…")
        layout.addWidget(self.detail)

        self.tree.currentItemChanged.connect(self._on_item_changed)
        # F6: double-click to open file
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

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
            # G1: reject system directories
            try:
                resolved = p.resolve()
                if any(resolved.is_relative_to(sd) for sd in _SYSTEM_DIRS):
                    QMessageBox.warning(
                        self, "System Directory",
                        f"Scanning system directories is not allowed:\n{resolved}"
                    )
                    return
            except Exception:
                pass
            existing_paths = {d for d, _ in self._scan_dirs}
            if p not in existing_paths:
                self._scan_dirs.append((p, "user-added"))
                self._update_dirs_label()

    @staticmethod
    def _split_pasted_text(text: str) -> list[str]:
        """Split clipboard text into individual path strings."""
        result: list[str] = []
        for part in re.split(r"[\n,;]+", text):
            part = part.strip().strip('"').strip("'")
            if not part:
                continue
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
        """Add directories from clipboard text."""
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
            # G1: reject system directories
            try:
                resolved = p.resolve()
                if any(resolved.is_relative_to(sd) for sd in _SYSTEM_DIRS):
                    skipped.append(f"{raw} (system directory)")
                    continue
            except Exception:
                pass
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

    def _clear_paths(self) -> None:
        """Remove all script directories from the scan list."""
        if not self._scan_dirs:
            return
        self._scan_dirs.clear()
        self._update_dirs_label()

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
        # F1: reset filter labels
        self._chk_high.setText("HIGH")
        self._chk_med.setText("MEDIUM")
        self._chk_low.setText("LOW")

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
        self._apply_filter()

        n_files = len(scripts)
        n_findings = len(findings)
        n_high = sum(1 for f in findings if f.severity == "HIGH")
        n_med  = sum(1 for f in findings if f.severity == "MEDIUM")
        n_low  = sum(1 for f in findings if f.severity == "LOW")

        # F1: update filter checkbox labels with counts
        self._chk_high.setText(f"HIGH ({n_high})")
        self._chk_med.setText(f"MEDIUM ({n_med})")
        self._chk_low.setText(f"LOW ({n_low})")

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

    def _filtered_findings(self) -> list[Finding]:
        """Return findings matching the current severity + category filter state."""
        allowed_sev: set[str] = set()
        if self._chk_high.isChecked():
            allowed_sev.add("HIGH")
        if self._chk_med.isChecked():
            allowed_sev.add("MEDIUM")
        if self._chk_low.isChecked():
            allowed_sev.add("LOW")
        cat_key = self._cat_combo.currentData()
        return [
            f for f in self._findings
            if f.severity in allowed_sev
            and (not cat_key or f.category == cat_key)
        ]

    def _apply_filter(self) -> None:
        """Re-populate the tree using the current severity + category filter state."""
        self._populate_tree(self._filtered_findings())

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
                child.setText(0, f"  Line {finding.line_no}" if finding.line_no > 0 else "  (file)")
                child.setText(1, finding.severity)
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
        self.detail.setMaximumHeight(DETAIL_HEIGHT_NORMAL)

        net_html = self._build_net_html(finding)
        decode_html = self._build_decode_html(finding)
        pkg_html = self._build_pkg_html(finding)
        context_html = self._build_context_html(finding)
        explanation_html = self._build_explanation_html(finding)

        sev_color = SEVERITY_COLOR.get(finding.severity, "#cccccc")
        safe_desc = html.escape(finding.description)
        safe_file_parent = html.escape(str(finding.file_path.parent))

        self.detail.setHtml(
            f"<b style='color:{sev_color};'>{finding.severity}</b>"
            f"&nbsp;&nbsp;<span style='color:#88aaff;'>"
            f"{html.escape(CATEGORY_LABELS.get(finding.category, finding.category))}</span>"
            f"&nbsp;&nbsp;<span style='color:#aaaaaa;font-size:8pt;'>"
            f"{html.escape(finding.file_path.name)} · Line {finding.line_no}</span><br>"
            f"<span style='color:#e0e0e0;font-size:9pt;'>{safe_desc}</span><br>"
            f"<span style='color:#888888;font-size:8pt;'>{safe_file_parent}</span>"
            f"{explanation_html}"
            f"{context_html}"
            f"{pkg_html}"
            f"{net_html}"
            f"{decode_html}"
        )

    def _build_net_html(self, finding: Finding) -> str:
        """Build HTML for network target display."""
        if finding.category not in _NET_CATEGORIES:
            return ""
        targets = _extract_network_targets(finding.line_text)
        if targets:
            items = "".join(
                f"<span style='color:#ff9944;font-family:Courier New,Courier,monospace;'>"
                f"{html.escape(t)}</span>  "
                for t in targets
            )
            return f"<br><span style='color:#aaaaaa;'>Target: </span>{items}"
        resolved = _resolve_url_vars(finding.line_text, finding.file_path)
        if resolved:
            items = "".join(
                f"<span style='color:#aaaaaa;'>{html.escape(var)}&nbsp;→&nbsp;</span>"
                f"<span style='color:#ff9944;font-family:Courier New,Courier,monospace;'>"
                f"{html.escape(val)}</span>  "
                for var, val in resolved
            )
            return f"<br><span style='color:#aaaaaa;'>Target (via variable): </span>{items}"
        return "<br><span style='color:#777777;font-size:8pt;'>Target: URL/IP stored in a variable — check the code above.</span>"

    def _build_decode_html(self, finding: Finding) -> str:
        """Build HTML for base64 decode preview."""
        if finding.category != "obfuscation" or "b64decode" not in finding.line_text:
            return ""
        result = _try_decode_base64(finding.line_text, finding.file_path, finding.line_no)
        if not result:
            self.detail.setMaximumHeight(DETAIL_HEIGHT_NORMAL)
            return "<br><span style='color:#777777;font-size:8pt;'>Decoded: could not extract payload from this line.</span>"
        desc, raw_bytes = result
        img_html = ""
        for magic, label, mime in _MAGIC_SIGNATURES:
            if mime and raw_bytes[:len(magic)] == magic:
                b64 = base64.b64encode(raw_bytes).decode()
                img_html = (
                    f"<br><img src='data:{mime};base64,{b64}' "
                    f"width='180' style='margin-top:4px;border:1px solid #444;'/>"
                )
                self.detail.setMaximumHeight(DETAIL_HEIGHT_IMAGE)
                break
        else:
            self.detail.setMaximumHeight(DETAIL_HEIGHT_NORMAL)
        return (
            f"<br><span style='color:#aaaaaa;'>Decoded: </span>"
            f"<span style='color:#ff9944;'>{html.escape(desc)}</span>"
            f"{img_html}"
        )

    def _build_pkg_html(self, finding: Finding) -> str:
        """Build HTML for package-install detail."""
        if finding.rule_id not in _SAFE_LIBS_RULE_IDS:
            return ""
        pkgs = _extract_packages(finding.line_text)
        if not pkgs:
            return ""
        whitelist_names = {lib.lower() for lib in _SAFE_LIBS}
        pkg_items = "".join(
            f"<span style='color:{'#88cc88' if p.split('[')[0].strip().lower() in whitelist_names else '#ffaa44'};'>"
            f"&nbsp;{html.escape(p)}&nbsp;</span> "
            for p in pkgs
        )
        return (
            f"<br><span style='color:#aaaaaa;'>Packages: </span>{pkg_items}"
            f"<br><span style='color:#666666;font-size:9pt;'>"
            f"Green = whitelisted / safe &nbsp;·&nbsp; Orange = not on whitelist</span>"
        )

    @staticmethod
    def _build_context_html(finding: Finding) -> str:
        """Build HTML for surrounding source code context."""
        if finding.line_no <= 0:
            return ""
        try:
            src_lines = _read_file_cached(finding.file_path).splitlines()
        except OSError:
            return ""
        lo = max(0, finding.line_no - 4)
        hi = min(len(src_lines), finding.line_no + 3)
        ctx_parts: list[str] = []
        for i in range(lo, hi):
            lineno_str = f"{i + 1:>5}"
            raw = html.escape(src_lines[i])
            if i + 1 == finding.line_no:
                ctx_parts.append(
                    f"<span style='color:#555555;'>{lineno_str} </span>"
                    f"<span style='color:#ffcc88;font-weight:bold;'>{raw}</span>"
                )
            else:
                ctx_parts.append(
                    f"<span style='color:#555555;'>{lineno_str} </span>"
                    f"<span style='color:#888888;'>{raw}</span>"
                )
        return (
            "<br><span style='font-family:Courier New,Courier,monospace;font-size:11pt;'>"
            + "<br>".join(ctx_parts)
            + "</span>"
        )

    @staticmethod
    def _build_explanation_html(finding: Finding) -> str:
        """Build HTML for rule explanation text."""
        explanation = _RULE_EXPLANATIONS.get(finding.rule_id, "")
        if "embedded image asset" in finding.description:
            explanation = _RULE_EXPLANATIONS.get("obf_b64_image", explanation)
        if not explanation:
            return ""
        return f"<br><span style='color:#cccccc;font-size:10pt;'>{explanation}</span>"

    # F6: Double-click to open file in editor
    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        finding: Finding | None = item.data(0, Qt.ItemDataRole.UserRole)
        if finding is None:
            return
        path = finding.file_path
        if not path.exists():
            return
        if sys.platform == "darwin":
            # macOS: open in default text editor
            try:
                _subprocess_mod.Popen(["open", "-t", str(path)])
            except OSError:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

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
        export_findings = self._filtered_findings()
        lines: list[str] = [
            "Siril Script Security Scanner — Report",
            f"Version: {VERSION}",
            "=" * 72,
            f"Scripts scanned: {len(self._scanned_paths)}",
            f"Total findings:  {len(self._findings)}  (exported: {len(export_findings)})",
            f"HIGH:   {sum(1 for f in export_findings if f.severity == 'HIGH')}",
            f"MEDIUM: {sum(1 for f in export_findings if f.severity == 'MEDIUM')}",
            f"LOW:    {sum(1 for f in export_findings if f.severity == 'LOW')}",
            "",
        ]
        by_file: dict[Path, list[Finding]] = {}
        for f in export_findings:
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
                # F4: include plain-text explanation in export
                explanation = _RULE_EXPLANATIONS.get(finding.rule_id, "")
                if "embedded image asset" in finding.description:
                    explanation = _RULE_EXPLANATIONS.get("obf_b64_image", explanation)
                if explanation:
                    plain = re.sub(r'<[^>]+>', '', explanation)
                    wrapped = textwrap.fill(plain, width=80, initial_indent="           ", subsequent_indent="           ")
                    lines.append(wrapped)
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
            "  • Denial of Service          (huge allocations, fork bombs)\n"
            "  • Social Engineering         (fake update / download dialogs)\n"
            "  • Supply Chain               (installing packages at runtime)\n\n"
            "2. HOW TO USE\n"
            "-------------\n"
            "The scanner probes the sirilpy interface for script directories and\n"
            "falls back to well-known default locations automatically.\n"
            "Each discovered directory shows its source in brackets.\n"
            "Use 'Add Directory…' to add extras, or 'Paste Paths' to paste from clipboard.\n"
            "Select the categories you want to scan, then press 'Scan Now'.\n"
            "Results appear grouped by file. Click any finding for details.\n"
            "Double-click a finding to open the file in your default text editor.\n\n"
            "3. SEVERITY LEVELS\n"
            "------------------\n"
            "  RED    HIGH   — Likely dangerous; review immediately.\n"
            "  ORANGE MEDIUM — Suspicious; may be legitimate but warrants review.\n"
            "  BLUE   LOW    — Informational; unlikely to be harmful on its own.\n\n"
            "4. EVASION RESISTANCE\n"
            "--------------------\n"
            "The scanner includes several anti-evasion measures:\n"
            "  • Multi-line continuation (backslash line joins)\n"
            "  • Triple-quoted string / docstring awareness\n"
            "  • Import alias expansion (e.g. 'import subprocess as sp')\n"
            "  • Comment-line filtering\n"
            "However, some evasion techniques remain beyond static analysis:\n"
            "  • Variable indirection (fn = os.remove; fn(path))\n"
            "  • Dynamic attribute access (getattr(os, 'rem'+'ove'))\n"
            "  • Deeply obfuscated payloads\n"
            "This tool is a first-pass aid, not a guarantee of safety.\n\n"
            "5. EXPORT\n"
            "---------\n"
            "Click 'Export Report…' to save the findings as a plain-text file.\n"
            "The export includes detailed explanations for each finding.\n\n"
            "6. REQUIREMENTS\n"
            "---------------\n"
            "Siril 1.4+ with Python script support, sirilpy (bundled with Siril),\n"
            "and PyQt6 (installed automatically when the script runs).\n\n"
            "For more details and menu setup, see the repository README at\n"
            "https://github.com/sramuschkat/Siril-Scripts\n\n"
            "7. AI-ASSISTED ANALYSIS TIP\n"
            "---------------------------\n"
            "For an additional layer of review, you can also check downloaded scripts\n"
            "by pasting their code into ChatGPT or Claude with the following prompt:\n\n"
            "  \"You are an expert Python developer and cybersecurity specialist.\n"
            "  Analyze the following Python script designed for the astrophotography\n"
            "  program Siril. The script can access Siril data via its API but runs\n"
            "  with full user-level OS permissions. Review the code for any malicious,\n"
            "  harmful, or risky behavior — including but not limited to: file system\n"
            "  access, network calls, data exfiltration, privilege escalation,\n"
            "  obfuscated code, or destructive operations. Provide a security risk\n"
            "  assessment and a clear recommendation on whether the script is safe\n"
            "  to run.\""
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
