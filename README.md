# 🔵 Okostemplom Gázleolvasó – Home Assistant Addon

Automatikus gázóra-leolvasó addon Home Assistanthoz. RTSP kamerakép alapján OCR technológiával olvassa le a gázóra állását, és MQTT-n keresztül automatikusan megjelenik a Home Assistant entitások között.

---

## ✨ Funkciók

- **Többkamerás támogatás** – tetszőleges számú leolvasó (kamera) kezelhető egyszerre
- **OCR-alapú leolvasás** – Tesseract OCR + OpenCV képfeldolgozással
- **RTSP stream kezelés** – bármely RTSP-kompatibilis IP kamera használható
- **Automatikus HA integráció** – MQTT Discovery: a leolvasók eszközként jelennek meg HA-ban, külön konfigurálás nélkül
- **Heti / havi fogyasztáskövetés** – az addon számítja és publisholja
- **Beépített WebUI** – leolvasók hozzáadása, szerkesztése, törlése, azonnali tesztelés – mind böngészőből
- **Sticky digits** – ha egy digit egy körben nem olvasható, az előző érvényes értéket tartja meg
- **Média fájlok** – minden leolvasáskor elmenti a nyers és feldolgozott képet

---

## 🖥️ Telepítés

### 1. Addon repository hozzáadása

A Home Assistant felületén:

**Beállítások → Bővítmények → Bővítmény-tároló → ⋮ → Tárolók kezelése**

Add hozzá a repository URL-t:
```
https://github.com/okostemplom/addons
```

### 2. Addon telepítése

Keresd meg az **Okostemplom Gázleolvasó** bővítményt és kattints a **Telepítés** gombra.

### 3. MQTT broker

Az addon MQTT Discovery-t használ. A legjobb élmény érdekében telepítsd a **Mosquitto broker** (hivatalos HA addon) bővítményt is.

Ha a Mosquitto addon fut, az MQTT hitelesítési adatokat **automatikusan átveszi** a Supervisor API-n keresztül – nem kell kézzel megadni semmit.

---

## ⚙️ Konfiguráció

Az addon opciói (Beállítások → Bővítmények → Gázleolvasó → Konfiguráció):

| Opció            | Alapértelmezett | Leírás |
|------------------|-----------------|--------|
| `mqtt_host`      | *(üres)*        | MQTT broker hostname. Ha üres és Mosquitto fut, automatikusan felismeri. |
| `mqtt_port`      | `1883`          | MQTT broker portja |
| `mqtt_username`  | *(üres)*        | MQTT felhasználónév (ha szükséges) |
| `mqtt_password`  | *(üres)*        | MQTT jelszó (ha szükséges) |

> **Megjegyzés:** Ha a hivatalos Mosquitto addon telepítve van, az összes MQTT-mező üresen hagyható – az addon automatikusan megkapja a credentials-t.

---

## 📷 Leolvasók beállítása (WebUI)

Az addon indítása után nyisd meg a **WebUI-t** (Megnyitás gomb vagy HA oldalsáv → Gázleolvasó ikon).

### Új leolvasó hozzáadása

1. Kattints az **„+ Új leolvasó"** gombra
2. Add meg a kamera adatait:
   - **Név** – pl. `Kazánház gáz`
   - **RTSP URL** – pl. `rtsp://user:pass@192.168.1.100:554/stream`
   - **Lekérdezési intervallum** – másodpercben (pl. `60`)
3. A **Beállítások** oldalon rajzold meg a ROI (Region of Interest) keretet a kameraképen – ez jelöli ki a számokat tartalmazó területet
4. Mentés után a leolvasó azonnal elindul

### ROI és képbeállítások

A leolvasó beállítási oldalán (⚙️ ikon):

| Beállítás         | Leírás |
|-------------------|--------|
| **Szegmensek száma** | A leolvasandó jegyek száma (általában 5) |
| **Forgásszög**    | Kép elforgatása fokokban (pl. `-2`) |
| **ROI Y start/end** | A leolvasási terület függőleges határa pixelben |
| **X start/end**   | A leolvasási terület vízszintes határa pixelben |

A beállítások mentése után a háttérszál automatikusan újraindul az új konfigurációval.

---

## 🏠 Home Assistant integráció

### MQTT Discovery – automatikus entitások

Minden leolvasó egy önálló **HA eszközként** jelenik meg, az alábbi szenzorokat hozza létre automatikusan:

| Entitás                     | Típus    | Mértékegység | Device class      | State class       |
|-----------------------------|----------|--------------|-------------------|-------------------|
| `{Név} Mérőállás`           | sensor   | m³           | `gas`             | `total_increasing`|
| `{Név} Heti fogyasztás`     | sensor   | m³           | `gas`             | `measurement`     |
| `{Név} Havi fogyasztás`     | sensor   | m³           | `gas`             | `measurement`     |
| `{Név} Utolsó leolvasás`    | sensor   | –            | `timestamp`       | –                 |
| `{Név} Snapshot URL`        | sensor   | –            | –                 | –                 |
| `{Név} Feldolgozott kép URL`| sensor   | –            | –                 | –                 |

### MQTT topic struktúra

```
homeassistant/sensor/gazleolvaso_{reader_id}_{suffix}/config   ← Discovery config (retained)
gazleolvaso/{reader_id}/state                                   ← Állapot payload (retained)
```

