# Settings Dashboard - Teljes Terv

## Projekt célja
Interaktív settings oldal megvalósítása, amely lehetővé teszi:
1. RTSP URL dinamikus megadása
2. ROI paraméterek (roi_y_start, roi_y_end, x_start, x_end) csúszkákkal és input mezőkkel való módosítása
3. Angle paraméter (rotáció) csúszkával való állítása
4. Real-time preview: snapshot + félig átlátszó ROI téglalap
5. Beállítások mentése és persistenciája

---

## Architektúra

### Frontend (HTML/CSS/JS - Settings Dashboard)

**Layout:**
- **Bal oldal (50%)**: Canvas element
  - Snapshot kép az RTSP stream-ből
  - Félig átlátszó ROI téglalap (dinamikusan rajzolt)
  - Real-time preview
  
- **Jobb oldal (50%)**: Vezérlőpanel
  - RTSP URL input mező
  - Angle csúszka + number input (-180...180)
  - ROI Y Start csúszka + number input (0...2160)
  - ROI Y End csúszka + number input (0...2160)
  - ROI X Start csúszka + number input (0...4096)
  - ROI X End csúszka + number input (0...4096)
  - "Snapshot frissítés" gomb (az új RTSP URL-ből)
  - "Beállítások mentése" gomb
  - Status message (mentés sikeres/sikertelen)

**Interakciós logika:**
1. Oldal betöltéskor: GET /api/settings → paraméterek betöltése
2. Oldal betöltéskor: GET /api/snapshot → initial snapshot megjelenítése
3. RTSP URL input change → "Snapshot frissítés" gomb enabled
4. "Snapshot frissítés" gomb click → GET /api/snapshot?rtsp_url=xxx
5. Bármelyik ROI/angle paraméter change → Canvas re-render (ROI téglalap újrarajzolása)
6. "Beállítások mentése" click → POST /api/settings + status message

---

### Backend (Flask API - main.py)

**Új endpointok:**

#### 1. GET /settings (vagy /api/settings)
Returns aktuális beállítások JSON-ben

```json
{
  "rtsp_url": "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1",
  "angle": -2,
  "roi_y_start": 560,
  "roi_y_end": 610,
  "x_start": 768,
  "x_end": 1005
}
```

**Forrás:** Environment variable (OPTIONS) vagy egy beállítások fájl

#### 2. GET /snapshot
Snapshot PNG az aktuális vagy megadott RTSP URL-ről

**Query paraméterek:**
- `rtsp_url` (opcionális): Ha meg van adva, ebből az URL-ből tölt snapshot-ot. Ha nincs, az aktuális RTSP_URL-t használja.

**Válasz:** PNG image blob

**Megjegyzés:** A snapshot RGB/BGR formátumban kell legyen (NEM szürkeítve!)

#### 3. POST /settings
Új beállítások mentése

**Request body:**
```json
{
  "rtsp_url": "rtsp://...",
  "angle": -2,
  "roi_y_start": 560,
  "roi_y_end": 610,
  "x_start": 768,
  "x_end": 1005
}
```

**Válasz:**
```json
{
  "success": true,
  "message": "Beállítások mentve"
}
```

**Persistencia:** 
- Environment variable (OPTIONS) frissítése VAGY
- Konfigurációs fájl írása (pl. /app/user_settings.json)

---

### Backend (detection.py) módosítások

**Módosítandó függvények:**

1. **`fetch_image(rtsp_url)`**
   - Már létezik, de nincs color handling
   - Módosítás: Térjen vissza BGR (OpenCV alapértelmezett) vagy RGB formátumban
   - Kezeljön tetszőleges RTSP URL-t

2. **`detect()` / Snapshot generálás**
   - Új függvény az URL-ből snapshot-ot lekérő logika
   - Ne alkalmazza az `apply_mask()` vagy `transform_image()` függvényeket (raw snapshot kell)

---

## Implementációs lépések

### 1. Backend módosítások (main.py)

**Szükséges import-ok:**
```python
from flask import jsonify, request, send_file
import io
import json
import os
from detection import fetch_image
import cv2
```

