# Konzept: Blink Comparator — Schneller Frame-Vergleich

**Siril Python Script (sirilpy) — Technisches Konzept für die Implementierung**

---

## 1. Zielsetzung

Ein Siril-Python-Script mit tkinter-GUI, das die aktuell geladene Sequenz als schnelle Blink-Animation abspielt. Damit erkennt der Nutzer auf einen Blick:

- Satelliten-Trails und Flugzeugspuren
- Durchziehende Wolken oder Dunst
- Schlechte Frames (Tracking-Fehler, Windböen)
- Bewegung von Kometen, Asteroiden oder Planeten
- Fokus-Drift über die Session
- Artefakte und Hotpixel-Muster

### Was Siril aktuell bietet (und was fehlt)

Siril hat einen Frame Selector (Open Frame List), mit dem man einzelne Frames einer Sequenz anklicken und anzeigen kann. Es fehlt jedoch:

1. **Automatisches Abspielen** als Animation mit konfigurierbarer Geschwindigkeit
2. **Schneller Wechsel** zwischen Frames ohne einzelnes Anklicken
3. **Tastatursteuerung** (Pfeiltasten, Leertaste für Play/Pause)
4. **Differenzbild-Modus** (Abweichungen vom Median/Referenz hervorheben)
5. **Zoom in einen Bildausschnitt** während der Animation
6. **Frame-Markierung** (gute/schlechte Frames direkt markieren → Deselektierung)

---

## 2. Architektur-Überblick

```
┌────────────────────────────────────────────────────────┐
│                     Siril (Host)                        │
│  ┌──────────────┐   sirilpy API   ┌─────────────────┐  │
│  │ Geladene      │◄──────────────►│  BlinkComparator │  │
│  │ Sequenz       │ get_sequence()  │  Python Script   │  │
│  │ (FITS/SER/    │ get_seq_frame() │                  │  │
│  │  FITSEQ)      │                 └────────┬────────┘  │
│  └──────────────┘                           │           │
└─────────────────────────────────────────────┼───────────┘
                                              │
                  ┌───────────────────────────┼──────────────────┐
                  │                           ▼                  │
                  │              BlinkComparator GUI              │
                  │                                              │
                  │  ┌────────────────────────────────────────┐  │
                  │  │          tkinter Canvas                 │  │
                  │  │     (Frame-Anzeige, Zoom-Region)       │  │
                  │  ├────────────────────────────────────────┤  │
                  │  │  [|◄] [◄] [▶/❚❚] [►] [►|]  ⏩ 3 fps  │  │
                  │  │  ━━━━━━━━━━●━━━━━━━━━━━━━━  Frame 42  │  │
                  │  ├────────────────────────────────────────┤  │
                  │  │  [✓] [✗] Markieren   FWHM: 3.2"       │  │
                  │  └────────────────────────────────────────┘  │
                  │                                              │
                  │  ┌──────────────┐  ┌──────────────────────┐  │
                  │  │ Frame-Cache  │  │ Differenz-Engine     │  │
                  │  │ (numpy/PIL)  │  │ (Median-Subtract)    │  │
                  │  └──────────────┘  └──────────────────────┘  │
                  └──────────────────────────────────────────────┘
```

---

## 3. Abhängigkeiten

```python
import sirilpy as s
s.ensure_installed("pillow")
s.ensure_installed("ttkthemes")
```

| Modul       | Zweck                                    | Pflicht? |
|------------|------------------------------------------|----------|
| `sirilpy`  | Siril-Interface, Sequenz-/Frame-Zugriff   | Ja       |
| `numpy`    | Array-Operationen, Autostretch            | Ja (Dep) |
| `tkinter`  | GUI, Canvas, Keyboard-Bindings            | Ja (stdlib) |
| `ttkthemes`| GUI-Theming                               | Ja       |
| `pillow`   | numpy → tkinter PhotoImage Konvertierung  | Ja       |

**Kein matplotlib nötig** — die Bildanzeige läuft komplett über tkinter Canvas + PIL/Pillow, was für flüssige Animationen deutlich performanter ist.

---

## 4. Sequenz-Zugriff über sirilpy

