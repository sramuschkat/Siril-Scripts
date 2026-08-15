"""Version and documentation consistency for Svenesis ImageMono Train.

Four documents describe the same behaviour: the in-app help, the two
manuals and the README. They drift silently — a rule gets changed in the
code and stays written down somewhere else in its old form. These checks
derive the facts from the code and hold every document against them.

Run:  python3 tests/test_imagemono_docs.py
"""
import ast
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "Svenesis-ImageMono-Train.py")
EN = os.path.join(ROOT, "Instructions",
                  "Svenesis-ImageMono-Train-Instructions.md")
DE = os.path.join(ROOT, "Instructions",
                  "Svenesis-ImageMono-Train-Instructions_de.md")
README = os.path.join(ROOT, "README.md")

src = open(SRC).read()
tree = ast.parse(src)
docs = {"EN": open(EN).read(), "DE": open(DE).read(),
        "README": open(README).read()}

fails = []


def check(ok, msg, detail=""):
    print(("   ok   " if ok else "   FAIL ") + msg
          + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(msg)


ver = re.search(r'^VERSION = "([\d.]+)"$', src, re.M).group(1)
consts = dict(re.findall(r"^([A-Z_]+) = ([\d.]+)$", src, re.M))

print(f"1) one version number, everywhere it is claimed  (VERSION = {ver})")
heads = re.findall(r"^#?\s*Script Version: ([\d.]+)$", src, re.M)
check(heads and all(h == ver for h in heads),
      f"the script's own {len(heads)} header line(s) agree", str(heads))
sirilpy = re.findall(r"^# (?:Siril|Python Module) Version: ([\d.]+)$",
                     src, re.M)
check(len(sirilpy) == 2,
      "the Siril and module requirements are stated separately")
floor = re.search(r'SIRILPY_MIN_VERSION = "([\d.]+)"', src).group(1)
check(re.search(r"^# Python Module Version: " + re.escape(floor) + r"$",
                src, re.M) is not None,
      f"the module requirement matches the enforced floor ({floor})")
top = src[src.index("CHANGELOG:\n") + len("CHANGELOG:\n"):]
check(top.startswith(f"{ver} - "), "the CHANGELOG opens with this version")
for path, pat in ((README, r"ImageMono-Train\.py` \(v([\d.]+)\)"),
                  (EN, r"\*\*Version ([\d.]+)\*\*"),
                  (DE, r"\*\*Version ([\d.]+)\*\*")):
    found = re.findall(pat, open(path).read())
    check(found == [ver], f"{os.path.basename(path)} claims {ver}", str(found))
for path in (EN, DE):
    check(re.search(rf"^## 17\..*{re.escape(ver)}", open(path).read(), re.M)
          is not None, f"{os.path.basename(path)} §17 is about {ver}")

print("\n2) released CHANGELOG entries are frozen")
head = subprocess.run(["git", "-C", ROOT, "show",
                       "HEAD:Svenesis-ImageMono-Train.py"],
                      capture_output=True, text=True).stdout
released = re.search(r'^VERSION = "([\d.]+)"$', head, re.M).group(1)


def entry(text, v):
    i = text.index(f"\n{v} - ")
    nxt = re.search(r"\n\d+\.\d+\.\d+ - ", text[i + 1:])
    return text[i:i + 1 + (nxt.start() if nxt else len(text))]


# Compare unconditionally.  Skipping when released == ver was the hole:
# a bullet added to the CURRENT entry after that version had already been
# committed rewrites shipped history, and that is exactly the case the
# check exists for.
check(entry(head, released) == entry(src, released),
      f"the released {released} entry is byte-identical to what shipped")
if released == ver:
    print(f"   note: {ver} is already committed — new work needs a new "
          "version, not another bullet under this one")

print("\n3) the help is valid HTML and covers every option")
fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "_show_help_dialog")
seg = ast.get_source_segment(src, fn)
tabs = {}
for call in ast.walk(fn):
    if not (isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "setHtml"):
        continue
    who = getattr(call.func.value, "id", "?")
    try:
        tabs[who] = ast.literal_eval(call.args[0])
    except ValueError:                       # f-strings: keep the literals
        tabs[who] = "".join(
            v.value for v in ast.walk(call.args[0])
            if isinstance(v, ast.Constant) and isinstance(v.value, str))
