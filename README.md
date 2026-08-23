# AstroSER to MP4 Converter (v1.3.0)

**AstroSER to MP4 Converter** è un'applicazione desktop leggera e potente progettata specificamente per gli astrofotografi. Consente di visualizzare, ottimizzare, colorizzare e convertire i filmati astronomici non compressi in formato `.ser` in video `.mp4` ad alta compatibilità (con supporto per colonne sonore audio) o in animazioni `.gif`.

---

## Caratteristiche principali

* **Drag & Drop Compatto**: Trascina il file `.ser` nell'area superiore per caricarlo istantaneamente.
* **Layout a Schede (Tabbed UI)**: Interfaccia organizzata in 4 schede tematiche (*Immagine & Colore*, *Velocità & Taglio*, *Colorizzazione HSL*, *Logo, Titoli & Audio*) per la massima chiarezza.
* **Anteprima con Segnalibri di Crop Visivi**: Slider di anteprima avanzato (`BookmarkSlider`) con visualizzazione in tempo reale, salto automatico al fotogramma e **segnalibri visivi colorati (🟢 Inizio Crop, 🔴 Fine Crop)** tracciati direttamente sulla barra.

### 📷 Immagine & Colore
* **Supporto File SER Già Debayerizzati (RGB/BGR)**: Rilevamento automatico di file a 3 canali o modalità esplicita *"Disattivato (Già a Colori / RGB)"* per preservare fedelmente la resa cromatica originale registrata dalla camera.
* **Debayerizzazione ad Alta Fedeltà**: Supporta gli algoritmi **Edge-Aware** (anti-righe e artefatti), **VNG** e Bilineare Standard, con override del pattern Bayer (`RGGB`, `BGGR`, `GRBG`, `GBRG`, `MONO`, `RGB`, `RGB_PLANAR`).
* **Auto-Stretch & Stiramento Gamma**: Ottimizzazione del contrasto dei dettagli scuri (12/14/16 bit) e stiramento gamma non lineare dei toni medi.
* **Auto White Balance (AWB)**: Bilanciamento automatico del bianco.

### ⏱️ Velocità & Taglio (Trim)
* **Regolazione della Velocità & Slow Motion**: Selezione manuale dei FPS o moltiplicatori rapidi di velocità, inclusi rallentamenti a **0.5x (1/2)**, **0.33x (1/3)**, **0.25x (1/4)**, **0.1x** ed accelerazioni fino a **10x**.
* **Taglio Fotogrammi (Trim Range)**: Definizione esplicita del fotogramma di partenza e di arrivo con pulsanti *"Da Anteprima"*.

### 🎨 Colorizzazione Solare & HSL
* **Motore LUT per Colorizzazione Solare**: Trasforma le riprese monocromatiche in immagini colorate astronomicamente accurate senza alcun alone o inversione al bordo del disco solare.
* **Preset Astronomici Nativi**: **Rosso Solare H-alpha (656nm - Rubino)**, **Arancione Solare**, **Giallo Solare (Continuum)**, **Oro Solare**, **Calcio-K (393nm - Violetto)**, **Blu (Deep Sky)**, **Inferno** e **Plasma**.
* **Regolazione HSL Personalizzata**: Cursori in tempo reale per **Tonalità (Hue 0-360°)**, **Saturazione** e **Luminosità**.

### 🎵 Logo, Titoli & Colonna Sonora Audio (NUOVO v1.3.0)
* **Incorporamento Colonna Sonora Audio nell'MP4**: Possibilità di aggiungere una traccia di sottofondo musicale al video `.mp4` esportato con ripetizione automatica in loop.
* **Libreria Colonne Sonore Inclusa (`colonne_sonore/`)**:
  * **Interstellar (Hans Zimmer Style)** (sketch da 30s)
  * **Beethoven - Sonata al chiaro di luna** (sketch 30s & versione completa)
  * **Beethoven - 5ª Sinfonia** (sketch 30s & versione completa)
  * **File Audio Personalizzato**: Supporta caricamento di brani `.wav`, `.mp3`, `.ogg`, `.aac`, `.flac`.
* **Filigrana Logo PNG**: Logo con trasparenza nei 4 angoli o al centro, dimensione (%) ed opacità (%) in anteprima live.
* **Schede Titolo Iniziale e Finale (Intro / Outro)**: Titoli di testa e di coda con supporto nativo per formati **FITS / `.fit` / `.fits`** gestiti via `astropy`.

---

## Come usare l'applicazione

1. Avvia `AstroSer2Mp4.exe` o esegui `python app.py`.
2. Trascina un file `.ser` sull'area superiore.
3. Utilizza le schede a sinistra per regolare colore, velocità, taglio, colorizzazione solare, ed eventuale colonna sonora audio.
4. Fai clic su **Converti / Esporta**.

---

## Requisiti di sistema e dipendenze

* Windows 10 o 11 (64-bit).
* Python 3.9+ (se eseguito da sorgente) con: `PyQt6`, `opencv-python`, `numpy`, `pillow`, `astropy`, `imageio-ffmpeg`.

---
*Sviluppato per gli appassionati di astrofotografia solare, planetaria e ISS.*