### 4.1 Sequenz-Metadaten lesen

```python
# Sequenz-Objekt holen
seq = siril.get_sequence()

# Wichtige Eigenschaften
seq.number        # Gesamtanzahl der Frames
seq.selnum        # Anzahl selektierter (included) Frames  
seq.reference     # Index des Referenz-Frames
seq.imgparam      # Liste mit Frame-Parametern (quality, etc.)
```

### 4.2 Einzelne Frames laden

```python
# Frame als FFit-Objekt holen (mit Pixeldaten + Keywords)
frame = siril.get_seq_frame(index)
# frame.data  → numpy array (channels, height, width), float32 oder uint16
# frame.keywords → FKeywords Objekt mit FITS-Metadaten

# Frame-Statistiken holen (ohne Pixeldaten zu laden)
stats = siril.get_seq_frame_stats(index, channel=0)
# stats.median, stats.mean, stats.sigma, ...

# Frame-Qualitätsdaten
# seq.imgparam[index].quality  → Qualitätswert (wenn berechnet)
# seq.imgparam[index].incl     → True/False (selektiert/deselektiert)
```

### 4.3 Frame-Selektion ändern

```python
# Frame deselektieren (0-basiert)
siril.set_seq_frame_incl(index, False)

# Mehrere Frames auf einmal (seit sirilpy 1.0.17)
siril.set_seq_frame_incl([3, 7, 12, 45], False)
```

### 4.4 Autostretch für Anzeige

Die Frames kommen als lineare Daten (float32). Für die Anzeige muss ein Autostretch angewandt werden. Zwei Optionen:

**Option A: Sirils Preview-Modus nutzen (falls verfügbar für Sequenz-Frames)**
```python
# Prüfen ob get_image_pixeldata(preview=True) für Seq-Frames geht
# → Funktioniert nur für das aktuell geladene Bild, NICHT für Seq-Frames
```

**Option B: Eigener Midtone-Transfer-Function (MTF) Autostretch (empfohlen)**
```python
def autostretch(data, shadows_clip=-2.8, target_median=0.25):
    """
    Midtone Transfer Function (MTF) Autostretch.
    Nachbau von Sirils/PixInsights STF-Autostretch.
    
    data: numpy array float32, Werte 0.0 - 1.0
    Rückgabe: numpy array uint8 (0-255), gestreckt
    """
    # Median und MAD (Median Absolute Deviation) berechnen
    median = np.median(data)
    mad = np.median(np.abs(data - median)) * 1.4826  # → σ-Äquivalent
    
    # Schatten-Clipping
    shadow = max(0.0, median + shadows_clip * mad)
    
    # Highlight (normalerweise 1.0)
    highlight = 1.0
    
    # Midtone berechnen
    if median - shadow > 0:
        midtone = MTF(target_median, median - shadow)
    else:
        midtone = 0.5
    
    # MTF anwenden
    stretched = np.clip((data - shadow) / (highlight - shadow), 0, 1)
    stretched = MTF(midtone, stretched)
    
    return (stretched * 255).astype(np.uint8)

def MTF(midtone, x):
    """Midtone Transfer Function."""
    if isinstance(x, np.ndarray):
        result = np.zeros_like(x)
        mask = x > 0
        result[mask] = (midtone - 1) * x[mask] / ((2 * midtone - 1) * x[mask] - midtone)
        return np.clip(result, 0, 1)
    else:
        if x == 0: return 0.0
        if x == 1: return 1.0
        return (midtone - 1) * x / ((2 * midtone - 1) * x - midtone)
```

---

## 5. Frame-Cache-System

Das Laden und Stretchen jedes Frames über sirilpy dauert je nach Bildgröße 50-500ms. Für flüssige Animation ist ein Cache essenziell.

### 5.1 Cache-Strategie