**Global változók:**
- `CURRENT_RTSP_URL` - dinamikusan beállítható
- Settings persistencia (opcionálisan fájl)

**Új route-ok:**
```python
@app.route('/api/settings', methods=['GET'])
def get_settings():
    # Aktuális beállítások JSON-ben
    
@app.route('/api/snapshot', methods=['GET'])
def get_snapshot():
    # rtsp_url query param vagy default
    # fetch_image(rtsp_url) meghívása
    # PNG encode és visszaadás
    
@app.route('/api/settings', methods=['POST'])
def save_settings():
    # Request body: rtsp_url, angle, roi_*, x_*
    # set_settings() meghívása
    # Persistencia
    # Success response
```

---

### 2. Frontend módosítások (templates/settings.html - ÚJ FILE)

**Struktúra:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Gázóra OCR - Beállítások</title>
    <style>
        /* Layout: flex, 50%-50% */
        /* Canvas stílus */
        /* Input/csúszka stílus */
        /* Responsive design */
    </style>
</head>
<body>
    <div class="container">
        <div class="preview-section">
            <canvas id="roiCanvas"></canvas>
        </div>
        <div class="controls-section">
            <input type="text" id="rtspUrl" placeholder="RTSP URL" />
            <button id="snapshotBtn">Snapshot frissítés</button>
            
            <label>Angle (rotáció):</label>
            <input type="range" id="angleSlider" min="-180" max="180" value="-2" />
            <input type="number" id="angleInput" min="-180" max="180" value="-2" />
            
            <label>ROI Y Start:</label>
            <input type="range" id="roiYStartSlider" min="0" max="2160" value="560" />
            <input type="number" id="roiYStartInput" min="0" max="2160" value="560" />
            
            <!-- ... további paraméterek ... -->
            
            <button id="saveBtn">Beállítások mentése</button>
            <div id="statusMsg"></div>
        </div>
    </div>
    
    <script>
        // Canvas setup
        // Snapshot betöltés
        // Event listeners (input change, slider, button click)
        // Real-time canvas re-render
        // API kommunikáció
    </script>
</body>
</html>
```

**JavaScript logika:**

1. **Inicializáció (DOMContentLoaded):**
   - GET /api/settings → paraméterek betöltése, input mezőkbe feltöltés
   - GET /api/snapshot → initial snapshot megjelenítése

2. **Canvas render függvény:**
   - Snapshot kép megjelenítése
   - ROI téglalap rajzolása:
     - `ctx.fillStyle = 'rgba(255, 0, 0, 0.3)'` (félig átlátszó vörös)
     - `ctx.fillRect(x_start, y_start, x_end-x_start, y_end-y_start)`
     - `ctx.strokeRect()` szegéllyel

3. **Event listeners:**
   - Input/slider onChange: Canvas re-render
   - "Snapshot frissítés" button: GET /api/snapshot?rtsp_url=xxx
   - "Beállítások mentése" button: POST /api/settings

4. **Slider ↔ Input szinkronizáció:**
   - Slider change → Input update
   - Input change → Slider update

---

## Workflow Diagram

```
Felhasználó
    ↓
Settings oldal megnyitása
    ↓
GET /api/settings (paraméterek betöltése)
GET /api/snapshot (initial snapshot)
    ↓
Canvas megjelenítés:
  - Snapshot kép
  - ROI téglalap
    ↓
Felhasználó módosít egy paramétert (csúszka/input)
    ↓
Canvas re-render
    ↓
Elégedett? → "Beállítások mentése" gomb
    ↓
POST /api/settings
    ↓
Backend: set_settings() meghívása
Backend: OPTIONS environment variable frissítése
Backend: Service automatikus újraindítása
    ↓
Frontend: Loading indikátor (2-5 mp)
    ↓
Status message: "Beállítások mentve és aktiválva ✓"
    ↓