check(len(tabs) >= 5, f"{len(tabs)} help documents found")


class Balance(HTMLParser):
    VOID = {"br", "hr", "img", "meta", "input"}

    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.bad.append(tag)
        else:
            self.stack.pop()


for name, doc in sorted(tabs.items()):
    b = Balance()
    b.feed(doc)
    check(not b.bad and not b.stack, f"{name} is balanced HTML "
          f"({len(doc)} chars)", f"bad={b.bad[:2]} open={b.stack[:2]}")

whole = " ".join(tabs.values())
labels = set()
win = next(n for n in tree.body if isinstance(n, ast.ClassDef)
           and n.name == "ImageMonoTrainWindow")
for n in ast.walk(win):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == "QCheckBox" and n.args:
        try:
            labels.add(ast.literal_eval(n.args[0]).strip())
        except Exception:                    # noqa: BLE001
            pass
missing = []
for lab in sorted(labels):
    core = re.split(r"[—:]", re.sub(r"\(.*?\)", "", lab))[0].strip(" +")
    core = {"Align filters to each other": "Align filters",
            "use SPCC": "SPCC"}.get(core, core)
    if len(core) >= 4 and core.lower() not in whole.lower():
        missing.append(lab)
check(not missing, f"all {len(labels)} checkboxes are explained in the help",
      str(missing))

print("\n4) the tabs can open the links they contain")
check("QTextEdit()" not in seg,
      "the tabs are QTextBrowsers — a QTextEdit draws <a> and does nothing")
check(seg.count("setOpenExternalLinks(True)") >= len(tabs),
      "each hands its links to the desktop browser")

print("\n5) the calibration rules read the same in code and in every document")
dark = float(consts["DARK_EXPOSURE_TOLERANCE"])
dflat = float(consts["DARKFLAT_EXPOSURE_TOLERANCE"])
temp = float(consts["CALIB_TEMP_TOLERANCE_C"])
print(f"   code says: dark {dark:.0%}, dark-flat {dflat:.0%}, "
      f"temp ±{temp:g} °C")
STALE = {
    "EN": ["Exposure time | exact", "reported and skipped",
           "degrades in three steps",
           # "Match flats to the same night" used to mean "drop flats from
           # nights with no lights", which on data where every night has
           # both changed nothing.  It now builds a master per night.
           "Uses only flats from the same date folder as the lights"],
    "DE": ["Belichtungszeit | exakt", "gemeldet und übersprungen",
           "in drei Stufen aus",
           "Nutzt nur Flats aus dem Datumsordner der Lights"],
    "README": ["exposure, gain, binning and image size must match exactly",
               "A non-matching dark is reported and skipped",
               "real bias / dark-flat → Siril's synthetic",
               '"match flats to the same night"** for rigs'],
}
WANT = {
    "EN": [f"within {dark * 100:.0f} %", f"within {dflat * 100:.0f} %",
           f"±{temp:g} °C", "INSTRUME", "calibrated in parts", "four steps"],
    "DE": [f"innerhalb {dark * 100:.0f} %", f"innerhalb {dflat * 100:.0f} %",
           f"±{temp:g} °C", "INSTRUME", "in Teilen kalibriert",
           "in vier Stufen aus"],
    "README": [f"{dark * 100:.0f} % band", f"within {dflat * 100:.0f} %",
               "INSTRUME", "calibrated in parts", "four steps",
               "sirilpy 1.0.0 or newer", "one master flat per night"],
}
WANT["EN"] += ["One master flat per night", "cross product"]
WANT["DE"] += ["Ein Master-Flat pro Nacht", "Kreuzprodukt"]
for lang, doc in docs.items():
    bad = [p for p in STALE[lang] if p in doc]
    check(not bad, f"{lang}: no superseded phrasing survives", str(bad))
    absent = [p for p in WANT[lang] if p not in doc]
    check(not absent, f"{lang}: all {len(WANT[lang])} current rules stated",
          str(absent))