```python
class FrameCache:
    """
    LRU-Cache für gestreckte Frame-Vorschaubilder.
    Speichert Frames als PIL.Image in verkleinerter Auflösung.
    """
    def __init__(self, siril, max_frames=50, display_width=800, display_height=600):
        self.siril = siril
        self.cache = {}          # {frame_index: PIL.Image}
        self.max_frames = max_frames
        self.display_width = display_width
        self.display_height = display_height
        self.access_order = []   # LRU-Tracking
        
        # Stretch-Parameter (einmal für die ganze Sequenz berechnen)
        self.stretch_params = None
    
    def compute_global_stretch(self, sample_indices):
        """
        Berechnet Stretch-Parameter aus einigen Sample-Frames,
        damit alle Frames mit denselben Parametern gestreckt werden.
        Das ist wichtig, damit Helligkeitsunterschiede zwischen Frames
        sichtbar bleiben (z.B. Wolkendurchzüge).
        """
        medians = []
        mads = []
        for idx in sample_indices:
            stats = self.siril.get_seq_frame_stats(idx, 0)
            medians.append(stats.median)
            mads.append(stats.avgDev)  # oder stats.sigma
        
        self.stretch_params = {
            'median': np.median(medians),
            'mad': np.median(mads),
        }
    
    def get_frame(self, index):
        """
        Holt Frame aus Cache oder lädt ihn aus Siril.
        Gibt PIL.Image zurück.
        """
        if index in self.cache:
            self._touch(index)
            return self.cache[index]
        
        # Frame laden
        frame = self.siril.get_seq_frame(index)
        frame_data = frame.data  # (channels, H, W)
        
        # Autostretch (mit globalen Parametern)
        if frame_data.dtype != np.float32:
            frame_data = frame_data.astype(np.float32)
            if frame_data.max() > 1.0:
                frame_data /= 65535.0  # uint16 → float32
        
        if frame_data.ndim == 3 and frame_data.shape[0] == 3:
            # RGB: Jeden Kanal einzeln stretchen, aber mit gleichen Parametern
            r = autostretch(frame_data[0], params=self.stretch_params)
            g = autostretch(frame_data[1], params=self.stretch_params)
            b = autostretch(frame_data[2], params=self.stretch_params)
            rgb = np.stack([r, g, b], axis=-1)  # (H, W, 3)
        else:
            # Mono
            mono = autostretch(frame_data[0], params=self.stretch_params)
            rgb = np.stack([mono, mono, mono], axis=-1)
        
        # PIL Image erzeugen + auf Anzeigegröße skalieren
        # WICHTIG: Siril speichert bottom-up → flippen
        rgb_flipped = np.flipud(rgb)
        img = Image.fromarray(rgb_flipped, 'RGB')
        img = img.resize(
            (self.display_width, self.display_height), 
            Image.LANCZOS
        )
        
        # In Cache speichern
        self._evict_if_needed()
        self.cache[index] = img
        self.access_order.append(index)
        
        return img
    
    def preload_range(self, start, count):
        """Lädt mehrere Frames im Voraus (z.B. in einem Thread)."""
        for i in range(start, min(start + count, self.total_frames)):
            if i not in self.cache:
                self.get_frame(i)
    
    def _touch(self, index):
        if index in self.access_order:
            self.access_order.remove(index)
        self.access_order.append(index)
    
    def _evict_if_needed(self):
        while len(self.cache) > self.max_frames:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
```

### 5.2 Vorlade-Strategie

```
Aktueller Frame: 42
Cache enthält: [38, 39, 40, 41, 42, 43, 44, 45, 46, 47]
                                    ↑ aktuell
Vorgeladen:     [48, 49, 50, 51, 52]  ← nächste 5 im Hintergrund-Thread

Bei Rückwärts-Abspielen:
Vorgeladen:     [37, 36, 35, 34, 33]  ← vorherige 5
```

Ein Hintergrund-Thread (`threading.Thread`) lädt Frames voraus, während die GUI den aktuellen Frame anzeigt.

---

## 6. GUI-Entwurf (tkinter)

