"""A headless stand-in for the handful of Qt classes the dialog uses:
enough behaviour (values, signals, visibility) to run the window's own
logic, and strict enough that a misspelt attribute on the window fails."""
class Signal:
    def __init__(self): self._subs = []
    def connect(self, fn): self._subs.append(fn)
    def emit(self, *a):
        import inspect
        for fn in list(self._subs):
            # PyQt drops the arguments a slot does not take.
            try:
                ps = inspect.signature(fn).parameters.values()
                if any(p.kind == p.VAR_POSITIONAL for p in ps):
                    n = len(a)
                else:
                    n = min(len(a), sum(1 for p in ps if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)))
            except (TypeError, ValueError):
                n = len(a)
            fn(*a[:n])
class _Enum:
    def __getattr__(self, name): return _Enum()
    def __or__(self, other): return self
    def __call__(self, *a, **k): return _Enum()
class FW:
    def __init__(self, *a, **k):
        self._visible, self._enabled, self._children, self._tip, self._style = True, True, [], "", ""
    def setVisible(self, on): self._visible = bool(on)
    def isVisible(self): return self._visible
    def setEnabled(self, on): self._enabled = bool(on)
    def isEnabled(self): return self._enabled
    def setToolTip(self, t): self._tip = t
    def setStyleSheet(self, t): self._style = t
    def addWidget(self, w, *a, **k):
        assert isinstance(w, FW), w
        self._children.append(w)
    def addLayout(self, l, *a, **k): self._children.append(l)
    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        if name.startswith(("set", "add", "resize", "show", "raise_", "append", "clear", "insert", "horizontalHeader")):
            return lambda *a, **k: FW()
        raise AttributeError(f"{type(self).__name__}.{name}")
class QWidget(FW): pass
class QMainWindow(FW):
    def __getattr__(self, name):
        if name in ("setCentralWidget", "setWindowTitle", "setStyleSheet", "resize", "close", "show"):
            return lambda *a, **k: None
        raise AttributeError(f"window has no attribute {name!r}")
class QFrame(FW): pass
class QGroupBox(FW):
    def __init__(self, title="", *a): super().__init__(); self.title = title
class QScrollArea(FW): pass
class QTabWidget(FW):
    def addTab(self, w, name): self._children.append(w)
class QTextEdit(FW):
    def __init__(self, *a): super().__init__(); self.lines = []
    def append(self, t): self.lines.append(t)
    def setHtml(self, t): self.lines = [t]
    def clear(self): self.lines = []
class QTableWidget(FW):
    def horizontalHeader(self): return FW()
class QProgressBar(FW):
    def setValue(self, v): self.v = v
class _Lay(FW):
    def addStretch(self, *a): pass
class QVBoxLayout(_Lay):
    def __init__(self, parent=None): super().__init__(); self.parent = parent
class QHBoxLayout(QVBoxLayout): pass
class QGridLayout(QVBoxLayout): pass
class QLabel(FW):
    def __init__(self, text="", *a): super().__init__(); self._text = text
    def setText(self, t): self._text = str(t)
    def text(self): return self._text
class QLineEdit(FW):
    def __init__(self, *a): super().__init__(); self._text = ""; self.textChanged = Signal(); self.textEdited = Signal()
    def setText(self, t):
        t = str(t)
        if t != self._text: self._text = t; self.textChanged.emit(t)
    def text(self): return self._text
    def type(self, t):            # a user typing
        self._text = str(t); self.textChanged.emit(self._text); self.textEdited.emit(self._text)
class QCheckBox(FW):
    def __init__(self, text="", *a): super().__init__(); self.label = text; self._on = False; self.toggled = Signal()
    def setChecked(self, on):
        on = bool(on)
        if on != self._on: self._on = on; self.toggled.emit(on)
    def isChecked(self): return self._on
class QToolButton(FW):
    def __init__(self, *a): super().__init__(); self._on = False; self._text = ""; self.toggled = Signal(); self.clicked = Signal(); self._checkable = False
    def setCheckable(self, on): self._checkable = bool(on)
    def setChecked(self, on):
        on = bool(on)
        if on != self._on: self._on = on; self.toggled.emit(on)
    def isChecked(self): return self._on
    def setText(self, t): self._text = t
    def text(self): return self._text
class QPushButton(FW):
    def __init__(self, text="", *a): super().__init__(); self._text = text; self.clicked = Signal()
class _Spin(FW):
    def __init__(self, *a): super().__init__(); self._v = 0; self._lo, self._hi = 0, 99; self.valueChanged = Signal()
    def setRange(self, lo, hi): self._lo, self._hi = lo, hi
    def setValue(self, v):
        v = min(max(v, self._lo), self._hi)
        if v != self._v: self._v = v; self.valueChanged.emit(v)
    def value(self): return self._v
class QSpinBox(_Spin): pass
class QDoubleSpinBox(_Spin): pass
class QComboBox(FW):
    SizeAdjustPolicy = _Enum()
    def __init__(self, *a): super().__init__(); self._items = []; self._i = -1; self.currentIndexChanged = Signal()
    def addItems(self, items):
        first = not self._items
        self._items += list(items)
        if first and self._items: self._i = 0; self.currentIndexChanged.emit(0)
    def currentIndex(self): return self._i
    def setCurrentIndex(self, i):
        if i != self._i: self._i = i; self.currentIndexChanged.emit(i)
    def currentText(self): return self._items[self._i] if 0 <= self._i < len(self._items) else ""
    def setCurrentText(self, t):
        if t in self._items: self.setCurrentIndex(self._items.index(t))
class QSettings:
    store = {}
    def __init__(self, *a): pass
    def value(self, key, default=None): return QSettings.store.get(key, default)
    def setValue(self, key, v): QSettings.store[key] = v
class QFileDialog:
    answer = ""
    @staticmethod
    def getExistingDirectory(*a, **k): return QFileDialog.answer
class QMessageBox:
    shown = []
    @staticmethod
    def warning(parent, title, text): QMessageBox.shown.append(text)
Qt = _Enum()
QSizePolicy = _Enum()
QHeaderView = _Enum()
NAMES = {k: v for k, v in globals().items() if k.startswith("Q") or k in ("Qt",)}