A state topic JSON payload-ja:
```json
{
  "value": "12345",
  "weekly": 3.2,
  "monthly": 14.7,
  "last_run": "2026-05-31T18:00:00",
  "snapshot_url": "/media/reader_abc12345_snapshot.png",
  "processed_url": "/media/reader_abc12345_processed.png"
}
```

### Példa: Lovelace kártya

```yaml
type: entities
title: Gázóra
entities:
  - entity: sensor.kazanhaz_gaz_meroallas
    name: Mérőállás
  - entity: sensor.kazanhaz_gaz_heti_fogyasztas
    name: Heti fogyasztás
  - entity: sensor.kazanhaz_gaz_havi_fogyasztas
    name: Havi fogyasztás
  - entity: sensor.kazanhaz_gaz_utolso_leolvasas
    name: Utolsó leolvasás
```

### Példa: Automatizáció (napi értesítés)

```yaml
automation:
  - alias: "Gázóra napi riport"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Gázóra állása"
          message: >
            Mérőállás: {{ states('sensor.kazanhaz_gaz_meroallas') }} m³
            (Havi: {{ states('sensor.kazanhaz_gaz_havi_fogyasztas') }} m³)
```

---

## 🔌 REST API

Az addon belső Flask API-t futtat (`http://<ha_ip>:8099`). HA Ingress-en keresztül is elérhető.

### Leolvasók

| Metódus  | Endpoint                        | Leírás                          |
|----------|---------------------------------|---------------------------------|
| `GET`    | `/api/readers`                  | Összes leolvasó listája          |
| `POST`   | `/api/readers`                  | Új leolvasó létrehozása          |
| `GET`    | `/api/readers/{id}`             | Egy leolvasó adatai              |
| `PUT`    | `/api/readers/{id}`             | Leolvasó frissítése              |
| `DELETE` | `/api/readers/{id}`             | Leolvasó törlése                 |
| `POST`   | `/api/readers/{id}/trigger`     | Azonnali leolvasás indítása      |

### Snapshots

| Metódus | Endpoint                        | Leírás                                      |
|---------|---------------------------------|---------------------------------------------|
| `GET`   | `/api/readers/{id}/snapshot`    | Élő kép lekérése az RTSP streamből (PNG)    |
| `GET`   | `/api/snapshot?rtsp_url=...`    | Tetszőleges RTSP URL snapshot-ja (PNG)      |

### Egyéb

| Metódus | Endpoint   | Leírás                    |
|---------|------------|---------------------------|
| `GET`   | `/healthz` | Egészségügyi állapot JSON |

---

## 🗂️ Fájlok és könyvtárak

| Útvonal                              | Leírás                                     |
|--------------------------------------|--------------------------------------------|
| `/data/readers.json`                 | Leolvasók konfigurációja (perzisztens)     |
| `/data/options.json`                 | Addon opciók (HA Supervisor írja)          |
| `/media/{reader_id}_snapshot.png`    | Legutóbbi nyers kameraképkivágás           |
| `/media/{reader_id}_processed.png`   | Feldolgozott (OCR előtt utolsó) kép        |
| `/media/{reader_id}_result.txt`      | Szöveges OCR eredmény                      |

---

## 🔍 Hibajelek az olvasott értékekben

| Jel | Jelentés |
|-----|----------|
| `?` | A Tesseract OCR nem tudta felismerni azt a számjegyet |
| `!` | Az RTSP stream nem adott vissza képet |

> Ha `?` vagy `!` jelenik meg, az addon az előző érvényes értéket tartja meg (sticky digits). A mérőállás szenzor értéke addig nem változik, amíg legalább egy jegy érvényes nem lesz.

---

## 🔧 Technikai követelmények

- **Architectúra:** `amd64` vagy `aarch64`
- **Home Assistant:** 2023.x vagy újabb
- **Kamera:** RTSP stream szükséges (pl. Hikvision, Dahua, Reolink, stb.)
- **Opcionális:** Mosquitto MQTT broker addon (automatikus integráció)

### Függőségek (Docker-ben előre telepítve)

- Python 3.x
- OpenCV (`opencv-python`)
- Tesseract OCR (`pytesseract`)
- Flask (webszerver)
- NumPy
- Paho MQTT

---

## 🐛 Hibaelhárítás

1. **Nem jelenik meg a leolvasó HA-ban:**
   - Ellenőrizd, hogy a Mosquitto addon fut-e, és az MQTT integráció aktív-e HA-ban
   - Nézd meg az addon naplóját (Bővítmények → Gázleolvasó → Napló)

2. **`!` az értékben – RTSP hiba:**
   - Ellenőrizd az RTSP URL-t a WebUI-ban a Snapshot gombbal
   - Győződj meg róla, hogy a kamera elérhető a HA hálózatából

3. **`?` az értékben – OCR hiba:**
   - Ellenőrizd a ROI beállításokat: pontosan a számokra kell illeszkednie
   - Növeld a képfelbontást vagy javítsd a megvilágítást
   - Próbálj más forgásszöget beállítani

4. **WebUI nem tölt be:**
   - Ellenőrizd, hogy az addon fut-e
   - Próbáld meg `http://<ha_ip>:8099/healthz` direkt eléréssel

---

## 📄 Licenc

MIT License – lásd [`LICENSE`](LICENSE) fájl.