```
╔═══════════════════════════════════════════════════════════════════╗
║  Blink Comparator                                          [x]  ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │                                                             │  ║
║  │                                                             │  ║
║  │                    FRAME-ANZEIGE                            │  ║
║  │                   (tkinter Canvas)                          │  ║
║  │                                                             │  ║
║  │                   Scroll-Rad = Zoom                         │  ║
║  │                   Rechtsklick+Drag = Pan                    │  ║
║  │                                                             │  ║
║  │                                                             │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                                                                   ║
║  Frame: 42 / 187 (included)       FWHM: 3.2"   BG: 0.0423       ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║  Frame-Slider (klickbar + Drag)                                   ║
║                                                                   ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │ [|◄]  [◄]  [ ▶ / ❚❚ ]  [►]  [►|]    Geschwindigkeit:   │     ║
║  │ First Prev  Play/Pause  Next Last    [===●=========] 3fps│     ║
║  └──────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │  Modus: (●) Normal  ( ) Differenz  ( ) Nur selektierte  │     ║
║  │                                                           │     ║
║  │  [✓ Behalten]  [✗ Verwerfen]         Zoom: [100% ▼]      │     ║
║  └──────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║  Verworfen: 3 Frames   [Änderungen übernehmen]   [Schließen]     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### 6.1 Keyboard-Shortcuts

| Taste              | Aktion                                     |
|--------------------|--------------------------------------------|
| `Leertaste`        | Play / Pause                                |
| `→` Pfeil rechts   | Nächster Frame                              |
| `←` Pfeil links    | Vorheriger Frame                            |
| `Home`             | Erster Frame                                |
| `End`              | Letzter Frame                               |
| `+` / `Mausrad ↑`  | Schneller (FPS erhöhen)                    |
| `-` / `Mausrad ↓`  | Langsamer (FPS verringern)                 |
| `G`                | Frame als gut markieren (include)           |
| `B`                | Frame als schlecht markieren (exclude)       |
| `D`                | Differenzmodus umschalten                   |
| `Z`                | Zoom umschalten (100% / Fit)                |
| `1`-`9`            | Geschwindigkeit: 1-9 FPS                    |
| `Esc`              | Script beenden                              |

---

## 7. Anzeigemodi

### 7.1 Normal-Modus

Zeigt jeden Frame mit Autostretch an. Standard-Modus.

### 7.2 Differenz-Modus

Berechnet die Differenz jedes Frames zu einem Referenzbild (Median-Stack oder Referenz-Frame). Hebt Abweichungen hervor:

```python
def compute_difference_frame(frame_data, reference_data):
    """
    Berechnet die absolute Differenz zum Referenzbild.
    Satelliten, Wolken, Tracking-Fehler werden hell hervorgehoben.
    """
    diff = np.abs(frame_data.astype(np.float32) - reference_data.astype(np.float32))
    
    # Kontrast verstärken
    diff = diff * 5.0  # Skalierung konfigurierbar
    diff = np.clip(diff, 0, 1)
    
    return diff
```

**Referenzbild-Optionen:**
- **Referenz-Frame der Sequenz** (seq.reference) — schnell, einfach
- **Median aus N Frames** — robuster, aber muss vorberechnet werden
- **Vorheriger Frame** — zeigt Änderungen zwischen aufeinanderfolgenden Frames

### 7.3 Nur-Selektierte-Modus

Überspringt deselektierte Frames. Nützlich, um nach dem Markieren zu prüfen, ob alle schlechten Frames entfernt wurden.

---

## 8. Programmablauf

```
Start des Scripts
        │
        ▼
┌──────────────────────────┐
│ sirilpy verbinden         │
│ Prüfen: Sequenz geladen? │
└────────┬─────────────────┘
         │ Nein → Fehlermeldung
         │ Ja ↓
         ▼