print("\n6) the rejection bands agree with the code everywhere")
ns = {}
i = src.index("SIGMA_MAX_FRAMES")
exec(src[i:src.index("\n\n", i)], ns)
lo, gesdt, lin = (ns["SIGMA_MAX_FRAMES"], ns["GESDT_MIN_FRAMES"],
                  ns["LINEAR_MIN_FRAMES"])
print(f"   bands: ≤4 · 5–{lo} · {lo + 1}–{gesdt - 1} · {gesdt}–{lin} · >{lin}")
code = src[src.index("VERSION = "):]          # not the historical CHANGELOG
check("more than 50 images" not in code,
      "no obsolete crossover comment survives in the code")
for lang, doc in docs.items():
    if lang == "README":
        continue
    check(f"{gesdt} – {lin}" in doc or f"{gesdt} - {lin}" in doc,
          f"{lang} names the GESDT band {gesdt}–{lin}")

print("\n6b) the manuals' HISTORICAL sections are frozen too")
# Same failure as the CHANGELOG hole, one file over: rewording a bullet
# under "What was new in 1.5.0" rewrites what a shipped version claimed
# to do.  It is easy to do by accident, because the current and the
# historical lists describe the same subjects in almost the same words.
def _version_sections(text):
    """``{version: body}`` for every "What's New / Neu in X" heading.

    Keyed by the VERSION, not by the wording, because the heading is
    reworded the moment a release is demoted from "what's new" to
    "what was new" -- and the body is the part that must not move.
    """
    heads = [(m.group(1), m.start(), m.end()) for m in
             re.finditer(r"^##+ .*?(\d+\.\d+\.\d+).*$", text, re.M)]
    out = {}
    for i, (ver, _s, end) in enumerate(heads):
        nxt = re.search(r"^##+ ", text[end:], re.M)
        out[ver] = text[end:end + (nxt.start() if nxt else len(text))]
    return out


for path in (EN, DE):
    name = os.path.basename(path)
    old = _version_sections(subprocess.run(
        ["git", "-C", ROOT, "show", f"HEAD:Instructions/{name}"],
        capture_output=True, text=True).stdout)
    now = _version_sections(open(path).read())
    # Everything both sides know about, except the release being written.
    shared = sorted((set(old) & set(now)) - {ver})
    moved = [v for v in shared if old[v] != now[v]]
    check(shared and not moved,
          f"{name}: all {len(shared)} already-released section(s) unchanged",
          f"rewritten: {moved}")

print("\n6c) every palette the code offers is written down")
# The dropdown, the SPCC wavelengths and the help tab all derive from
# _NB_PALETTES, so adding one is a single line -- which is exactly how a
# palette reaches users while both manuals still list the old set.
pal_ns = {}
i = src.index("_NB_PALETTES = {")
exec(src[i:src.index("\n}", i) + 2], pal_ns)
names = sorted(pal_ns["_NB_PALETTES"])
print(f"   {len(names)} assignment palettes: {', '.join(names)}")
for lang, path in (("EN", EN), ("DE", DE)):
    doc = open(path).read()
    absent = [p for p in names if f"| {p} |" not in doc]
    check(not absent, f"{lang}: all {len(names)} are in the palette table",
          str(absent))

print("\n7) both manuals stay parallel")
en_h, de_h = docs["EN"].count("\n### "), docs["DE"].count("\n### ")
print(f"   {en_h} sub-headings EN, {de_h} DE")
check(en_h == de_h, "the manuals have the same number of sub-headings")
check(docs["EN"].count("| exact") == docs["DE"].count("| exakt"),
      "and the same number of exact-match table rows")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL DOC CHECKS PASSED")