Vége
```

---

## Technikai részletek

### Canvas ROI rajzolás

```javascript
function drawROI(canvas, image, roi) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Kép megjelenítése
    ctx.drawImage(image, 0, 0);
    
    // ROI téglalap (félig átlátszó)
    ctx.fillStyle = 'rgba(255, 0, 0, 0.3)';
    ctx.fillRect(roi.x_start, roi.y_start, 
                 roi.x_end - roi.x_start, 
                 roi.y_end - roi.y_start);
    
    // Szegély
    ctx.strokeStyle = 'rgba(255, 0, 0, 0.8)';
    ctx.lineWidth = 2;
    ctx.strokeRect(roi.x_start, roi.y_start, 
                   roi.x_end - roi.x_start, 
                   roi.y_end - roi.y_start);
}
```

### RTSP URL kezelés

Backend-ben:
- Default: `RTSP_URL` a `detection.py`-ből
- POST /api/settings-vel új URL beállítható
- Persistencia: environment variable vagy fájl

Frontend-ben:
- Input mező az aktuális RTSP URL-lel
- "Snapshot frissítés" gomb az új URL-ből való snapshot letöltésre

---

## Settings persistencia - Home Assistant integráció

**Megközelítés:** Home Assistant OPTIONS environment variable módosítása

**Workflow:**
1. POST /api/settings fogadása
2. OPTIONS environment variable frissítése az új beállításokkal
3. Automatikus service újraindítás az új beállítások aktiválásához

**Újraindítás megvalósítása:**

**Option A: Automatikus újraindítás (Javasolt)**
- Backend: `systemctl restart addon_okostemplom_gazleolvaso` (vagy `/run/s6-rc-service-up gazleolvaso`)
- Frontend: "Beállítások mentve és szolgáltatás újraindítva" üzenet
- Jobb UX, szükségtelen felhasználói interakció

**Option B: Felhasználó által iniciált újraindítás (Fallback)**
- Frontend: "Beállítások mentve. Kérjük, indítsa újra a service-t a beállítások érvénybe léptetéséhez" üzenet
- Újraindítás gomb a UI-ban, amely POST /api/restart végpontot hív meg
- Használat: Ha az automatikus újraindítás nem működik

**Technikai részletek (Option A):**
- OPTIONS env var frissítése JSON fájlba (`/media/addon_options.json`)
- Backend feldolgozás: `json.dump()` az új opciókkal
- Újraindítás: Home Assistant supervisor API hívás VAGY `subprocess.run(['supervisorctl', 'restart', 'gazleolvaso'])`
- Hiba kezelés: Ha az újraindítás sikertelen, hibáüzenet küldése
- Status: "Beállítások mentve. Service újraindítása..." → "Sikeresen mentve és újraindítva"

**API végpont módosítás (POST /api/settings):**
```
Request → Paraméter validáció → OPTIONS frissítés → Service újraindítás → Válasz
```

**Frontend feedback:**
- Spinner/loading indikátor az újraindítás közben (2-5 másodperc)
- Success message: "Beállítások mentve és aktiválva ✓"
- Error fallback: "Beállítások mentve, de újraindítás sikertelen. Kérem, indítsa újra manuálisan."

---

## Ellenőrzőlista az implementáció során

- [ ] Backend: GET /api/settings endpoint
- [ ] Backend: GET /api/snapshot endpoint
- [ ] Backend: POST /api/settings endpoint
- [ ] Backend: Settings persistencia (JSON fájl)
- [ ] Backend: detection.py módosítások (fetch_image, stb.)
- [ ] Frontend: settings.html létrehozása
- [ ] Frontend: Canvas setup és render
- [ ] Frontend: Input/slider szinkronizáció
- [ ] Frontend: Real-time preview (ROI téglalap)
- [ ] Frontend: API kommunikáció
- [ ] Frontend: Status message-ek
- [ ] Tesztelés: RTSP URL megváltoztatása
- [ ] Tesztelés: ROI paraméterek módosítása
- [ ] Tesztelés: Settings mentése és betöltése
- [ ] Tesztelés: Real-time preview pontossága

---

## Megjegyzések

- A snapshot canvas-ra való rajzolása vélhetően skálázást igényelhet (ha a kamera felbontása nagy)
- A ROI téglalap koordinátáinak kell lenniük a canvas-re vonatkozólag (lehet hogy skálázni kell)
- Az RTSP URL szenzitív adat, vigyázni kell vele az UI-ban