┌──────────────────────────┐
│ Sequenz-Metadaten lesen   │
│  - Anzahl Frames          │
│  - Bildgröße              │
│  - Included/Excluded      │
│  - Referenz-Frame         │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Stretch-Parameter aus      │
│ Sample-Frames berechnen    │
│ (5-10 Frames samplen)     │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ GUI initialisieren         │
│  - Canvas                  │
│  - Controls                │
│  - Keyboard Bindings       │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Ersten Frame laden         │
│ + Vorlade-Thread starten   │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│                Event Loop                     │
│                                               │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Play-   │  │ Frame-   │  │ Keyboard-   │  │
│  │ Timer   │  │ Slider   │  │ Events      │  │
│  │ (after) │  │ (drag)   │  │ (shortcuts) │  │
│  └────┬────┘  └────┬─────┘  └──────┬──────┘  │
│       │            │               │          │
│       └────────────┴───────────────┘          │
│                    │                          │
│                    ▼                          │
│           ┌─────────────────┐                 │
│           │ show_frame(idx) │                 │
│           │  - Cache prüfen │                 │
│           │  - Laden/Stretch│                 │
│           │  - Canvas update│                 │
│           │  - Info update  │                 │
│           └─────────────────┘                 │
│                                               │
│  Nutzer markiert Frames → pending_changes[]   │
│                                               │
│  [Übernehmen] → set_seq_frame_incl() für alle │
│  [Schließen]  → GUI beenden                   │
└───────────────────────────────────────────────┘
```

---

## 9. Frame-Info-Anzeige

Pro Frame werden (wenn verfügbar) angezeigt:

```python
def get_frame_info(siril, seq, frame_index):
    """Sammelt Anzeige-Informationen für einen Frame."""
    info = {
        'index': frame_index,
        'total': seq.number,
        'included': seq.imgparam[frame_index].incl,
    }
    
    # Statistiken holen (sofern berechnet)
    try:
        stats = siril.get_seq_frame_stats(frame_index, channel=0)
        info['median_bg'] = f"{stats.median:.4f}"
        info['noise'] = f"{stats.sigma:.4f}"
    except:
        info['median_bg'] = "n/a"
        info['noise'] = "n/a"
    
    # FWHM (sofern Sterne erkannt wurden)
    try:
        reg = siril.get_seq_frame_registration(frame_index, channel=0)
        info['fwhm'] = f"{reg.fwhm:.2f}\""
        info['roundness'] = f"{reg.roundness:.2f}"
        info['quality'] = f"{reg.quality:.4f}"
    except:
        info['fwhm'] = "n/a"
        info['roundness'] = "n/a"
        info['quality'] = "n/a"
    
    # Keywords (Zeitstempel, Belichtung)
    try:
        frame_fit = siril.get_seq_frame(frame_index, get_data=False)
        kw = frame_fit.keywords
        info['exposure'] = f"{kw.exposure:.1f}s"
        info['date'] = str(kw.date_obs) if kw.date_obs else "n/a"
    except:
        info['exposure'] = "n/a"
        info['date'] = "n/a"
    
    return info
```

Darstellung im GUI als einzeilige Statusleiste:

```
Frame 42/187 (included) │ FWHM: 3.2" │ BG: 0.0423 │ σ: 0.0012 │ 120.0s │ 2026-01-15 22:14:03
```

---

## 10. Zoom-Funktionalität

```python
class ZoomableCanvas:
    """
    tkinter Canvas mit Zoom und Pan.
    """
    def __init__(self, parent, width, height):
        self.canvas = tk.Canvas(parent, width=width, height=height, bg='black')
        self.zoom_level = 1.0  # 1.0 = Fit to window
        self.pan_x = 0
        self.pan_y = 0
        
        # Mausrad → Zoom
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)        # Windows
        self.canvas.bind('<Button-4>', self._on_mousewheel_linux)    # Linux up
        self.canvas.bind('<Button-5>', self._on_mousewheel_linux)    # Linux down
        
        # Rechtsklick + Drag → Pan
        self.canvas.bind('<ButtonPress-3>', self._on_pan_start)
        self.canvas.bind('<B3-Motion>', self._on_pan_move)
    
    def display_image(self, pil_image):
        """Zeigt ein PIL.Image mit aktuellem Zoom/Pan an."""
        if self.zoom_level == 1.0:
            # Fit to canvas
            display = pil_image.copy()
        else:
            # Crop + Zoom
            w, h = pil_image.size
            crop_w = int(w / self.zoom_level)
            crop_h = int(h / self.zoom_level)
            x1 = max(0, self.pan_x - crop_w // 2)
            y1 = max(0, self.pan_y - crop_h // 2)
            x2 = min(w, x1 + crop_w)
            y2 = min(h, y1 + crop_h)
            cropped = pil_image.crop((x1, y1, x2, y2))
            display = cropped.resize(
                (self.canvas.winfo_width(), self.canvas.winfo_height()),
                Image.NEAREST  # NEAREST für 1:1 Pixel bei hohem Zoom
            )
        
        # PIL → tkinter PhotoImage
        self.photo = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
```

---

## 11. Play-Animation mit tkinter `after()`

```python
class AnimationController:
    """Steuert die Abspiel-Animation."""
    
    def __init__(self, gui, cache, total_frames):
        self.gui = gui
        self.cache = cache
        self.total_frames = total_frames
        self.current_frame = 0
        self.playing = False
        self.fps = 3.0           # Frames pro Sekunde
        self.direction = 1       # 1 = vorwärts, -1 = rückwärts
        self.loop = True         # Am Ende von vorne beginnen
        self.only_included = False  # Nur selektierte Frames
        self._after_id = None
    
    def play(self):
        self.playing = True
        self._schedule_next()
    
    def pause(self):
        self.playing = False
        if self._after_id:
            self.gui.root.after_cancel(self._after_id)
            self._after_id = None
    
    def toggle(self):
        if self.playing:
            self.pause()
        else:
            self.play()
    
    def _schedule_next(self):
        if not self.playing:
            return
        
        delay_ms = int(1000 / self.fps)
        self._after_id = self.gui.root.after(delay_ms, self._advance)
    
    def _advance(self):
        if not self.playing:
            return
        
        # Nächsten Frame finden
        next_frame = self.current_frame + self.direction
        
        if self.only_included:
            # Überspringe deselektierte Frames
            while 0 <= next_frame < self.total_frames:
                if self.gui.seq.imgparam[next_frame].incl:
                    break
                next_frame += self.direction
        
        if next_frame >= self.total_frames:
            if self.loop:
                next_frame = 0
            else:
                self.pause()
                return
        elif next_frame < 0:
            if self.loop:
                next_frame = self.total_frames - 1
            else:
                self.pause()
                return
        
        self.current_frame = next_frame
        self.gui.show_frame(next_frame)
        
        # Vorlade-Thread für kommende Frames anstoßen
        self.cache.preload_range(
            next_frame + self.direction, 
            count=5
        )
        
        self._schedule_next()
```

---

## 12. Frame-Markierung und Übernahme

Markierungen werden zunächst **lokal gesammelt** und erst auf Knopfdruck an Siril übermittelt. Das verhindert versehentliche Änderungen.

```python
class FrameMarker:
    """Verwaltet Frame-Markierungen (include/exclude)."""
    
    def __init__(self, seq):
        # Originaler Zustand aus Siril
        self.original = {i: seq.imgparam[i].incl for i in range(seq.number)}
        # Pending Changes
        self.changes = {}  # {frame_index: new_included_state}
    
    def mark_include(self, index):
        if self.original[index] == True and index not in self.changes:
            return  # Keine Änderung nötig
        self.changes[index] = True
    
    def mark_exclude(self, index):
        if self.original[index] == False and index not in self.changes:
            return
        self.changes[index] = False
    
    def get_pending_count(self):
        return len(self.changes)
    
    def get_newly_excluded(self):
        return [i for i, v in self.changes.items() 
                if v == False and self.original[i] == True]
    
    def apply_to_siril(self, siril):
        """Überträgt alle Änderungen an Siril."""
        exclude_list = [i for i, v in self.changes.items() if v == False]
        include_list = [i for i, v in self.changes.items() if v == True]
        
        if exclude_list:
            siril.set_seq_frame_incl(exclude_list, False)
        if include_list:
            siril.set_seq_frame_incl(include_list, True)
        
        siril.log(f"[BlinkComparator] {len(exclude_list)} Frames deselektiert, "
                  f"{len(include_list)} Frames selektiert.")
        
        self.changes.clear()
```

---

## 13. Datei- und Projektstruktur

```
blink_comparator/
├── BlinkComparator.py        # Hauptscript (Siril Entry Point)
├── README.md                  # Installationsanleitung + Nutzungsdoku
└── examples/
    └── screenshot.png         # Screenshot für README
```

Auslieferung als **einzelne .py-Datei** (alle Klassen im selben File).

---

## 14. Metadaten-Header

```python
"""
# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Blink Comparator
# Script Version: 1.0.0
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: processing
# Script Description: Animates the currently loaded sequence for rapid
#   visual inspection. Allows marking frames for inclusion/exclusion.
#   Similar to PixInsight's Blink process.
# Script Author: [dein Name]
"""
```

---

## 15. Log-Ausgabe

```
[BlinkComparator] Sequenz geladen: r_pp_light_ (187 Frames, 4656x3520, RGB)
[BlinkComparator] 182 included, 5 excluded
[BlinkComparator] Stretch-Parameter berechnet aus 10 Sample-Frames
[BlinkComparator] Cache: max 50 Frames, Anzeige: 800x600
[BlinkComparator] GUI gestartet — Tastenkürzel: Leertaste=Play, ←→=Nav, G/B=Mark
[BlinkComparator] ──────────────────────────────────────
[BlinkComparator] Session beendet:
[BlinkComparator]   3 Frames neu deselektiert: #23, #89, #142
[BlinkComparator]   Änderungen an Siril übermittelt.
```

---

## 16. Edge Cases und Fehlerbehandlung

| Situation                              | Handling                                                  |
|----------------------------------------|-----------------------------------------------------------|
| Keine Sequenz geladen                  | Fehlermeldung + Abbruch                                   |
| Sequenz mit nur 1 Frame               | Warnung, trotzdem anzeigen (kein Blink möglich)           |
| Sehr große Frames (>50 MP)            | Anzeige-Auflösung begrenzen, Cache-Größe reduzieren      |
| Alle Frames deselektiert               | Warnung anzeigen, trotzdem navigierbar                    |
| SER-Sequenz (8/16-bit)               | Datentyp-Erkennung, korrekte Normalisierung               |
| FITSEQ (Cube)                          | Funktioniert identisch, sirilpy abstrahiert                |
| Frame-Laden schlägt fehl              | Frame überspringen, Fehlermeldung im Log                  |
| Zu wenig RAM für Cache                | Cache-Größe dynamisch an verfügbaren RAM anpassen         |

---

## 17. Performance-Überlegungen

| Aspekt                | Lösung                                                       |
|-----------------------|--------------------------------------------------------------|
| Frame-Laden (50-500ms)| LRU-Cache + Vorlade-Thread                                   |
| Stretch-Berechnung    | Numpy-Vektoroperationen, globale Stretch-Parameter           |
| Canvas-Update         | PIL.ImageTk.PhotoImage statt matplotlib (10x schneller)      |
| Großer Bildformat      | Runterskalieren auf Canvas-Größe vor dem Cachen             |
| Memory                | Cache-Limit (default 50 Frames × ~1.5 MB = ~75 MB)         |
| Threading             | Vorlade-Thread für nächste Frames, GUI im Main-Thread       |
| FITS-Orientierung     | `np.flipud()` einmal beim Laden (Siril=bottom-up)           |

**Ziel-Performance:** Flüssiges Abspielen mit 3-10 FPS bei vorgeladenem Cache, akzeptable 1-2 FPS beim erstmaligen Durchlauf ohne Cache.

---

## 18. Erweiterungsmöglichkeiten (spätere Versionen)

| Feature                              | Beschreibung                                                   |
|-------------------------------------|----------------------------------------------------------------|
| **GIF/MP4-Export**                  | Animation als GIF oder Video exportieren                       |
| **Statistik-Overlay**               | FWHM/Background als Balken-Overlay pro Frame                  |
| **Stern-Tracking-Linie**            | Zeigt die Drift eines Sterns über alle Frames                  |
| **Split-View**                      | Zwei Frames nebeneinander vergleichen                          |
| **Histogram pro Frame**             | Kleines Histogramm-Fenster, das mitzählt                      |
| **Auto-Reject**                     | Automatische Markierung basierend auf Schwellenwerten          |
| **Crosshair/Fadenkreuz**            | Festes Fadenkreuz zum Erkennen von Positionsverschiebungen     |
| **Annotationen/Notizen**            | Textnotizen an einzelne Frames anhängen                        |
